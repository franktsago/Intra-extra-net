from django.test import TestCase
from django.urls import reverse

from accounts.models import INTRANET_ROLES, Role, User


class StagiaireInterfaceTest(TestCase):
    def test_stagiaire_same_perimeter_as_employee(self):
        emp = User.objects.create_user("e_test", password="x", role=Role.EMPLOYE)
        stg = User.objects.create_user("s_test", password="x", role=Role.STAGIAIRE)
        for u in (emp, stg):
            self.assertTrue(u.is_internal)
            self.assertFalse(u.is_external)
            self.assertFalse(u.is_manager)
            self.assertFalse(u.is_rh)
            self.assertFalse(u.is_ceo)
            self.assertFalse(u.is_admin_lpm)
            self.assertFalse(u.can_validate_leave)
        self.assertIn(Role.STAGIAIRE, INTRANET_ROLES)

    def test_stagiaire_gets_employee_profile(self):
        from employees.models import Employee
        stg = User.objects.create_user("s_test2", password="x", role=Role.STAGIAIRE)
        emp = Employee.objects.get(user=stg)
        self.assertEqual(emp.contract_type, Employee.Contract.STAGE)


class AdminRoleChoiceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.admin = User.objects.create_user("adm", password="x", role=Role.ADMIN, is_superuser=True)

    def test_admin_role_hidden_for_non_admin_creation(self):
        from accounts.forms import UserCreateForm
        codes = [v for v, _ in UserCreateForm(viewer=self.rh).fields["role"].choices]
        self.assertNotIn(Role.ADMIN, codes)

    def test_rh_cannot_add_ceo_or_admin(self):
        from accounts.forms import UserCreateForm
        codes = [v for v, _ in UserCreateForm(viewer=self.rh).fields["role"].choices]
        self.assertNotIn(Role.CEO, codes)
        self.assertNotIn(Role.ADMIN, codes)
        self.assertIn(Role.EMPLOYE, codes)

    def test_ceo_can_add_ceo_but_not_admin(self):
        from accounts.forms import UserCreateForm
        codes = [v for v, _ in UserCreateForm(viewer=self.ceo).fields["role"].choices]
        self.assertIn(Role.CEO, codes)
        self.assertNotIn(Role.ADMIN, codes)

    def test_rh_ceo_can_access_user_management(self):
        from django.urls import reverse
        for u in (self.rh, self.ceo):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("accounts:user_list")).status_code, 200)
            self.assertEqual(self.client.get(reverse("accounts:user_create")).status_code, 200)

    def test_rh_cannot_edit_admin_account(self):
        from django.urls import reverse
        self.client.force_login(self.rh)
        r = self.client.get(reverse("accounts:user_edit", args=[self.admin.pk]))
        self.assertEqual(r.status_code, 302)  # redirigé, pas de 403

    def test_rh_cannot_edit_ceo_or_client(self):
        from django.urls import reverse
        cli = User.objects.create_user("cli_e", password="x", role=Role.CLIENT)
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("accounts:user_edit", args=[self.ceo.pk])).status_code, 302)
        self.assertEqual(self.client.get(reverse("accounts:user_edit", args=[cli.pk])).status_code, 302)

    def test_ceo_can_edit_client(self):
        from django.urls import reverse
        cli = User.objects.create_user("cli_f", password="x", role=Role.CLIENT)
        self.client.force_login(self.ceo)
        self.assertEqual(self.client.get(reverse("accounts:user_edit", args=[cli.pk])).status_code, 200)

    def test_rh_can_delete_employee(self):
        from django.urls import reverse
        emp = User.objects.create_user("victim", password="x", role=Role.EMPLOYE)
        self.client.force_login(self.rh)
        r = self.client.post(reverse("accounts:user_delete", args=[emp.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(User.objects.filter(pk=emp.pk).exists())

    def test_rh_cannot_delete_ceo(self):
        from django.urls import reverse
        self.client.force_login(self.rh)
        self.client.post(reverse("accounts:user_delete", args=[self.ceo.pk]))
        self.assertTrue(User.objects.filter(pk=self.ceo.pk).exists())  # bloqué

    def test_rh_cannot_delete_client_but_ceo_can(self):
        from django.urls import reverse
        cli = User.objects.create_user("cli", password="x", role=Role.CLIENT)
        self.client.force_login(self.rh)
        self.client.post(reverse("accounts:user_delete", args=[cli.pk]))
        self.assertTrue(User.objects.filter(pk=cli.pk).exists())   # RH bloquée
        self.client.force_login(self.ceo)
        self.client.post(reverse("accounts:user_delete", args=[cli.pk]))
        self.assertFalse(User.objects.filter(pk=cli.pk).exists())  # CEO autorisé

    def test_ceo_can_delete_employee_not_admin(self):
        from django.urls import reverse
        emp = User.objects.create_user("victim2", password="x", role=Role.EMPLOYE)
        self.client.force_login(self.ceo)
        self.client.post(reverse("accounts:user_delete", args=[emp.pk]))
        self.assertFalse(User.objects.filter(pk=emp.pk).exists())
        self.client.post(reverse("accounts:user_delete", args=[self.admin.pk]))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())  # super-admin protégé

    def test_admin_role_visible_for_admin(self):
        from accounts.forms import UserCreateForm
        codes = [v for v, _ in UserCreateForm(viewer=self.admin).fields["role"].choices]
        self.assertIn(Role.ADMIN, codes)

    def test_editing_admin_keeps_choice(self):
        from accounts.forms import UserEditForm
        codes = [v for v, _ in UserEditForm(instance=self.admin, viewer=self.rh).fields["role"].choices]
        self.assertIn(Role.ADMIN, codes)  # éviter de perdre la valeur affichée

    def test_broadcast_roles_exclude_admin_for_rh(self):
        from notifications.forms import BroadcastForm
        codes = [v for v, _ in BroadcastForm(viewer=self.rh).fields["roles"].choices]
        self.assertNotIn(Role.ADMIN, codes)


class HideAdminInFormDropdownsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("adm", password="x", role=Role.ADMIN, is_superuser=True)
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)

    def test_admin_excluded_from_person_dropdowns_for_others(self):
        from business.forms import ClientForm, OpportunityForm
        from marketing.forms import CampaignForm
        from tasks.forms import TaskForm
        from extranet.forms import ProjectForm
        checks = [
            (ClientForm(viewer=self.rh), "owner"),
            (OpportunityForm(viewer=self.rh), "owner"),
            (CampaignForm(viewer=self.rh), "manager"),
            (TaskForm(viewer=self.rh), "assigned_to"),
            (ProjectForm(viewer=self.rh), "internal_lead"),
        ]
        for form, field in checks:
            ids = set(form.fields[field].queryset.values_list("id", flat=True))
            self.assertNotIn(self.admin.id, ids, f"admin visible dans {field}")

    def test_admin_present_in_own_forms(self):
        from tasks.forms import TaskForm
        ids = set(TaskForm(viewer=self.admin).fields["assigned_to"].queryset.values_list("id", flat=True))
        self.assertIn(self.admin.id, ids)


class HideSuperAdminTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from employees.models import Employee
        cls.admin = User.objects.create_user("super", password="x", role=Role.ADMIN,
                                              is_superuser=True, first_name="Super", last_name="Admin")
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE,
                                            first_name="Eric", last_name="Mballa")
        # Fiche employé pour le super admin (afin de tester l'annuaire).
        Employee.objects.get_or_create(user=cls.admin, defaults={"matricule": "ADM001"})

    def test_admin_hidden_from_directory_for_others(self):
        self.client.force_login(self.emp)
        r = self.client.get(reverse("employees:list"))
        self.assertNotContains(r, "Super Admin")

    def test_admin_sees_himself_in_directory(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("employees:list"))
        self.assertContains(r, "Super Admin")

    def test_admin_hidden_from_message_recipients(self):
        from messaging.models import allowed_recipients
        ids_emp = set(allowed_recipients(self.emp).values_list("id", flat=True))
        self.assertNotIn(self.admin.id, ids_emp)
        # Le super admin, lui, voit tout le monde.
        ids_admin = set(allowed_recipients(self.admin).values_list("id", flat=True))
        self.assertIn(self.emp.id, ids_admin)

    def test_admin_hidden_from_project_lead_choices(self):
        from extranet.forms import ProjectForm
        lead_ids = set(ProjectForm(viewer=self.emp).fields["internal_lead"].queryset
                       .values_list("id", flat=True))
        self.assertNotIn(self.admin.id, lead_ids)
        lead_ids_admin = set(ProjectForm(viewer=self.admin).fields["internal_lead"].queryset
                             .values_list("id", flat=True))
        self.assertIn(self.admin.id, lead_ids_admin)


class UserCreateFonctionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh2", password="x", role=Role.RH)

    def test_create_user_with_new_position(self):
        from django.urls import reverse
        from employees.models import Employee, Position
        self.client.force_login(self.rh)
        r = self.client.post(reverse("accounts:user_create"), {
            "username": "n.ouveau", "first_name": "Nina", "last_name": "OUVEAU",
            "email": "n@lpm.cm", "role": Role.EMPLOYE, "phone": "", "organization": "",
            "new_positions": ["Community Manager"],
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
            "emergency_contact": "Contact U", "emergency_contact_phone": "+237 690000000",
        })
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="n.ouveau")
        # Le poste a été créé et rattaché à la fiche employé.
        self.assertTrue(Position.objects.filter(title="Community Manager").exists())
        emp = Employee.objects.get(user=u)
        self.assertEqual(emp.position.title, "Community Manager")

    def test_existing_position_reused(self):
        from django.urls import reverse
        from employees.models import Employee, Position
        Position.objects.create(title="Comptable")
        self.client.force_login(self.rh)
        self.client.post(reverse("accounts:user_create"), {
            "username": "c.ompta", "first_name": "Carl", "last_name": "OMPTA",
            "email": "c@lpm.cm", "role": Role.EMPLOYE, "phone": "", "organization": "",
            "new_positions": ["Comptable"],
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
            "emergency_contact": "Contact U", "emergency_contact_phone": "+237 690000000",
        })
        self.assertEqual(Position.objects.filter(title="Comptable").count(), 1)  # réutilisé


class UserCreateProfileFieldsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh3", password="x", role=Role.RH)

    def test_profile_fields_saved_on_creation(self):
        from django.urls import reverse
        from employees.models import Department, Employee
        dep = Department.objects.create(name="Studio Créa")
        dep2 = Department.objects.create(name="Communication")
        self.client.force_login(self.rh)
        r = self.client.post(reverse("accounts:user_create"), {
            "username": "p.rofil", "first_name": "Paul", "last_name": "ROFIL",
            "email": "p@lpm.cm", "role": Role.EMPLOYE, "phone": "", "organization": "",
            "new_positions": ["Designer"],
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
            "gender": "M", "departments": [dep.pk, dep2.pk], "contract_type": "CDD",
            "status": "ACTIVE", "city": "Douala", "hire_date": "2026-01-15",
            "cnps_number": "", "address": "", "birth_date": "",
            "emergency_contact": "Marie ROFIL", "emergency_contact_phone": "+237 699 00 11 22",
        })
        self.assertEqual(r.status_code, 302)
        emp = Employee.objects.get(user__username="p.rofil")
        # Rattaché à PLUSIEURS départements.
        self.assertEqual(emp.departments.count(), 2)
        self.assertIn(dep, emp.departments.all())
        self.assertIn(dep2, emp.departments.all())
        self.assertEqual(emp.contract_type, "CDD")
        self.assertEqual(emp.position.title, "Designer")
        self.assertEqual(emp.city, "Douala")

    def test_employee_can_have_multiple_positions(self):
        from employees.models import Employee, Position
        u = User.objects.create_user("multi", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=u)
        p1 = Position.objects.create(title="Designer")
        p2 = Position.objects.create(title="Chef de projet")
        emp.positions.set([p1, p2])
        self.assertEqual(emp.positions.count(), 2)
        self.assertIn("Designer", emp.position_titles)
        self.assertIn("Chef de projet", emp.position_titles)

    def test_birth_day_month_only(self):
        from django.urls import reverse
        from employees.models import Employee
        self.client.force_login(self.rh)
        self.client.post(reverse("accounts:user_create"), {
            "username": "b.day", "first_name": "Bea", "last_name": "DAY",
            "email": "b@lpm.cm", "role": Role.EMPLOYE, "phone": "", "organization": "",
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
            "birth_day": "15", "birth_month": "8", "city": "Douala",
            "emergency_contact": "Contact U", "emergency_contact_phone": "+237 690000000",
        })
        emp = Employee.objects.get(user__username="b.day")
        # Jour et mois conservés ; année non significative (sentinelle).
        self.assertEqual((emp.birth_date.day, emp.birth_date.month), (15, 8))


