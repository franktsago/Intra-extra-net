"""Messagerie interne & externe (conversations 1-à-1 entre utilisateurs).

Règles de cloisonnement :
  • Un collaborateur interne peut écrire à n'importe quel utilisateur actif
    (interne ou externe — client / partenaire / fournisseur / consultant).
  • Un utilisateur externe ne peut écrire qu'à des collaborateurs internes
    (jamais à un autre externe), conformément à la séparation intranet/extranet.
"""

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from accounts.models import INTRANET_ROLES

# Délai pendant lequel l'expéditeur peut modifier son message (10 minutes).
EDIT_WINDOW_SECONDS = 10 * 60


class Message(models.Model):
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sent_messages", verbose_name="Expéditeur",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="received_messages", verbose_name="Destinataire",
    )
    body = models.TextField("Message", blank=True)
    attachment = models.FileField("Pièce jointe", upload_to="messages/%Y/%m/", blank=True, null=True)
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="replies", verbose_name="En réponse à")
    is_pinned = models.BooleanField("Épinglé", default=False)
    is_forwarded = models.BooleanField("Transféré", default=False)
    deleted_for_all = models.BooleanField("Supprimé pour tous", default=False)
    deleted_for = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+")
    is_read = models.BooleanField("Lu", default=False)
    created_at = models.DateTimeField("Envoyé le", default=timezone.now)
    edited_at = models.DateTimeField("Modifié le", null=True, blank=True)

    class Meta:
        verbose_name = "Message"
        verbose_name_plural = "Messages"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read"]),
            models.Index(fields=["sender", "recipient"]),
        ]

    def __str__(self):
        return f"{self.sender} → {self.recipient} ({self.created_at:%d/%m %H:%M})"

    @property
    def ext(self):
        import os
        return os.path.splitext(self.attachment.name)[1].lower().lstrip(".") if self.attachment else ""

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "svg", "bmp"}

    @property
    def is_audio(self):
        name = (self.attachment.name or "").lower() if self.attachment else ""
        return (self.ext in {"mp3", "wav", "oga", "m4a", "aac", "opus", "weba"}
                or "voix" in name or "voice" in name)

    @property
    def is_video(self):
        if self.is_audio:
            return False
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}

    @property
    def short(self):
        if self.deleted_for_all:
            return "Message supprimé"
        if self.body:
            return self.body[:60]
        return "🎤 Message vocal" if self.is_audio else ("📎 Pièce jointe" if self.attachment else "")

    @property
    def within_edit_window(self):
        """Le message texte est-il encore modifiable (≤ 10 min, non supprimé) ?"""
        if self.deleted_for_all or not self.body:
            return False
        return (timezone.now() - self.created_at).total_seconds() <= EDIT_WINDOW_SECONDS

    @property
    def reaction_summary(self):
        return _reaction_summary(self)


def _reaction_summary(msg):
    """Regroupe les réactions par emoji avec le nombre et les noms (qui a réagi)."""
    groups = {}
    for r in msg.reactions.select_related("user").all():
        groups.setdefault(r.emoji, []).append(r.user.get_full_name() or r.user.username)
    return [{"emoji": e, "count": len(names), "names": ", ".join(names)}
            for e, names in groups.items()]


def can_delete_message(user, msg):
    """Peut supprimer un message direct : l'expéditeur, ou RH/CEO/admin."""
    return (msg.sender_id == user.id or getattr(user, "is_rh", False)
            or user.is_superuser)


def external_contact_ids(user):
    """Interlocuteurs LPM autorisés pour un externe.

    Conformément au cloisonnement extranet, un client ne peut écrire qu'aux
    **responsables associés à ses projets** (chargés de compte) et à la
    **Direction Générale (CEO)** / l'administrateur principal.
    """
    from accounts.models import Role, User
    from extranet.models import Project
    lead_ids = set(
        Project.objects.filter(client=user)
        .exclude(internal_lead=None)
        .values_list("internal_lead_id", flat=True)
    )
    direction_ids = set(
        User.objects.filter(role__in=[Role.CEO, Role.ADMIN], is_active=True)
        .values_list("id", flat=True)
    )
    return lead_ids | direction_ids


