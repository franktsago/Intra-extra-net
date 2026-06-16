"""RSE — Responsabilité Sociale et Environnementale."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class RSEIndicator(models.Model):
    """Indicateur RSE mesurable."""

    class Category(models.TextChoices):
        CARBON = "CARBON", "Empreinte carbone"
        DIVERSITY = "DIVERSITY", "Diversité & inclusion"
        SOCIAL = "SOCIAL", "Impact social"
        GOVERNANCE = "GOVERNANCE", "Gouvernance"

    category = models.CharField("Catégorie", max_length=12, choices=Category.choices)
    name = models.CharField("Nom de l'indicateur", max_length=200)
    value = models.DecimalField("Valeur", max_digits=12, decimal_places=2)
    unit = models.CharField("Unité", max_length=50)
    target = models.DecimalField("Objectif", max_digits=12, decimal_places=2, null=True, blank=True)
    year = models.IntegerField("Année", default=timezone.now().year)
    source = models.CharField("Source", max_length=200, blank=True)
    notes = models.TextField("Notes", blank=True)
    updated_at = models.DateTimeField("Mis à jour le", auto_now=True)

    class Meta:
        verbose_name = "Indicateur RSE"
        ordering = ["category", "name"]

    def __str__(self):
        return f"{self.name} ({self.year})"

    @property
    def progress_pct(self):
        if not self.target or self.target == 0:
            return 0
        return min(round(float(self.value) / float(self.target) * 100), 100)


class RSEInitiative(models.Model):
    """Initiative RSE (projet, action)."""

    class Category(models.TextChoices):
        SOLIDARITY = "SOLIDARITY", "Solidarité"
        PARTNERSHIP = "PARTNERSHIP", "Partenariat"
        VOLUNTEERING = "VOLUNTEERING", "Bénévolat"
        ECO = "ECO", "Écologie"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planifiée"
        ACTIVE = "ACTIVE", "En cours"
        DONE = "DONE", "Terminée"
        CANCELLED = "CANCELLED", "Annulée"

    title = models.CharField("Titre", max_length=200)
    description = models.TextField("Description", blank=True)
    category = models.CharField("Catégorie", max_length=12, choices=Category.choices, default=Category.OTHER)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField("Date de début", null=True, blank=True)
    end_date = models.DateField("Date de fin", null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="rse_initiatives", verbose_name="Responsable",
    )
    impact = models.TextField("Impact attendu / réalisé", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Initiative RSE"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class RSEReport(models.Model):
    """Rapport RSE annuel."""

    year = models.IntegerField("Année", unique=True)
    title = models.CharField("Titre", max_length=200)
    content = models.TextField("Contenu")
    published = models.BooleanField("Publié", default=False)
    document = models.FileField("Document PDF", upload_to="rse/reports/", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="rse_reports", verbose_name="Créé par",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Rapport RSE"
        ordering = ["-year"]

    def __str__(self):
        return f"Rapport RSE {self.year}"


class RSEResource(models.Model):
    """Ressource de sensibilisation RSE."""

    class Kind(models.TextChoices):
        GUIDE = "GUIDE", "Guide"
        ELEARNING = "ELEARNING", "E-learning"
        QUIZ = "QUIZ", "Quiz"
        ECO_TIP = "ECO_TIP", "Éco-geste"

    title = models.CharField("Titre", max_length=200)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices)
    content = models.TextField("Contenu")
    file = models.FileField("Fichier", upload_to="rse/resources/", null=True, blank=True)
    published = models.BooleanField("Publié", default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Ressource RSE"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class RSESupplier(models.Model):
    """Fournisseur évalué selon des critères RSE."""

    name = models.CharField("Nom", max_length=200)
    criteria = models.TextField("Critères RSE évalués")
    score = models.IntegerField("Score (0-10)", default=5)
    certified = models.BooleanField("Certifié", default=False)
    policy_url = models.URLField("URL politique RSE", blank=True)
    notes = models.TextField("Notes", blank=True)
    evaluated_at = models.DateField("Date d'évaluation", null=True, blank=True)

    class Meta:
        verbose_name = "Fournisseur RSE"
        ordering = ["-score"]

    def __str__(self):
        return self.name
