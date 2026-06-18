"""Ressources Humaines avancées : contrats, présences/pointage, recrutement, évaluation.

Complète les modules existants (employés, congés, discipline) pour couvrir
l'ensemble du périmètre RH du cahier des charges.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from employees.models import Department, Employee


# --------------------------------------------------------------------------- #
# Contrats
# --------------------------------------------------------------------------- #
class Contract(models.Model):
    class Type(models.TextChoices):
        CDI = "CDI", "CDI"
        CDD = "CDD", "CDD"
        STAGE = "STAGE", "Stage"
        TEMP = "TEMP", "Temporaire / Mission"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="contracts")
    type = models.CharField("Type", max_length=10, choices=Type.choices, default=Type.CDI)
    title = models.CharField("Intitulé du poste", max_length=150, blank=True)
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin", null=True, blank=True)
    salary = models.DecimalField("Salaire mensuel de base (FCFA)", max_digits=12, decimal_places=0, default=0)
    file = models.FileField("Contrat signé (PDF)", upload_to="hr/contracts/%Y/", blank=True, null=True)
    is_active = models.BooleanField("Actif", default=True)
    created_at = models.DateTimeField(default=timezone.now)

    # --- Éléments saisis manuellement pour la génération du contrat ---
    # Identité du salarié (non couverte par la fiche employé).
    birth_info = models.CharField("Date et lieu de naissance", max_length=150, blank=True)
    nationality = models.CharField("Nationalité", max_length=60, blank=True, default="Camerounaise")
    id_number = models.CharField("N° CNI / Passeport", max_length=60, blank=True)
    # Conditions de travail.
    work_location = models.CharField("Lieu de travail", max_length=200, blank=True)
    probation_months = models.PositiveSmallIntegerField("Période d'essai (mois)", default=0)
    duties = models.TextField("Fonctions et responsabilités (une par ligne)", blank=True)
    work_schedule = models.CharField("Horaires de travail", max_length=200, blank=True,
                                     default="Du lundi au vendredi, de 08h00 à 17h00")
    # Rémunération (primes).
    transport_allowance = models.DecimalField("Prime de transport (FCFA)", max_digits=12, decimal_places=0, default=0)
    housing_allowance = models.DecimalField("Prime de logement (FCFA)", max_digits=12, decimal_places=0, default=0)
    performance_allowance = models.DecimalField("Prime de rendement (FCFA)", max_digits=12, decimal_places=0, default=0)
    other_allowances = models.CharField("Autres primes / avantages", max_length=200, blank=True)
    pay_day = models.PositiveSmallIntegerField("Jour de paiement du salaire", default=30)
    place_signed = models.CharField("Fait à", max_length=80, blank=True, default="Douala")

    class Meta:
        verbose_name = "Contrat"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.employee.full_name}"

    @property
    def gross_salary(self):
        """Salaire brut = base + primes."""
        return int(self.salary + self.transport_allowance + self.housing_allowance
                   + self.performance_allowance)


# --------------------------------------------------------------------------- #
# Présences / Pointage
# --------------------------------------------------------------------------- #
class OfficeLocation(models.Model):
    """Lieu de pointage (siège). Calibrable depuis l'app par le RH/admin sur place."""

    name = models.CharField("Nom du site", max_length=120, default="Siège LPM")
    lat = models.FloatField("Latitude")
    lng = models.FloatField("Longitude")
    radius_m = models.PositiveIntegerField("Rayon autorisé (m)", default=500)
    # Date de début du pointage : les jours ANTÉRIEURS ne sont jamais comptés
    # (ni présences/absences générées, ni retenues salariales).
    start_date = models.DateField("Date de début du pointage", null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lieu de pointage"
        verbose_name_plural = "Lieu de pointage"

    def __str__(self):
        return f"{self.name} ({self.lat}, {self.lng})"

    @classmethod
    def current(cls):
        return cls.objects.first()


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Présent"
        LATE = "LATE", "En retard"
        ABSENT = "ABSENT", "Absent"
        LEAVE = "LEAVE", "En congé"
        MISSION = "MISSION", "En mission"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField("Date", default=timezone.localdate)
    check_in = models.DateTimeField("Arrivée", null=True, blank=True)
    check_out = models.DateTimeField("Départ", null=True, blank=True)
    status = models.CharField("Statut", max_length=8, choices=Status.choices, default=Status.PRESENT)
    note = models.CharField("Note", max_length=200, blank=True)
    # Géolocalisation du pointage (anti-fraude : vérifie la présence au bureau).
    check_in_lat = models.FloatField("Latitude arrivée", null=True, blank=True)
    check_in_lng = models.FloatField("Longitude arrivée", null=True, blank=True)
    distance_m = models.PositiveIntegerField("Distance au bureau (m)", null=True, blank=True)
    on_site = models.BooleanField("Pointé sur site", default=False)

    class Meta:
        verbose_name = "Présence"
        verbose_name_plural = "Présences"
        ordering = ["-date"]
        unique_together = ("employee", "date")

    def __str__(self):
        return f"{self.employee.full_name} — {self.date}"

    @property
    def worked(self):
        if self.check_in and self.check_out:
            h = (self.check_out - self.check_in).total_seconds() / 3600
            return f"{h:.1f} h"
        return "—"

    @property
    def status_color(self):
        return {"PRESENT": "emerald", "LATE": "amber", "ABSENT": "red",
                "LEAVE": "sky", "MISSION": "violet"}.get(self.status, "slate")


def hourly_rate(employee):
    """Taux horaire brut = salaire mensuel du contrat actif / heures légales mensuelles."""
    from django.conf import settings
    c = employee.contracts.filter(is_active=True).order_by("-start_date").first()
    salary = float(c.salary) if c and c.salary else 0.0
    monthly_h = getattr(settings, "LPM_MONTHLY_HOURS", 173.33) or 173.33
    return salary / monthly_h if salary else 0.0


def late_threshold_min():
    """Minute de la journée au-delà de laquelle une arrivée est « En retard » (08h10 par défaut)."""
    from django.conf import settings
    return getattr(settings, "LPM_WORK_START_MIN", 8 * 60 + 10)


def status_for_checkin(check_in_local):
    """Statut d'arrivée : « En retard » si pointage strictement après le seuil, sinon « Présent »."""
    minutes = check_in_local.hour * 60 + check_in_local.minute
    return Attendance.Status.LATE if minutes > late_threshold_min() else Attendance.Status.PRESENT


def attendance_minutes_late(rec):
    """Minutes de retard d'un pointage (0 si à l'heure / absent / congé).

    Mesurées à partir du seuil de retard (08h10) : une arrivée à 08h25 = 15 min.
    """
    if rec.status != Attendance.Status.LATE or not rec.check_in:
        return 0
    lt = timezone.localtime(rec.check_in)
    return max(0, (lt.hour * 60 + lt.minute) - late_threshold_min())


def salary_impacts(month_start, employees=None):
    """Incidences salariales du mois : retards + absences → retenue proportionnelle.

    La retenue retard (prorata) est multipliée par le **coefficient global**
    (PayrollSetting). Un **ajustement manuel** (SalaryAdjustment) sur l'employé/mois
    force le montant final. Retourne des dicts
    {employee, late, late_minutes, absent, computed, deduction, overridden, reason}.
    """
    from datetime import date as _date
    from django.conf import settings
    # Bornes du mois.
    if month_start.month == 12:
        nxt = _date(month_start.year + 1, 1, 1)
    else:
        nxt = _date(month_start.year, month_start.month + 1, 1)
    qs = employees if employees is not None else clocking_employees()
    hours_per_day = getattr(settings, "LPM_WORK_HOURS_PER_DAY", 8)
    coeff = float(PayrollSetting.current().late_coefficient)
    # Les jours antérieurs à la date de début du pointage ne comptent pas.
    period_start = month_start
    start = attendance_start_date()
    if start and start > period_start:
        period_start = start
    # Ajustements manuels du mois (montant forcé) indexés par employé.
    overrides = {
        a.employee_id: a for a in SalaryAdjustment.objects.filter(month=month_start)
    }
    rows = []
    for emp in qs:
        recs = Attendance.objects.filter(employee=emp, date__gte=period_start, date__lt=nxt)
        late = absent = late_min = 0
        for r in recs:
            if r.status == Attendance.Status.LATE:
                late += 1
                late_min += attendance_minutes_late(r)
            elif r.status == Attendance.Status.ABSENT:
                absent += 1
        rate = hourly_rate(emp)
        computed = int(round(rate * (late_min / 60.0) * coeff + rate * hours_per_day * absent))
        ov = overrides.get(emp.id)
        deduction = int(ov.amount) if ov else computed
        rows.append({
            "employee": emp, "late": late, "late_minutes": late_min,
            "absent": absent, "computed": computed, "deduction": deduction,
            "overridden": ov is not None, "reason": ov.reason if ov else "",
        })
    return rows


def clocking_roles():
    """Rôles tenus de pointer : employés, stagiaires, responsables et RH (pas le CEO/admin)."""
    from accounts.models import Role
    return [Role.EMPLOYE, Role.STAGIAIRE, Role.MANAGER, Role.RH]


def must_clock(user):
    """Vrai si l'utilisateur doit pointer (employé, stagiaire, responsable, RH)."""
    prop = getattr(user, "must_clock", None)
    if isinstance(prop, bool):
        return prop
    return getattr(user, "effective_role", None) in set(clocking_roles())


def clocking_employees():
    """Employés concernés par le pointage (employés, stagiaires, responsables, RH).

    Inclut les employés « En congé » : ils restent visibles dans la feuille de
    présence (marqués « En congé » par `ensure_absences`) au lieu de disparaître.
    Les comptes suspendus / sortis des effectifs sont exclus."""
    from employees.models import WORKFORCE_STATUSES
    return Employee.objects.filter(
        status__in=WORKFORCE_STATUSES,
        user__role__in=clocking_roles(),
    )


def attendance_start_date():
    """Date de début du pointage : avant elle, rien n'est compté.

    Priorité au réglage en base (OfficeLocation), puis à la variable
    d'environnement LPM_ATTENDANCE_START. None = aucune restriction.
    """
    loc = OfficeLocation.current()
    if loc and loc.start_date:
        return loc.start_date
    from django.conf import settings
    return getattr(settings, "LPM_ATTENDANCE_START", None)


def ensure_absences(day):
    """Marque « Absent » (ou « En congé ») les employés devant pointer et sans pointage.

    N'agit que pour aujourd'hui (après l'heure de début) ou les jours passés ;
    ne touche jamais aux pointages déjà enregistrés. Un congé approuvé prime.
    Les jours antérieurs à la date de début du pointage sont ignorés.
    """
    from django.conf import settings
    today = timezone.localdate()
    if day > today:
        return
    start = attendance_start_date()
    if start and day < start:
        return
    if day == today:
        now = timezone.localtime()
        if now.hour * 60 + now.minute < getattr(settings, "LPM_WORK_START_MIN", 480):
            return  # avant l'heure de début, on ne marque pas encore absent
    from conges.models import LeaveRequest
    existing = set(Attendance.objects.filter(date=day).values_list("employee_id", flat=True))
    on_leave = set(LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED, start_date__lte=day, end_date__gte=day,
    ).values_list("employee_id", flat=True))
    # Employés en mission ce jour-là → comptés « En mission » (jamais absents).
    on_mission = set(Mission.objects.filter(
        start_date__lte=day, end_date__gte=day,
    ).values_list("employee_id", flat=True))

    def _status_for(emp_id):
        if emp_id in on_mission:
            return Attendance.Status.MISSION
        if emp_id in on_leave:
            return Attendance.Status.LEAVE
        return Attendance.Status.ABSENT

    to_create = [
        Attendance(employee=emp, date=day, status=_status_for(emp.id))
        for emp in clocking_employees() if emp.id not in existing
    ]
    if to_create:
        Attendance.objects.bulk_create(to_create)


