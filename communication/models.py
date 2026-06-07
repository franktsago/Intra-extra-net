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
