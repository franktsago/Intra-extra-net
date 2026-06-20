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

    def test_employee_stagiaire_cannot_manage(self):
        for u in (self.emp, self.stg):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:create")).status_code, 403)
            self.assertEqual(self.client.get(reverse("communication:edit", args=[self.article.pk])).status_code, 403)
            self.assertEqual(self.client.get(reverse("communication:delete", args=[self.article.pk])).status_code, 403)

    def test_rh_can_delete(self):
        self.client.force_login(self.rh)
        r = self.client.post(reverse("communication:delete", args=[self.article.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(News.objects.filter(pk=self.article.pk).exists())

    # --- Workflow de validation des actualités (responsable → RH/CEO/admin) ---
    def test_manager_can_access_create(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("communication:create")).status_code, 200)

    def test_manager_news_goes_to_pending(self):
        self.client.force_login(self.mgr)
        self.client.post(reverse("communication:create"), {
            "title": "Annonce du responsable", "category": News.Category.GENERAL,
            "summary": "", "content": "Contenu test", "is_pinned": False})
        art = News.objects.get(title="Annonce du responsable")
        self.assertEqual(art.mod_status, News.ModStatus.PENDING)
        self.assertFalse(art.is_visible)

    def test_secondary_role_validator_is_notified(self):
        from notifications.models import Notification
        from communication.views import _can_moderate_news
        # Un responsable dont RH est un rôle SECONDAIRE doit être notifié et pouvoir valider.
        sec_rh = User.objects.create_user("sec_rh", password="x", role=Role.MANAGER,
                                          secondary_roles="RH")
        self.client.force_login(self.mgr)
        self.client.post(reverse("communication:create"), {
            "title": "Annonce à valider", "category": News.Category.GENERAL,
            "summary": "", "content": "Contenu", "is_pinned": False})
        self.assertTrue(Notification.objects.filter(
            recipient=sec_rh, title__icontains="valider").exists())
        self.assertTrue(_can_moderate_news(sec_rh))

    def test_pending_news_hidden_from_feed(self):
        News.objects.create(title="En attente", slug="en-attente", content="x",
                            author=self.mgr, mod_status=News.ModStatus.PENDING)
        self.client.force_login(self.emp)
        r = self.client.get(reverse("communication:list"))
        self.assertNotContains(r, "En attente")

    def test_rh_news_published_directly(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("communication:create"), {
            "title": "Note RH directe", "category": News.Category.RH,
            "summary": "", "content": "Contenu", "is_pinned": False})
        art = News.objects.get(title="Note RH directe")
        self.assertEqual(art.mod_status, News.ModStatus.APPROVED)
        self.assertTrue(art.is_visible)

    def test_moderation_queue_access(self):
        self.client.force_login(self.rh)
        self.assertEqual(self.client.get(reverse("communication:moderation")).status_code, 200)
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("communication:moderation")).status_code, 403)

    def test_approve_publishes(self):
        art = News.objects.create(title="À valider", slug="a-valider", content="x",
                                  author=self.mgr, mod_status=News.ModStatus.PENDING)
        self.client.force_login(self.ceo)
        self.client.post(reverse("communication:approve", args=[art.pk]))
        art.refresh_from_db()
        self.assertEqual(art.mod_status, News.ModStatus.APPROVED)
        self.assertTrue(art.is_visible)

    def test_reject_keeps_hidden(self):
        art = News.objects.create(title="À refuser", slug="a-refuser", content="x",
                                  author=self.mgr, mod_status=News.ModStatus.PENDING)
        self.client.force_login(self.rh)
        self.client.post(reverse("communication:reject", args=[art.pk]), {"reason": "Hors sujet"})
        art.refresh_from_db()
        self.assertEqual(art.mod_status, News.ModStatus.REJECTED)
        self.assertFalse(art.is_visible)
        self.assertEqual(art.reject_reason, "Hors sujet")

    def test_author_sees_own_pending(self):
        art = News.objects.create(title="Mon brouillon", slug="mon-brouillon", content="x",
                                  author=self.mgr, mod_status=News.ModStatus.PENDING)
        self.client.force_login(self.mgr)
        self.assertEqual(
            self.client.get(reverse("communication:detail", args=[art.slug])).status_code, 200)

    def test_other_employee_cannot_see_pending(self):
        art = News.objects.create(title="Caché", slug="cache", content="x",
                                  author=self.mgr, mod_status=News.ModStatus.PENDING)
        self.client.force_login(self.emp)
        self.assertEqual(
            self.client.get(reverse("communication:detail", args=[art.slug])).status_code, 404)


class CommunicationExtendedAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr_com2", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_com2", password="x", role=Role.EMPLOYE)
        cls.ext = User.objects.create_user("ext_com2", password="x", role=Role.CLIENT)

    def test_press_list_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:press_list")).status_code, 200)

    def test_press_list_redirige_externe(self):
        self.client.force_login(self.ext)
        self.assertEqual(self.client.get(reverse("communication:press_list")).status_code, 302)

    def test_key_messages_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:key_messages")).status_code, 200)

    def test_newsletter_list_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:newsletter_list")).status_code, 200)

    def test_event_projects_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("communication:event_projects")).status_code, 200)

    def test_event_project_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("communication:event_project_create")).status_code, 403)

    def test_event_project_create_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("communication:event_project_create")).status_code, 200)
