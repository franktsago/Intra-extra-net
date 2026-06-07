from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from communication.models import News


class NewsPermissionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("adm", password="x", role=Role.ADMIN, is_superuser=True)
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.stg = User.objects.create_user("stg", password="x", role=Role.STAGIAIRE)
        cls.article = News.objects.create(title="Bienvenue", slug="bienvenue",
                                          content="Texte", author=cls.rh)

    # --- Consultation : tout le personnel ---
    def test_all_internal_can_consult(self):
        for u in (self.emp, self.stg, self.mgr, self.rh, self.ceo, self.admin):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:list")).status_code, 200)
            self.assertEqual(
                self.client.get(reverse("communication:detail", args=[self.article.slug])).status_code, 200)

    def test_news_on_dashboard(self):
        self.client.force_login(self.emp)
        r = self.client.get(reverse("dashboard:home"))
        self.assertContains(r, "Bienvenue")

    # --- Gestion : RH / CEO / Admin uniquement ---
    def test_rh_ceo_admin_can_manage(self):
        for u in (self.rh, self.ceo, self.admin):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:create")).status_code, 200)
            self.assertEqual(self.client.get(reverse("communication:edit", args=[self.article.pk])).status_code, 200)
            self.assertEqual(self.client.get(reverse("communication:delete", args=[self.article.pk])).status_code, 200)

    def test_manager_employee_stagiaire_cannot_manage(self):
        for u in (self.mgr, self.emp, self.stg):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:create")).status_code, 403)
            self.assertEqual(self.client.get(reverse("communication:edit", args=[self.article.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("communication:delete", args=[self.article.pk])).status_code, 403)

    def test_rh_can_delete(self):
        self.client.force_login(self.rh)
        r = self.client.post(reverse("communication:delete", args=[self.article.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(News.objects.filter(pk=self.article.pk).exists())
