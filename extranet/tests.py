import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from business.models import Client, Quote, QuoteEvent
from extranet.models import ClientRequest, Creative, Project, ProjectFile, Ticket
from messaging.models import allowed_recipients, can_message
from notifications.models import Notification, notify


class ExtranetPortalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ceo = User.objects.create_user("ceo", password="x", role=Role.CEO)
        cls.lead = User.objects.create_user("lead", password="x", role=Role.MANAGER)
        cls.other_mgr = User.objects.create_user("mgr2", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp", password="x", role=Role.EMPLOYE)
        cls.client_u = User.objects.create_user("cli", password="x", role=Role.CLIENT)
        cls.bclient = Client.objects.create(name="ACME", extranet_user=cls.client_u)
        cls.project = Project.objects.create(name="Site web", client=cls.client_u,
                                             internal_lead=cls.lead)
        cls.report = ProjectFile.objects.create(
            project=cls.project, title="Rapport mensuel", direction="TO_CLIENT",
            kind=ProjectFile.Kind.REPORT, file="extranet/r.pdf")
        cls.doc = ProjectFile.objects.create(
            project=cls.project, title="Brief", direction="TO_CLIENT",
            kind=ProjectFile.Kind.DOCUMENT, file="extranet/d.pdf")

    # --- Messaging recipients restriction ---
    def test_external_can_only_message_lead_and_ceo(self):
        ids = set(allowed_recipients(self.client_u).values_list("id", flat=True))
        self.assertIn(self.lead.id, ids)      # responsable du projet
        self.assertIn(self.ceo.id, ids)       # direction
        self.assertNotIn(self.other_mgr.id, ids)  # responsable non lié
        self.assertNotIn(self.emp.id, ids)        # employé lambda
        self.assertTrue(can_message(self.client_u, self.lead))
        self.assertTrue(can_message(self.client_u, self.ceo))
        self.assertFalse(can_message(self.client_u, self.emp))
        self.assertFalse(can_message(self.client_u, self.other_mgr))

    # --- Notification audience ---
    def test_notification_audience_auto(self):
        n_ext = notify(self.client_u, "Hello")
        n_int = notify(self.lead, "Hello")
        self.assertEqual(n_ext.audience, Notification.Audience.EXTERNAL)
        self.assertEqual(n_int.audience, Notification.Audience.INTERNAL)

    def test_notification_list_scoped(self):
        notify(self.client_u, "Externe")
        # bruit interne ne doit pas apparaître pour le client
        Notification.objects.create(recipient=self.client_u, title="Interne",
                                    audience=Notification.Audience.INTERNAL)
        self.client.force_login(self.client_u)
        r = self.client.get(reverse("notifications:list"))
        self.assertContains(r, "Externe")
        self.assertNotContains(r, "Interne")

    # --- Reports page ---
    def test_client_reports_only_reports(self):
        self.client.force_login(self.client_u)
        r = self.client.get(reverse("extranet:reports"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Rapport mensuel")
        self.assertNotContains(r, "Brief")  # un document n'est pas un rapport

    # --- Formulaire projet : listes filtrées par périmètre ---
    def test_project_form_querysets_filtered(self):
        from extranet.forms import ProjectForm
        form = ProjectForm()
        client_ids = set(form.fields["client"].queryset.values_list("id", flat=True))
        lead_ids = set(form.fields["internal_lead"].queryset.values_list("id", flat=True))
        # Client : externes uniquement
        self.assertIn(self.client_u.id, client_ids)
        self.assertNotIn(self.lead.id, client_ids)
        self.assertNotIn(self.ceo.id, client_ids)
        # Chargé LPM : internes uniquement
        self.assertIn(self.lead.id, lead_ids)
        self.assertIn(self.ceo.id, lead_ids)
        self.assertNotIn(self.client_u.id, lead_ids)

    # --- CEO voit tous les projets (comme le super admin) ---
    def test_ceo_sees_all_projects(self):
        Project.objects.create(name="Autre projet", client=self.client_u,
                               internal_lead=self.other_mgr)
        self.client.force_login(self.ceo)
        r = self.client.get(reverse("extranet:home"))
        self.assertContains(r, "Site web")
        self.assertContains(r, "Autre projet")
        self.assertContains(self.client.get(reverse("extranet:progress")), "Autre projet")

    def test_manager_sees_only_own_projects(self):
        self.client.force_login(self.other_mgr)
        r = self.client.get(reverse("extranet:home"))
        self.assertNotContains(r, "Site web")  # piloté par self.lead, pas other_mgr

    # --- Progress & validations reachable ---
    def test_progress_and_validations(self):
        self.client.force_login(self.client_u)
        self.assertEqual(self.client.get(reverse("extranet:progress")).status_code, 200)
        Quote.objects.create(client=self.bclient, title="Devis 1", status=Quote.Status.SENT)
        r = self.client.get(reverse("extranet:validations"))
        self.assertContains(r, "Devis 1")
        self.assertContains(r, "Brief")  # document TO_CLIENT en attente

    # --- Réclamations / tickets ---
    def test_client_creates_ticket_and_lead_responds(self):
        self.client.force_login(self.client_u)
        r = self.client.post(reverse("extranet:tickets"), {
            "kind": "RECLAMATION", "subject": "Souci visuel", "description": "Le logo est flou",
        })
        self.assertEqual(r.status_code, 302)
        t = Ticket.objects.get(subject="Souci visuel")
        self.assertEqual(t.client, self.client_u)
        self.assertTrue(t.reference.startswith("TIC-"))
        # Le CEO (direction) est notifié
        self.assertTrue(Notification.objects.filter(recipient=self.ceo, title__icontains="ticket").exists())
        # Le manager change le statut → le client est notifié
        self.client.force_login(self.ceo)
        self.client.post(reverse("extranet:ticket", args=[t.pk]), {"status": "RESOLVED"})
        t.refresh_from_db()
        self.assertEqual(t.status, "RESOLVED")
        self.assertTrue(Notification.objects.filter(recipient=self.client_u, audience="EXTERNAL").exists())

    def test_employee_cannot_access_tickets(self):
        self.client.force_login(self.emp)
        # employé interne non-manager → redirigé hors de l'extranet
        self.assertEqual(self.client.get(reverse("extranet:tickets")).status_code, 302)

    def test_client_redirige_si_ticket_autre_client(self):
        other = User.objects.create_user("cli2", password="x", role=Role.CLIENT)
        t = Ticket.objects.create(client=other, subject="Privé", description="x")
        self.client.force_login(self.client_u)
        r = self.client.get(reverse("extranet:ticket", args=[t.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertRedirects(r, reverse("extranet:tickets"), fetch_redirect_response=False)

    # --- Demandes ---
    def test_client_submits_request_notifies_direction(self):
        self.client.force_login(self.client_u)
        r = self.client.post(reverse("extranet:requests"), {
            "kind": "CAMPAIGN", "title": "Lancement produit", "details": "Campagne Q3",
        })
        self.assertEqual(r.status_code, 302)
        dem = ClientRequest.objects.get(title="Lancement produit")
        self.assertEqual(dem.status, "SUBMITTED")
        self.assertTrue(Notification.objects.filter(recipient=self.ceo, title__icontains="demande").exists())
        # Un responsable accepte
        self.client.force_login(self.ceo)
        self.client.post(reverse("extranet:request_decide", args=[dem.pk, "accept"]))
        dem.refresh_from_db()
        self.assertEqual(dem.status, "ACCEPTED")

    # --- Téléchargements & galerie accessibles ---
    def test_downloads_and_gallery(self):
        self.client.force_login(self.client_u)
        r = self.client.get(reverse("extranet:downloads"))
        self.assertContains(r, "Rapport mensuel")  # rapport listé
        self.assertEqual(self.client.get(reverse("extranet:gallery")).status_code, 200)
        self.assertEqual(self.client.get(reverse("extranet:campaigns")).status_code, 200)

    # --- Module 2 : devis « demander des modifications » + historique ---
    def test_quote_request_changes_logs_event(self):
        q = Quote.objects.create(client=self.bclient, title="Devis Z",
                                 status=Quote.Status.SENT, owner=self.lead)
        self.client.force_login(self.client_u)
        # Sans commentaire → refusé, reste SENT
        self.client.post(reverse("extranet:client_quote_decide", args=[q.pk, "changes"]), {})
        q.refresh_from_db()
        self.assertEqual(q.status, Quote.Status.SENT)
        # Avec commentaire → statut CHANGES + événement journalisé
        self.client.post(reverse("extranet:client_quote_decide", args=[q.pk, "changes"]),
                         {"comment": "Merci de baisser le tarif de production."})
        q.refresh_from_db()
        self.assertEqual(q.status, Quote.Status.CHANGES)
        ev = QuoteEvent.objects.filter(quote=q, action=QuoteEvent.Action.CHANGES).first()
        self.assertIsNotNone(ev)
        self.assertIn("baisser", ev.comment.lower())
        # Le commercial est notifié
        self.assertTrue(Notification.objects.filter(recipient=self.lead, title__icontains="Devis").exists())

    def test_quote_accept_logs_signed_event(self):
        q = Quote.objects.create(client=self.bclient, title="Devis A",
                                 status=Quote.Status.SENT, owner=self.lead)
        self.client.force_login(self.client_u)
        self.client.post(reverse("extranet:client_quote_decide", args=[q.pk, "accept"]),
                         {"signature": "Jean Client"})
        q.refresh_from_db()
        self.assertEqual(q.status, Quote.Status.SIGNED)
        self.assertTrue(QuoteEvent.objects.filter(quote=q, action=QuoteEvent.Action.SIGNED).exists())

    # --- Module 3 : créations graphiques (versions + validation) ---
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_creative_versions_workflow(self):
        # LPM publie la V1
        self.client.force_login(self.lead)  # internal_lead du projet
        img = SimpleUploadedFile("v1.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        self.client.post(reverse("extranet:creative_create"),
                         {"project": self.project.pk, "title": "Affiche promo", "note": "Première piste", "file": img})
        cr = Creative.objects.get(title="Affiche promo")
        self.assertEqual(cr.versions.count(), 1)
        self.assertEqual(cr.current_version.number, 1)
        # Le client demande des corrections
        self.client.force_login(self.client_u)
        self.client.post(reverse("extranet:creative", args=[cr.pk]), {"decide": "changes"})
        cr.refresh_from_db()
        self.assertEqual(cr.status, Creative.Status.CHANGES)
        self.assertEqual(cr.current_version.status, "CHANGES")
        # LPM publie la V2
        self.client.force_login(self.lead)
        img2 = SimpleUploadedFile("v2.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")
        self.client.post(reverse("extranet:creative", args=[cr.pk]),
                         {"add_version": "1", "file": img2, "note": "Corrigée"})
        cr.refresh_from_db()
        self.assertEqual(cr.versions.count(), 2)
        self.assertEqual(cr.current_version.number, 2)
        self.assertEqual(cr.status, Creative.Status.IN_REVIEW)
        # Le client valide la version finale
        self.client.force_login(self.client_u)
        self.client.post(reverse("extranet:creative", args=[cr.pk]), {"decide": "approve"})
        cr.refresh_from_db()
        self.assertEqual(cr.status, Creative.Status.APPROVED)
        self.assertEqual(cr.current_version.status, "APPROVED")

    def test_employee_cannot_create_creative(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("extranet:creative_create")).status_code, 403)

    # --- Intégration intranet : nav + dashboard selon le rôle ---
    def test_intranet_integration_for_manager(self):
        Ticket.objects.create(client=self.client_u, subject="X", description="y",
                              status=Ticket.Status.OPEN)
        self.client.force_login(self.lead)  # responsable
        dash = self.client.get(reverse("dashboard:home")).content.decode("utf-8", "ignore")
        # Liens de navigation intranet présents
        self.assertIn("/extranet/reclamations", dash)
        self.assertIn("/extranet/demandes", dash)
        self.assertIn("/extranet/creations", dash)
        # Encart « Relation client » sur le tableau de bord
        self.assertIn("Relation client", dash)
        # Accès direct depuis l'intranet (shell intranet)
        r = self.client.get(reverse("extranet:tickets"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "nav-link")  # shell intranet, pas extranet

    def test_intranet_integration_hidden_for_employee(self):
        self.client.force_login(self.emp)
        dash = self.client.get(reverse("dashboard:home")).content.decode("utf-8", "ignore")
        self.assertNotIn("/extranet/reclamations", dash)
        self.assertNotIn("Relation client", dash)
