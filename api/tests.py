from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from employees.models import Employee


class ApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_api", password="Lpm@2026", role=Role.RH,
                                          first_name="Reg", last_name="RH")
        cls.emp = User.objects.create_user("emp_api", password="Lpm@2026", role=Role.EMPLOYE,
                                           first_name="Em", last_name="P")

    def _token(self, username, password="Lpm@2026"):
        r = self.client.post(reverse("api:token"), {"username": username, "password": password})
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()["token"]

    def test_token_required(self):
        # Sans token → 401/403
        self.assertIn(self.client.get(reverse("api:me")).status_code, (401, 403))

    def test_me_with_token(self):
        tok = self._token("emp_api")
        r = self.client.get(reverse("api:me"), HTTP_AUTHORIZATION=f"Token {tok}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["username"], "emp_api")
        self.assertEqual(r.json()["role"], "EMPLOYE")

    def test_employee_sees_only_self_rh_sees_all(self):
        # Employé : ne voit que sa fiche
        tok_e = self._token("emp_api")
        r = self.client.get("/api/employees/", HTTP_AUTHORIZATION=f"Token {tok_e}")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        results = data["results"] if isinstance(data, dict) else data
        self.assertEqual(len(results), 1)
        # RH : voit plusieurs fiches
        tok_rh = self._token("rh_api")
        r2 = self.client.get("/api/employees/", HTTP_AUTHORIZATION=f"Token {tok_rh}")
        d2 = r2.json()
        res2 = d2["results"] if isinstance(d2, dict) else d2
        self.assertGreaterEqual(len(res2), 2)
