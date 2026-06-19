from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from employees.models import Employee
from tasks.models import Task


class TaskValidationWorkflowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from employees.models import Department
        cls.dep = Department.objects.create(name="Marketing", code="MKT")
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        # Le signal accounts.signals crée automatiquement la fiche Employee.
        emp_emp = Employee.objects.get(user=cls.emp)
        emp_emp.manager = Employee.objects.get(user=cls.mgr)
        emp_emp.save()
        # Cloisonnement par département : manager et employé dans le même département.
        Employee.objects.get(user=cls.mgr).departments.set([cls.dep])
        emp_emp.departments.set([cls.dep])

    def test_employee_creates_pending_task_then_manager_approves(self):
        self.client.force_login(self.emp)
        r = self.client.post(reverse("tasks:create"), {
            "title": "Ma tache", "description": "desc", "priority": "NORMAL",
        })
        self.assertEqual(r.status_code, 302)
        task = Task.objects.get(title="Ma tache")
        self.assertFalse(task.is_approved)
        self.assertEqual(task.assigned_to, self.emp)
        self.assertEqual(task.created_by, self.emp)

        # Employee cannot change status while pending
        r = self.client.post(reverse("tasks:detail", args=[task.pk]), {"status": "IN_PROGRESS"})
        task.refresh_from_db()
        self.assertEqual(task.status, "TODO")

        # Manager approves
        self.client.force_login(self.mgr)
        r = self.client.get(reverse("tasks:approve", args=[task.pk, "approve"]))
        task.refresh_from_db()
        self.assertTrue(task.is_approved)
        self.assertEqual(task.approved_by, self.mgr)

        # Now employee can change status
        self.client.force_login(self.emp)
        self.client.post(reverse("tasks:detail", args=[task.pk]), {"status": "IN_PROGRESS"})
        task.refresh_from_db()
        self.assertEqual(task.status, "IN_PROGRESS")

    def test_manager_created_task_is_active_immediately(self):
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("tasks:create"), {
            "title": "Tache chef", "priority": "NORMAL", "status": "TODO",
            "assignees": [self.emp.pk],
        })
        self.assertEqual(r.status_code, 302)
        task = Task.objects.get(title="Tache chef")
        self.assertTrue(task.is_approved)
        self.assertEqual(task.assigned_to, self.emp)

    def test_assigned_task_redirects_to_team_scope_and_is_visible(self):
        """Une tâche assignée à un membre doit rester visible pour le responsable
        (redirection vers « Mon équipe », sinon le filtre « Mes tâches » la cache)."""
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("tasks:create"), {
            "title": "Tache equipe", "priority": "NORMAL", "status": "TODO",
            "assignees": [self.emp.pk],
        })
        self.assertEqual(r.status_code, 302)
        self.assertIn("scope=all", r["Location"])
        task = Task.objects.get(title="Tache equipe")
        # Invisible sous « Mes tâches »…
        mine = self.client.get(reverse("tasks:board") + "?scope=mine")
        self.assertNotContains(mine, "Tache equipe")
        # …mais bien présente sous « Mon équipe ».
        team = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(team, "Tache equipe")
        # L'employé assigné la voit et est notifié.
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(
            recipient=self.emp, title__icontains="assign").exists())
        self.client.force_login(self.emp)
        emp_board = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(emp_board, "Tache equipe")

    def test_employee_cannot_approve(self):
        task = Task.objects.create(title="P", assigned_to=self.emp, created_by=self.emp, is_approved=False)
        self.client.force_login(self.emp)
        r = self.client.get(reverse("tasks:approve", args=[task.pk, "approve"]))
        self.assertEqual(r.status_code, 403)
        task.refresh_from_db()
        self.assertFalse(task.is_approved)