def notify_ending_contracts(today=None):
    """Notifie RH/CEO/admin des contrats à durée déterminée (CDD/Stage/Temporaire)
    arrivant à échéance, à J-7, J-1 et le jour J. Renvoie le nombre de contrats signalés."""
    from accounts.models import Role, User
    from django.urls import reverse
    from notifications.models import Notification, notify
    today = today or timezone.localdate()
    recips, seen = [], set()
    for u in (list(User.objects.filter(role__in=[Role.RH, Role.CEO, Role.ADMIN], is_active=True))
              + list(User.objects.filter(is_superuser=True, is_active=True))):
        if u.id not in seen:
            seen.add(u.id)
            recips.append(u)
    if not recips:
        return 0
    labels = {"CDD": "CDD", "STAGE": "stage", "TEMP": "mission temporaire"}
    url = reverse("hr:contracts")
    count = 0
    qs = (Contract.objects.filter(is_active=True, end_date__isnull=False)
          .exclude(type="CDI").select_related("employee__user"))
    for c in qs:
        delta = (c.end_date - today).days
        # Rappel chaque jour à partir de 4 jours avant la fin (J-4 → jour J).
        if 0 <= delta <= 4:
            kind = labels.get(c.type, "contrat")
            quand = "aujourd'hui" if delta == 0 else ("demain" if delta == 1 else f"dans {delta} jours")
            title = f"Fin de {kind} — {c.employee.full_name}"
            for u in recips:
                # Idempotent : une seule notification par jour / contrat / destinataire,
                # quel que soit le nombre d'exécutions du runner quotidien.
                if Notification.objects.filter(
                        recipient=u, title=title, created_at__date=today).exists():
                    continue
                notify(u, title,
                       f"Le {kind} de {c.employee.full_name} arrive à échéance {quand} "
                       f"({c.end_date:%d/%m/%Y}).",
                       Notification.Level.WARNING, url)
            count += 1
    return count


