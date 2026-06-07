"""Gestion des projets & événements (cœur opérationnel de LPM).

Un projet possède un TYPE (campagne, événement, autre). Les projets de type
« événement » exploitent des champs spécifiques (lieu, date, participants,
prestataires) pour couvrir l'activité événementielle (roadshows, lancements,
activations, conférences, foires).

Avancement = % de phases terminées. Phases standard créées à l'ouverture :
Brief → Design → Validation → Déploiement → Reporting.
"""

import os

from django.conf import settings
from django.db import models
from django.utils import timezone

DEFAULT_PHASES = ["Brief", "Design", "Validation", "Déploiement", "Reporting"]


class Project(models.Model):
    class Kind(models.TextChoices):
        CAMPAIGN = "CAMPAIGN", "Campagne marketing"
        EVENT = "EVENT", "Événement"
        OTHER = "OTHER", "Autre projet"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "À démarrer"
        ACTIVE = "ACTIVE", "En cours"
        ON_HOLD = "ON_HOLD", "En pause"
        DONE = "DONE", "Terminé"
        CANCELLED = "CANCELLED", "Annulé"

    name = models.CharField("Nom du projet", max_length=200)
    code = models.CharField("Code", max_length=30, blank=True)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.CAMPAIGN)
    client = models.ForeignKey(
        "business.Client", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="projects", verbose_name="Client",
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="projets_diriges", verbose_name="Chef de projet",
    )
    team = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="projets_equipe",
        verbose_name="Équipe projet",
    )
    description = models.TextField("Description / Brief", blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PLANNED)
    start_date = models.DateField("Date de début", null=True, blank=True)
    deadline = models.DateField("Échéance", null=True, blank=True)
    budget = models.DecimalField("Budget alloué (FCFA)", max_digits=14, decimal_places=0, default=0)
    spent = models.DecimalField("Budget consommé (FCFA)", max_digits=14, decimal_places=0, default=0)

    # --- Champs spécifiques aux événements ---
    location = models.CharField("Lieu", max_length=200, blank=True)
    event_date = models.DateField("Date de l'événement", null=True, blank=True)
    providers = models.TextField("Prestataires", blank=True)
    attendees_expected = models.PositiveIntegerField("Participants attendus", null=True, blank=True)
    attendees_actual = models.PositiveIntegerField("Participants réels", null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Projet"
        verbose_name_plural = "Projets & événements"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating:
            if not self.code:
                self.code = f"PRJ-{timezone.localdate():%Y}-{self.pk:04d}"
                super().save(update_fields=["code"])
            for i, name in enumerate(DEFAULT_PHASES):
                self.phases.create(name=name, order=i)

    @property
    def progress(self):
        phases = list(self.phases.all())
        if not phases:
            return 0
        done = sum(1 for p in phases if p.status == Phase.Status.DONE)
        return round(done / len(phases) * 100)

    @property
    def budget_pct(self):
        if not self.budget:
            return 0
        return min(round(float(self.spent) / float(self.budget) * 100), 100)

    @property
    def is_over_budget(self):
        return self.budget and self.spent > self.budget

    @property
    def status_color(self):
        return {"PLANNED": "slate", "ACTIVE": "blue", "ON_HOLD": "amber",
                "DONE": "emerald", "CANCELLED": "red"}.get(self.status, "slate")


class Phase(models.Model):
    class Status(models.TextChoices):
        TODO = "TODO", "À faire"
        DOING = "DOING", "En cours"
        DONE = "DONE", "Terminée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField("Phase", max_length=120)
    order = models.PositiveSmallIntegerField("Ordre", default=0)
    status = models.CharField("Statut", max_length=6, choices=Status.choices, default=Status.TODO)
    due_date = models.DateField("Échéance", null=True, blank=True)

    class Meta:
        verbose_name = "Phase"
        ordering = ["order"]

    def __str__(self):
        return f"{self.project.name} — {self.name}"


class ProjectMedia(models.Model):
    """Rapport terrain / galerie du projet (photos, vidéos, documents)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="media")
    file = models.FileField("Fichier", upload_to="projects/%Y/%m/")
    caption = models.CharField("Légende", max_length=200, blank=True)
    latitude = models.FloatField("Latitude", null=True, blank=True)
    longitude = models.FloatField("Longitude", null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="project_media")
    created_at = models.DateTimeField(default=timezone.now)

    @property
    def has_geo(self):
        return self.latitude is not None and self.longitude is not None

    @property
    def maps_url(self):
        if self.has_geo:
            return f"https://www.google.com/maps?q={self.latitude},{self.longitude}"
        return ""

    class Meta:
        verbose_name = "Média de projet"
        verbose_name_plural = "Médias de projet"
        ordering = ["-created_at"]

    def __str__(self):
        return self.caption or os.path.basename(self.file.name)

    @property
    def ext(self):
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}

    @property
    def is_video(self):
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}
