from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from employees.models import Department


class DepartmentCrudTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("super", password="x", role=Role.ADMIN, is_superuser=True, is_staff=True)
        cls.emp = User.objects.create_user("emp2", password="x", role=Role.EMPLOYE)

    def test_admin_create_edit_delete(self):
        self.client.force_login(self.admin)
        # Create
        r = self.client.post(reverse("employees:departments"), {"name": "Finance", "code": "FIN"})
        self.assertEqual(r.status_code, 302)
        dep = Department.objects.get(name="Finance")
        # Edit
        r = self.client.post(reverse("employees:department_edit", args=[dep.pk]),
                             {"name": "Finance & Compta", "code": "FIN"})
        self.assertEqual(r.status_code, 302)
        dep.refresh_from_db()
        self.assertEqual(dep.name, "Finance & Compta")
        # Delete
        r = self.client.post(reverse("employees:department_delete", args=[dep.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Department.objects.filter(pk=dep.pk).exists())

    def test_multiple_managers(self):
        from employees.models import department_ids_for
        r1 = User.objects.create_user("dm1", password="x", role=Role.MANAGER)
        r2 = User.objects.create_user("dm2", password="x", role=Role.MANAGER)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("employees:departments"),
                             {"name": "Studio", "code": "STU", "managers": [r1.pk, r2.pk]})
        self.assertEqual(r.status_code, 302)
        dep = Department.objects.get(name="Studio")
        # Les deux sont responsables…
        self.assertEqual(set(dep.managers.values_list("pk", flat=True)), {r1.pk, r2.pk})
        self.assertEqual(dep.manager_id, r1.pk)   # principal = 1er
        # …et chacun « dirige » le département (cloisonnement).
        self.assertIn(dep.id, department_ids_for(r1))
        self.assertIn(dep.id, department_ids_for(r2))

    def test_employee_forbidden(self):
        dep = Department.objects.create(name="RH")
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("employees:departments")).status_code, 403)
        self.assertEqual(self.client.post(reverse("employees:department_edit", args=[dep.pk]),
                                          {"name": "X"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("employees:department_delete", args=[dep.pk])).status_code, 403)


class MatriculeAutoTest(TestCase):
    """Matricule attribué automatiquement, croissant, non modifiable."""

    def test_auto_assigned_on_creation(self):
        from employees.models import Employee
        u = User.objects.create_user("matuser", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=u)  # créé par le signal
        self.assertTrue(emp.matricule)
        self.assertTrue(emp.matricule.startswith("LPM"))

    def test_sequence_is_ascending(self):
        from employees.models import Employee, generate_matricule
        u1 = User.objects.create_user("seq1", password="x", role=Role.EMPLOYE)
        u2 = User.objects.create_user("seq2", password="x", role=Role.EMPLOYE)
        m1 = Employee.objects.get(user=u1).matricule
        m2 = Employee.objects.get(user=u2).matricule
        n1, n2 = int(m1[3:]), int(m2[3:])
        self.assertEqual(n2, n1 + 1)            # strictement croissant, pas de trou
        # Le prochain matricule suit la séquence.
        self.assertEqual(int(generate_matricule()[3:]), n2 + 1)

    def test_field_is_not_editable(self):
        from employees.models import Employee
        self.assertFalse(Employee._meta.get_field("matricule").editable)

    def test_matricule_absent_from_form(self):
        from employees.forms import EmployeeForm
        self.assertNotIn("matricule", EmployeeForm().fields)


class EmployeeEditAppliesTest(TestCase):
    """L'édition d'une fiche dans l'annuaire répercute l'identité sur le compte (item 1)."""

    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_an", password="x", role=Role.RH)
        cls.target = User.objects.create_user(
            "j.dupont", password="x", role=Role.EMPLOYE,
            first_name="Jean", last_name="Dupont", email="old@lpm.cm", phone="+237 600000000")
        from employees.models import Employee
        cls.emp = Employee.objects.get(user=cls.target)

    def test_edit_updates_linked_user(self):
        self.client.force_login(self.rh)
        r = self.client.post(reverse("employees:edit", args=[self.emp.pk]), {
            "first_name": "Jean-Pierre", "last_name": "DUPONT",
            "email": "new@lpm.cm", "phone": "+237 655112233",
            "gender": "M", "hire_date": "2024-01-01",
            "contract_type": "CDI", "status": "ACTIVE", "city": "Douala",
            "emergency_contact": "Marie", "emergency_contact_phone": "+237 699112233",
        })
        self.assertEqual(r.status_code, 302)
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, "Jean-Pierre")
        self.assertEqual(self.target.last_name, "DUPONT")
        self.assertEqual(self.target.email, "new@lpm.cm")
        self.assertEqual(self.target.phone, "+237 655112233")

    def test_form_exposes_identity_initial(self):
        from employees.forms import EmployeeForm
        form = EmployeeForm(instance=self.emp, viewer=self.rh)
        self.assertEqual(form.fields["first_name"].initial, "Jean")
        self.assertEqual(form.fields["email"].initial, "old@lpm.cm")


