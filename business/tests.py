from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from business.models import Client, Quote


class CeoValidationTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)

    def test_manager_created_client_pending_then_ceo_validates(self):
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("business:client_create"),
                             {"name": "ACME SARL", "kind": "PROSPECT", "city": "Douala"})
        self.assertEqual(r.status_code, 302)
        c = Client.objects.get(name="ACME SARL")
        self.assertFalse(c.is_validated)
        self.assertEqual(c.owner, self.mgr)
        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(recipient=self.ceo, title__icontains="client").exists())
        self.client.force_login(self.ceo)
        self.client.post(reverse("business:client_validate", args=[c.pk]))
        c.refresh_from_db()
        self.assertTrue(c.is_validated)
        self.assertEqual(c.validated_by, self.ceo)

    def test_ceo_created_client_auto_validated(self):
        self.client.force_login(self.ceo)
        self.client.post(reverse("business:client_create"),
                         {"name": "Beta SARL", "kind": "PROSPECT", "city": "Douala"})
        self.assertTrue(Client.objects.get(name="Beta SARL").is_validated)

    def test_manager_send_quote_requires_ceo(self):
        c = Client.objects.create(name="Gamma", is_validated=True)
        q = Quote.objects.create(client=c, title="Devis X", status=Quote.Status.DRAFT, owner=self.mgr)
        self.client.force_login(self.mgr)
        self.client.get(reverse("business:quote_status", args=[q.pk, "send"]))
        q.refresh_from_db()
        self.assertEqual(q.status, Quote.Status.INTERNAL)

    def test_ceo_send_quote_ok(self):
        c = Client.objects.create(name="Delta", is_validated=True)
        q = Quote.objects.create(client=c, title="Devis Y", status=Quote.Status.DRAFT, owner=self.ceo)
        self.client.force_login(self.ceo)
        self.client.get(reverse("business:quote_status", args=[q.pk, "send"]))
        q.refresh_from_db()
        self.assertEqual(q.status, Quote.Status.SENT)

    def test_executive_page_has_chart_context(self):
        """Le tableau de bord exécutif expose les séries 12 mois pour le graphique."""
        self.client.force_login(self.ceo)
        r = self.client.get(reverse("business:executive"))
        self.assertEqual(r.status_code, 200)
        for key in ("chart_labels", "chart_ca", "chart_enc"):
            self.assertIn(key, r.context)
            self.assertEqual(len(r.context[key]), 12)
        self.assertContains(r, "chart.umd.min.js")
        self.assertContains(r, "caChart")
