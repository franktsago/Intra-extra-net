from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User
from conges.models import LeaveRequest, LeaveType
from employees.models import Employee
from notifications.models import Notification


class HolidayNotificationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.client_u = User.objects.create_user("cli", password="x", role=Role.CLIENT)

    def test_internal_only_does_not_notify_clients(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("conges:holidays"), {
            "date": "2026-12-25", "name": "Noël", "audience": "INTERNAL",
        })
        self.assertTrue(Notification.objects.filter(recipient=self.emp).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.client_u).exists())

    def test_both_notifies_clients_as_external(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("conges:holidays"), {
            "date": "2026-08-15", "name": "Assomption", "audience": "BOTH",
        })
        self.assertTrue(Notification.objects.filter(recipient=self.emp).exists())
        n_cli = Notification.objects.filter(recipient=self.client_u)
        self.assertEqual(n_cli.count(), 1)
        # La notif client est cloisonnée côté extranet.
        self.assertEqual(n_cli.first().audience, Notification.Audience.EXTERNAL)

    def test_employee_can_view_holidays_no_403(self):
        # Point 7 : l'employé ne doit plus tomber sur un 403 sur les jours fériés.
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("conges:holidays")).status_code, 200)


class LeaveRequestRolesTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.ltype = LeaveType.objects.create(name="Congé annuel", code="ANN")

    def _request_leave(self, user):
        self.client.force_login(user)
        start = timezone.localdate() + timedelta(days=10)
        end = start + timedelta(days=2)
        return self.client.post(reverse("conges:create"), {
            "leave_type": self.ltype.pk,
            "start_date": start.isoformat(), "end_date": end.isoformat(), "reason": "Repos",
        })

    def test_manager_and_rh_can_request_leave(self):
        for u in (self.mgr, self.rh):
            r = self._request_leave(u)
            self.assertEqual(r.status_code, 302)
            emp = Employee.objects.get(user=u)
            self.assertTrue(LeaveRequest.objects.filter(employee=emp).exists())

    def test_employee_without_manager_validated_directly_by_rh(self):
        emp_u = User.objects.create_user("nomgr", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=emp_u)
        emp.manager = None
        emp.save()
        self._request_leave(emp_u)
        lr = LeaveRequest.objects.get(employee=emp)
        # Sans responsable : la chaîne se réduit à la RH.
        self.assertEqual(lr.chain, [Role.RH])
        # La RH valide directement → approuvé en une étape.
        self.client.force_login(self.rh)
        self.client.post(reverse("conges:decide", args=[lr.pk]), {"decision": "approve", "comment": ""})
        lr.refresh_from_db()
        self.assertEqual(lr.status, LeaveRequest.Status.APPROVED)

    def test_rh_leave_notifies_ceo_and_admin(self):
        admin = User.objects.create_superuser("superadmin", password="x", role=Role.ADMIN)
        self._request_leave(self.rh)
        # La demande de congé de la RH (chaîne → CEO) notifie le CEO ET l'admin.
        self.assertTrue(Notification.objects.filter(
            recipient=self.ceo, title__icontains="valider").exists())
        self.assertTrue(Notification.objects.filter(
            recipient=admin, title__icontains="valider").exists())

    def test_employee_leave_does_not_spam_admin(self):
        admin = User.objects.create_superuser("superadmin2", password="x", role=Role.ADMIN)
        emp_u = User.objects.create_user("simple", password="x", role=Role.EMPLOYE)
        e = Employee.objects.get(user=emp_u)
        e.manager = Employee.objects.get(user=self.mgr)
        e.save()
        self._request_leave(emp_u)
        # Un congé d'employé (étape responsable) ne notifie PAS l'admin.
        self.assertFalse(Notification.objects.filter(
            recipient=admin, title__icontains="valider").exists())

    def test_approved_leave_notifies_all_staff(self):
        bystander = User.objects.create_user("temoin", password="x", role=Role.EMPLOYE)
        emp_u = User.objects.create_user("nomgr2", password="x", role=Role.EMPLOYE)
        emp = Employee.objects.get(user=emp_u)
        emp.manager = None
        emp.save()
        self._request_leave(emp_u)
        lr = LeaveRequest.objects.get(employee=emp)
        self.client.force_login(self.rh)
        self.client.post(reverse("conges:decide", args=[lr.pk]), {"decision": "approve", "comment": ""})
        lr.refresh_from_db()
        self.assertEqual(lr.status, LeaveRequest.Status.APPROVED)
        # Un collègue non concerné est informé du congé (annonce au personnel).
        self.assertTrue(Notification.objects.filter(
            recipient=bystander, title__icontains="congé approuvé").exists())
        # L'intéressé reçoit sa notif personnelle, pas le doublon d'annonce.
        self.assertEqual(Notification.objects.filter(
            recipient=emp_u, title__icontains="congé approuvé").count(), 1)


