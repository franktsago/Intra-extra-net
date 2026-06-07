"""Module disciplinaire — conforme au Code du Travail camerounais.

Échelle des sanctions (art. 30 du Code du Travail, règlement intérieur type) :
    1. Avertissement écrit
    2. Blâme
    3. Mise à pied disciplinaire (1 à 8 jours, sans solde)
    4. Licenciement

Procédure et droits de la défense :
    • Toute sanction supérieure à l'avertissement requiert la convocation
      préalable du salarié à un entretien (respect du contradictoire).
    • La sanction doit être notifiée par écrit et motivée.
    • Une même faute ne peut être sanctionnée deux fois.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from employees.models import Employee


class DisciplinaryRecord(models.Model):
    class SanctionType(models.TextChoices):
        WARNING = "WARNING", "Avertissement écrit"
        REPRIMAND = "REPRIMAND", "Blâme"
        SUSPENSION = "SUSPENSION", "Mise à pied (1 à 8 jours)"
        DISMISSAL = "DISMISSAL", "Licenciement"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        CONVENED = "CONVENED", "Salarié convoqué (entretien préalable)"
        NOTIFIED = "NOTIFIED", "Sanction notifiée"
        CLOSED = "CLOSED", "Clôturée / contestée"

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="disciplinary_records",
        verbose_name="Employé",
    )
    sanction_type = models.CharField("Type de sanction", max_length=12, choices=SanctionType.choices)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    facts = models.TextField("Faits reprochés")
    fault_date = models.DateField("Date des faits", null=True, blank=True)

    # Entretien préalable (droits de la défense)
    hearing_date = models.DateField("Date de l'entretien préalable", null=True, blank=True)
    employee_defense = models.TextField("Explications du salarié", blank=True)

    # Mise à pied
    suspension_days = models.PositiveSmallIntegerField(
        "Durée de mise à pied (jours)", null=True, blank=True,
        help_text="1 à 8 jours maximum (Code du Travail).",
    )
    suspension_start = models.DateField("Début de la mise à pied", null=True, blank=True)

    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="sanctions_prononcees", verbose_name="Prononcée par",
    )
    notified_at = models.DateField("Notifiée le", null=True, blank=True)
    reference = models.CharField("Référence document", max_length=30, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Dossier disciplinaire"
        verbose_name_plural = "Dossiers disciplinaires"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_sanction_type_display()} — {self.employee.full_name}"

    @property
    def requires_hearing(self):
        """Toute sanction au-delà de l'avertissement requiert un entretien préalable."""
        return self.sanction_type != self.SanctionType.WARNING

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.sanction_type == self.SanctionType.SUSPENSION and self.suspension_days:
            if not (1 <= self.suspension_days <= 8):
                raise ValidationError(
                    {"suspension_days": "La mise à pied disciplinaire est limitée à 8 jours (Code du Travail)."}
                )
