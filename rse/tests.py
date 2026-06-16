from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User


class RSEAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr_rse", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_rse", password="x", role=Role.EMPLOYE)
        cls.ext = User.objects.create_user("ext_rse", password="x", role=Role.CLIENT)

    def test_dashboard_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("rse:dashboard")).status_code, 200)

    def test_dashboard_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("rse:dashboard")).status_code, 403)

    def test_dashboard_redirige_non_authentifie(self):
        self.client.logout()
        r = self.client.get(reverse("rse:dashboard"))
        self.assertIn(r.status_code, [302, 403])

    def test_dashboard_redirige_externe(self):
        self.client.force_login(self.ext)
        self.assertEqual(self.client.get(reverse("rse:dashboard")).status_code, 302)

    def test_initiatives_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("rse:initiatives")).status_code, 200)

    def test_reports_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("rse:reports")).status_code, 200)

    def test_reports_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("rse:reports")).status_code, 403)

    def test_resources_200_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("rse:resources")).status_code, 200)

    def test_suppliers_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("rse:suppliers")).status_code, 200)

    def test_suppliers_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("rse:suppliers")).status_code, 403)

    def test_initiative_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("rse:initiative_create")).status_code, 403)

    def test_initiative_create_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("rse:initiative_create")).status_code, 200)
