"""Module Marketing : campagnes multicanal, calendrier éditorial, médiathèque.

S'appuie sur les marques clientes (business.Client) et peut être rattaché à un
projet (projects.Project). Couvre :
  • Campagnes (digitales, terrain, SMS, WhatsApp) avec objectifs & KPI.
  • Calendrier éditorial / publications réseaux sociaux + validation des contenus.
  • Bibliothèque média par marque (images, vidéos, logos, chartes).
"""

import os

from django.conf import settings
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    class Channel(models.TextChoices):
        DIGITAL = "DIGITAL", "Digitale"
        TERRAIN = "TERRAIN", "Terrain"
        SMS = "SMS", "SMS"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        MIX = "MIX", "Multicanal"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planifiée"
        ACTIVE = "ACTIVE", "En cours"
        DONE = "DONE", "Terminée"
        CANCELLED = "CANCELLED", "Annulée"

    name = models.CharField("Nom de la campagne", max_length=200)
    brand = models.ForeignKey(
        "business.Client", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="campaigns", verbose_name="Marque / Client",
    )
    project = models.ForeignKey(
        "projects.Project", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="campaigns", verbose_name="Projet lié",
    )
    channel = models.CharField("Canal", max_length=10, choices=Channel.choices, default=Channel.DIGITAL)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PLANNED)
    objectives = models.TextField("Objectifs", blank=True)
    budget = models.DecimalField("Budget (FCFA)", max_digits=14, decimal_places=0, default=0)
    start_date = models.DateField("Début", null=True, blank=True)
    end_date = models.DateField("Fin", null=True, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="campagnes", verbose_name="Responsable",
    )
    # KPI
    target_reach = models.PositiveIntegerField("Portée visée", null=True, blank=True)
    actual_reach = models.PositiveIntegerField("Portée atteinte", null=True, blank=True)
    leads = models.PositiveIntegerField("Leads générés", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Campagne"
        verbose_name_plural = "Campagnes"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    @property
    def reach_pct(self):
        if not self.target_reach:
            return 0
        return min(round((self.actual_reach or 0) / self.target_reach * 100), 100)

    @property
    def status_color(self):
        return {"PLANNED": "slate", "ACTIVE": "blue", "DONE": "emerald", "CANCELLED": "red"}.get(self.status, "slate")

    @property
    def channel_icon(self):
        return {"DIGITAL": "fa-globe", "TERRAIN": "fa-people-group", "SMS": "fa-comment-sms",
                "WHATSAPP": "fa-whatsapp", "MIX": "fa-layer-group"}.get(self.channel, "fa-bullhorn")


class Post(models.Model):
    """Publication du calendrier éditorial (réseaux sociaux) + validation."""

    class Platform(models.TextChoices):
        FACEBOOK = "FACEBOOK", "Facebook"
        INSTAGRAM = "INSTAGRAM", "Instagram"
        LINKEDIN = "LINKEDIN", "LinkedIn"
        TIKTOK = "TIKTOK", "TikTok"
        WHATSAPP = "WHATSAPP", "WhatsApp"
        X = "X", "X (Twitter)"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        PENDING = "PENDING", "À valider"
        APPROVED = "APPROVED", "Validé"
        PUBLISHED = "PUBLISHED", "Publié"
        REJECTED = "REJECTED", "Rejeté"

    brand = models.ForeignKey(
        "business.Client", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posts", verbose_name="Marque / Client",
    )
    campaign = models.ForeignKey(
        Campaign, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posts", verbose_name="Campagne",
    )
    platform = models.CharField("Plateforme", max_length=10, choices=Platform.choices, default=Platform.FACEBOOK)
    title = models.CharField("Titre", max_length=200)
    content = models.TextField("Contenu", blank=True)
    media = models.FileField("Visuel / Vidéo", upload_to="marketing/posts/%Y/%m/", blank=True, null=True)
    scheduled_at = models.DateTimeField("Programmé le")
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="posts_crees", verbose_name="Auteur",
    )
    validator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="posts_valides", verbose_name="Validé par",
    )
    review_comment = models.CharField("Commentaire de validation", max_length=255, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Publication"
        verbose_name_plural = "Calendrier éditorial"
        ordering = ["scheduled_at"]

    def __str__(self):
        return self.title

    @property
    def status_color(self):
        return {"DRAFT": "slate", "PENDING": "amber", "APPROVED": "sky",
                "PUBLISHED": "emerald", "REJECTED": "red"}.get(self.status, "slate")

    @property
    def platform_icon(self):
        return {"FACEBOOK": "fa-facebook", "INSTAGRAM": "fa-instagram", "LINKEDIN": "fa-linkedin",
                "TIKTOK": "fa-tiktok", "WHATSAPP": "fa-whatsapp", "X": "fa-x-twitter"}.get(self.platform, "fa-hashtag")

    @property
    def is_image(self):
        if not self.media:
            return False
        return os.path.splitext(self.media.name)[1].lower().lstrip(".") in {"jpg", "jpeg", "png", "gif", "webp"}


class MediaAsset(models.Model):
    """Bibliothèque média par marque (images, vidéos, logos, chartes)."""

    class Kind(models.TextChoices):
        IMAGE = "IMAGE", "Image"
        VIDEO = "VIDEO", "Vidéo"
        LOGO = "LOGO", "Logo"
        CHARTE = "CHARTE", "Charte graphique"
        DOC = "DOC", "Document"

    brand = models.ForeignKey(
        "business.Client", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="assets", verbose_name="Marque / Client",
    )
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.IMAGE)
    title = models.CharField("Titre", max_length=200)
    file = models.FileField("Fichier", upload_to="marketing/library/%Y/%m/")
    tags = models.CharField("Mots-clés", max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="assets_ajoutes")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Média"
        verbose_name_plural = "Médiathèque"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def ext(self):
        return os.path.splitext(self.file.name)[1].lower().lstrip(".")

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}

    @property
    def is_video(self):
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}


