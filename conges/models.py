"""Gestion des congés — conforme au Code du Travail camerounais.

Workflow de validation (cahier des charges) :
    1. L'employé soumet une demande.            → statut SOUMISE
    2. Le responsable reçoit une notification.
    3. Le responsable valide ou refuse.         → VALIDEE_RESP / REFUSEE
    4. Le RH reçoit la décision et entérine.     → VALIDEE_RH (définitif)
    5. Mise à jour automatique du solde.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from employees.models import Employee

from .cameroon import compter_jours_ouvrables, droit_annuel


class Holiday(models.Model):
    """Jour férié (fixe ou mobile). Saisi par le RH, notamment les fêtes mobiles."""

    date = models.DateField("Date", unique=True)
    name = models.CharField("Libellé", max_length=120)

    class Meta:
        verbose_name = "Jour férié"
        verbose_name_plural = "Jours fériés"
        ordering = ["date"]

    def __str__(self):
        return f"{self.date:%d/%m/%Y} — {self.name}"


class LeaveType(models.Model):
    """Type de congé (annuel, maladie, maternité, exceptionnel, sans solde…)."""

    name = models.CharField("Libellé", max_length=80, unique=True)
    code = models.CharField("Code", max_length=20, unique=True)
    is_paid = models.BooleanField("Payé", default=True)
    deducts_balance = models.BooleanField(
        "Décompté du solde annuel", default=True,
        help_text="Décoché pour la maladie, la maternité ou les permissions exceptionnelles.",
    )
    default_days = models.PositiveSmallIntegerField(
        "Durée légale (jours)", default=0,
        help_text="Durée de référence, ex. 98 jours pour la maternité (14 semaines).",
    )
    color = models.CharField("Couleur (hex)", max_length=7, default="#0073DE")
    legal_reference = models.CharField("Référence légale", max_length=120, blank=True)

    class Meta:
        verbose_name = "Type de congé"
        verbose_name_plural = "Types de congé"
        ordering = ["name"]

    def __str__(self):
        return self.name


# Circuit de validation selon le rôle du DEMANDEUR (du 1er au dernier niveau).
from accounts.models import Role  # noqa: E402

VALIDATION_CHAINS = {
    Role.EMPLOYE: [Role.MANAGER, Role.RH],
    Role.STAGIAIRE: [Role.MANAGER, Role.RH],  # même circuit que l'employé
    Role.MANAGER: [Role.RH, Role.CEO],
    Role.RH: [Role.CEO],
    Role.CEO: [Role.ADMIN],
    Role.ADMIN: [],  # l'admin principal n'a pas de validateur
}

ROLE_LABELS = {
    Role.MANAGER: "Responsable hiérarchique",
    Role.RH: "Service RH",
    Role.CEO: "Direction Générale (CEO)",
    Role.ADMIN: "Administration",
}


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "En cours de validation"
        APPROVED = "APPROVED", "Approuvée"
        REJECTED = "REJECTED", "Refusée"
        CANCELLED = "CANCELLED", "Annulée"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="leave_requests",
        verbose_name="Employé",
    )
    leave_type = models.ForeignKey(
        LeaveType, on_delete=models.PROTECT, related_name="requests",
        verbose_name="Type de congé",
    )
    start_date = models.DateField("Date de début")
    end_date = models.DateField("Date de fin")
    reason = models.TextField("Motif", blank=True)
    days_count = models.DecimalField(
        "Jours ouvrables", max_digits=5, decimal_places=1, default=0
    )
    status = models.CharField(
        "Statut", max_length=20, choices=Status.choices, default=Status.PENDING
    )
    current_level = models.PositiveSmallIntegerField("Niveau courant", default=0)
    reference = models.CharField("Référence document", max_length=30, blank=True)

    created_at = models.DateTimeField("Soumise le", default=timezone.now)
    decided_at = models.DateTimeField("Décidée le", null=True, blank=True)

    class Meta:
        verbose_name = "Demande de congé"
        verbose_name_plural = "Demandes de congé"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.full_name} — {self.leave_type.name} ({self.start_date:%d/%m} → {self.end_date:%d/%m})"

    def save(self, *args, **kwargs):
        feries = set(Holiday.objects.values_list("date", flat=True))
        self.days_count = compter_jours_ouvrables(self.start_date, self.end_date, feries)
        super().save(*args, **kwargs)

    # ----- Circuit de validation dynamique ----- #
    @property
    def chain(self):
        """Liste ordonnée des rôles validateurs selon le rôle du demandeur.

        Si l'employé n'a pas de responsable hiérarchique, l'étape « Responsable »
        est retirée : la RH valide alors directement.
        """
        base = list(VALIDATION_CHAINS.get(self.employee.user.role, [Role.RH]))
        if Role.MANAGER in base and not self.employee.manager_id:
            base = [r for r in base if r != Role.MANAGER] or [Role.RH]
        return base

    @property
    def current_role(self):
        """Rôle attendu pour la décision à l'étape courante (ou None si terminé)."""
        c = self.chain
        return c[self.current_level] if self.current_level < len(c) else None

    @property
    def total_levels(self):
        return len(self.chain)

    def steps(self):
        """Liste des étapes pour l'affichage (rôle, libellé, approbation éventuelle)."""
        approvals = {a.level: a for a in self.approvals.all()}
        out = []
        for i, role in enumerate(self.chain):
            out.append({
                "index": i + 1,
                "role": role,
                "label": ROLE_LABELS.get(role, role),
                "approval": approvals.get(i),
                "is_current": (self.status == self.Status.PENDING and i == self.current_level),
            })
        return out

    @property
    def is_final(self):
        return self.status in {self.Status.APPROVED, self.Status.REJECTED, self.Status.CANCELLED}

    @property
    def status_color(self):
        return {
            self.Status.PENDING: "amber",
            self.Status.APPROVED: "emerald",
            self.Status.REJECTED: "red",
            self.Status.CANCELLED: "slate",
        }.get(self.status, "slate")