def can_message(sender, recipient):
    """Indique si `sender` est autorisé à écrire à `recipient`."""
    if not recipient.is_active or sender.id == recipient.id:
        return False
    if sender.is_external:
        # Un externe ne peut écrire qu'à un responsable de SES projets ou au CEO.
        return recipient.role in INTRANET_ROLES and recipient.id in external_contact_ids(sender)
    # Un employé/stagiaire (interne non-encadrant) ne discute pas avec les clients.
    if not sender.is_manager and recipient.is_external:
        return False
    return True  # Un encadrant interne peut écrire à tout le monde.


def allowed_recipients(user):
    """Liste des destinataires autorisés pour `user`."""
    from accounts.models import EXTRANET_ROLES, Role, User
    qs = User.objects.filter(is_active=True).exclude(pk=user.pk)
    if user.is_external:
        qs = qs.filter(id__in=external_contact_ids(user))
    elif not user.is_manager:
        # Employé / stagiaire : uniquement des interlocuteurs internes (pas de clients).
        qs = qs.exclude(role__in=EXTRANET_ROLES)
    # Le super administrateur reste masqué des sélecteurs (sauf pour lui-même).
    if not user.is_admin_lpm:
        qs = qs.exclude(role=Role.ADMIN).exclude(is_superuser=True)
    return qs.order_by("first_name", "last_name")


def conversation_messages(user_a, user_b):
    """Tous les messages échangés entre deux utilisateurs."""
    return Message.objects.filter(
        Q(sender=user_a, recipient=user_b) | Q(sender=user_b, recipient=user_a)
    ).select_related("sender", "recipient")


def unread_count(user):
    return Message.objects.filter(recipient=user, is_read=False).count()


# --------------------------------------------------------------------------- #
# Chat de groupe (type WhatsApp) — discussions internes
# --------------------------------------------------------------------------- #
class ChatGroup(models.Model):
    name = models.CharField("Nom du groupe", max_length=120)
    description = models.CharField("Description", max_length=255, blank=True)
    is_general = models.BooleanField("Canal général (tous les employés)", default=False)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="chat_groups", verbose_name="Membres")
    admins = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name="chat_groups_admin", blank=True,
        verbose_name="Administrateurs du groupe")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="chat_groups_crees")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Groupe de discussion"
        verbose_name_plural = "Groupes de discussion"
        ordering = ["-is_general", "name"]

    def __str__(self):
        return self.name

    def last_message(self):
        return self.group_messages.select_related("sender").last()

    def unread_for(self, user):
        read = self.reads.filter(user=user).first()
        qs = self.group_messages.exclude(sender=user)
        if read and read.last_read_at:
            qs = qs.filter(created_at__gt=read.last_read_at)
        return qs.count()


class GroupMessage(models.Model):
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name="group_messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_messages")
    body = models.TextField("Message", blank=True)
    attachment = models.FileField("Pièce jointe", upload_to="chat/%Y/%m/", blank=True, null=True)
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="replies", verbose_name="En réponse à")
    is_pinned = models.BooleanField("Épinglé", default=False)
    is_forwarded = models.BooleanField("Transféré", default=False)
    is_system = models.BooleanField("Message système", default=False)
    deleted_for_all = models.BooleanField("Supprimé pour tous", default=False)
    deleted_for = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    edited_at = models.DateTimeField("Modifié le", null=True, blank=True)

    class Meta:
        verbose_name = "Message de groupe"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.sender} @ {self.group}"

    @property
    def ext(self):
        import os
        return os.path.splitext(self.attachment.name)[1].lower().lstrip(".") if self.attachment else ""

    @property
    def is_image(self):
        return self.ext in {"jpg", "jpeg", "png", "gif", "webp", "bmp"}

    @property
    def is_audio(self):
        name = (self.attachment.name or "").lower() if self.attachment else ""
        return (self.ext in {"mp3", "wav", "oga", "m4a", "aac", "opus", "weba"}
                or "voix" in name or "voice" in name)

    @property
    def is_video(self):
        if self.is_audio:
            return False
        return self.ext in {"mp4", "webm", "ogg", "mov", "m4v"}

    @property
    def short(self):
        if self.deleted_for_all:
            return "Message supprimé"
        if self.body:
            return self.body[:60]
        return "🎤 Message vocal" if self.is_audio else ("📎 Pièce jointe" if self.attachment else "")

    @property
    def within_edit_window(self):
        """Le message texte est-il encore modifiable (≤ 10 min, non supprimé) ?"""
        if self.deleted_for_all or self.is_system or not self.body:
            return False
        return (timezone.now() - self.created_at).total_seconds() <= EDIT_WINDOW_SECONDS

    @property
    def reaction_summary(self):
        return _reaction_summary(self)


