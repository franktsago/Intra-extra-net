"""Notifications internes (in-app)."""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Notification(models.Model):
    class Level(models.TextChoices):
        INFO = "INFO", "Information"
        SUCCESS = "SUCCESS", "Succès"
        WARNING = "WARNING", "Avertissement"
        ERROR = "ERROR", "Alerte"

    class Audience(models.TextChoices):
        INTERNAL = "INTERNAL", "Intranet"
        EXTERNAL = "EXTERNAL", "Extranet"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="notifications", verbose_name="Destinataire",
    )
    title = models.CharField("Titre", max_length=200)
    message = models.CharField("Message", max_length=500, blank=True)
    level = models.CharField("Niveau", max_length=8, choices=Level.choices, default=Level.INFO)
    audience = models.CharField(
        "Périmètre", max_length=8, choices=Audience.choices, default=Audience.INTERNAL,
        help_text="Cloisonne les notifications intranet et extranet.",
    )
    url = models.CharField("Lien", max_length=300, blank=True)
    is_read = models.BooleanField("Lue", default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["recipient", "is_read"])]

    def __str__(self):
        return f"{self.title} → {self.recipient}"


def notify(recipient, title, message="", level=Notification.Level.INFO, url="", email=True):
    """Crée une notification in-app et l'envoie aussi par e-mail (multicanal).

    L'e-mail part via le backend configuré (console en dev, SMTP en prod via .env).
    Désactivable globalement avec NOTIFY_EMAIL=False, ou par appel (email=False).
    """
    if recipient is None:
        return None
    # Cloisonnement : le périmètre découle du destinataire (externe → extranet).
    audience = (Notification.Audience.EXTERNAL if getattr(recipient, "is_external", False)
                else Notification.Audience.INTERNAL)
    notif = Notification.objects.create(
        recipient=recipient, title=title, message=message, level=level, url=url,
        audience=audience,
    )
    if email and getattr(settings, "NOTIFY_EMAIL", True) and getattr(recipient, "email", ""):
        _send_email(recipient, title, message, url)
    return notif


def notify_internal_staff(title, message="", level=Notification.Level.INFO, url="",
                          exclude=None, email=False):
    """Diffuse une notification in-app à TOUT le personnel interne actif.

    `exclude` : un utilisateur (ou un itérable) à ne pas notifier (ex. l'intéressé).
    E-mail désactivé par défaut pour éviter d'inonder les boîtes lors d'une diffusion.
    Retourne le nombre de destinataires notifiés.
    """
    from accounts.models import INTRANET_ROLES, User
    exclude_ids = set()
    if exclude is not None:
        items = exclude if hasattr(exclude, "__iter__") else [exclude]
        exclude_ids = {getattr(u, "id", u) for u in items}
    qs = User.objects.filter(role__in=INTRANET_ROLES, is_active=True).exclude(id__in=exclude_ids)
    count = 0
    for u in qs:
        notify(u, title, message, level, url, email=email)
        count += 1
    return count


def _send_email(recipient, title, message, url):
    from django.core.mail import send_mail
    base = getattr(settings, "SITE_BASE_URL", "")
    link = (base + url) if url else base
    body = f"Bonjour {recipient.get_full_name() or recipient.username},\n\n{title}\n{message}"
    if link:
        body += f"\n\nAccéder : {link}"
    body += "\n\n— Intranet LPM Consulting Group"
    try:
        send_mail(subject=f"[LPM] {title}",
                  message=body,
                  from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                  recipient_list=[recipient.email], fail_silently=True)
    except Exception:
        pass


# --- Canaux SMS / WhatsApp (pluggables) ---
def send_sms(phone, message):
    """Envoi SMS — branchez ici votre fournisseur (ex. opérateur, Twilio).

    En l'absence de fournisseur configuré, l'envoi est journalisé (dev).
    """
    import logging
    logging.getLogger("lpm.sms").info("SMS → %s : %s", phone, message)
    return False  # passez à True une fois le fournisseur intégré


def send_whatsapp(phone, message):
    """Envoi WhatsApp — branchez l'API WhatsApp Business / fournisseur ici."""
    import logging
    logging.getLogger("lpm.whatsapp").info("WhatsApp → %s : %s", phone, message)
    return False