class LeaveApproval(models.Model):
    """Trace d'une décision à un niveau du circuit de validation d'un congé."""

    leave = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="approvals"
    )
    level = models.PositiveSmallIntegerField("Niveau")
    role = models.CharField("Rôle validateur", max_length=20)
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="leave_approvals", verbose_name="Validé par",
    )
    approved = models.BooleanField("Approuvé", default=True)
    comment = models.CharField("Commentaire", max_length=255, blank=True)
    decided_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Validation de congé"
        verbose_name_plural = "Validations de congé"
        ordering = ["level"]

    def __str__(self):
        return f"{self.leave} — niveau {self.level} ({'OK' if self.approved else 'refus'})"


class LeaveBalanceAdjustment(models.Model):
    """Ajustement manuel du solde (report N-1, correction RH, solde de tout compte)."""

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="balance_adjustments"
    )
    days = models.DecimalField("Jours (+/-)", max_digits=5, decimal_places=1)
    reason = models.CharField("Motif", max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Ajustement de solde"
        verbose_name_plural = "Ajustements de solde"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.full_name}: {self.days:+} j ({self.reason})"


def solde_conges(employee):
    """Calcule le solde de congé annuel d'un employé (jours ouvrables).

    Solde = droits acquis (1,5 j/mois + majorations) + ajustements − congés pris.
    """
    acquis = droit_annuel(
        mois_service=max(employee.seniority_months, 0),
        anciennete_annees=employee.seniority_years,
        est_mineur=_est_mineur(employee),
    )
    ajustements = sum(
        a.days for a in employee.balance_adjustments.all()
    )
    pris = sum(
        r.days_count for r in employee.leave_requests.filter(
            status=LeaveRequest.Status.APPROVED,
            leave_type__deducts_balance=True,
        )
    )
    return round(float(acquis) + float(ajustements) - float(pris), 1)


def _est_mineur(employee):
    if not employee.birth_date:
        return False
    today = timezone.localdate()
    age = today.year - employee.birth_date.year - (
        (today.month, today.day) < (employee.birth_date.month, employee.birth_date.day)
    )
    return age < 18