class TaskRenderAndNotifyTest(TestCase):
    """Tâche terminée → notification au créateur ; dépôt de rendu (fichiers)."""

    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("rn_mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("rn_emp", password="x", role=Role.EMPLOYE)
        e = Employee.objects.get(user=cls.emp)
        e.manager = Employee.objects.get(user=cls.mgr)
        e.save()
        cls.task = Task.objects.create(title="Livrable X", assigned_to=cls.emp,
                                       created_by=cls.mgr, is_approved=True)

    def test_done_notifies_assigner(self):
        from notifications.models import Notification
        self.client.force_login(self.emp)
        self.client.post(reverse("tasks:detail", args=[self.task.pk]), {"status": "DONE"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "DONE")
        self.assertTrue(Notification.objects.filter(
            recipient=self.mgr, title__icontains="termin").exists())

    def test_assignee_uploads_render(self):
        import tempfile
        from django.test import override_settings
        from django.core.files.uploadedfile import SimpleUploadedFile
        from tasks.models import TaskAttachment
        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            self.client.force_login(self.emp)
            r = self.client.post(reverse("tasks:attach", args=[self.task.pk]), {
                "files": [SimpleUploadedFile("rendu.pdf", b"%PDF-1.4"),
                          SimpleUploadedFile("notes.txt", b"notes")]})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(TaskAttachment.objects.filter(task=self.task).count(), 2)

    def test_other_cannot_upload(self):
        other = User.objects.create_user("rn_other", password="x", role=Role.EMPLOYE)
        self.client.force_login(other)
        from django.core.files.uploadedfile import SimpleUploadedFile
        r = self.client.post(reverse("tasks:attach", args=[self.task.pk]),
                             {"files": [SimpleUploadedFile("x.txt", b"x")]})
        self.assertEqual(r.status_code, 403)


class TaskTeamAssignmentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from employees.models import Department
        cls.dep = Department.objects.create(name="Marketing", code="MKT")
        cls.mgr = User.objects.create_user("mgr2", password="x", role=Role.MANAGER)
        cls.member = User.objects.create_user("member", password="x", role=Role.EMPLOYE)
        cls.outsider = User.objects.create_user("outsider", password="x", role=Role.EMPLOYE)
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        # Manager et membre dans le même département ; l'« outsider » dans un autre.
        Employee.objects.get(user=cls.mgr).departments.set([cls.dep])
        Employee.objects.get(user=cls.member).departments.set([cls.dep])
        other = Department.objects.create(name="Finance", code="FIN")
        Employee.objects.get(user=cls.outsider).departments.set([other])

    def test_manager_assigns_only_to_department(self):
        from tasks.forms import TaskForm
        ids = set(TaskForm(viewer=self.mgr).fields["assigned_to"].queryset.values_list("id", flat=True))
        self.assertIn(self.member.id, ids)       # membre de son département
        self.assertIn(self.mgr.id, ids)          # lui-même
        self.assertNotIn(self.outsider.id, ids)  # autre département

    def test_rh_can_assign_to_anyone(self):
        from tasks.forms import TaskForm
        ids = set(TaskForm(viewer=self.rh).fields["assigned_to"].queryset.values_list("id", flat=True))
        self.assertIn(self.outsider.id, ids)
        self.assertIn(self.member.id, ids)

    def test_assigned_to_is_required(self):
        from tasks.forms import TaskForm
        self.assertTrue(TaskForm(viewer=self.mgr).fields["assigned_to"].required)
        form = TaskForm(data={"title": "Sans assignation", "priority": "NORMAL",
                              "status": "TODO"}, viewer=self.mgr)
        self.assertFalse(form.is_valid())
        self.assertIn("assigned_to", form.errors)


class TaskDepartmentScopeTest(TestCase):
    """Cloisonnement des tâches par département : chacun ne voit que le sien (item)."""

    @classmethod
    def setUpTestData(cls):
        from employees.models import Department
        cls.mkt = Department.objects.create(name="Marketing", code="MKT")
        cls.ops = Department.objects.create(name="Événementiel", code="OPS")
        cls.mgr = User.objects.create_user("mgr_dep", password="x", role=Role.MANAGER)
        cls.member = User.objects.create_user("mem_dep", password="x", role=Role.EMPLOYE)
        cls.other = User.objects.create_user("oth_dep", password="x", role=Role.EMPLOYE)
        cls.rh = User.objects.create_user("rh_dep", password="x", role=Role.RH)
        Employee.objects.get(user=cls.mgr).departments.set([cls.mkt])
        Employee.objects.get(user=cls.member).departments.set([cls.mkt])
        Employee.objects.get(user=cls.other).departments.set([cls.ops])
        # Tâche du département Marketing (assignée au membre) et tâche Événementiel.
        cls.t_mkt = Task.objects.create(title="TacheMKT", assigned_to=cls.member,
                                        created_by=cls.mgr, is_approved=True)
        cls.t_ops = Task.objects.create(title="TacheOPS", assigned_to=cls.other,
                                        created_by=cls.other, is_approved=True)

    def test_member_sees_department_tasks(self):
        # L'équipe voit les tâches de son département, comme son manager.
        self.client.force_login(self.member)
        r = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(r, "TacheMKT")
        self.assertNotContains(r, "TacheOPS")

    def test_manager_sees_only_own_department(self):
        self.client.force_login(self.mgr)
        r = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(r, "TacheMKT")
        self.assertNotContains(r, "TacheOPS")

    def test_other_department_isolated(self):
        self.client.force_login(self.other)
        r = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(r, "TacheOPS")
        self.assertNotContains(r, "TacheMKT")

    def test_rh_sees_all(self):
        self.client.force_login(self.rh)
        r = self.client.get(reverse("tasks:board") + "?scope=all")
        self.assertContains(r, "TacheMKT")
        self.assertContains(r, "TacheOPS")


class MultiAssignTest(TestCase):
    """Un responsable assigne une tâche à plusieurs membres : une tâche par membre,
    et la notification mentionne les collègues associés (espace de chacun)."""

    @classmethod
    def setUpTestData(cls):
        from employees.models import Department
        cls.dep = Department.objects.create(name="Studio", code="STU")
        cls.mgr = User.objects.create_user("ma_mgr", password="x", role=Role.MANAGER,
                                            first_name="Max", last_name="MGR")
        cls.m1 = User.objects.create_user("ma_m1", password="x", role=Role.EMPLOYE,
                                           first_name="Ana", last_name="UN")
        cls.m2 = User.objects.create_user("ma_m2", password="x", role=Role.EMPLOYE,
                                           first_name="Bob", last_name="DEUX")
        for u in (cls.mgr, cls.m1, cls.m2):
            Employee.objects.get(user=u).departments.add(cls.dep)

    def test_creates_one_task_per_member(self):
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("tasks:create"), {
            "title": "Tache groupe", "priority": "NORMAL", "status": "TODO",
            "assignees": [self.m1.pk, self.m2.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Task.objects.filter(title="Tache groupe").count(), 2)
        self.assertTrue(Task.objects.filter(title="Tache groupe", assigned_to=self.m1).exists())
        self.assertTrue(Task.objects.filter(title="Tache groupe", assigned_to=self.m2).exists())

    def test_notification_mentions_colleagues(self):
        from notifications.models import Notification
        self.client.force_login(self.mgr)
        self.client.post(reverse("tasks:create"), {
            "title": "Tache duo", "priority": "NORMAL", "status": "TODO",
            "assignees": [self.m1.pk, self.m2.pk]})
        n1 = Notification.objects.filter(recipient=self.m1, title__icontains="assign").first()
        self.assertIsNotNone(n1)
        self.assertIn("Bob DEUX", n1.message)        # Ana est informée qu'elle traite avec Bob
        n2 = Notification.objects.filter(recipient=self.m2, title__icontains="assign").first()
        self.assertIn("Ana UN", n2.message)          # …et réciproquement

    def test_single_assign_has_no_colleague_mention(self):
        from notifications.models import Notification
        self.client.force_login(self.mgr)
        self.client.post(reverse("tasks:create"), {
            "title": "Tache solo", "priority": "NORMAL", "status": "TODO",
            "assignees": [self.m1.pk]})
        n = Notification.objects.filter(recipient=self.m1, title__icontains="assign").first()
        self.assertNotIn("Vous traiterez cette tâche avec", n.message)


class EmployeeCannotEditAssignedTaskTest(TestCase):
    """Un employé ne peut PAS modifier la tâche que son responsable lui a assignée :
    il ne peut que changer le statut (et ajouter son rendu)."""

    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("ce_mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("ce_emp", password="x", role=Role.EMPLOYE)
        cls.task = Task.objects.create(title="Original", description="desc",
                                       assigned_to=cls.emp, created_by=cls.mgr, is_approved=True)

    def test_employee_has_no_title_field(self):
        self.client.force_login(self.emp)
        r = self.client.get(reverse("tasks:detail", args=[self.task.pk]))
        self.assertNotContains(r, 'name="title"')   # champ d'édition absent

    def test_employee_post_cannot_change_title(self):
        self.client.force_login(self.emp)
        self.client.post(reverse("tasks:detail", args=[self.task.pk]),
                         {"title": "Pirate", "description": "x", "status": "IN_PROGRESS"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Original")       # titre/description inchangés
        self.assertEqual(self.task.description, "desc")
        self.assertEqual(self.task.status, "IN_PROGRESS")   # mais le statut change