class Lead(models.Model):
    """Prospect / lead commercial."""
    class Status(models.TextChoices):
        NEW = "NEW", "Nouveau"
        CONTACTED = "CONTACTED", "Contacté"
        QUALIFIED = "QUALIFIED", "Qualifié"
        CONVERTED = "CONVERTED", "Converti"
        LOST = "LOST", "Perdu"

    class Source(models.TextChoices):
        SEO = "SEO", "SEO"
        SEA = "SEA", "SEA / Ads"
        SOCIAL = "SOCIAL", "Réseaux sociaux"
        REFERRAL = "REFERRAL", "Référence"
        EVENT = "EVENT", "Événement"
        OTHER = "OTHER", "Autre"

    first_name = models.CharField("Prénom", max_length=100)
    last_name = models.CharField("Nom", max_length=100)
    company = models.CharField("Entreprise", max_length=200, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    source = models.CharField("Source", max_length=10, choices=Source.choices, default=Source.OTHER)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.NEW)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_entries")
    notes = models.TextField("Notes", blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="leads_assignes")
    created_at = models.DateTimeField(default=timezone.now)
    last_contact = models.DateField("Dernier contact", null=True, blank=True)

    class Meta:
        verbose_name = "Lead / Prospect"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.company})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class SEOKeyword(models.Model):
    """Suivi de position SEO par mot-clé."""
    keyword = models.CharField("Mot-clé", max_length=200)
    url = models.URLField("URL cible", blank=True)
    position = models.PositiveSmallIntegerField("Position", null=True, blank=True)
    previous_position = models.PositiveSmallIntegerField("Position précédente", null=True, blank=True)
    search_volume = models.PositiveIntegerField("Volume de recherche/mois", null=True, blank=True)
    difficulty = models.PositiveSmallIntegerField("Difficulté (0-100)", null=True, blank=True)
    notes = models.TextField("Notes / Opportunités", blank=True)
    updated_at = models.DateField("Mis à jour le", null=True, blank=True)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="seo_keywords")

    class Meta:
        verbose_name = "Mot-clé SEO"
        ordering = ["position"]

    def __str__(self):
        return self.keyword

    @property
    def trend(self):
        if self.position is None or self.previous_position is None:
            return "stable"
        if self.position < self.previous_position:
            return "up"
        if self.position > self.previous_position:
            return "down"
        return "stable"


