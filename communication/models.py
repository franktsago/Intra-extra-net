"""Actualités, annonces et communication interne."""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class News(models.Model):
    class Category(models.TextChoices):
        GENERAL = "GENERAL", "Information générale"
        RH = "RH", "Note RH"
        EVENT = "EVENT", "Événement"
        ALERT = "ALERT", "Annonce importante"

    class ModStatus(models.TextChoices):
        PENDING = "PENDING", "En attente de validation"
        APPROVED = "APPROVED", "Validée"
        REJECTED = "REJECTED", "Refusée"

    title = models.CharField("Titre", max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    category = models.CharField(
        "Catégorie", max_length=10, choices=Category.choices, default=Category.GENERAL
    )
    summary = models.CharField("Résumé", max_length=300, blank=True)
    content = models.TextField("Contenu")
    image = models.ImageField("Image", upload_to="actualites/%Y/%m/", blank=True, null=True)
    is_pinned = models.BooleanField("Épinglé (bannière)", default=False)
    is_published = models.BooleanField("Publié", default=True)
    # Modération : une actualité créée par un responsable doit être validée par
    # la RH / le CEO / l'administrateur avant d'apparaître dans le fil.
    mod_status = models.CharField(
        "Validation", max_length=10, choices=ModStatus.choices, default=ModStatus.APPROVED
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="actualites_validees", verbose_name="Validée par",
    )
    reviewed_at = models.DateTimeField("Validée le", null=True, blank=True)
    reject_reason = models.CharField("Motif de refus", max_length=300, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="actualites", verbose_name="Auteur",
    )
    created_at = models.DateTimeField("Publié le", default=timezone.now)

    class Meta:
        verbose_name = "Actualité"
        verbose_name_plural = "Actualités"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return self.title

    @property
    def is_visible(self):
        """Affichable dans le fil : publiée ET validée."""
        return self.is_published and self.mod_status == self.ModStatus.APPROVED

    @property
    def is_pending(self):
        return self.mod_status == self.ModStatus.PENDING

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "actualite"
            slug, i = base, 2
            while News.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug
        super().save(*args, **kwargs)


class Comment(models.Model):
    news = models.ForeignKey(News, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField("Commentaire")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Commentaire"
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire de {self.author} sur {self.news}"


class Event(models.Model):
    """Événement du calendrier interne (réunion, anniversaire, événement)."""

    class Kind(models.TextChoices):
        MEETING = "MEETING", "Réunion"
        EVENT = "EVENT", "Événement"
        BIRTHDAY = "BIRTHDAY", "Anniversaire"
        REMINDER = "REMINDER", "Rappel"

    title = models.CharField("Titre", max_length=200)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.EVENT)
    start = models.DateTimeField("Début")
    end = models.DateTimeField("Fin", null=True, blank=True)
    location = models.CharField("Lieu", max_length=200, blank=True)
    description = models.TextField("Description", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="evenements"
    )

    class Meta:
        verbose_name = "Événement"
        verbose_name_plural = "Calendrier & événements"
        ordering = ["start"]

    def __str__(self):
        return f"{self.title} ({self.start:%d/%m/%Y})"


class PressReview(models.Model):
    """Revue de presse — article ou citation dans les médias."""
    class MediaType(models.TextChoices):
        ONLINE = "ONLINE", "En ligne"
        PRINT = "PRINT", "Presse écrite"
        TV = "TV", "Télévision"
        RADIO = "RADIO", "Radio"
        SOCIAL = "SOCIAL", "Réseaux sociaux"

    class Tone(models.TextChoices):
        POSITIVE = "POSITIVE", "Positif"
        NEUTRAL = "NEUTRAL", "Neutre"
        NEGATIVE = "NEGATIVE", "Négatif"

    title = models.CharField("Titre de l'article", max_length=300)
    source = models.CharField("Source / Média", max_length=200)
    media_type = models.CharField("Type de média", max_length=8, choices=MediaType.choices, default=MediaType.ONLINE)
    tone = models.CharField("Tonalité", max_length=8, choices=Tone.choices, default=Tone.NEUTRAL)
    url = models.URLField("URL", blank=True)
    excerpt = models.TextField("Extrait / Citation", blank=True)
    published_at = models.DateField("Date de publication")
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="press_reviews")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Article de presse"
        verbose_name_plural = "Revue de presse"
        ordering = ["-published_at"]

    def __str__(self):
        return f"{self.title} — {self.source}"


