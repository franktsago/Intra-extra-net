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
        # Nouveaux modules
        self._stock(people)
        self._rse(people)
        self._marketing_digital(people)
        self._communication_ext(people)
        self._hr_onboarding(people)
        self._projects_ext(people)
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
        from employees.models import Department
        if Proj.objects.exists():
            return
        kribi = BClient.objects.filter(name="Kribi Global SARL").first()
        guinness = BClient.objects.filter(name="Guinness Cameroun").first()
        # Chaque projet est rattaché au département qui le pilote.
        dep_mkt = Department.objects.filter(code="MKT").first()
        dep_ops = Department.objects.filter(code="OPS").first()
        # Campagne marketing (département Marketing)
        pr1 = Proj.objects.create(
            name="Campagne NESCAFÉ 3en1 — Activation", kind=Proj.Kind.CAMPAIGN,
            department=dep_mkt,
            client=kribi, manager=p["mkt"].user, status=Proj.Status.ACTIVE,
            description="Activation terrain et événementielle pour le lancement régional.",
            start_date=date.today() - timedelta(days=20), deadline=date.today() + timedelta(days=25),
            budget=5000000, spent=2100000)
        pr1.team.set([p["e1"].user, p["e3"].user])
        # Avancer quelques phases
        for ph in pr1.phases.all()[:2]:
            ph.status = Phase.Status.DONE; ph.save()
        # Événement (département Production & Événementiel)
        pr2 = Proj.objects.create(
            name="Lancement Guinness Smooth — Roadshow", kind=Proj.Kind.EVENT,
            department=dep_ops,
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

    # ================================================================ STOCK ===
    def _stock(self, p):
        from stock.models import (
            BorrowRequest, MaintenanceItem, PostEventReconciliation,
            PurchaseOrder, StockItem, StockMovement, StockSupplier,
        )
        if StockItem.objects.exists():
            return
        today = date.today()

        # ---- Fournisseurs ----
        sup1, _ = StockSupplier.objects.get_or_create(
            name="Bureau Express Cameroun",
            defaults=dict(contact_name="Armand FOUDA",
                          email="armand@bureau-express.cm", phone="+237 6 55 11 22 33",
                          address="Rue de la Joie, Douala Akwa"))
        sup2, _ = StockSupplier.objects.get_or_create(
            name="Cameroon IT Solutions",
            defaults=dict(contact_name="Service commercial",
                          email="commercial@camit.cm", phone="+237 6 77 88 99 00",
                          address="Bonapriso, Douala"))
        sup3, _ = StockSupplier.objects.get_or_create(
            name="Sono & Lumière Pro",
            defaults=dict(contact_name="Michel ATEBA",
                          email="michel@sonopro.cm", phone="+237 6 55 22 33 44",
                          address="Akwa, Douala"))

        # ---- Inventaire Magasin LPMC (issu du fichier Excel) ----
        # Matériel événementiel / technique
        evt_items = [
            dict(mat_id="MAT-001", name="Machine fumigène", brand_model="Look Solutions Viper",
                 serial_number="VPR-2021-0044",
                 category=StockItem.Category.EVENEMENT, status=StockItem.Status.GOOD,
                 quantity=1, min_quantity=1, unit="unité", location="Réserve événementiel – E1",
                 estimated_value=180000, supplier=sup3,
                 description="Machine à fumée professionnelle avec télécommande."),
            dict(mat_id="MAT-002", name="Enceinte JBL EON615", brand_model="JBL EON615",
                 serial_number="JBL-EON615-0821",
                 category=StockItem.Category.TECHNIQUE, status=StockItem.Status.GOOD,
                 quantity=2, min_quantity=2, unit="unité", location="Réserve son – E2",
                 estimated_value=350000, supplier=sup3,
                 description="Enceinte amplifiée 1000W, Bluetooth, 15 pouces."),
            dict(mat_id="MAT-003", name="Rallonge électrique 25m", brand_model="3M multi-prises",
                 category=StockItem.Category.TECHNIQUE, status=StockItem.Status.USED,
                 quantity=4, min_quantity=2, unit="unité", location="Réserve son – E2",
                 estimated_value=15000, supplier=sup1,
                 description="Câble 3x1.5mm, protection parafoudre."),
            dict(mat_id="MAT-004", name="Micro sans fil Sennheiser", brand_model="Sennheiser XSW 1-825",
                 serial_number="SEN-XSW-4412",
                 category=StockItem.Category.TECHNIQUE, status=StockItem.Status.GOOD,
                 quantity=2, min_quantity=1, unit="unité", location="Réserve son – E2",
                 estimated_value=220000, supplier=sup3,
                 description="Set micro main + récepteur, portée 100m."),
            dict(mat_id="MAT-005", name="Console de mixage Yamaha MG10", brand_model="Yamaha MG10XU",
                 serial_number="YAM-MG10-9923",
                 category=StockItem.Category.TECHNIQUE, status=StockItem.Status.GOOD,
                 quantity=1, min_quantity=1, unit="unité", location="Réserve son – E2",
                 estimated_value=195000, supplier=sup3,
                 description="Table de mixage 10 canaux, USB, effets intégrés."),
            dict(mat_id="MAT-006", name="Projecteur LED PAR 64", brand_model="Eurolite LED PAR-64",
                 category=StockItem.Category.TECHNIQUE, status=StockItem.Status.GOOD,
                 quantity=6, min_quantity=4, unit="unité", location="Réserve lumière – E3",
                 estimated_value=45000, supplier=sup3,
                 description="PAR 64 RGB, 18× 3W, DMX."),
            dict(mat_id="MAT-007", name="Toile de projection 2×3m",
                 category=StockItem.Category.EVENEMENT, status=StockItem.Status.USED,
                 quantity=2, min_quantity=1, unit="unité", location="Réserve événementiel – E1",
                 estimated_value=35000, supplier=sup1,
                 description="Toile matte blanche, trépied inclus."),
            dict(mat_id="MAT-008", name="Vidéoprojecteur Epson EB-X51", brand_model="Epson EB-X51",
                 serial_number="EPS-EBX51-3301",
                 category=StockItem.Category.EVENEMENT, status=StockItem.Status.GOOD,
                 quantity=2, min_quantity=1, unit="unité", location="Salle de conférence / Réserve",
                 estimated_value=420000, supplier=sup2,
                 description="3600 lumens, HDMI, USB, sac de transport inclus."),
            dict(mat_id="MAT-009", name="Banderole rétractable Roll-up",
                 category=StockItem.Category.EVENEMENT, status=StockItem.Status.GOOD,
                 quantity=5, min_quantity=2, unit="unité", location="Réserve événementiel – E1",
                 estimated_value=25000, supplier=sup1,
                 description="Roll-up 85×200cm, sac de transport."),
            dict(mat_id="MAT-010", name="Nappe de table (lot 10)",
                 category=StockItem.Category.EVENEMENT, status=StockItem.Status.USED,
                 quantity=3, min_quantity=2, unit="lot", location="Réserve événementiel – E1",
                 estimated_value=18000, supplier=sup1,
                 description="Nappes noires 183×274cm, polyester, lavables."),
        ]
        # Matériel informatique & bureautique
        it_items = [
            dict(mat_id="MAT-011", name="Ordinateur portable Dell Latitude", brand_model="Dell Latitude 5430",
                 serial_number="DELL-LAT-5430-0011",
                 category=StockItem.Category.IT, status=StockItem.Status.GOOD,
                 quantity=4, min_quantity=2, unit="unité", location="Armoire IT – A1",
                 estimated_value=850000, supplier=sup2,
                 description="Core i5, 16 Go RAM, SSD 512 Go."),
            dict(mat_id="MAT-012", name="Imprimante HP LaserJet Pro", brand_model="HP LaserJet M404dn",
                 serial_number="HP-LJ-M404-0022",
                 category=StockItem.Category.IT, status=StockItem.Status.GOOD,
                 quantity=2, min_quantity=1, unit="unité", location="Armoire IT – A2",
                 estimated_value=320000, supplier=sup2,
                 description="Réseau, recto-verso automatique."),
            dict(mat_id="MAT-013", name="Disque dur externe 1 To", brand_model="Seagate Backup Plus",
                 category=StockItem.Category.IT, status=StockItem.Status.GOOD,
                 quantity=3, min_quantity=2, unit="unité", location="Armoire IT – A3",
                 estimated_value=35000, supplier=sup2,
                 description="USB 3.0, compatible Mac/PC."),
            dict(mat_id="MAT-014", name="Clé USB 32 Go (lot 5)",
                 category=StockItem.Category.IT, status=StockItem.Status.GOOD,
                 quantity=4, min_quantity=3, unit="lot", location="Armoire IT – A3",
                 estimated_value=8000, supplier=sup2,
                 description="USB 3.0, lecture 90 Mo/s."),
        ]
        # Mobilier & bureautique
        office_items = [
            dict(mat_id="MAT-015", name="Chaise de bureau ergonomique",
                 category=StockItem.Category.MOBILIER, status=StockItem.Status.GOOD,
                 quantity=12, min_quantity=5, unit="unité", location="Réserve mobilier – B2",
                 estimated_value=95000, supplier=sup1,
                 description="Accoudoirs réglables, soutien lombaire."),
            dict(mat_id="MAT-016", name="Table pliante 180cm",
                 category=StockItem.Category.MOBILIER, status=StockItem.Status.GOOD,
                 quantity=6, min_quantity=3, unit="unité", location="Réserve mobilier – B1",
                 estimated_value=45000, supplier=sup1,
                 description="Plateau polyéthylène, pieds acier, repliable."),
            dict(mat_id="MAT-017", name="Ramette papier A4 80g",
                 category=StockItem.Category.BUREAUTIQUE, status=StockItem.Status.GOOD,
                 quantity=8, min_quantity=10, unit="ramette", location="Réserve papeterie – C1",
                 estimated_value=4500, supplier=sup1,
                 description="500 feuilles, blanc extra."),
            dict(mat_id="MAT-018", name="Cartouche HP 26A",
                 category=StockItem.Category.BUREAUTIQUE, status=StockItem.Status.GOOD,
                 quantity=1, min_quantity=3, unit="unité", location="Réserve papeterie – C2",
                 estimated_value=28000, supplier=sup1,
                 description="Toner HP LaserJet Pro M402/M426, ~3100 pages."),
            dict(mat_id="MAT-019", name="Stylos bille BIC (lot 50)",
                 category=StockItem.Category.CONSOMMABLE, status=StockItem.Status.GOOD,
                 quantity=4, min_quantity=5, unit="lot", location="Réserve papeterie – C1",
                 estimated_value=3500, supplier=sup1,
                 description="Bleus et noirs, pointe moyenne."),
        ]
        # Un article hors service
        hs_item_data = dict(
            mat_id="MAT-020", name="Enceinte JBL EON612 (HS)", brand_model="JBL EON612",
            serial_number="JBL-EON612-0112",
            category=StockItem.Category.TECHNIQUE,
            status=StockItem.Status.OUT_OF_SERVICE,
            quantity=1, min_quantity=0, unit="unité", location="Réserve son – E2",
            estimated_value=0, supplier=sup3,
            description="En panne depuis le séminaire Kribi — tweeter grillé. Fiche de maintenance ouverte.")

        all_item_data = evt_items + it_items + office_items + [hs_item_data]
        created_items = {}
        for data in all_item_data:
            item = StockItem(**data)
            item.save()
            created_items[item.mat_id] = item

        # ---- Mouvements d'entrée initiaux (stock entrant) ----
        for mat_id, item in list(created_items.items())[:10]:
            StockMovement.objects.create(
                item=item, kind=StockMovement.Kind.IN, quantity=item.quantity,
                reason="Stock initial — inventaire 2026",
                performed_by=p["rh"].user,
                store_manager=p["rh"].user,
                movement_status=StockMovement.MovementStatus.VALIDATED)

        # Mouvement de sortie — emprunt roadshow Guinness
        enceinte = created_items["MAT-002"]
        micro = created_items["MAT-004"]
        console = created_items["MAT-005"]
        fumigene = created_items["MAT-001"]
        projecteur = created_items["MAT-008"]

        StockMovement.objects.create(
            item=enceinte, kind=StockMovement.Kind.BORROW, quantity=2,
            reason="Roadshow Guinness Smooth — Douala",
            destination="Hôtel Sawa Douala", departure_state="Bon état",
            performed_by=p["e3"].user, store_manager=p["rh"].user,
            movement_status=StockMovement.MovementStatus.VALIDATED)
        StockMovement.objects.create(
            item=micro, kind=StockMovement.Kind.BORROW, quantity=2,
            reason="Roadshow Guinness Smooth — Douala",
            destination="Hôtel Sawa Douala", departure_state="Bon état",
            performed_by=p["e3"].user, store_manager=p["rh"].user,
            movement_status=StockMovement.MovementStatus.VALIDATED)
        # Retour partiel
        StockMovement.objects.create(
            item=micro, kind=StockMovement.Kind.RETURN, quantity=2,
            reason="Retour roadshow Guinness — Douala",
            origin="Hôtel Sawa Douala", return_state="Bon état",
            performed_by=p["e3"].user, store_manager=p["rh"].user,
            movement_status=StockMovement.MovementStatus.VALIDATED)
        # Attribution définitive PC
        pc = created_items["MAT-011"]
        StockMovement.objects.create(
            item=pc, kind=StockMovement.Kind.OUT, quantity=1,
            reason="Attribution à Daniel SAKSAK (Marketing)",
            destination="Daniel SAKSAK", departure_state="Neuf",
            performed_by=p["rh"].user, store_manager=p["rh"].user,
            movement_status=StockMovement.MovementStatus.VALIDATED)
        pc.quantity -= 1
        pc.save(update_fields=["quantity"])

        # ---- Fiches de réconciliation post-événement ----
        # Séminaire Kribi : enceinte HS non retournée en bon état
        PostEventReconciliation.objects.create(
            event_name="Séminaire de cohésion — Kribi 2026",
            event_date=today - timedelta(days=45),
            item=created_items["MAT-020"],  # enceinte HS
            qty_out=2, qty_returned=1,
            return_state=PostEventReconciliation.ReturnState.DAMAGED,
            action=PostEventReconciliation.Action.REPAIR,
            responsible=p["e3"].user,
            comments="L'une des enceintes EON612 est revenue avec le tweeter grillé. Fiche de maintenance ouverte.")
        PostEventReconciliation.objects.create(
            event_name="Séminaire de cohésion — Kribi 2026",
            event_date=today - timedelta(days=45),
            item=fumigene,
            qty_out=1, qty_returned=1,
            return_state=PostEventReconciliation.ReturnState.GOOD,
            action=PostEventReconciliation.Action.OK,
            responsible=p["e3"].user,
            comments="RAS.")
        # Roadshow Guinness (partiel, encore en cours)
        PostEventReconciliation.objects.create(
            event_name="Roadshow Guinness Smooth — Douala",
            event_date=today - timedelta(days=5),
            item=enceinte,
            qty_out=2, qty_returned=2,
            return_state=PostEventReconciliation.ReturnState.USED,
            action=PostEventReconciliation.Action.OK,
            responsible=p["e3"].user,
            comments="Enceintes revenues avec légère poussière, nettoyage effectué.")

        # ---- Fiches de maintenance ----
        hs = created_items["MAT-020"]
        MaintenanceItem.objects.create(
            item=hs,
            problem="Tweeter grillé — aucun son dans les hautes fréquences. Constaté au retour du séminaire Kribi.",
            detected_at=today - timedelta(days=44),
            responsible=p["rh"].user,
            recommended_action=MaintenanceItem.RecommendedAction.REPAIR,
            estimated_cost=35000,
            status=MaintenanceItem.Status.PENDING,
            comments="Devis à demander à SonoPro.")
        # Rallonge partiellement défectueuse
        rallonge = created_items["MAT-003"]
        MaintenanceItem.objects.create(
            item=rallonge,
            problem="Une des 4 rallonges présente un câble dénudé sur 5cm — risque électrique.",
            detected_at=today - timedelta(days=10),
            responsible=p["mkt"].user,
            recommended_action=MaintenanceItem.RecommendedAction.SCRAP,
            estimated_cost=15000,
            status=MaintenanceItem.Status.PENDING,
            comments="A isoler immédiatement. Mise au rebut recommandée, remplacer.")

        # ---- Demandes d'emprunt ----
        BorrowRequest.objects.create(
            item=projecteur, requested_by=p["e3"].user, quantity=1,
            purpose="Présentation client — Roadshow Guinness Yaoundé",
            start_date=today + timedelta(days=2), end_date=today + timedelta(days=7),
            status=BorrowRequest.Status.APPROVED,
            decided_by=p["rh"].user, decided_at=timezone.now())
        BorrowRequest.objects.create(
            item=created_items["MAT-012"], requested_by=p["e1"].user, quantity=1,
            purpose="Impression supports campagne NESCAFÉ",
            start_date=today + timedelta(days=1), end_date=today + timedelta(days=1),
            status=BorrowRequest.Status.PENDING)

        # ---- Bon de commande (cartouches + ramettes en rupture) ----
        PurchaseOrder.objects.create(
            supplier=sup1,
            items="4x Cartouche HP 26A (ref MAT-018)\n10x Ramette papier A4 80g (ref MAT-017)\n2x Stylos BIC lot 50 (ref MAT-019)",
            total_amount=10 * 4500 + 4 * 28000 + 2 * 3500,
            status=PurchaseOrder.Status.SENT,
            order_date=today - timedelta(days=3),
            expected_date=today + timedelta(days=4),
            notes="Livraison urgente — plusieurs références en alerte stock.",
            created_by=p["rh"].user)

        self.stdout.write("  Stock : inventaire Excel (20 articles), mouvements, maintenance, reconciliations OK.")

    # ================================================================== RSE ===
    def _rse(self, p):
        from rse.models import (
            RSEIndicator, RSEInitiative, RSEReport, RSEResource, RSESupplier,
        )
        if RSEIndicator.objects.exists():
            return
        year = date.today().year

        # Indicateurs par catégorie
        indicators = [
            (RSEIndicator.Category.CARBON, "Empreinte carbone annuelle", 85.4, 60, "tonnes CO2e", "Rapport GES interne"),
            (RSEIndicator.Category.CARBON, "Consommation électrique bureau", 32800, 28000, "kWh", "Factures AES-SONEL"),
            (RSEIndicator.Category.DIVERSITY, "Taux de féminisation", 38, 45, "%", "RH – Effectifs 2026"),
            (RSEIndicator.Category.DIVERSITY, "Collaborateurs en situation de handicap", 1, 2, "personnes", "RH – Effectifs 2026"),
            (RSEIndicator.Category.SOCIAL, "Heures de formation par collaborateur/an", 24, 30, "h", "Plan de formation 2026"),
            (RSEIndicator.Category.SOCIAL, "Taux de turn-over", 12, 8, "%", "RH – Départs 2026"),
            (RSEIndicator.Category.GOVERNANCE, "Satisfaction collaborateurs (sondage)", 7.2, 8.0, "/10", "Enquête RH Q1-2026"),
            (RSEIndicator.Category.GOVERNANCE, "Fournisseurs évalués sur critères RSE", 3, 10, "fournisseurs", "Achats 2026"),
        ]
        for cat, name, value, target, unit, source in indicators:
            RSEIndicator.objects.create(
                category=cat, name=name, value=value, target=target,
                unit=unit, year=year, source=source)

        # Initiatives
        RSEInitiative.objects.create(
            title="Programme « Zéro plastique » au bureau",
            description="Remplacement des bouteilles et couverts plastiques par des équipements réutilisables dans les espaces communs.",
            category=RSEInitiative.Category.ECO,
            status=RSEInitiative.Status.ACTIVE,
            start_date=date.today() - timedelta(days=45),
            responsible=p["rh"].user,
            impact="Réduction estimée de 80% des déchets plastiques sur site.")
        RSEInitiative.objects.create(
            title="Journée de solidarité — École primaire de Bépanda",
            description="Réhabilitation des sanitaires et don de fournitures scolaires à l'école primaire publique de Bépanda.",
            category=RSEInitiative.Category.SOLIDARITY,
            status=RSEInitiative.Status.DONE,
            start_date=date.today() - timedelta(days=90),
            end_date=date.today() - timedelta(days=60),
            responsible=p["e3"].user,
            impact="120 élèves bénéficiaires, couverture média locale.")
        RSEInitiative.objects.create(
            title="Partenariat avec l'Université de Douala — Stages",
            description="Convention de partenariat pour l'accueil de stagiaires en marketing et communication.",
            category=RSEInitiative.Category.PARTNERSHIP,
            status=RSEInitiative.Status.ACTIVE,
            start_date=date.today() - timedelta(days=120),
            responsible=p["mkt"].user,
            impact="3 stagiaires accueillis en 2026.")
        RSEInitiative.objects.create(
            title="Formation aux gestes d'urgence (SST)",
            description="Sensibilisation aux gestes de premiers secours pour 10 collaborateurs volontaires.",
            category=RSEInitiative.Category.OTHER,
            status=RSEInitiative.Status.PLANNED,
            start_date=date.today() + timedelta(days=20),
            responsible=p["rh"].user,
            impact="Personnel formé aux gestes d'urgence.")

        # Rapport annuel
        RSEReport.objects.create(
            year=year - 1, title=f"Rapport RSE {year - 1} — LPM Consulting Group",
            content=(
                f"## Synthèse RSE {year - 1}\n\n"
                "LPM Consulting Group s'engage dans une démarche RSE structurée autour de quatre piliers : "
                "environnement, social, diversité et gouvernance.\n\n"
                "### Environnement\nRéduction de 12% de notre empreinte carbone grâce au télétravail partiel.\n\n"
                "### Social\n2 journées de solidarité organisées, 45 heures de formation par collaborateur.\n\n"
                "### Diversité\nObjectif parité en cours d'atteinte — 38% de femmes dans les effectifs.\n\n"
                "### Gouvernance\n100% des décisions stratégiques documentées et partagées."
            ),
            published=True,
            created_by=p["ceo"].user)

        # Ressources de sensibilisation
        RSEResource.objects.create(
            title="Guide des éco-gestes au bureau",
            kind=RSEResource.Kind.GUIDE,
            content=(
                "## Vos éco-gestes quotidiens\n\n"
                "**Énergie** : éteignez votre écran et votre PC en quittant le bureau.\n"
                "**Impression** : imprimez recto-verso et seulement si nécessaire.\n"
                "**Eau** : signalez toute fuite au service logistique.\n"
                "**Déplacements** : privilégiez les réunions en visioconférence.\n"
                "**Tri** : utilisez les bacs de tri sélectif dans les espaces communs."
            ),
            published=True)
        RSEResource.objects.create(
            title="Charte diversité & inclusion LPM",
            kind=RSEResource.Kind.GUIDE,
            content=(
                "LPM Consulting Group s'engage à offrir un environnement de travail respectueux "
                "de toutes les diversités (genre, âge, origine, handicap).\n\n"
                "Tout acte de discrimination fera l'objet d'une procédure disciplinaire."
            ),
            published=True)
        RSEResource.objects.create(
            title="Quiz : connaissez-vous notre politique RSE ?",
            kind=RSEResource.Kind.QUIZ,
            content=(
                "1. Quel est notre objectif de réduction carbone d'ici 2028 ?\n"
                "   a) 10%  b) 30%  c) 50%\n\n"
                "2. Combien de stagiaires avons-nous accueillis en 2026 ?\n"
                "   a) 1  b) 3  c) 5\n\n"
                "Réponses : 1-b, 2-b"
            ),
            published=True)

        # Fournisseurs responsables
        RSESupplier.objects.create(
            name="Bureau Express Cameroun", criteria="Fournisseur local, circuit court, FCFA",
            score=7, certified=False,
            policy_url="",
            notes="Fournisseur historique basé à Douala — favorise l'emploi local.",
            evaluated_at=date.today() - timedelta(days=30))
        RSESupplier.objects.create(
            name="Cameroon IT Solutions", criteria="Équipements reconditionnés proposés, politique de recyclage",
            score=6, certified=False,
            notes="Propose des ordinateurs reconditionnés — à développer.",
            evaluated_at=date.today() - timedelta(days=60))

        self.stdout.write("  RSE : indicateurs, initiatives, rapport, ressources OK.")

    # ======================================================== MARKETING DIGITAL ===
    def _marketing_digital(self, p):
        from marketing.models import (
            ABTest, AdCampaign, Campaign, EmailCampaign, Lead, SEOKeyword,
        )
        if Lead.objects.exists():
            return
        camp = Campaign.objects.first()
        today = date.today()

        # Leads / Prospects
        leads = [
            dict(first_name="Thierry", last_name="ONDOUA", company="Brasseries du Cameroun",
                 email="t.ondoua@bdc.cm", phone="+237 6 70 44 55 66",
                 source=Lead.Source.EVENT, status=Lead.Status.QUALIFIED,
                 campaign=camp, assigned_to=p["mkt"].user,
                 notes="Rencontré lors du salon PROMOTE 2026. Intéressé par les activations terrain.",
                 last_contact=today - timedelta(days=5)),
            dict(first_name="Nadège", last_name="BIYONG", company="Orange Cameroun",
                 email="n.biyong@orange.cm", phone="+237 6 55 33 44 55",
                 source=Lead.Source.REFERRAL, status=Lead.Status.CONTACTED,
                 assigned_to=p["mkt"].user,
                 notes="Recommandée par Jean MBALLA (Kribi Global). Budget events ~8M.",
                 last_contact=today - timedelta(days=12)),
            dict(first_name="Rodrigue", last_name="NJIKE", company="Saham Assurances",
                 email="r.njike@saham.cm",
                 source=Lead.Source.SEO, status=Lead.Status.NEW,
                 assigned_to=p["e1"].user,
                 notes="A rempli le formulaire de contact depuis le site web."),
            dict(first_name="Évelyne", last_name="MANGA", company="Société Générale Cameroun",
                 email="e.manga@sgcm.cm", phone="+237 6 88 00 11 22",
                 source=Lead.Source.SOCIAL, status=Lead.Status.CONVERTED,
                 campaign=camp, assigned_to=p["mkt"].user,
                 notes="Devenue cliente — contrat signé Q1 2026.",
                 last_contact=today - timedelta(days=40)),
            dict(first_name="Patrick", last_name="TALOM", company="Canal+ Afrique",
                 email="p.talom@canalplus.cm",
                 source=Lead.Source.SEA, status=Lead.Status.LOST,
                 notes="Budget gelé jusqu'en 2027 selon leurs retours.",
                 last_contact=today - timedelta(days=90)),
        ]
        for data in leads:
            Lead.objects.create(**data)

        # Mots-clés SEO
        keywords = [
            ("agence marketing Douala", "https://lpmconsulting.cm/services", 4, 8, 880, 42),
            ("agence événementielle Cameroun", "https://lpmconsulting.cm/evenements", 7, 12, 590, 38),
            ("activation terrain FMCG Cameroun", "https://lpmconsulting.cm/activation", 12, 18, 320, 31),
            ("community management Douala", "https://lpmconsulting.cm/digital", 3, 6, 1200, 45),
            ("campagne publicitaire Cameroun", "https://lpmconsulting.cm/campagnes", 9, 9, 480, 52),
            ("agence communication Yaoundé", "https://lpmconsulting.cm", 15, 22, 720, 55),
        ]
        for kw, url, pos, prev, vol, diff in keywords:
            SEOKeyword.objects.create(
                keyword=kw, url=url, position=pos, previous_position=prev,
                search_volume=vol, difficulty=diff,
                campaign=camp, updated_at=today - timedelta(days=7))

        # Campagnes Ads
        AdCampaign.objects.create(
            name="Google Ads — Branding LPM Q2", platform=AdCampaign.Platform.GOOGLE,
            status=AdCampaign.Status.ACTIVE, campaign=camp,
            budget=500000, spent=312000, impressions=48200, clicks=1840, conversions=12,
            start_date=today - timedelta(days=20), end_date=today + timedelta(days=10),
            notes="CTR en hausse depuis l'ajout des extensions d'appel.")
        AdCampaign.objects.create(
            name="Meta Ads — Recrutement stagiaires", platform=AdCampaign.Platform.META,
            status=AdCampaign.Status.ENDED, campaign=camp,
            budget=150000, spent=148500, impressions=62300, clicks=2100, conversions=8,
            start_date=today - timedelta(days=60), end_date=today - timedelta(days=30),
            notes="Campagne terminée. 8 candidatures reçues via le formulaire.")
        AdCampaign.objects.create(
            name="LinkedIn Ads — B2B Awareness", platform=AdCampaign.Platform.LINKEDIN,
            status=AdCampaign.Status.PAUSED,
            budget=300000, spent=95000, impressions=18400, clicks=490, conversions=3,
            start_date=today - timedelta(days=30),
            notes="Mis en pause — reformulation du message en cours.")

        # Email marketing
        EmailCampaign.objects.create(
            subject="LPM Consulting — Nos nouvelles offres événementielles 2026",
            preview_text="Découvrez notre catalogue événementiel mis à jour",
            status=EmailCampaign.Status.SENT, campaign=camp,
            sent_at=timezone.now() - timedelta(days=15),
            recipients_count=342, opens=198, clicks=87, unsubscribes=4,
            content="<p>Chers partenaires,</p><p>Retrouvez notre nouveau catalogue...</p>")
        EmailCampaign.objects.create(
            subject="Newsletter LPM — Résultats campagne NESCAFÉ",
            preview_text="12 villes, 45 000 contacts, 320 leads",
            status=EmailCampaign.Status.SENT,
            sent_at=timezone.now() - timedelta(days=7),
            recipients_count=180, opens=141, clicks=63, unsubscribes=1,
            content="<p>Retour sur notre activation terrain...</p>")
        EmailCampaign.objects.create(
            subject="Invitation — Séminaire Marketing Digital Douala",
            preview_text="15 juillet 2026 — Hôtel Akwa Palace",
            status=EmailCampaign.Status.SCHEDULED, campaign=camp,
            scheduled_at=timezone.now() + timedelta(days=5),
            recipients_count=520)

        # Tests A/B
        ABTest.objects.create(
            name="A/B Objet email — Offre événementielle",
            hypothesis="Un objet avec un chiffre (ex: '5 raisons') génère plus d'ouvertures.",
            variant_a="Nos offres événementielles 2026",
            variant_b="5 raisons de confier vos événements à LPM",
            metric="Taux d'ouverture", status=ABTest.Status.DONE,
            winner="B", result="Variante B : +18% d'ouvertures. Adopter le format chiffré.",
            start_date=today - timedelta(days=30), end_date=today - timedelta(days=15))
        ABTest.objects.create(
            name="A/B CTA site web — Page Services",
            hypothesis="Un bouton 'Demandez un devis' convertit mieux que 'Contactez-nous'.",
            variant_a="Contactez-nous", variant_b="Demandez un devis gratuit",
            metric="Clics sur le bouton CTA", status=ABTest.Status.RUNNING,
            start_date=today - timedelta(days=10))

        self.stdout.write("  Marketing Digital : leads, SEO, ads, email, A/B tests OK.")

    # ================================================= COMMUNICATION ÉTENDUE ===
    def _communication_ext(self, p):
        from communication.models import (
            Event, EventParticipant, EventProject, EventReport, EventSupplier,
            KeyMessage, Newsletter, PressReview,
        )
        if PressReview.objects.exists():
            return
        today = date.today()

        # Revue de presse
        press = [
            dict(title="LPM Consulting primée au Gala de la Communication Camerounaise",
                 source="Mutations", media_type=PressReview.MediaType.PRINT,
                 tone=PressReview.Tone.POSITIVE,
                 excerpt="L'agence LPM Consulting Group a reçu le prix de la Meilleure Campagne Événementielle lors de la 8e édition du Gala.",
                 published_at=today - timedelta(days=20), added_by=p["mkt"].user),
            dict(title="Les agences de com camerounaises à l'ère du digital",
                 source="Eco Matin", media_type=PressReview.MediaType.ONLINE,
                 url="https://www.ecomatin.net",
                 tone=PressReview.Tone.POSITIVE,
                 excerpt="LPM Consulting Group figure parmi les pionnières de la transformation digitale dans le secteur des événements.",
                 published_at=today - timedelta(days=45), added_by=p["mkt"].user),
            dict(title="Rapport : état du marché publicitaire au Cameroun 2026",
                 source="UNCT Media Monitor",
                 media_type=PressReview.MediaType.ONLINE,
                 tone=PressReview.Tone.NEUTRAL,
                 excerpt="Le marché publicitaire camerounais progresse de 8% en 2025, porté par le digital et l'événementiel.",
                 published_at=today - timedelta(days=60), added_by=p["rh"].user),
        ]
        for data in press:
            PressReview.objects.create(**data)

        # Messages clés
        messages_cles = [
            dict(category=KeyMessage.Category.PITCH,
                 title="Pitch standard — Présentation LPM Consulting",
                 content=(
                     "LPM Consulting Group est une agence conseil en communication, marketing et événementiel "
                     "basée à Douala, Cameroun. Depuis plus de 10 ans, nous accompagnons les marques leaders "
                     "(FMCG, Télécom, Finance) dans leur développement au Cameroun et en Afrique centrale.\n\n"
                     "Nos expertises : stratégie de marque, activation terrain, communication digitale, "
                     "production événementielle (roadshows, conventions, galas)."
                 ),
                 audience="Prospects, partenaires, médias", is_active=True,
                 created_by=p["ceo"].user),
            dict(category=KeyMessage.Category.FAQ,
                 title="Comment travaillez-vous avec un nouveau client ?",
                 content=(
                     "Notre processus en 4 étapes :\n"
                     "1. **Brief** — Session de découverte pour comprendre vos enjeux (30 min)\n"
                     "2. **Stratégie** — Recommandation créative et plan d'action (J+5)\n"
                     "3. **Validation** — Présentation et ajustements\n"
                     "4. **Exécution** — Production et suivi avec reporting hebdomadaire"
                 ),
                 audience="Prospects lors des RDV commerciaux", is_active=True,
                 created_by=p["mkt"].user),
            dict(category=KeyMessage.Category.RESPONSE,
                 title="Réponse type : délai de production d'une campagne",
                 content=(
                     "Le délai standard de production d'une campagne est de **3 à 6 semaines** selon "
                     "la complexité (brief simple vs. production multi-supports).\n\n"
                     "Pour les activations terrain : comptez 2 semaines de préparation minimum après validation du brief."
                 ),
                 audience="Clients qui demandent les délais", is_active=True,
                 created_by=p["mkt"].user),
            dict(category=KeyMessage.Category.SPEECH,
                 title="Allocution — Cérémonie de vœux 2026",
                 content=(
                     "Chers collaborateurs, chers partenaires,\n\n"
                     "En ce début d'année 2026, je tiens à vous adresser mes vœux les plus sincères. "
                     "L'année écoulée a été riche en défis et en succès : nous avons livré plus de 40 projets, "
                     "accueilli 3 nouveaux collaborateurs et renforcé nos partenariats stratégiques.\n\n"
                     "2026 sera l'année de notre transformation digitale. Ensemble, construisons LPM de demain."
                 ),
                 audience="Collaborateurs, partenaires", is_active=True,
                 created_by=p["ceo"].user),
        ]
        for data in messages_cles:
            KeyMessage.objects.create(**data)

        # Newsletters internes
        Newsletter.objects.create(
            subject="LPM Infos — Juin 2026",
            content=(
                "## Bonjour à toute l'équipe !\n\n"
                "**Au programme ce mois-ci :**\n"
                "- Retour sur l'activation NESCAFÉ (45 000 contacts, +320 leads)\n"
                "- Bienvenue à Steve MBALLA, notre nouveau stagiaire Marketing\n"
                "- Reminder : soumettez vos demandes de congés avant le 15 juillet\n"
                "- RSE : journée solidarité le 28 juin — inscrivez-vous !\n\n"
                "Bonne lecture, l'équipe RH"
            ),
            status=Newsletter.Status.SENT,
            sent_at=timezone.now() - timedelta(days=10),
            recipients_count=8, opens=7, created_by=p["rh"].user)
        Newsletter.objects.create(
            subject="Flash Info — Victoire au Gala de la Com !",
            content=(
                "Toute l'équipe est fière d'annoncer notre prix au Gala de la Communication Camerounaise 2026 !\n\n"
                "Merci à tous pour votre implication dans la campagne NESCAFÉ.\n\n"
                "Une petite fête s'impose vendredi soir au bureau — soyez là !"
            ),
            status=Newsletter.Status.SENT,
            sent_at=timezone.now() - timedelta(days=20),
            recipients_count=8, opens=8, created_by=p["mkt"].user)
        Newsletter.objects.create(
            subject="LPM Infos — Juillet 2026 (à venir)",
            content="En cours de rédaction…",
            status=Newsletter.Status.DRAFT, created_by=p["rh"].user)

        # Projet événementiel — Roadshow Guinness (lié à l'Event existant)
        ev = Event.objects.first()
        ep = EventProject.objects.create(
            name="Roadshow Guinness Smooth — 3 villes",
            event=None,
            brief=(
                "Roadshow de lancement du nouveau Guinness Smooth dans les villes de Douala, Yaoundé et Bafoussam. "
                "Durée : 3 jours par ville. Cibles : distribution moderne et CHR."
            ),
            location="Douala → Yaoundé → Bafoussam",
            date=date.today() + timedelta(days=30),
            budget=15000000, status=EventProject.Status.ACTIVE,
            responsible=p["e3"].user,
            retro_planning=(
                "J-30 : Brief fournisseurs\n"
                "J-20 : Validation créations\n"
                "J-15 : Envoi des invitations\n"
                "J-7 : Briefing équipe terrain\n"
                "J-3 : Vérification logistique\n"
                "J0 : Kick-off Douala"
            ),
            notes="Budget validé par le client. Prestataires à confirmer avant J-20.")

        # Prestataires
        EventSupplier.objects.create(
            event_project=ep, name="SonoPro Cameroun",
            service="Sonorisation & éclairage scénique",
            contact="Michel ATEBA", phone="+237 6 55 22 33 44",
            email="michel@sonopro.cm", quote_amount=2500000,
            status="CONFIRMED", notes="Devis signé. À régler 30% avant J-7.")
        EventSupplier.objects.create(
            event_project=ep, name="SafeGuard Security",
            service="Sécurité et accueil VIP",
            contact="Service commercial", phone="+237 6 77 44 55 66",
            quote_amount=800000, status="CONTACTED")
        EventSupplier.objects.create(
            event_project=ep, name="Délices Traiteur",
            service="Cocktail de lancement — 300 couverts",
            contact="Mireille EWANE", phone="+237 6 88 11 22 33",
            email="contact@delices-traiteur.cm", quote_amount=1800000,
            status="CONFIRMED")

        # Participants (invités presse & VIP)
        participants = [
            ("Jean-Pierre", "MBELE", "Guinness Cameroun", "jp.mbele@guinness.cm", "REGISTERED"),
            ("Agathe", "NFONO", "Journaliste — Mutations", "a.nfono@mutations.cm", "INVITED"),
            ("Cyril", "DONFACK", "Distributeur — Bafoussam", "c.donfack@distrib.cm", "REGISTERED"),
            ("Rachelle", "ONGONO", "Influenceuse food & lifestyle", "r.ongono@gmail.com", "ATTENDED"),
        ]
        for fn, ln, comp, email, status in participants:
            EventParticipant.objects.create(
                event_project=ep, first_name=fn, last_name=ln,
                company=comp, email=email, status=status)

        # Deuxième projet : Séminaire RH terminé avec bilan
        ep2 = EventProject.objects.create(
            name="Séminaire de cohésion — Kribi 2026",
            brief="Séminaire annuel de renforcement de la cohésion d'équipe sur 2 jours.",
            location="Hôtel Ilomba — Kribi",
            date=date.today() - timedelta(days=45),
            budget=3500000, status=EventProject.Status.DONE,
            responsible=p["rh"].user,
            notes="Très bonne ambiance — à renouveler en fin d'année.")
        EventReport.objects.create(
            event_project=ep2,
            summary="Séminaire réussi malgré la pluie le premier jour. Activités team-building très appréciées.",
            participants_count=9, budget_spent=3280000,
            feedback="Excellentes retours de l'équipe. Note moyenne : 8,5/10.",
            kpis="Taux de participation : 100%. NPS collaborateurs : +42.",
            learnings="Anticiper la météo pour les activités en plein air. Prévoir un plan B indoor.",
            created_by=p["rh"].user)

        self.stdout.write("  Communication : presse, messages clés, newsletters, événements OK.")

    # ================================================= ONBOARDING RH ===
    def _hr_onboarding(self, p):
        from hr.models import OnboardingPlan, OnboardingProgress, OnboardingStep
        if OnboardingPlan.objects.exists():
            return

        # Plan générique pour tous les collaborateurs
        plan_gen = OnboardingPlan.objects.create(
            name="Intégration Collaborateur — Parcours Standard",
            description="Parcours d'intégration applicable à tout nouveau salarié (CDI / CDD). Durée : 30 jours.",
            role_target="EMPLOYE", created_by=p["rh"].user)
        steps_gen = [
            (1, 1, "Accueil & présentation de l'équipe",
             "Visite des locaux, remise du badge, rencontre avec les équipes."),
            (2, 1, "Remise du matériel & accès informatiques",
             "Ordinateur, badge, email, accès aux outils (intranet, Drive, messagerie)."),
            (3, 2, "Lecture du règlement intérieur & politique RH",
             "Signature de la clause de confidentialité et du règlement intérieur."),
            (4, 3, "Réunion de cadrage avec le responsable direct",
             "Présentation des objectifs des 3 premiers mois, planning d'intégration."),
            (5, 5, "Formation aux outils métier",
             "Formation intranet, CRM (si applicable), outils de gestion de projets."),
            (6, 10, "Point d'étonnement J+10",
             "Entretien informel avec le RH : premières impressions, besoins."),
            (7, 15, "Bilan mi-parcours avec le responsable",
             "Évaluation des premières semaines, ajustements si nécessaire."),
            (8, 30, "Entretien de fin d'intégration",
             "Bilan des 30 premiers jours, validation de la période d'intégration."),
        ]
        for order, day, title, desc in steps_gen:
            OnboardingStep.objects.create(
                plan=plan_gen, order=order, day=day, title=title, description=desc)

        # Plan spécifique Marketing
        plan_mkt = OnboardingPlan.objects.create(
            name="Intégration Chargé(e) de Marketing",
            description="Parcours spécifique pour les profils marketing, communication et digital.",
            role_target="MANAGER", created_by=p["rh"].user)
        steps_mkt = [
            (1, 1, "Présentation du portefeuille clients",
             "Revue des clients actifs, des campagnes en cours et des projets à venir."),
            (2, 3, "Formation aux outils marketing (Meta Ads, Google Ads)",
             "Formation pratique sur les plateformes publicitaires."),
            (3, 5, "Briefing sur l'identité de marque LPM",
             "Charte graphique, ton éditorial, guide de style."),
            (4, 7, "Participation à une réunion client",
             "Observation d'une réunion de présentation de campagne."),
            (5, 15, "Prise en main d'un dossier client autonome",
             "Premier projet en responsabilité, avec supervision."),
        ]
        for order, day, title, desc in steps_mkt:
            OnboardingStep.objects.create(
                plan=plan_mkt, order=order, day=day, title=title, description=desc)

        # Suivi pour le stagiaire en cours
        stg_emp = p["stg"]
        prog = OnboardingProgress.objects.create(
            employee=stg_emp, plan=plan_mkt,
            started_at=date.today() - timedelta(days=14),
            notes="Bonne intégration, motivé.")
        # Étapes complétées
        done_steps = plan_mkt.steps.filter(order__lte=3)
        prog.completed_steps.set(done_steps)

        self.stdout.write("  Onboarding : 2 plans, étapes, suivi stagiaire OK.")

    # ================================================= PROJETS ÉTENDUS ===
    def _projects_ext(self, p):
        from projects.models import Benchmark, Project as Proj, Ticket
        if Ticket.objects.exists():
            return
        proj = Proj.objects.first()
        today = date.today()

        # Backlog / Tickets
        tickets = [
            dict(title="Le calendrier éditorial n'affiche pas les posts du mois précédent",
                 kind=Ticket.Kind.BUG, status=Ticket.Status.OPEN,
                 priority=Ticket.Priority.HIGH, project=proj,
                 description="Quand on navigue en arrière dans le calendrier éditorial, les posts du mois précédent n'apparaissent pas. Reproductible sur Chrome et Firefox.",
                 reported_by=p["mkt"].user, assigned_to=p["e1"].user),
            dict(title="Ajouter l'export PDF des devis",
                 kind=Ticket.Kind.FEATURE, status=Ticket.Status.IN_PROGRESS,
                 priority=Ticket.Priority.NORMAL, project=proj,
                 description="Le client souhaite télécharger les devis en PDF directement depuis l'extranet. La génération PDF est déjà disponible côté intranet, à exposer côté client.",
                 reported_by=p["fin"].user, assigned_to=p["e1"].user),
            dict(title="Page de connexion extranet — erreur 500 sur mot de passe oublié",
                 kind=Ticket.Kind.BUG, status=Ticket.Status.DONE,
                 priority=Ticket.Priority.CRITICAL,
                 description="Une erreur 500 se produisait lors du clic sur 'Mot de passe oublié' sur la page extranet. Corrigé en v1.2.4.",
                 reported_by=p["ceo"].user, assigned_to=p["e1"].user,
                 resolved_at=timezone.now() - timedelta(days=5)),
            dict(title="Intégrer les analytics Google Tag Manager",
                 kind=Ticket.Kind.FEATURE, status=Ticket.Status.OPEN,
                 priority=Ticket.Priority.NORMAL,
                 description="Installer GTM sur le site vitrine et configurer les événements de conversion (formulaire de contact, clics CTA).",
                 reported_by=p["mkt"].user),
            dict(title="Performance : la liste des campagnes charge lentement (+5 000 posts)",
                 kind=Ticket.Kind.TASK, status=Ticket.Status.OPEN,
                 priority=Ticket.Priority.HIGH, project=proj,
                 description="La vue campagnes avec beaucoup de posts prend >3s. Implémenter la pagination côté liste et le lazy loading des médias.",
                 reported_by=p["e1"].user),
            dict(title="Documenter l'API REST externe (DRF)",
                 kind=Ticket.Kind.TASK, status=Ticket.Status.OPEN,
                 priority=Ticket.Priority.LOW,
                 description="Rédiger la documentation Swagger/OpenAPI pour tous les endpoints DRF existants.",
                 reported_by=p["ceo"].user, assigned_to=p["e1"].user),
        ]
        for data in tickets:
            Ticket.objects.create(**data)

        # Benchmarks & Veille
        benchmarks = [
            dict(title="Hootsuite vs Buffer — Gestion des réseaux sociaux",
                 category=Benchmark.Category.TOOL,
                 url="https://www.hootsuite.com",
                 summary=(
                     "Hootsuite : interface plus complète, meilleur pour les équipes (approbation des posts). "
                     "Buffer : plus simple, tarif plus accessible pour les TPE. "
                     "**Recommandation** : Hootsuite pour notre usage multi-clients."
                 ),
                 rating=4, tags="social media, outils, gestion", added_by=p["mkt"].user),
            dict(title="Semrush — Outil SEO complet",
                 category=Benchmark.Category.TOOL,
                 url="https://www.semrush.com",
                 summary=(
                     "Outil de référence pour le suivi des positions, l'analyse de la concurrence et l'audit technique SEO. "
                     "Prix élevé (~$120/mois) mais rentable pour les agences. "
                     "**À tester** sur le compte LPM avant décision d'abonnement."
                 ),
                 rating=5, tags="SEO, audit, concurrence", added_by=p["e1"].user),
            dict(title="Digitale Agency Africa — Concurrent direct à surveiller",
                 category=Benchmark.Category.COMPETITOR,
                 summary=(
                     "Agence basée à Yaoundé, forte sur le digital et les réseaux sociaux. "
                     "Points forts : équipe junior réactive, tarifs compétitifs. "
                     "Points faibles : peu d'expérience événementielle, pas de capabilities B2B. "
                     "**Surveiller** leurs recrutements et publications LinkedIn."
                 ),
                 rating=3, tags="concurrent, Yaoundé, digital", added_by=p["mkt"].user),
            dict(title="Tendance 2026 : Short-form video en Afrique centrale",
                 category=Benchmark.Category.TREND,
                 url="https://www.statista.com",
                 summary=(
                     "Le contenu vidéo court (TikTok, Instagram Reels) explose en Afrique centrale : "
                     "+65% d'audience mobile en 2025. Les marques FMCG adoptent massivement ce format. "
                     "**Action** : intégrer la production de Reels dans notre offre standard d'ici Q3 2026."
                 ),
                 rating=5, tags="tendance, vidéo, mobile, TikTok", added_by=p["mkt"].user),
            dict(title="HubSpot CRM — Alternative à notre gestion leads actuelle",
                 category=Benchmark.Category.TOOL,
                 url="https://www.hubspot.com",
                 summary=(
                     "Version gratuite très complète pour le suivi des leads et l'email marketing. "
                     "Intégration native avec Gmail/Outlook. "
                     "**Décision** : à tester sur le périmètre commercial avant d'envisager l'intégration."
                 ),
                 rating=4, tags="CRM, leads, email, gratuit", added_by=p["fin"].user),
        ]
        for data in benchmarks:
            Benchmark.objects.create(**data)

        self.stdout.write("  Projets : tickets, benchmarks & veille OK.")