# --------------------------------------------------------------------------- #
# Missions (ordre de mission) — enregistrées par RH / CEO / admin
# --------------------------------------------------------------------------- #
class Mission(models.Model):
    """Mission/déplacement professionnel : l'employé concerné est « En mission »
    les jours couverts (compté présent, sans pointage ni retenue)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="missions",
                                 verbose_name="Personne en mission")
    start_date = models.DateField("Du")
    end_date = models.DateField("Au")
    destination = models.CharField("Destination / lieu", max_length=150, blank=True)
    objet = models.TextField("Objet de la mission", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name="missions_creees", verbose_name="Enregistrée par")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Mission"
        verbose_name_plural = "Missions"
        ordering = ["-start_date"]

    def __str__(self):
        return f"Mission {self.employee.full_name} ({self.start_date}→{self.end_date})"

    @property
    def is_current(self):
        return self.start_date <= timezone.localdate() <= self.end_date

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1


def apply_mission_to_attendance(mission):
    """Marque « En mission » les jours déjà écoulés/en cours de la mission,
    en écrasant un éventuel « Absent » et sans toucher à un pointage réel."""
    from datetime import timedelta
    today = timezone.localdate()
    d = mission.start_date
    while d <= mission.end_date and d <= today:
        rec, created = Attendance.objects.get_or_create(
            employee=mission.employee, date=d,
            defaults={"status": Attendance.Status.MISSION})
        # On ne convertit que les jours sans présence réelle (absent/congé/rien).
        if not created and rec.check_in is None and rec.status in (
                Attendance.Status.ABSENT, Attendance.Status.LEAVE):
            rec.status = Attendance.Status.MISSION
            rec.save(update_fields=["status"])
        d += timedelta(days=1)


# --------------------------------------------------------------------------- #
# Paramètres de paie + ajustements manuels de retenue
# --------------------------------------------------------------------------- #
class PayrollSetting(models.Model):
    """Réglage global de la paie (singleton). Modifiable par CEO / RH / admin."""

    late_coefficient = models.DecimalField(
        "Coefficient de retenue sur retard", max_digits=5, decimal_places=2, default=1,
        help_text="Multiplie la retenue prorata des retards (1,00 = 100 %, 0,50 = moitié, 0 = aucune).")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètre de paie"
        verbose_name_plural = "Paramètres de paie"

    def __str__(self):
        return f"Coefficient retard : {self.late_coefficient}"

    @classmethod
    def current(cls):
        return cls.objects.first() or cls()


class SalaryAdjustment(models.Model):
    """Montant de retenue forcé pour un employé sur un mois (ajustement manuel)."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="salary_adjustments")
    month = models.DateField("Mois (1er jour)")
    amount = models.DecimalField("Montant retenu (FCFA)", max_digits=12, decimal_places=0, default=0)
    reason = models.CharField("Motif", max_length=200, blank=True)
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name="ajustements_paie")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ajustement de retenue"
        verbose_name_plural = "Ajustements de retenue"
        unique_together = ("employee", "month")

    def __str__(self):
        return f"{self.employee.full_name} — {self.month:%m/%Y} : {self.amount} FCFA"


