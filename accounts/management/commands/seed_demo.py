"""Peuple la base avec des données de démonstration réalistes (LPM Consulting Group).

Usage :
    python manage.py seed_demo

Crée : un administrateur, des départements, des employés (inspirés de l'organigramme),
des types de congé conformes au droit camerounais, des actualités, des tâches,
un espace extranet client, et quelques notifications.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import Role, User
from communication.models import Event, News
from conges.models import LeaveRequest, LeaveType
from disciplinary.models import DisciplinaryRecord
from employees.models import Department, Employee, Position
from extranet.models import ExtranetMessage, Project, ProjectFile
from notifications.models import notify
from tasks.models import Task

PWD = "Lpm@2026"


class Command(BaseCommand):
    help = "Crée un jeu de données de démonstration pour LPM Consulting Group."

    def handle(self, *args, **opts):
        self.stdout.write("Peuplement en cours…")
        self._leave_types()
        admin = self._admin()
        depts = self._departments()
        people = self._people(depts)
        self._news(admin)
        self._events()
        self._tasks(people)
        self._leaves(people)
        self._disciplinary(people)
        self._extranet(people)
        self._messages(people)
        self._business(people)
        self._projects(people)
        self._marketing(people)
        self._chat(people)
        self._hr(people)
        self._office()
        self._repair_profiles()
        self.stdout.write(self.style.SUCCESS(
            f"\n[OK] Termine. Comptes crees (mot de passe : {PWD}) :\n"
            "   - admin        : Administrateur principal (acces total)\n"
            "   - b.kell       : Directeur General / CEO (super-admin secondaire)\n"
            "   - r.ndjigue    : Responsable RH\n"
            "   - p.bosseck    : Responsable de service (Finances)\n"
            "   - d.saksak     : Employe\n"
            "   - s.mballa     : Stagiaire (meme interface qu'un employe)\n"
            "   - client.kribi : Client (extranet)\n"
        ))

    # ------------------------------------------------------------------ #
    def _leave_types(self):
        data = [
            ("Congé annuel payé", "ANNUEL", True, True, 18, "Art. 89 Code du Travail", "#0073DE"),
            ("Congé maladie", "MALADIE", True, False, 0, "Certificat médical", "#f59e0b"),
            ("Congé de maternité", "MATERNITE", True, False, 98, "Art. 84 — 14 semaines", "#ec4899"),
            ("Congé de paternité", "PATERNITE", True, False, 3, "Convention collective", "#6366f1"),
            ("Permission exceptionnelle", "EXCEPT", True, False, 0, "Événement familial", "#10b981"),
            ("Congé sans solde", "SANS_SOLDE", False, False, 0, "Accord employeur", "#64748b"),
        ]
        for name, code, paid, deduct, days, ref, color in data:
            LeaveType.objects.get_or_create(code=code, defaults=dict(
                name=name, is_paid=paid, deducts_balance=deduct,
                default_days=days, legal_reference=ref, color=color))

    def _admin(self):
        # Super administrateur : accès total + peut endosser tous les rôles internes.
        all_roles = "CEO,RH,MANAGER,EMPLOYE"
        admin, created = User.objects.get_or_create(
            username="admin",
            defaults=dict(first_name="Super", last_name="Admin", email="admin@lpmconsulting.cm",
                          role=Role.ADMIN, is_staff=True, is_superuser=True,
                          secondary_roles=all_roles, phone="+237 6 99 00 00 00"))
        if created:
            admin.set_password(PWD)
            admin.save()
        # Garantir le statut super admin + les rôles endossables.
        changed = False
        if admin.role != Role.ADMIN or not admin.is_superuser or not admin.is_staff:
            admin.role = Role.ADMIN; admin.is_superuser = True; admin.is_staff = True; changed = True
        if admin.secondary_roles != all_roles:
            admin.secondary_roles = all_roles; changed = True
        if changed:
            admin.save()
        return admin

    def _office(self):
        from hr.models import OfficeLocation
        loc = OfficeLocation.objects.first() or OfficeLocation()
        loc.name = "Siège LPM Consulting Group — Douala"
        loc.lat = 4.07424
        loc.lng = 9.71709
        loc.radius_m = 500
        loc.save()

    def _repair_profiles(self):
        """Garantit une fiche employé à chaque compte interne (hors super admin)."""
        from accounts.models import INTRANET_ROLES
        n = 0
        for u in User.objects.filter(role__in=INTRANET_ROLES).exclude(role=Role.ADMIN):
            if not Employee.objects.filter(user=u).exists():
                Employee.objects.create(user=u)  # matricule auto (séquence croissante)
                n += 1
        if n:
            self.stdout.write(f"  {n} fiche(s) employe creee(s) pour des comptes existants.")

    def _departments(self):
        names = {
            "DG": ("Direction Générale", "DG"),
            "RH": ("Ressources Humaines", "RH"),
            "FIN": ("Direction des Opérations & Finances", "DOF"),
            "MKT": ("Marketing & Communication", "MKT"),
            "COM": ("Commercial", "COM"),
            "OPS": ("Production & Événementiel", "OPS"),
        }
        out = {}
        for key, (name, code) in names.items():
            out[key], _ = Department.objects.get_or_create(name=name, defaults={"code": code})
        return out

    def _mk(self, username, first, last, role, dept, title, hire, manager=None, gender="M",
            contract=None, bday=None):
        user, created = User.objects.get_or_create(
            username=username,
            defaults=dict(first_name=first, last_name=last, role=role,
                          email=f"{username}@lpmconsulting.cm", phone="+237 6 "))
        if created:
            user.set_password(PWD)
            user.save()
        elif user.role != role:  # sync du rôle si le compte existait déjà
            user.role = role
            user.save(update_fields=["role"])
        pos, _ = Position.objects.get_or_create(title=title, department=dept)
        # La fiche peut déjà exister (créée par le signal post_save) : on la complète.
        # Le matricule est auto-attribué par Employee.save() (séquence croissante).
        emp, _ = Employee.objects.get_or_create(user=user)
        emp.hire_date = hire
        emp.manager = manager
        emp.gender = gender
        emp.contract_type = contract or Employee.Contract.CDI
        emp.city = "Douala"
        if bday:  # (jour, mois) — année sentinelle, on ne conserve que jour/mois
            emp.birth_date = date(2000, bday[1], bday[0])
        emp.save()
        # Relations multiples (département(s) / poste(s)).
        emp.departments.set([dept])
        emp.positions.set([pos])
        return emp

    def _people(self, d):
        p = {}
        today = date.today()
        p["ceo"] = self._mk("b.kell", "Boris", "KELL", Role.CEO, d["DG"],
                            "Directeur Général (CEO)", today - timedelta(days=2600), bday=(12, 6))
        p["rh"] = self._mk("r.ndjigue", "Régine", "NDJIGUE", Role.RH, d["RH"],
                           "Responsable RH", today - timedelta(days=1500), p["ceo"], "F", bday=(25, 6))
        p["fin"] = self._mk("p.bosseck", "Pascal", "BOSSECK", Role.MANAGER, d["FIN"],
                            "Directeur des Opérations & Finances", today - timedelta(days=1800), p["ceo"], bday=(2, 7))
        p["mkt"] = self._mk("f.tsago", "Frank", "TSAGO", Role.MANAGER, d["MKT"],
                            "Responsable Marketing", today - timedelta(days=1200), p["ceo"], bday=(18, 11))
        p["e1"] = self._mk("d.saksak", "Daniel", "SAKSAK", Role.EMPLOYE, d["MKT"],
                           "Chef de projet", today - timedelta(days=700), p["mkt"], bday=(9, 6))
        p["e2"] = self._mk("g.ndedi", "Gaëlle", "NDEDI", Role.EMPLOYE, d["COM"],
                           "Chargée de clientèle", today - timedelta(days=400), p["fin"], "F", bday=(28, 6))
        p["e3"] = self._mk("h.linda", "Linda", "HERVÉ", Role.EMPLOYE, d["OPS"],
                           "Coordinatrice événementiel", today - timedelta(days=300), p["mkt"], "F", bday=(20, 6))
        p["stg"] = self._mk("s.mballa", "Steve", "MBALLA", Role.STAGIAIRE, d["MKT"],
                            "Stagiaire Marketing", today - timedelta(days=60), p["mkt"],
                            contract=Employee.Contract.STAGE, bday=(15, 6))
        # Exemple de multi-rôles : Pascal BOSSECK est Responsable ET RH (peut basculer).
        fin_user = p["fin"].user
        if fin_user.secondary_roles != "RH":
            fin_user.secondary_roles = "RH"
            fin_user.save(update_fields=["secondary_roles"])
        # Responsables de département
        d["RH"].manager = p["rh"].user; d["RH"].save()
        d["FIN"].manager = p["fin"].user; d["FIN"].save()
        d["MKT"].manager = p["mkt"].user; d["MKT"].save()
        d["DG"].manager = p["ceo"].user; d["DG"].save()
        # Client extranet
        client, created = User.objects.get_or_create(
            username="client.kribi",
            defaults=dict(first_name="Jean", last_name="MBALLA", role=Role.CLIENT,
                          email="contact@kribiglobal.cm", organization="Kribi Global SARL"))
        if created:
            client.set_password(PWD)
            client.save()
        p["client"] = client
        return p

    def _news(self, admin):
        if News.objects.exists():
            return
        News.objects.create(
            title="Lancement officiel de l'intranet LPM Consulting Group",
            category=News.Category.ALERT, is_pinned=True, author=admin,
            summary="Notre nouvelle plateforme digitale est en ligne !",
            content="Chers collaborateurs,\n\nNous avons le plaisir de vous annoncer le lancement "
                    "de notre intranet. Vous pouvez désormais consulter les actualités, gérer vos "
                    "congés, accéder aux documents et collaborer plus efficacement.\n\nBonne découverte !")
        News.objects.create(
            title="Note RH : campagne de congés annuels 2026",
            category=News.Category.RH, author=admin,
            summary="Planifiez vos congés via la plateforme.",
            content="Le service RH invite l'ensemble du personnel à soumettre les demandes de congés "
                    "annuels directement depuis le module « Congés ». Pour rappel, le droit légal est "
                    "de 1,5 jour ouvrable par mois de service (Code du Travail camerounais).")
        News.objects.create(
            title="Séminaire d'équipe — Kribi", category=News.Category.EVENT, author=admin,
            summary="Retour en images sur notre dernier séminaire.",
            content="Merci à toutes et à tous pour votre engagement lors du séminaire de cohésion.")

    def _events(self):
        if Event.objects.exists():
            return
        now = timezone.now()
        Event.objects.create(title="Réunion mensuelle de direction", kind=Event.Kind.MEETING,
                             start=now + timedelta(days=3, hours=9), location="Salle de conférence")
        Event.objects.create(title="Point hebdomadaire Marketing", kind=Event.Kind.MEETING,
                             start=now + timedelta(days=1, hours=10), location="Open space")
        Event.objects.create(title="Clôture comptable mensuelle", kind=Event.Kind.REMINDER,
                             start=now + timedelta(days=7))

    def _tasks(self, p):
        if Task.objects.exists():
            return
        Task.objects.create(title="Préparer le rapport d'activité Q2", assigned_to=p["e1"].user,
                           created_by=p["mkt"].user, priority=Task.Priority.HIGH,
                           due_date=date.today() + timedelta(days=5))
        Task.objects.create(title="Mettre à jour la base clients", assigned_to=p["e2"].user,
                           created_by=p["fin"].user, status=Task.Status.IN_PROGRESS)
        Task.objects.create(title="Valider le budget événementiel", assigned_to=p["mkt"].user,
                           created_by=p["ceo"].user, priority=Task.Priority.URGENT,
                           due_date=date.today() - timedelta(days=1))

    def _leaves(self, p):
        if LeaveRequest.objects.exists():
            return
        annuel = LeaveType.objects.get(code="ANNUEL")
        # Demande d'un employé → 1er validateur : son responsable (Frank TSAGO).
        LeaveRequest.objects.create(
            employee=p["e1"], leave_type=annuel,
            start_date=date.today() + timedelta(days=10),
            end_date=date.today() + timedelta(days=17),
            reason="Congé annuel — repos familial",
            status=LeaveRequest.Status.PENDING, current_level=0)
        notify(p["mkt"].user, "Congé à valider",
               f"{p['e1'].full_name} a soumis une demande (niveau Responsable).")

    def _disciplinary(self, p):
        if DisciplinaryRecord.objects.exists():
            return
        DisciplinaryRecord.objects.create(
            employee=p["e3"], sanction_type=DisciplinaryRecord.SanctionType.WARNING,
            status=DisciplinaryRecord.Status.NOTIFIED,
            facts="Retards répétés non justifiés constatés sur le mois écoulé.",
            fault_date=date.today() - timedelta(days=15),
            notified_at=date.today() - timedelta(days=10), decided_by=p["rh"].user)

    def _messages(self, p):
        from messaging.models import Message
        if Message.objects.exists():
            return
        pairs = [
            (p["rh"].user, p["e1"].user, "Bonjour Daniel, merci de transmettre ton planning de congés cette semaine."),
            (p["e1"].user, p["rh"].user, "Bonjour, c'est noté. Je vous l'envoie aujourd'hui."),
            (p["fin"].user, p["ceo"].user, "Le budget du projet NESCAFÉ est validé de notre côté."),
        ]
        for sender, recipient, body in pairs:
            Message.objects.create(sender=sender, recipient=recipient, body=body)

    def _business(self, p):
        from business.models import (
            Client as BClient, Invoice, Opportunity, Payment, Quote,
        )
        if BClient.objects.exists():
            return
        c1 = BClient.objects.create(
            name="Kribi Global SARL", kind=BClient.Kind.CLIENT, contact_name="Jean MBALLA",
            email="contact@kribiglobal.cm", phone="+237 6 70 00 00 00", sector="Distribution",
            owner=p["mkt"].user, extranet_user=p["client"])
        c2 = BClient.objects.create(
            name="Guinness Cameroun", kind=BClient.Kind.PROSPECT, contact_name="Service Marketing",
            phone="+237 6 99 11 22 33", sector="Brasserie", owner=p["fin"].user)
        c3 = BClient.objects.create(
            name="MTN Cameroon", kind=BClient.Kind.CLIENT, contact_name="Direction Marketing",
            sector="Télécom", owner=p["mkt"].user)
        Opportunity.objects.create(client=c2, title="Campagne lancement Guinness Smooth",
            amount=12000000, stage=Opportunity.Stage.PROPOSAL, probability=60,
            owner=p["fin"].user)
        Opportunity.objects.create(client=c3, title="Activation terrain MTN MoMo",
            amount=8500000, stage=Opportunity.Stage.NEGOTIATION, probability=75, owner=p["mkt"].user)
        # Devis signé pour Kribi Global
        q = Quote.objects.create(client=c1, title="Campagne d'activation NESCAFÉ 3en1",
            status=Quote.Status.SIGNED, owner=p["mkt"].user)
        q.lines.create(designation="Conception créative & déclinaisons", quantity=1, unit_price=1500000)
        q.lines.create(designation="Activation terrain (10 sites)", quantity=10, unit_price=350000)
        q.lines.create(designation="Reporting & médias", quantity=1, unit_price=800000)
        # Facture partiellement payée
        inv = Invoice.objects.create(kind=Invoice.Kind.CLIENT, client=c1, quote=q,
            title="Campagne NESCAFÉ 3en1 — Acompte", status=Invoice.Status.SENT,
            due_date=date.today() + timedelta(days=15), created_by=p["fin"].user)
        inv.lines.create(designation="Acompte 50% campagne NESCAFÉ", quantity=1, unit_price=2900000)
        Payment.objects.create(invoice=inv, amount=1500000, method=Payment.Method.MOMO,
            reference="MOMO-0099283", recorded_by=p["fin"].user)
        inv.refresh_status()
        # Devis ENVOYÉ au client (en attente de sa réponse — testable côté extranet)
        q2 = Quote.objects.create(client=c1, title="Extension digitale Q3",
            status=Quote.Status.SENT, owner=p["mkt"].user,
            valid_until=date.today() + timedelta(days=20))
        q2.lines.create(designation="Community management (3 mois)", quantity=3, unit_price=450000)
        q2.lines.create(designation="Production de contenus", quantity=1, unit_price=900000)

    def _projects(self, p):
        from projects.models import Phase, Project as Proj
        from business.models import Client as BClient
        if Proj.objects.exists():
            return
        kribi = BClient.objects.filter(name="Kribi Global SARL").first()
        guinness = BClient.objects.filter(name="Guinness Cameroun").first()
        # Campagne marketing
        pr1 = Proj.objects.create(
            name="Campagne NESCAFÉ 3en1 — Activation", kind=Proj.Kind.CAMPAIGN,
            client=kribi, manager=p["mkt"].user, status=Proj.Status.ACTIVE,
            description="Activation terrain et événementielle pour le lancement régional.",
            start_date=date.today() - timedelta(days=20), deadline=date.today() + timedelta(days=25),
            budget=5000000, spent=2100000)
        pr1.team.set([p["e1"].user, p["e3"].user])
        # Avancer quelques phases
        for ph in pr1.phases.all()[:2]:
            ph.status = Phase.Status.DONE; ph.save()
        # Événement
        pr2 = Proj.objects.create(
            name="Lancement Guinness Smooth — Roadshow", kind=Proj.Kind.EVENT,
            client=guinness, manager=p["e3"].user, status=Proj.Status.PLANNED,
            description="Roadshow de lancement dans 3 villes.",
            start_date=date.today() + timedelta(days=10), deadline=date.today() + timedelta(days=40),
            budget=15000000, spent=0,
            location="Douala, Yaoundé, Bafoussam", event_date=date.today() + timedelta(days=30),
            providers="Sonorisation : SonoPro · Sécurité : SafeGuard · Traiteur : Délices",
            attendees_expected=2000)
        pr2.team.set([p["e1"].user, p["e2"].user])

    def _marketing(self, p):
        from marketing.models import Campaign, Post
        from business.models import Client as BClient
        if Campaign.objects.exists():
            return
        kribi = BClient.objects.filter(name="Kribi Global SARL").first()
        camp = Campaign.objects.create(
            name="NESCAFÉ 3en1 — Digital & Terrain", brand=kribi, channel=Campaign.Channel.MIX,
            status=Campaign.Status.ACTIVE, objectives="Notoriété + drive-to-store sur Douala/Yaoundé.",
            budget=3000000, start_date=date.today() - timedelta(days=10),
            end_date=date.today() + timedelta(days=20), manager=p["mkt"].user,
            target_reach=500000, actual_reach=210000, leads=320)
        now = timezone.now()
        Post.objects.create(brand=kribi, campaign=camp, platform=Post.Platform.INSTAGRAM,
            title="Teaser NESCAFÉ 3en1", content="Bientôt disponible ! ☕", scheduled_at=now + timedelta(days=1),
            status=Post.Status.PENDING, author=p["e1"].user)
        Post.objects.create(brand=kribi, campaign=camp, platform=Post.Platform.FACEBOOK,
            title="Jeu concours NESCAFÉ", content="Gagnez des lots !", scheduled_at=now + timedelta(days=3),
            status=Post.Status.APPROVED, author=p["e1"].user, validator=p["mkt"].user)
        Post.objects.create(brand=kribi, campaign=camp, platform=Post.Platform.WHATSAPP,
            title="Diffusion catalogue", content="Catalogue produits", scheduled_at=now - timedelta(days=2),
            status=Post.Status.PUBLISHED, author=p["e3"].user, validator=p["mkt"].user)

    def _chat(self, p):
        from messaging.models import ChatGroup, GroupMessage, get_general_group
        general = get_general_group()
        if not general.group_messages.exists():
            GroupMessage.objects.create(group=general, sender=p["ceo"].user,
                body="Bienvenue à toutes et à tous sur le canal général de LPM Consulting ! 🎉")
            GroupMessage.objects.create(group=general, sender=p["rh"].user,
                body="Pensez à mettre à jour vos fiches de profil. Merci !")
        if not ChatGroup.objects.filter(is_general=False).exists():
            grp = ChatGroup.objects.create(name="Équipe Marketing", description="Coordination des campagnes",
                created_by=p["mkt"].user)
            grp.members.add(p["mkt"].user, p["e1"].user, p["e3"].user)
            GroupMessage.objects.create(group=grp, sender=p["mkt"].user,
                body="On cale le planning de la campagne NESCAFÉ cet après-midi ?")
            GroupMessage.objects.create(group=grp, sender=p["e1"].user,
                body="Oui, je prépare les visuels d'ici 14h.")

    def _hr(self, p):
        from hr.models import (
            Attendance, Candidate, Contract, Evaluation, Interview, JobOpening,
            Mission, Objective,
        )
        from django.utils import timezone as tz
        if Contract.objects.exists():
            return
        # Contrats
        for emp in [p["e1"], p["e2"], p["e3"], p["mkt"], p["fin"]]:
            Contract.objects.create(
                employee=emp, type=Contract.Type.CDI,
                title=emp.position.title if emp.position else "",
                start_date=emp.hire_date, salary=350000, is_active=True)
        # Présences du jour
        now = tz.now()
        Attendance.objects.get_or_create(employee=p["e1"], date=tz.localdate(),
            defaults=dict(check_in=now - timedelta(hours=3), status=Attendance.Status.PRESENT))
        Attendance.objects.get_or_create(employee=p["e2"], date=tz.localdate(),
            defaults=dict(check_in=now - timedelta(hours=2, minutes=40), status=Attendance.Status.LATE))
        # Mission en cours (déplacement professionnel) — enregistrée par la RH.
        Mission.objects.create(
            employee=p["e3"], start_date=tz.localdate() - timedelta(days=1),
            end_date=tz.localdate() + timedelta(days=2), destination="Yaoundé",
            objet="Coordination événement client sur site.", created_by=p["rh"].user)
        # Recrutement
        opening = JobOpening.objects.create(title="Chargé(e) de communication digitale",
            description="Gestion des réseaux sociaux et campagnes digitales.", positions=1,
            created_by=p["rh"].user)
        cand = Candidate.objects.create(opening=opening, full_name="Aïcha NANA",
            email="aicha.nana@email.cm", phone="+237 6 70 11 22 33",
            status=Candidate.Status.INTERVIEW, rating=4)
        Candidate.objects.create(opening=opening, full_name="Eric FOTSO",
            email="eric.fotso@email.cm", status=Candidate.Status.NEW)
        Interview.objects.create(candidate=cand, scheduled_at=now + timedelta(days=2),
            interviewer=p["mkt"].user, mode="Présentiel", recommendation=Interview.Reco.FAVORABLE,
            feedback="Bon profil, maîtrise des outils.")
        # Évaluation
        ev = Evaluation.objects.create(employee=p["e1"], period="Année 2026 — S1",
            evaluator=p["mkt"].user, status=Evaluation.Status.SUBMITTED,
            comment="Très bon trimestre, en progression sur la gestion de projet.")
        Objective.objects.create(evaluation=ev, label="Livraison des campagnes dans les délais",
            kpi="% campagnes à l'heure", weight=40, rating=85)
        Objective.objects.create(evaluation=ev, label="Satisfaction client",
            kpi="Note moyenne /5", weight=30, rating=80)
        Objective.objects.create(evaluation=ev, label="Montée en compétences",
            kpi="Formations suivies", weight=30, rating=70)

    def _extranet(self, p):
        proj, created = Project.objects.get_or_create(
            reference="LPM-2026-014",
            defaults=dict(
                name="Lancement produit NESCAFÉ 3en1",
                client=p["client"], internal_lead=p["mkt"].user,
                description="Campagne d'activation terrain et événementielle pour le lancement régional.",
                status=Project.Status.ACTIVE, progress=65,
                start_date=date.today() - timedelta(days=30),
                deadline=date.today() + timedelta(days=20)))
        if created:
            ExtranetMessage.objects.create(project=proj, sender=p["mkt"].user,
                body="Bonjour, voici le planning prévisionnel de la campagne. À votre disposition.")
            ExtranetMessage.objects.create(project=proj, sender=p["client"],
                body="Merci, le planning nous convient. Nous validons le budget.")
        # Un rapport (consultable/téléchargeable) et un document à valider.
        ProjectFile.objects.get_or_create(
            project=proj, title="Rapport d'activité — semaine 3",
            defaults=dict(direction=ProjectFile.Direction.TO_CLIENT,
                          kind=ProjectFile.Kind.REPORT, uploaded_by=p["mkt"].user,
                          file="extranet/demo/rapport-s3.pdf"))
        ProjectFile.objects.get_or_create(
            project=proj, title="Maquette visuelle à valider",
            defaults=dict(direction=ProjectFile.Direction.TO_CLIENT,
                          kind=ProjectFile.Kind.DOCUMENT, uploaded_by=p["mkt"].user,
                          validation=ProjectFile.Validation.PENDING,
                          file="extranet/demo/maquette.pdf"))
        if created:
            notify(p["client"], "Bienvenue sur l'extranet LPM",
                   "Votre espace projet est désormais accessible.")
        # Réclamation et demande de démo (modules tickets & demandes).
        from extranet.models import ClientRequest, Ticket
        Ticket.objects.get_or_create(
            client=p["client"], subject="Couleur du logo sur l'affiche",
            defaults=dict(kind=Ticket.Kind.RECLAMATION, project=proj,
                          description="La teinte du logo diffère de notre charte sur l'affiche v1.",
                          status=Ticket.Status.IN_PROGRESS, assigned_to=p["mkt"].user))
        ClientRequest.objects.get_or_create(
            client=p["client"], title="Activation pour la fête des mères",
            defaults=dict(kind=ClientRequest.Kind.EVENT,
                          details="Animation en grande surface sur Douala, budget ~3M, mi-mai.",
                          budget=3000000, status=ClientRequest.Status.SUBMITTED))
        # Création graphique de démo avec deux versions (V1 corrigée → V2 en revue).
        from extranet.models import Creative, CreativeVersion
        crea, c_created = Creative.objects.get_or_create(
            project=proj, title="Affiche NESCAFÉ 3en1",
            defaults=dict(status=Creative.Status.IN_REVIEW, created_by=p["mkt"].user))
        if c_created:
            CreativeVersion.objects.create(
                creative=crea, number=1, file="creatives/demo/affiche-v1.png",
                note="Première proposition", status=CreativeVersion.Status.CHANGES,
                uploaded_by=p["mkt"].user)
            CreativeVersion.objects.create(
                creative=crea, number=2, file="creatives/demo/affiche-v2.png",
                note="Couleurs corrigées", status=CreativeVersion.Status.PENDING,
                uploaded_by=p["mkt"].user)