class SignatureStampTest(TestCase):
    """RH/CEO/admin peuvent enregistrer leur signature et leur cachet ; pas les autres."""

    def _png(self):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        b = BytesIO()
        Image.new("RGBA", (3, 3), (0, 0, 0, 0)).save(b, "PNG")
        b.seek(0)
        return SimpleUploadedFile("x.png", b.read(), content_type="image/png")

    def test_can_sign_property(self):
        self.assertTrue(User.objects.create_user("rhs", password="x", role=Role.RH).can_sign)
        self.assertTrue(User.objects.create_user("ceos", password="x", role=Role.CEO).can_sign)
        self.assertFalse(User.objects.create_user("emps", password="x", role=Role.EMPLOYE).can_sign)

    def test_rh_uploads_signature_and_stamp(self):
        import tempfile
        from django.test import override_settings
        rh = User.objects.create_user("rhup", password="x", role=Role.RH)
        self.client.force_login(rh)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            r = self.client.post(reverse("accounts:profile"), {
                "save_signature": "1", "signature": self._png(), "stamp": self._png()})
            self.assertEqual(r.status_code, 302)
            rh.refresh_from_db()
            self.assertTrue(rh.signature)
            self.assertTrue(rh.stamp)

    def test_employee_has_no_signature_section(self):
        emp = User.objects.create_user("empns", password="x", role=Role.EMPLOYE)
        self.client.force_login(emp)
        r = self.client.get(reverse("accounts:profile"))
        self.assertNotContains(r, "Signature &amp; cachet")


class EmergencyContactTest(TestCase):
    """Personne à contacter : obligatoire (nom + tel valide) pour un interne,
    2e contact optionnel, non requis pour un externe."""

    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("ecadmin", password="x", role=Role.ADMIN)

    def _post_emp(self, **extra):
        data = {
            "username": "ecemp", "first_name": "Eric", "last_name": "CONTACT",
            "email": "ec@lpm.cm", "role": Role.EMPLOYE, "phone": "", "organization": "",
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
            "gender": "M", "contract_type": "CDI", "status": "ACTIVE",
            "city": "Douala", "hire_date": "2026-01-15",
        }
        data.update(extra)
        self.client.force_login(self.admin)
        return self.client.post(reverse("accounts:user_create"), data)

    def test_internal_requires_contact(self):
        r = self._post_emp()  # sans contact
        self.assertEqual(r.status_code, 200)  # formulaire réaffiché
        self.assertFalse(User.objects.filter(username="ecemp").exists())

    def test_invalid_phone_rejected(self):
        r = self._post_emp(emergency_contact="Awa", emergency_contact_phone="abc")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="ecemp").exists())

    def test_valid_contact_creates(self):
        from employees.models import Employee
        r = self._post_emp(emergency_contact="Awa NJIE",
                           emergency_contact_phone="+237 699 00 11 22")
        self.assertEqual(r.status_code, 302)
        emp = Employee.objects.get(user__username="ecemp")
        self.assertEqual(emp.emergency_contact, "Awa NJIE")
        self.assertTrue(emp.emergency_contact_phone)

    def test_external_does_not_require_contact(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("accounts:user_create"), {
            "username": "ecclient", "first_name": "Cli", "last_name": "ENT",
            "email": "cli@x.cm", "role": Role.CLIENT, "phone": "", "organization": "ACME",
            "password1": "Lpm@2026xy", "password2": "Lpm@2026xy",
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(User.objects.filter(username="ecclient").exists())