# --------------------------------------------------------------------------- #
# Recrutement
# --------------------------------------------------------------------------- #
class JobOpening(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        CLOSED = "CLOSED", "Clôturé"

    title = models.CharField("Poste à pourvoir", max_length=150)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name="openings")
    description = models.TextField("Description du poste", blank=True)
    positions = models.PositiveSmallIntegerField("Nombre de postes", default=1)
    status = models.CharField("Statut", max_length=8, choices=Status.choices, default=Status.OPEN)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Offre d'emploi"
        verbose_name_plural = "Offres d'emploi"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Candidate(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "Nouvelle candidature"
        SHORTLIST = "SHORTLIST", "Présélectionné"
        INTERVIEW = "INTERVIEW", "En entretien"
        HIRED = "HIRED", "Recruté"
        REJECTED = "REJECTED", "Non retenu"

    opening = models.ForeignKey(JobOpening, on_delete=models.CASCADE, related_name="candidates")
    full_name = models.CharField("Nom du candidat", max_length=150)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Téléphone", max_length=40, blank=True)
    cv = models.FileField("CV", upload_to="hr/cv/%Y/", blank=True, null=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.NEW)
    rating = models.PositiveSmallIntegerField("Note (/5)", default=0)
    notes = models.TextField("Notes", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Candidature"
        ordering = ["-created_at"]

    def __str__(self):
        return self.full_name

    @property
    def status_color(self):
        return {"NEW": "slate", "SHORTLIST": "sky", "INTERVIEW": "amber",
                "HIRED": "emerald", "REJECTED": "red"}.get(self.status, "slate")


class Interview(models.Model):
    class Reco(models.TextChoices):
        FAVORABLE = "FAVORABLE", "Favorable"
        RESERVE = "RESERVE", "Avec réserve"
        DEFAVORABLE = "DEFAVORABLE", "Défavorable"

    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name="interviews")
    scheduled_at = models.DateTimeField("Date & heure")
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                    related_name="entretiens")
    mode = models.CharField("Mode", max_length=12, default="Présentiel")
    feedback = models.TextField("Compte-rendu", blank=True)
    recommendation = models.CharField("Recommandation", max_length=12, choices=Reco.choices, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Entretien"
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"Entretien — {self.candidate.full_name}"


# --------------------------------------------------------------------------- #
# Évaluation / Performance
# --------------------------------------------------------------------------- #
class Evaluation(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SUBMITTED = "SUBMITTED", "Soumise"
        VALIDATED = "VALIDATED", "Validée"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="evaluations")
    period = models.CharField("Période", max_length=40, help_text="ex. Année 2026 — S1")
    evaluator = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                  related_name="evaluations_menees")
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    comment = models.TextField("Appréciation générale", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Évaluation"
        verbose_name_plural = "Évaluations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Évaluation {self.employee.full_name} — {self.period}"

    @property
    def score(self):
        """Score global pondéré (sur 100) à partir des objectifs/KPI."""
        objs = list(self.objectives.all())
        total_w = sum(o.weight for o in objs)
        if not total_w:
            return 0
        return round(sum(o.rating * o.weight for o in objs) / total_w)

    @property
    def score_color(self):
        s = self.score
        return "emerald" if s >= 75 else "amber" if s >= 50 else "red"


class Objective(models.Model):
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name="objectives")
    label = models.CharField("Objectif", max_length=200)
    kpi = models.CharField("Indicateur (KPI)", max_length=200, blank=True)
    weight = models.PositiveSmallIntegerField("Poids (%)", default=20)
    rating = models.PositiveSmallIntegerField("Atteinte (%)", default=0)
    comment = models.CharField("Commentaire", max_length=255, blank=True)

    class Meta:
        verbose_name = "Objectif / KPI"
        ordering = ["id"]

    def __str__(self):
        return self.label


