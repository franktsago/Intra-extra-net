from django.test import TestCase

from accounts.models import Role, User
from documents.models import Document
from employees.models import Employee


class DocumentTeamVisibilityTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.mgr = User.objects.create_user("mgr", password="x", role=Role.MANAGER)
        cls.member = User.objects.create_user("member", password="x", role=Role.EMPLOYE)
        cls.other = User.objects.create_user("other", password="x", role=Role.EMPLOYE)
        cls.rh = User.objects.create_user("rh", password="x", role=Role.RH)
        emp_member = Employee.objects.get(user=cls.member)
        emp_member.manager = Employee.objects.get(user=cls.mgr)
        emp_member.save()
        cls.doc = Document.objects.create(
            title="Note équipe", file="documents/x.pdf",
            visibility=Document.Visibility.TEAM, team_owner=cls.mgr, uploaded_by=cls.mgr)

    def test_team_doc_visibility(self):
        self.assertTrue(self.doc.can_view(self.mgr))      # propriétaire
        self.assertTrue(self.doc.can_view(self.member))   # membre de l'équipe
        self.assertTrue(self.doc.can_view(self.rh))       # RH/direction
        self.assertFalse(self.doc.can_view(self.other))   # hors équipe


class ConfidentialDocumentTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rh = User.objects.create_user("rh_c", password="x", role=Role.RH)
        cls.mgr = User.objects.create_user("mgr_c", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_c", password="x", role=Role.EMPLOYE)
        cls.doc = Document.objects.create(
            title="Stratégie 2027", file="documents/secret.pdf",
            visibility=Document.Visibility.ALL, is_confidential=True, uploaded_by=cls.rh)

    def test_read_inline_allowed(self):
        from django.urls import reverse
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("documents:view", args=[self.doc.pk])).status_code, 200)

    def test_download_blocked_for_confidential(self):
        from django.urls import reverse
        self.client.force_login(self.emp)
        r = self.client.get(reverse("documents:download", args=[self.doc.pk]))
        self.assertEqual(r.status_code, 302)  # redirigé vers la lecture, pas de fichier

    def test_only_rh_can_mark_confidential(self):
        from documents.forms import DocumentForm
        self.assertIn("is_confidential", DocumentForm(viewer=self.rh).fields)
        self.assertNotIn("is_confidential", DocumentForm(viewer=self.mgr).fields)

    def test_manager_cannot_delete_confidential(self):
        from django.urls import reverse
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("documents:delete", args=[self.doc.pk]))
        self.assertTrue(Document.objects.filter(pk=self.doc.pk).exists())  # bloqué
        # RH peut supprimer
        self.client.force_login(self.rh)
        self.client.post(reverse("documents:delete", args=[self.doc.pk]))
        self.assertFalse(Document.objects.filter(pk=self.doc.pk).exists())


class DocumentSharingTest(TestCase):
    """Partage ciblé par un employé : collègues, responsable, ou les deux."""

    @classmethod
    def setUpTestData(cls):
        from employees.models import Department
        dep = Department.objects.create(name="Marketing", code="MKT")
        cls.mgr = User.objects.create_user("dshare_mgr", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("dshare_emp", password="x", role=Role.EMPLOYE)
        cls.colleague = User.objects.create_user("dshare_col", password="x", role=Role.EMPLOYE)
        cls.outsider = User.objects.create_user("dshare_out", password="x", role=Role.EMPLOYE)
        Employee.objects.get(user=cls.emp).departments.set([dep])
        Employee.objects.get(user=cls.colleague).departments.set([dep])
        e = Employee.objects.get(user=cls.emp)
        e.manager = Employee.objects.get(user=cls.mgr)
        e.save()

    def _doc(self, vis):
        return Document.objects.create(title="Rendu", file="documents/x.txt",
                                       visibility=vis, uploaded_by=self.emp)

    def test_for_my_manager(self):
        d = self._doc("MY_MANAGER")
        self.assertTrue(d.can_view(self.mgr))
        self.assertTrue(d.can_view(self.emp))
        self.assertFalse(d.can_view(self.colleague))
        self.assertFalse(d.can_view(self.outsider))

    def test_for_colleagues(self):
        d = self._doc("COLLEAGUES")
        self.assertTrue(d.can_view(self.colleague))
        self.assertFalse(d.can_view(self.outsider))

    def test_for_both(self):
        d = self._doc("COLL_MGR")
        self.assertTrue(d.can_view(self.mgr))
        self.assertTrue(d.can_view(self.colleague))
        self.assertFalse(d.can_view(self.outsider))

    def test_employee_can_open_upload(self):
        from django.urls import reverse
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("documents:upload")).status_code, 200)