class Call(models.Model):
    """Appel audio/vidéo (signalisation légère via polling ; média via Jitsi)."""
    class Status(models.TextChoices):
        RINGING = "RINGING", "Sonne"
        ONGOING = "ONGOING", "En cours"
        COMPLETED = "COMPLETED", "Terminé"
        MISSED = "MISSED", "Manqué"
        DECLINED = "DECLINED", "Refusé"

    caller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="calls_made")
    other = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.CASCADE, related_name="calls_received")
    group = models.ForeignKey("ChatGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="calls")
    mode = models.CharField(max_length=6, default="video")  # audio / video
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RINGING)
    room = models.CharField(max_length=120)
    created_at = models.DateTimeField(default=timezone.now)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Appel"
        ordering = ["-created_at"]

    @property
    def is_group(self):
        return self.group_id is not None

    @property
    def status_color(self):
        # En cours = vert ; reçu/terminé = bleu ; manqué/refusé = rouge.
        return {"ONGOING": "emerald", "COMPLETED": "lpm", "MISSED": "red",
                "DECLINED": "red", "RINGING": "amber"}.get(self.status, "slate")


class CallSignal(models.Model):
    """Message de signalisation WebRTC (offre / réponse / candidat ICE).

    Échangé entre les deux participants d'un appel direct (1-à-1) via polling :
    chaque pair lit les signaux émis par l'AUTRE pair après un identifiant donné.
    """
    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="signals")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    kind = models.CharField(max_length=10)  # offer / answer / ice
    payload = models.TextField()             # JSON (SDP ou candidat ICE)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["call", "id"])]


class ConversationPin(models.Model):
    """Épinglage d'une conversation (directe ou groupe) par un utilisateur."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversation_pins")
    other = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.CASCADE, related_name="+")
    group = models.ForeignKey("ChatGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Conversation épinglée"


class ConversationClear(models.Model):
    """Effacement d'une conversation directe pour UN seul utilisateur.

    On masque l'historique antérieur à `cleared_at` côté `user` uniquement :
    l'autre interlocuteur conserve toute sa conversation (façon WhatsApp).
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conv_clears")
    other = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    cleared_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Conversation effacée"
        unique_together = ("user", "other")


def clear_cutoffs(user):
    """Dictionnaire {other_id: cleared_at} des conversations effacées par `user`."""
    return dict(ConversationClear.objects.filter(user=user).values_list("other_id", "cleared_at"))


class Reaction(models.Model):
    """Réaction emoji à un message (direct ou de groupe), façon WhatsApp."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reactions")
    emoji = models.CharField(max_length=8)
    message = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE,
                                related_name="reactions")
    group_message = models.ForeignKey(GroupMessage, null=True, blank=True, on_delete=models.CASCADE,
                                      related_name="reactions")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Réaction"


class GroupRead(models.Model):
    group = models.ForeignKey(ChatGroup, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="group_reads")
    last_read_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("group", "user")


def get_general_group():
    """Canal général : tous les employés internes actifs. Créé/synchronisé à la volée."""
    from accounts.models import User
    grp, _ = ChatGroup.objects.get_or_create(
        is_general=True, defaults={"name": "Canal général — Tout le personnel"})
    internes = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
    grp.members.add(*internes)
    return grp


def my_groups(user):
    return ChatGroup.objects.filter(members=user).prefetch_related("members")


def unread_chat_count(user):
    return sum(g.unread_for(user) for g in ChatGroup.objects.filter(members=user))


def is_group_admin(user, group):
    """Administrateur d'un groupe : son créateur, un administrateur désigné,
    ou un RH/CEO/admin LPM (qui supervise toutes les discussions)."""
    if group.created_by_id == user.id or getattr(user, "is_rh", False) or user.is_superuser:
        return True
    return group.admins.filter(pk=user.pk).exists()


def can_delete_group_message(user, msg):
    """Supprimer un message de groupe : l'expéditeur ou un admin du groupe."""
    return msg.sender_id == user.id or is_group_admin(user, msg.group)