# --------------------------------------------------------------------------- #
# Onboarding
# --------------------------------------------------------------------------- #
class OnboardingPlan(models.Model):
    """Parcours d'intégration type par profil."""
    name = models.CharField("Nom du parcours", max_length=200)
    description = models.TextField(blank=True)
    role_target = models.CharField("Rôle visé", max_length=50, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="onboarding_plans")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Plan d'intégration"

    def __str__(self):
        return self.name


class OnboardingStep(models.Model):
    """Étape d'un plan d'intégration."""
    plan = models.ForeignKey(OnboardingPlan, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveSmallIntegerField("Ordre", default=1)
    title = models.CharField("Titre", max_length=200)
    description = models.TextField(blank=True)
    day = models.PositiveSmallIntegerField("Jour J+", default=1)
    document = models.ForeignKey("documents.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="onboarding_steps")

    class Meta:
        verbose_name = "Étape d'intégration"
        ordering = ["order"]

    def __str__(self):
        return f"J+{self.day} — {self.title}"


class OnboardingProgress(models.Model):
    """Suivi d'intégration individuel pour un employé."""
    employee = models.ForeignKey("employees.Employee", on_delete=models.CASCADE, related_name="onboarding_progress")
    plan = models.ForeignKey(OnboardingPlan, on_delete=models.CASCADE, related_name="progress")
    started_at = models.DateField("Démarré le", default=timezone.now)
    completed_steps = models.ManyToManyField(OnboardingStep, blank=True, related_name="completed_by")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Suivi d'intégration"
        unique_together = ("employee", "plan")

    def __str__(self):
        return f"{self.employee} — {self.plan}"

    @property
    def completion_rate(self):
        total = self.plan.steps.count()
        done = self.completed_steps.count()
        return round(done / total * 100) if total else 0
