"""Extranet : espaces clients/partenaires, projets, partage de fichiers, messagerie."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Project(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "À démarrer"
        ACTIVE = "ACTIVE", "En cours"
        ON_HOLD = "ON_HOLD", "En pause"
        DONE = "DONE", "Terminé"

    name = models.CharField("Nom du projet", max_length=200)
    reference = models.CharField("Référence", max_length=40, blank=True)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="projets_client", verbose_name="Client / partenaire",
        help_text="Utilisateur externe propriétaire de l'espace.",
    )
    internal_lead = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="projets_pilotes", verbose_name="Chargé de compte (LPM)",
    )
    description = models.TextField("Description", blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.ACTIVE)
    progress = models.PositiveSmallIntegerField("Avancement (%)", default=0)
    start_date = models.DateField("Date de début", null=True, blank=True)
    deadline = models.DateField("Échéance", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Projet (extranet)"
        verbose_name_plural = "Projets (extranet)"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class ProjectFile(models.Model):
    """Fichier échangé dans le cadre d'un projet (dans les deux sens)."""

    class Direction(models.TextChoices):
        TO_CLIENT = "TO_CLIENT", "LPM → Client"
        FROM_CLIENT = "FROM_CLIENT", "Client → LPM"

    class Validation(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Validé"
        REJECTED = "REJECTED", "Rejeté"

    class Kind(models.TextChoices):
        DOCUMENT = "DOCUMENT", "Document"
        REPORT = "REPORT", "Rapport"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="files")
    file = models.FileField("Fichier", upload_to="extranet/%Y/%m/")
    title = models.CharField("Intitulé", max_length=200)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.DOCUMENT)
    direction = models.CharField("Sens", max_length=12, choices=Direction.choices)
    validation = models.CharField(
        "Validation", max_length=10, choices=Validation.choices, default=Validation.PENDING
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="extranet_files"
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Fichier de projet"
        verbose_name_plural = "Fichiers de projet"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def ext(self):
        import os
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}

    @property
    def is_video(self):
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}


class ExtranetMessage(models.Model):
    """Message rattaché à un projet (communication client ↔ LPM)."""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField("Message")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Message extranet"
        ordering = ["created_at"]

    def __str__(self):
        return f"Message de {self.sender} ({self.created_at:%d/%m %H:%M})"


class Creative(models.Model):
    """Création graphique soumise à la validation du client (avec versions)."""

    class Status(models.TextChoices):
        IN_REVIEW = "IN_REVIEW", "En revue"
        CHANGES = "CHANGES", "Corrections demandées"
        APPROVED = "APPROVED", "Validée"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="creatives")
    title = models.CharField("Intitulé", max_length=200)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.IN_REVIEW)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="creatives_crees")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Création graphique"
        verbose_name_plural = "Créations graphiques"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def status_color(self):
        return {"IN_REVIEW": "blue", "CHANGES": "orange", "APPROVED": "emerald"}.get(self.status, "slate")

    @property
    def current_version(self):
        return self.versions.order_by("-number").first()


class CreativeVersion(models.Model):
    """Une version d'un visuel (V1, V2, V3…)."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        CHANGES = "CHANGES", "Corrections demandées"
        APPROVED = "APPROVED", "Validée"

    creative = models.ForeignKey(Creative, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveSmallIntegerField("Version", default=1)
    file = models.FileField("Visuel", upload_to="creatives/%Y/%m/")
    note = models.CharField("Note du graphiste", max_length=255, blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PENDING)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="creative_versions")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["number"]
        unique_together = ("creative", "number")

    def __str__(self):
        return f"{self.creative.title} — V{self.number}"

    @property
    def status_color(self):
        return {"PENDING": "slate", "CHANGES": "orange", "APPROVED": "emerald"}.get(self.status, "slate")

    @property
    def ext(self):
        import os
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}

    @property
    def is_video(self):
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}


class CreativeComment(models.Model):
    """Commentaire d'un client/LPM sur une version de visuel."""

    version = models.ForeignKey(CreativeVersion, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField("Commentaire")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} (V{self.version.number})"


class Ticket(models.Model):
    """Réclamation / incident / demande d'assistance ouverte par un client."""

    class Kind(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident"
        RECLAMATION = "RECLAMATION", "Réclamation"
        ASSISTANCE = "ASSISTANCE", "Demande d'assistance"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        RESOLVED = "RESOLVED", "Résolu"
        CLOSED = "CLOSED", "Fermé"

    reference = models.CharField("Référence", max_length=20, blank=True)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="tickets", verbose_name="Client",
    )
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tickets", verbose_name="Projet concerné",
    )
    kind = models.CharField("Type", max_length=12, choices=Kind.choices, default=Kind.RECLAMATION)
    subject = models.CharField("Objet", max_length=200)
    description = models.TextField("Description")
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="tickets_assignes", verbose_name="Pris en charge par",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réclamation / ticket"
        verbose_name_plural = "Réclamations / tickets"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference or 'TICKET'} — {self.subject}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.reference:
            self.reference = f"TIC-{self.created_at:%Y}-{self.pk:04d}"
            super().save(update_fields=["reference"])

    @property
    def status_color(self):
        return {"OPEN": "amber", "IN_PROGRESS": "blue",
                "RESOLVED": "emerald", "CLOSED": "slate"}.get(self.status, "slate")

    @property
    def is_open(self):
        return self.status in {self.Status.OPEN, self.Status.IN_PROGRESS}


class TicketReply(models.Model):
    """Échange dans un ticket (client ↔ support LPM)."""

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="replies")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField("Message")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Réponse de {self.author} ({self.created_at:%d/%m %H:%M})"


class ClientRequest(models.Model):
    """Demande soumise par un client (nouvelle campagne, devis, création, événement)."""

    class Kind(models.TextChoices):
        CAMPAIGN = "CAMPAIGN", "Nouvelle campagne"
        QUOTE = "QUOTE", "Demande de devis"
        GRAPHIC = "GRAPHIC", "Création graphique"
        EVENT = "EVENT", "Événement"

    class Status(models.TextChoices):
        SUBMITTED = "SUBMITTED", "Soumise"
        IN_REVIEW = "IN_REVIEW", "En étude"
        ACCEPTED = "ACCEPTED", "Acceptée"
        DECLINED = "DECLINED", "Refusée"

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="demandes", verbose_name="Client",
    )
    kind = models.CharField("Type de demande", max_length=10, choices=Kind.choices, default=Kind.CAMPAIGN)
    title = models.CharField("Intitulé", max_length=200)
    details = models.TextField("Détails / besoin")
    budget = models.DecimalField("Budget indicatif (FCFA)", max_digits=14, decimal_places=0,
                                 null=True, blank=True)
    deadline = models.DateField("Échéance souhaitée", null=True, blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.SUBMITTED)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Demande client"
        verbose_name_plural = "Demandes clients"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.title}"

    @property
    def status_color(self):
        return {"SUBMITTED": "amber", "IN_REVIEW": "blue",
                "ACCEPTED": "emerald", "DECLINED": "red"}.get(self.status, "slate")
