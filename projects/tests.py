from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User


class ProjectDepartmentScopeTest(TestCase):
    """Chaque département gère ses projets : la liste est cloisonnée par département."""

    @classmethod
    def setUpTestData(cls):
        from employees.models import Department, Employee
        from projects.models import Project
        cls.mkt = Department.objects.create(name="Marketing", code="MKT")
        cls.ops = Department.objects.create(name="Événementiel", code="OPS")
        cls.rh = User.objects.create_user("rh_prj2", password="x", role=Role.RH)
        cls.mgr_mkt = User.objects.create_user("mgr_mkt2", password="x", role=Role.MANAGER)
        Employee.objects.get(user=cls.mgr_mkt).departments.set([cls.mkt])
        # Employé membre du département Marketing (équipe du manager MKT).
        cls.emp_mkt = User.objects.create_user("emp_mkt2", password="x", role=Role.EMPLOYE)
        Employee.objects.get(user=cls.emp_mkt).departments.set([cls.mkt])
        # Employé sans département, mais chef d'un projet ponctuel.
        cls.emp = User.objects.create_user("emp_prj2", password="x", role=Role.EMPLOYE)
        cls.proj_mkt = Project.objects.create(name="ProjetAlpha", department=cls.mkt)
        cls.proj_ops = Project.objects.create(name="ProjetBeta", department=cls.ops)
        cls.proj_emp = Project.objects.create(name="ProjetGamma", department=cls.ops, manager=cls.emp)

    def test_manager_sees_only_own_department(self):
        self.client.force_login(self.mgr_mkt)
        r = self.client.get(reverse("projects:list"))
        self.assertContains(r, "ProjetAlpha")
        self.assertNotContains(r, "ProjetBeta")

    def test_team_member_sees_department_projects(self):
        # L'équipe voit les projets de son département, comme son manager —
        # même sans être nommément affectée au projet.
        self.client.force_login(self.emp_mkt)
        r = self.client.get(reverse("projects:list"))
        self.assertContains(r, "ProjetAlpha")        # projet du département MKT
        self.assertNotContains(r, "ProjetBeta")      # autre département

    def test_rh_sees_all_departments(self):
        self.client.force_login(self.rh)
        r = self.client.get(reverse("projects:list"))
        self.assertContains(r, "ProjetAlpha")
        self.assertContains(r, "ProjetBeta")

    def test_rh_can_filter_by_department(self):
        self.client.force_login(self.rh)
        r = self.client.get(reverse("projects:list") + f"?dept={self.mkt.id}")
        self.assertContains(r, "ProjetAlpha")
        self.assertNotContains(r, "ProjetBeta")

    def test_employee_without_department_sees_only_assigned(self):
        # Un employé sans département ne voit que les projets où il intervient.
        self.client.force_login(self.emp)
        r = self.client.get(reverse("projects:list"))
        self.assertContains(r, "ProjetGamma")        # il en est le chef
        self.assertNotContains(r, "ProjetAlpha")
        self.assertNotContains(r, "ProjetBeta")

    def test_manager_form_limited_to_own_departments(self):
        from projects.forms import ProjectForm
        form = ProjectForm(viewer=self.mgr_mkt)
        dept_ids = set(form.fields["department"].queryset.values_list("id", flat=True))
        self.assertEqual(dept_ids, {self.mkt.id})

    def test_rh_form_sees_all_departments(self):
        from projects.forms import ProjectForm
        form = ProjectForm(viewer=self.rh)
        dept_ids = set(form.fields["department"].queryset.values_list("id", flat=True))
        self.assertIn(self.mkt.id, dept_ids)
        self.assertIn(self.ops.id, dept_ids)


class ProjectMediaDeleteTest(TestCase):
    """Suppression d'un média du rapport terrain : auteur ou responsable."""

    @classmethod
    def setUpTestData(cls):
        from projects.models import Project
        cls.mgr = User.objects.create_user("pm_mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("pm_emp", password="x", role=Role.EMPLOYE)
        cls.other = User.objects.create_user("pm_oth", password="x", role=Role.EMPLOYE)
        cls.proj = Project.objects.create(name="ProjMedia")

    def _media(self, uploader):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from projects.models import ProjectMedia
        return ProjectMedia.objects.create(
            project=self.proj, uploaded_by=uploader,
            file=SimpleUploadedFile("rapport.txt", b"data"))

    def test_uploader_can_delete(self):
        import tempfile
        from django.test import override_settings
        from projects.models import ProjectMedia
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            m = self._media(self.emp)
            self.client.force_login(self.emp)
            r = self.client.post(reverse("projects:media_delete", args=[self.proj.pk, m.pk]))
            self.assertEqual(r.status_code, 302)
            self.assertFalse(ProjectMedia.objects.filter(pk=m.pk).exists())

    def test_other_employee_cannot_delete(self):
        import tempfile
        from django.test import override_settings
        from projects.models import ProjectMedia
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            m = self._media(self.emp)
            self.client.force_login(self.other)
            r = self.client.post(reverse("projects:media_delete", args=[self.proj.pk, m.pk]))
            self.assertEqual(r.status_code, 403)
            self.assertTrue(ProjectMedia.objects.filter(pk=m.pk).exists())

    def test_manager_can_delete_any(self):
        import tempfile
        from django.test import override_settings
        from projects.models import ProjectMedia
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            m = self._media(self.emp)
            self.client.force_login(self.mgr)
            r = self.client.post(reverse("projects:media_delete", args=[self.proj.pk, m.pk]))
            self.assertEqual(r.status_code, 302)
            self.assertFalse(ProjectMedia.objects.filter(pk=m.pk).exists())


class ProjectsBacklogAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("prj_admin", password="x", role=Role.ADMIN)
        cls.emp = User.objects.create_user("prj_emp", password="x", role=Role.EMPLOYE)

    def test_ticket_list_accessible_to_internal_user(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("projects:ticket_list")).status_code, 200)

    def test_benchmark_list_accessible_to_internal_user(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("projects:benchmark_list")).status_code, 200)

    def test_ticket_create_accessible_to_internal_user(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("projects:ticket_create")).status_code, 200)

    def test_benchmark_create_accessible_to_internal_user(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("projects:benchmark_create")).status_code, 200)

