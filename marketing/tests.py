from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User


class MarketingDigitalAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr_mkt", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_mkt", password="x", role=Role.EMPLOYE)
        cls.ext = User.objects.create_user("ext_mkt", password="x", role=Role.CLIENT)

    def test_kpi_dashboard_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:kpi_dashboard")).status_code, 200)

    def test_kpi_dashboard_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("marketing:kpi_dashboard")).status_code, 403)

    def test_kpi_dashboard_redirige_externe(self):
        self.client.force_login(self.ext)
        self.assertEqual(self.client.get(reverse("marketing:kpi_dashboard")).status_code, 302)

    def test_lead_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:lead_list")).status_code, 200)

    def test_digital_hub_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:digital_hub")).status_code, 200)

    def test_seo_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:seo_list")).status_code, 200)

    def test_ads_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:ads_list")).status_code, 200)

    def test_email_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:email_list")).status_code, 200)

    def test_abtest_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("marketing:abtest_list")).status_code, 200)

    def test_seo_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("marketing:seo_create")).status_code, 403)
