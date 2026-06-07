from datetime import date, timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Role, User
from employees.models import Employee, upcoming_birthdays
from notifications.models import Notification


class BirthdayNotifyTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_b", password="x", role=Role.RH)
        cls.mgr = User.objects.create_user("mgr_b", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_b", password="x", role=Role.EMPLOYE)
        e = Employee.objects.get(user=cls.emp)
        e.manager = Employee.objects.get(user=cls.mgr)
        e.save()
        cls.emp_profile = e

    def _set_bday(self, offset_days):
        d = timezone.localdate() + timedelta(days=offset_days)
        # année arbitraire dans le passé pour calculer l'âge
        self.emp_profile.birth_date = date(1990, d.month, d.day)
        self.emp_profile.save()

    def test_day_of_notifies_everyone(self):
        self._set_bday(0)
        call_command("birthday_notify")
        # L'intéressé reçoit un message chaleureux
        self.assertTrue(Notification.objects.filter(
            recipient=self.emp, title__startswith="Joyeux anniversaire").exists())
        # Les autres reçoivent l'annonce
        self.assertTrue(Notification.objects.filter(
            recipient=self.rh, title__icontains="Anniversaire de").exists())
        # Idempotent : un 2e passage ne double pas
        before = Notification.objects.count()
        call_command("birthday_notify")
        self.assertEqual(Notification.objects.count(), before)

    def test_three_days_before_notifies_management(self):
        self._set_bday(3)
        call_command("birthday_notify")
        self.assertTrue(Notification.objects.filter(
            recipient=self.rh, title__startswith="Anniversaire à venir").exists())
        self.assertTrue(Notification.objects.filter(
            recipient=self.mgr, title__startswith="Anniversaire à venir").exists())
        # L'intéressé n'est PAS prévenu en amont
        self.assertFalse(Notification.objects.filter(
            recipient=self.emp, title__startswith="Anniversaire à venir").exists())

    def test_upcoming_birthdays_helper(self):
        self._set_bday(5)
        rows = upcoming_birthdays(Employee.objects.filter(status=Employee.Status.ACTIVE))
        ids = [r["employee"].id for r in rows]
        self.assertIn(self.emp_profile.id, ids)


class BirthdaySpaceTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_s", password="x", role=Role.RH)
        cls.emp = User.objects.create_user("emp_s", password="x", role=Role.EMPLOYE)
        e = Employee.objects.get(user=cls.emp)
        e.birth_date = date(2000, 3, 14)
        e.save()

    def test_rh_sees_birthday_space(self):
        from django.urls import reverse
        self.client.force_login(self.rh)
        r = self.client.get(reverse("hr:birthdays"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "14 mars")

    def test_employee_blocked(self):
        from django.urls import reverse
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("hr:birthdays")).status_code, 403)


class DailyAutoTriggerTest(TestCase):
    def test_dashboard_visit_triggers_birthday_notifications(self):
        from django.urls import reverse
        from django.core.cache import cache
        from notifications.models import Notification
        cache.clear()
        rh = User.objects.create_user("rh_auto", password="x", role=Role.RH)
        bday = User.objects.create_user("bday_auto", password="x", role=Role.EMPLOYE,
                                        first_name="Joie", last_name="DUJOUR")
        e = Employee.objects.get(user=bday)
        today = timezone.localdate()
        e.birth_date = date(2000, today.month, today.day)
        e.save()
        # La RH ouvre son tableau de bord → le runner quotidien se déclenche.
        self.client.force_login(rh)
        self.client.get(reverse("dashboard:home"))
        # L'intéressé a reçu le message chaleureux, la RH l'annonce.
        self.assertTrue(Notification.objects.filter(
            recipient=bday, title__startswith="Joyeux anniversaire").exists())
        self.assertTrue(Notification.objects.filter(
            recipient=rh, title__icontains="Anniversaire de").exists())
