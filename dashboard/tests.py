from django.test import TestCase
from django.urls import reverse


class PWATest(TestCase):
    """Endpoints PWA : manifeste + service worker accessibles sans authentification."""

    def test_manifest_ok(self):
        r = self.client.get(reverse("dashboard:manifest"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/json")
        data = r.json()
        self.assertEqual(data["short_name"], "LPM")
        self.assertTrue(data["icons"])

    def test_service_worker_ok(self):
        r = self.client.get(reverse("dashboard:service_worker"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("javascript", r["Content-Type"])
        self.assertEqual(r["Service-Worker-Allowed"], "/")
        self.assertIn("addEventListener", r.content.decode())