class AbsencesVisibilityTest(TestCase):
    """Tout le personnel interne voit qui est en congé et en mission."""

    @classmethod
    def setUpTestData(cls):
        cls.viewer = User.objects.create_user("viewer", password="x", role=Role.EMPLOYE)
        cls.rh = User.objects.create_user("rhabs", password="x", role=Role.RH)
        cls.on_leave_u = User.objects.create_user("encongé", password="x", role=Role.EMPLOYE)
        cls.on_mission_u = User.objects.create_user("enmission", password="x", role=Role.EMPLOYE)
        cls.on_leave_u.first_name, cls.on_leave_u.last_name = "Carla", "CONGE"
        cls.on_leave_u.save()
        cls.on_mission_u.first_name, cls.on_mission_u.last_name = "Momo", "MISSION"
        cls.on_mission_u.save()
        today = timezone.localdate()
        lt = LeaveType.objects.create(name="Congé annuel")
        LeaveRequest.objects.create(
            employee=Employee.objects.get(user=cls.on_leave_u), leave_type=lt,
            start_date=today - timedelta(days=1), end_date=today + timedelta(days=2),
            status=LeaveRequest.Status.APPROVED)
        from hr.models import Mission
        Mission.objects.create(
            employee=Employee.objects.get(user=cls.on_mission_u),
            start_date=today - timedelta(days=1), end_date=today + timedelta(days=2),
            destination="Yaoundé", created_by=cls.rh)

    def test_ordinary_employee_sees_leave_and_mission(self):
        self.client.force_login(self.viewer)
        r = self.client.get(reverse("conges:absences"))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode("utf-8", "ignore")
        self.assertIn("CONGE", body)       # personne en congé visible
        self.assertIn("MISSION", body)     # personne en mission visible
        self.assertIn("Yaoundé", body)

    def test_external_cannot_access(self):
        cli = User.objects.create_user("cliabs", password="x", role=Role.CLIENT)
        self.client.force_login(cli)
        self.assertEqual(self.client.get(reverse("conges:absences")).status_code, 403)


class LeaveDeleteAbsencesTest(TestCase):
    """RH/CEO/admin peuvent supprimer un congé depuis Absences ; pas les autres."""

    def test_rh_deletes_leave(self):
        rh = User.objects.create_user("rhdel", password="x", role=Role.RH)
        empu = User.objects.create_user("empdel", password="x", role=Role.EMPLOYE)
        lt = LeaveType.objects.create(name="Annuel del")
        lr = LeaveRequest.objects.create(
            employee=Employee.objects.get(user=empu), leave_type=lt,
            start_date=timezone.localdate(), end_date=timezone.localdate() + timedelta(days=1),
            status=LeaveRequest.Status.APPROVED)
        self.client.force_login(rh)
        r = self.client.post(reverse("conges:leave_delete", args=[lr.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(LeaveRequest.objects.filter(pk=lr.pk).exists())

    def test_employee_cannot_delete_leave(self):
        empu = User.objects.create_user("empnodel", password="x", role=Role.EMPLOYE)
        lt = LeaveType.objects.create(name="Annuel x")
        lr = LeaveRequest.objects.create(
            employee=Employee.objects.get(user=empu), leave_type=lt,
            start_date=timezone.localdate(), end_date=timezone.localdate(),
            status=LeaveRequest.Status.APPROVED)
        self.client.force_login(empu)
        self.assertEqual(self.client.post(reverse("conges:leave_delete", args=[lr.pk])).status_code, 403)
        self.assertTrue(LeaveRequest.objects.filter(pk=lr.pk).exists())


class FriendlyErrorPagesTest(TestCase):
    def test_404_friendly(self):
        u = User.objects.create_user("err404", password="x", role=Role.EMPLOYE)
        self.client.force_login(u)
        r = self.client.get("/page-inexistante-xyz/")
        self.assertEqual(r.status_code, 404)
        self.assertIn("Retour à l'accueil", r.content.decode("utf-8", "ignore"))

    def test_403_friendly(self):
        u = User.objects.create_user("err403", password="x", role=Role.EMPLOYE)
        self.client.force_login(u)
        r = self.client.get(reverse("hr:contracts"))  # réservé RH
        self.assertEqual(r.status_code, 403)
        self.assertIn("Retour à l'accueil", r.content.decode("utf-8", "ignore"))
