from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from notifications.models import Notification


class BroadcastTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.client_u = User.objects.create_user("cli", password="x", role=Role.CLIENT)

    def test_broadcast_to_staff_only(self):
        self.client.force_login(self.rh)
        r = self.client.post(reverse("notifications:broadcast"), {
            "title": "Réunion", "message": "Lundi 9h", "target": "INTERNAL",
            "level": "INFO",
        })
        self.assertEqual(r.status_code, 302)
        # L'employé (interne) reçoit une notif intranet ; le client non.
        n_emp = Notification.objects.filter(recipient=self.emp)
        self.assertEqual(n_emp.count(), 1)
        self.assertEqual(n_emp.first().audience, Notification.Audience.INTERNAL)
        self.assertFalse(Notification.objects.filter(recipient=self.client_u).exists())

    def test_broadcast_to_clients_only(self):
        self.client.force_login(self.rh)
        self.client.post(reverse("notifications:broadcast"), {
            "title": "Maintenance", "message": "Samedi", "target": "EXTERNAL", "level": "INFO",
        })
        n_cli = Notification.objects.filter(recipient=self.client_u)
        self.assertEqual(n_cli.count(), 1)
        self.assertEqual(n_cli.first().audience, Notification.Audience.EXTERNAL)
        self.assertFalse(Notification.objects.filter(recipient=self.emp).exists())

    def test_broadcast_both_and_role_refine(self):
        self.client.force_login(self.rh)
        # Affinage : seulement les employés (intranet), pas les clients
        self.client.post(reverse("notifications:broadcast"), {
            "title": "Note", "message": "x", "target": "BOTH", "level": "INFO",
            "roles": ["EMPLOYE"],
        })
        self.assertTrue(Notification.objects.filter(recipient=self.emp).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.client_u).exists())

    def test_employee_cannot_broadcast(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("notifications:broadcast")).status_code, 403)


class NotificationFeedTest(TestCase):
    """Flux JSON temps réel : nouvelles notifications après un id + compteur."""

    def test_feed_returns_new_after_id(self):
        import json
        u = User.objects.create_user("feed_u", password="x", role=Role.EMPLOYE)
        n1 = Notification.objects.create(recipient=u, title="Un",
                                         audience=Notification.Audience.INTERNAL)
        n2 = Notification.objects.create(recipient=u, title="Deux",
                                         audience=Notification.Audience.INTERNAL)
        self.client.force_login(u)
        d = json.loads(self.client.get(reverse("notifications:feed") + "?after=%d" % n1.id).content)
        self.assertEqual(d["unread"], 2)
        self.assertEqual(d["last_id"], n2.id)
        titles = [x["title"] for x in d["new"]]
        self.assertIn("Deux", titles)
        self.assertNotIn("Un", titles)   # déjà vue (≤ after)

    def test_feed_audience_isolated(self):
        import json
        cli = User.objects.create_user("feed_cli", password="x", role=Role.CLIENT)
        Notification.objects.create(recipient=cli, title="Interne par erreur",
                                    audience=Notification.Audience.INTERNAL)
        self.client.force_login(cli)
        d = json.loads(self.client.get(reverse("notifications:feed")).content)
        self.assertEqual(d["unread"], 0)   # un externe ne voit pas l'audience interne