class AdCampaign(models.Model):
    """Campagne SEA / Ads (Google Ads, Meta Ads, etc.)."""
    class Platform(models.TextChoices):
        GOOGLE = "GOOGLE", "Google Ads"
        META = "META", "Meta Ads"
        TIKTOK = "TIKTOK", "TikTok Ads"
        LINKEDIN = "LINKEDIN", "LinkedIn Ads"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "En pause"
        ENDED = "ENDED", "Terminée"
        DRAFT = "DRAFT", "Brouillon"

    name = models.CharField("Nom", max_length=200)
    platform = models.CharField("Plateforme", max_length=10, choices=Platform.choices)
    status = models.CharField("Statut", max_length=6, choices=Status.choices, default=Status.DRAFT)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="ad_campaigns")
    budget = models.DecimalField("Budget total (FCFA)", max_digits=14, decimal_places=0, default=0)
    spent = models.DecimalField("Dépensé (FCFA)", max_digits=14, decimal_places=0, default=0)
    impressions = models.PositiveIntegerField("Impressions", default=0)
    clicks = models.PositiveIntegerField("Clics", default=0)
    conversions = models.PositiveIntegerField("Conversions", default=0)
    start_date = models.DateField("Début", null=True, blank=True)
    end_date = models.DateField("Fin", null=True, blank=True)
    notes = models.TextField("Résultats / Notes", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Campagne Ads"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_platform_display()})"

    @property
    def ctr(self):
        return round(self.clicks / self.impressions * 100, 2) if self.impressions else 0

    @property
    def cpa(self):
        return round(float(self.spent) / self.conversions) if self.conversions else 0

    @property
    def roas(self):
        return 0


class EmailCampaign(models.Model):
    """Campagne email marketing."""
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SCHEDULED = "SCHEDULED", "Planifiée"
        SENT = "SENT", "Envoyée"
        ARCHIVED = "ARCHIVED", "Archivée"

    subject = models.CharField("Objet", max_length=200)
    preview_text = models.CharField("Texte d'aperçu", max_length=200, blank=True)
    content = models.TextField("Contenu HTML", blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    campaign = models.ForeignKey(Campaign, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_campaigns")
    scheduled_at = models.DateTimeField("Envoi planifié", null=True, blank=True)
    sent_at = models.DateTimeField("Envoyé le", null=True, blank=True)
    recipients_count = models.PositiveIntegerField("Destinataires", default=0)
    opens = models.PositiveIntegerField("Ouvertures", default=0)
    clicks = models.PositiveIntegerField("Clics", default=0)
    unsubscribes = models.PositiveIntegerField("Désabonnements", default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Email marketing"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subject

    @property
    def open_rate(self):
        return round(self.opens / self.recipients_count * 100, 1) if self.recipients_count else 0

    @property
    def click_rate(self):
        return round(self.clicks / self.recipients_count * 100, 1) if self.recipients_count else 0


class ABTest(models.Model):
    """Test A/B."""
    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planifié"
        RUNNING = "RUNNING", "En cours"
        DONE = "DONE", "Terminé"

    name = models.CharField("Nom du test", max_length=200)
    hypothesis = models.TextField("Hypothèse")
    variant_a = models.TextField("Variante A")
    variant_b = models.TextField("Variante B")
    metric = models.CharField("Métrique mesurée", max_length=100)
    status = models.CharField("Statut", max_length=8, choices=Status.choices, default=Status.PLANNED)
    winner = models.CharField("Gagnant", max_length=1, blank=True, choices=[("A", "A"), ("B", "B")])
    result = models.TextField("Résultat / Décision actée", blank=True)
    start_date = models.DateField("Début", null=True, blank=True)
    end_date = models.DateField("Fin", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Test A/B"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name
