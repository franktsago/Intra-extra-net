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