class KeyMessage(models.Model):
    """Messages clés, éléments de langage & discours officiels."""
    class Category(models.TextChoices):
        PITCH = "PITCH", "Pitch / Présentation"
        FAQ = "FAQ", "FAQ interne"
        RESPONSE = "RESPONSE", "Réponse type"
        SPEECH = "SPEECH", "Discours officiel"
        OTHER = "OTHER", "Autre"

    category = models.CharField("Catégorie", max_length=10, choices=Category.choices)
    title = models.CharField("Titre", max_length=200)
    content = models.TextField("Contenu")
    audience = models.CharField("Audience cible", max_length=200, blank=True)
    is_active = models.BooleanField("Actif", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="key_messages")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Message clé"
        verbose_name_plural = "Messages clés"
        ordering = ["category", "title"]

    def __str__(self):
        return self.title


class Newsletter(models.Model):
    """Newsletter interne — historique et statistiques."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SENT = "SENT", "Envoyée"
        ARCHIVED = "ARCHIVED", "Archivée"

    subject = models.CharField("Sujet", max_length=200)
    content = models.TextField("Contenu")
    status = models.CharField("Statut", max_length=8, choices=Status.choices, default=Status.DRAFT)
    sent_at = models.DateTimeField("Envoyée le", null=True, blank=True)
    recipients_count = models.PositiveIntegerField("Destinataires", default=0)
    opens = models.PositiveIntegerField("Ouvertures", default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="newsletters")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Newsletter"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject

    @property
    def open_rate(self):
        return round(self.opens / self.recipients_count * 100, 1) if self.recipients_count else 0


class EventProject(models.Model):
    """Fiche projet événementiel."""
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planifié"
        ACTIVE = "ACTIVE", "En préparation"
        DONE = "DONE", "Terminé"
        CANCELLED = "CANCELLED", "Annulé"

    name = models.CharField("Nom de l'événement", max_length=200)
    event = models.OneToOneField(Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="project")
    brief = models.TextField("Brief", blank=True)
    location = models.CharField("Lieu", max_length=200, blank=True)
    date = models.DateField("Date prévue", null=True, blank=True)
    budget = models.DecimalField("Budget (FCFA)", max_digits=14, decimal_places=0, default=0)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PLANNED)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="event_projects")
    retro_planning = models.TextField("Rétroplanning", blank=True)
    notes = models.TextField("Notes", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Projet événement"
        ordering = ["-date"]

    def __str__(self):
        return self.name


class EventSupplier(models.Model):
    """Prestataire pour un événement."""
    event_project = models.ForeignKey(EventProject, on_delete=models.CASCADE, related_name="suppliers")
    name = models.CharField("Nom du prestataire", max_length=200)
    service = models.CharField("Prestation", max_length=200)
    contact = models.CharField("Contact", max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    quote_amount = models.DecimalField("Montant devis (FCFA)", max_digits=14, decimal_places=0, default=0)
    status = models.CharField("Statut", max_length=10,
        choices=[("PROSPECT", "Prospect"), ("CONTACTED", "Contacté"), ("CONFIRMED", "Confirmé"), ("CANCELLED", "Annulé")],
        default="PROSPECT")
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Prestataire événement"

    def __str__(self):
        return f"{self.name} — {self.service}"


class EventParticipant(models.Model):
    """Participant à un événement."""
    event_project = models.ForeignKey(EventProject, on_delete=models.CASCADE, related_name="participants")
    first_name = models.CharField("Prénom", max_length=100)
    last_name = models.CharField("Nom", max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField("Organisation", max_length=200, blank=True)
    status = models.CharField("Statut", max_length=10,
        choices=[("INVITED", "Invité"), ("REGISTERED", "Inscrit"), ("ATTENDED", "Présent"), ("ABSENT", "Absent")],
        default="INVITED")
    badge_printed = models.BooleanField("Badge imprimé", default=False)
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Participant"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class EventReport(models.Model):
    """Bilan post-événement."""
    event_project = models.OneToOneField(EventProject, on_delete=models.CASCADE, related_name="report")
    summary = models.TextField("Résumé")
    participants_count = models.PositiveIntegerField("Nombre de participants", default=0)
    budget_spent = models.DecimalField("Budget dépensé (FCFA)", max_digits=14, decimal_places=0, default=0)
    feedback = models.TextField("Retours clients / participants", blank=True)
    kpis = models.TextField("KPIs atteints", blank=True)
    learnings = models.TextField("Enseignements pour la suite", blank=True)
    photos_url = models.URLField("Lien album photos", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="event_reports")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Bilan post-événement"

    def __str__(self):
        return f"Bilan — {self.event_project.name}"