class ActiveSyncTest(TestCase):
    """Désactiver un compte le sort des effectifs et le masque partout (item 2)."""

    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_act", password="x", role=Role.RH)
        cls.target = User.objects.create_user(
            "p.parti", password="x", role=Role.EMPLOYE,
            first_name="Paul", last_name="Parti", email="p@lpm.cm")
        from employees.models import Employee
        cls.emp = Employee.objects.get(user=cls.target)

    def test_deactivation_terminates_employee(self):
        from employees.models import Employee
        self.client.force_login(self.rh)
        # is_active non coché (absent du POST) → compte désactivé.
        r = self.client.post(reverse("accounts:user_edit", args=[self.target.pk]), {
            "first_name": "Paul", "last_name": "Parti", "email": "p@lpm.cm",
            "role": Role.EMPLOYE, "phone": "", "organization": ""})
        self.assertEqual(r.status_code, 302)
        self.target.refresh_from_db()
        self.emp.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(self.emp.status, Employee.Status.TERMINATED)

    def test_inactive_hidden_from_directory(self):
        self.target.is_active = False
        self.target.save(update_fields=["is_active"])
        self.client.force_login(self.rh)
        r = self.client.get(reverse("employees:list"))
        self.assertNotContains(r, "Paul")
        # …mais visible avec le filtre explicite.
        r2 = self.client.get(reverse("employees:list") + "?inactifs=1")
        self.assertContains(r2, "Paul")

    def test_reactivation_restores_active(self):
        from employees.models import Employee
        self.emp.status = Employee.Status.TERMINATED
        self.emp.save(update_fields=["status"])
        self.target.is_active = False
        self.target.save(update_fields=["is_active"])
        self.client.force_login(self.rh)
        self.client.post(reverse("accounts:user_edit", args=[self.target.pk]), {
            "first_name": "Paul", "last_name": "Parti", "email": "p@lpm.cm",
            "role": Role.EMPLOYE, "phone": "", "organization": "", "is_active": "on"})
        self.emp.refresh_from_db()
        self.assertEqual(self.emp.status, Employee.Status.ACTIVE)


class ContractTypeInUserListTest(TestCase):
    """Le type de contrat figure dans la liste des utilisateurs (item 3)."""

    def test_contract_type_shown(self):
        rh = User.objects.create_user("rh_ct", password="x", role=Role.RH)
        u = User.objects.create_user("c.dd", password="x", role=Role.EMPLOYE,
                                     first_name="Cyril", last_name="DD")
        from employees.models import Employee
        emp = Employee.objects.get(user=u)
        emp.contract_type = Employee.Contract.CDD
        emp.save(update_fields=["contract_type"])
        self.client.force_login(rh)
        r = self.client.get(reverse("accounts:user_list"))
        self.assertContains(r, "CDD")


class SensitiveInfoVisibilityTest(TestCase):
    """Type de contrat / date d'embauche / ancienneté : visibles RH/direction seulement."""

    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_sens", password="x", role=Role.RH)
        cls.emp_viewer = User.objects.create_user("emp_viewer", password="x", role=Role.EMPLOYE)
        from employees.models import Employee
        cls.target = Employee.objects.get(
            user=User.objects.create_user("t.cible", password="x", role=Role.EMPLOYE,
                                          first_name="Tom", last_name="CIBLE"))

    def test_employee_does_not_see_contract_and_hire_date(self):
        self.client.force_login(self.emp_viewer)
        r = self.client.get(reverse("employees:detail", args=[self.target.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Type de contrat")
        self.assertNotContains(r, "Date d'embauche")
        self.assertNotContains(r, "Ancienneté")

    def test_rh_sees_contract_and_hire_date(self):
        self.client.force_login(self.rh)
        r = self.client.get(reverse("employees:detail", args=[self.target.pk]))
        self.assertContains(r, "Type de contrat")
        self.assertContains(r, "Date d'embauche")


class HRDocumentsTest(TestCase):
    """RH/CEO/admin téléchargent attestations + contrat ; les autres non."""

    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rhdoc", password="x", role=Role.RH)
        cls.emp_user = User.objects.create_user("docemp", password="x", role=Role.EMPLOYE)
        from employees.models import Employee
        cls.emp = Employee.objects.get(user=cls.emp_user)

    def test_salarie_gets_travail_not_stage(self):
        """Un salarié (CDI/CDD/Temp) : attestation de travail OK, attestation de stage refusée."""
        self.client.force_login(self.rh)
        r = self.client.get(reverse("employees:attestation_travail", args=[self.emp.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(self.client.get(
            reverse("employees:attestation_stage", args=[self.emp.pk])).status_code, 403)

    def test_stagiaire_gets_stage_not_travail(self):
        """Un stagiaire : attestation de stage OK, attestation de travail refusée."""
        from employees.models import Employee
        stg = Employee.objects.get(
            user=User.objects.create_user("docstg", password="x", role=Role.STAGIAIRE))
        self.client.force_login(self.rh)
        r = self.client.get(reverse("employees:attestation_stage", args=[stg.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(self.client.get(
            reverse("employees:attestation_travail", args=[stg.pk])).status_code, 403)

    def test_employee_cannot_download_attestations(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(
            reverse("employees:attestation_travail", args=[self.emp.pk])).status_code, 403)

    def test_contract_download_404_without_file_then_ok(self):
        import tempfile
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from datetime import date
        from hr.models import Contract
        self.client.force_login(self.rh)
        # Aucun contrat avec fichier → 404.
        self.assertEqual(self.client.get(
            reverse("employees:contract_download", args=[self.emp.pk])).status_code, 404)
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            Contract.objects.create(employee=self.emp, type=Contract.Type.CDI,
                                    start_date=date(2026, 1, 1), is_active=True,
                                    file=SimpleUploadedFile("c.pdf", b"%PDF-1.4 test",
                                                            content_type="application/pdf"))
            r = self.client.get(reverse("employees:contract_download", args=[self.emp.pk]))
            self.assertEqual(r.status_code, 200)
