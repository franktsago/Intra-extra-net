"""Vues de la messagerie : boîte de réception, conversation, nouveau message."""

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import User

from accounts.utils import internal_required
from accounts.models import EXTRANET_ROLES, INTRANET_ROLES, Role

from .forms import GroupForm, GroupMessageForm, MessageForm, NewConversationForm
from .models import (
    ChatGroup, ConversationClear, ConversationPin, GroupMessage, GroupRead, Message,
    allowed_recipients, can_delete_group_message, can_delete_message, can_message,
    clear_cutoffs, conversation_messages, get_general_group, is_group_admin, my_groups,
)


@login_required
def inbox(request):
    """Hub de messagerie unifié (façon WhatsApp) : conversations directes + groupes
    dans une seule liste, avec la conversation active à droite."""
    me = request.user

    # --- Conversations directes ---
    cutoffs = clear_cutoffs(me)  # {other_id: date d'effacement} pour masquer l'historique
    msgs = (Message.objects.filter(Q(sender=me) | Q(recipient=me))
            .select_related("sender", "recipient").order_by("created_at"))
    convos = {}
    for m in msgs:
        other = m.recipient if m.sender_id == me.id else m.sender
        cut = cutoffs.get(other.id)
        if cut and m.created_at <= cut:
            continue  # message antérieur à l'effacement → masqué pour moi
        c = convos.setdefault(other.id, {"user": other, "last": None, "unread": 0})
        c["last"] = m
        if m.recipient_id == me.id and not m.is_read:
            c["unread"] += 1
    items = []
    for c in convos.values():
        items.append({
            "type": "direct", "key": "u%d" % c["user"].id, "user": c["user"],
            "name": c["user"].get_full_name() or c["user"].username,
            "last": c["last"], "last_at": c["last"].created_at, "unread": c["unread"],
        })

    # --- Groupes (internes + groupes mixtes avec clients) ---
    if me.is_internal:
        get_general_group()  # synchronise le canal général (personnel interne)
    for g in my_groups(me):
        last = g.last_message()
        items.append({
            "type": "group", "key": "g%d" % g.id, "group": g, "name": g.name,
            "last": last, "last_at": last.created_at if last else g.created_at,
            "unread": g.unread_for(me), "is_general": g.is_general,
        })
    # --- Épinglage des conversations (les épinglées remontent en tête) ---
    pins_u = set(ConversationPin.objects.filter(user=me, other__isnull=False)
                 .values_list("other_id", flat=True))
    pins_g = set(ConversationPin.objects.filter(user=me, group__isnull=False)
                 .values_list("group_id", flat=True))
    for it in items:
        it["pinned"] = (it["type"] == "direct" and it["user"].id in pins_u) or \
                       (it["type"] == "group" and it["group"].id in pins_g)
    items.sort(key=lambda x: x["last_at"], reverse=True)
    items.sort(key=lambda x: not x["pinned"])  # stable → épinglées d'abord

    # --- Conversation active ---
    conv = request.GET.get("conv", "")
    active = None
    if conv[:1] == "u" and conv[1:].isdigit():
        other = User.objects.filter(pk=int(conv[1:])).first()
        if other and can_message(me, other):
            Message.objects.filter(sender=other, recipient=me, is_read=False).update(is_read=True)
            conv_qs = conversation_messages(me, other).prefetch_related("deleted_for", "reactions")
            cut = cutoffs.get(other.id)
            if cut:
                conv_qs = conv_qs.filter(created_at__gt=cut)
            msgs_qs = list(conv_qs)
            active = {"type": "direct", "other": other, "msgs": msgs_qs, "key": "u%d" % other.id,
                      "pinned_msgs": [m for m in msgs_qs if m.is_pinned],
                      "form": MessageForm(), "can_admin": me.is_rh or me.is_superuser,
                      "pinned": other.id in pins_u,
                      "last_id": msgs_qs[-1].id if msgs_qs else 0,
                      "poll_kind": "d", "poll_pk": other.id}
    elif conv[:1] == "g" and conv[1:].isdigit():
        group = ChatGroup.objects.filter(pk=int(conv[1:])).first()
        if group and me in group.members.all():
            GroupRead.objects.update_or_create(
                group=group, user=me, defaults={"last_read_at": timezone.now()})
            msgs_qs = list(group.group_messages.select_related("sender").prefetch_related("deleted_for", "reactions"))
            active = {"type": "group", "group": group, "msgs": msgs_qs, "key": "g%d" % group.id,
                      "pinned_msgs": [m for m in msgs_qs if m.is_pinned],
                      "form": GroupMessageForm(), "is_admin": is_group_admin(me, group),
                      "pinned": group.id in pins_g,
                      "last_id": msgs_qs[-1].id if msgs_qs else 0,
                      "poll_kind": "g", "poll_pk": group.id}

    return render(request, "messaging/hub.html", {"items": items, "active": active})


def _hub(conv=None):
    """URL du hub, éventuellement avec une conversation active."""
    url = reverse("messaging:inbox")
    return url + ("?conv=%s" % conv if conv else "")


def _notify_added_to_group(group, actor, users):
    """Trace l'ajout de membres : message système « X a ajouté Y » dans la
    conversation + notification (cloche) à chaque personne ajoutée."""
    from notifications.models import notify
    users = [u for u in users if u.id != actor.id]
    if not users:
        return
    actor_name = actor.get_full_name() or actor.username
    names = ", ".join(u.get_full_name() or u.username for u in users)
    GroupMessage.objects.create(
        group=group, sender=actor, is_system=True,
        body=f"{actor_name} a ajouté {names}")
    url = reverse("messaging:group", args=[group.pk])
    for u in users:
        notify(u, "Ajout à un groupe",
               f"{actor_name} vous a ajouté au groupe « {group.name} ».", url=url)


def _notify_promoted_admin(group, actor, user):
    """Prévient une personne qu'elle vient d'être nommée administrateur du groupe :
    message système visible de tous + notification (cloche) dans son espace."""
    from notifications.models import notify
    actor_name = actor.get_full_name() or actor.username
    user_name = user.get_full_name() or user.username
    GroupMessage.objects.create(
        group=group, sender=actor, is_system=True,
        body=f"{actor_name} a nommé {user_name} administrateur")
    notify(user, "Vous êtes administrateur",
           f"{actor_name} vous a nommé administrateur du groupe « {group.name} ».",
           url=reverse("messaging:group", args=[group.pk]))


@login_required
def thread(request, pk):
    """Envoi d'un message direct ; affichage délégué au hub unifié."""
    me = request.user
    other = get_object_or_404(User, pk=pk)
    if not can_message(me, other):
        raise PermissionDenied("Vous ne pouvez pas échanger avec cet utilisateur.")
    if request.method == "POST":
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid() and (form.cleaned_data.get("body") or form.cleaned_data.get("attachment")):
            msg = form.save(commit=False)
            msg.sender = me
            msg.recipient = other
            rid = request.POST.get("reply_to")
            if rid:
                msg.reply_to = Message.objects.filter(
                    pk=rid).filter(Q(sender=me, recipient=other) | Q(sender=other, recipient=me)).first()
            msg.save()  # signalé par le badge « Messagerie » (pas de cloche)
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                from django.http import JsonResponse
                return JsonResponse({"ok": True, "id": msg.id})
        elif request.headers.get("X-Requested-With") == "XMLHttpRequest":
            from django.http import JsonResponse
            return JsonResponse({"ok": False}, status=400)
    return redirect(_hub("u%d" % other.pk))


@login_required
def message_delete(request, pk):
    """Supprime un message direct POUR TOUT LE MONDE (réservé à l'expéditeur).
    Le message laisse une trace « Ce message a été supprimé »."""
    msg = get_object_or_404(Message, pk=pk)
    me = request.user
    if me.id not in (msg.sender_id, msg.recipient_id):
        raise PermissionDenied("Accès refusé.")
    if msg.sender_id != me.id:
        raise PermissionDenied("Seul l'expéditeur peut supprimer pour tout le monde.")
    other_id = msg.recipient_id if msg.sender_id == me.id else msg.sender_id
    if request.method == "POST":
        msg.deleted_for_all = True
        msg.body = ""
        if msg.attachment:
            msg.attachment.delete(save=False)
            msg.attachment = None
        msg.save()
        flash.success(request, "Message supprimé pour tout le monde.")
    return redirect(_hub("u%d" % other_id))


@login_required
def forward(request, kind, pk):
    """Transfère un message vers une autre conversation (directe ou groupe).
    Le message transféré porte la mention « Transféré »."""
    import os
    from django.core.files.base import ContentFile
    me = request.user
    # Récupère le message source et vérifie l'accès.
    if kind == "d":
        src = get_object_or_404(Message, pk=pk)
        if me.id not in (src.sender_id, src.recipient_id):
            raise PermissionDenied("Accès refusé.")
    elif kind == "g":
        src = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
        if me not in src.group.members.all():
            raise PermissionDenied("Accès refusé.")
    else:
        from django.http import Http404
        raise Http404()
    if src.deleted_for_all:
        raise PermissionDenied("Ce message n'est plus disponible.")

    def _new_attachment(dest):
        if src.attachment:
            src.attachment.open("rb")
            dest.attachment.save(os.path.basename(src.attachment.name),
                                 ContentFile(src.attachment.read()), save=False)
            src.attachment.close()

    if request.method == "POST":
        target = request.POST.get("target", "")
        if target[:1] == "u" and target[1:].isdigit():
            other = get_object_or_404(User, pk=int(target[1:]))
            if not can_message(me, other):
                raise PermissionDenied("Destinataire non autorisé.")
            m = Message(sender=me, recipient=other, body=src.body, is_forwarded=True)
            _new_attachment(m)
            m.save()
            flash.success(request, "Message transféré.")
            return redirect(_hub("u%d" % other.id))
        if target[:1] == "g" and target[1:].isdigit() and me.is_internal:
            grp = get_object_or_404(ChatGroup, pk=int(target[1:]))
            if me not in grp.members.all():
                raise PermissionDenied("Groupe non autorisé.")
            m = GroupMessage(group=grp, sender=me, body=src.body, is_forwarded=True)
            _new_attachment(m)
            m.save()
            flash.success(request, "Message transféré.")
            return redirect(_hub("g%d" % grp.id))
        flash.error(request, "Choisissez une destination.")
    # GET : liste des destinations possibles.
    people = allowed_recipients(me)
    groups = my_groups(me) if me.is_internal else ChatGroup.objects.none()
    preview = src.short
    return render(request, "messaging/forward.html", {
        "people": people, "groups": groups, "kind": kind, "pk": pk, "preview": preview})


@login_required
def message_edit(request, pk):
    """Modifie le texte d'un message direct (expéditeur, dans les 10 min)."""
    msg = get_object_or_404(Message, pk=pk)
    me = request.user
    if msg.sender_id != me.id:
        raise PermissionDenied("Seul l'expéditeur peut modifier son message.")
    other_id = msg.recipient_id if msg.sender_id == me.id else msg.sender_id
    if request.method == "POST":
        if not msg.within_edit_window:
            flash.error(request, "Le délai de modification (10 minutes) est dépassé.")
        else:
            body = (request.POST.get("body") or "").strip()
            if body:
                msg.body = body
                msg.edited_at = timezone.now()
                msg.save(update_fields=["body", "edited_at"])
                flash.success(request, "Message modifié.")
    return redirect(_hub("u%d" % other_id))


@login_required
def message_delete_me(request, pk):
    """Supprime un message direct UNIQUEMENT pour soi (laisse une trace côté utilisateur)."""
    msg = get_object_or_404(Message, pk=pk)
    me = request.user
    if me.id not in (msg.sender_id, msg.recipient_id):
        raise PermissionDenied("Accès refusé.")
    other_id = msg.recipient_id if msg.sender_id == me.id else msg.sender_id
    if request.method == "POST":
        msg.deleted_for.add(me)
        flash.success(request, "Message supprimé pour vous.")
    return redirect(_hub("u%d" % other_id))


@login_required
def thread_delete(request, pk):
    """Efface la conversation avec un interlocuteur UNIQUEMENT pour soi.
    L'autre personne conserve son exemplaire (comportement façon WhatsApp)."""
    other = get_object_or_404(User, pk=pk)
    if request.method == "POST":
        ConversationClear.objects.update_or_create(
            user=request.user, other=other, defaults={"cleared_at": timezone.now()})
        flash.success(request, "Conversation supprimée pour vous.")
    return redirect("messaging:inbox")


@login_required
def new_message(request):
    me = request.user
    recipients = allowed_recipients(me)
    if request.method == "POST":
        form = NewConversationForm(request.POST, request.FILES, recipients=recipients)
        if form.is_valid():
            other = get_object_or_404(User, pk=form.cleaned_data["recipient"])
            if not can_message(me, other):
                raise PermissionDenied("Destinataire non autorisé.")
            Message.objects.create(
                sender=me, recipient=other,
                body=form.cleaned_data["body"],
                attachment=form.cleaned_data.get("attachment"),
            )
            # Pas de notification (cloche) : signalé par le badge « Messagerie ».
            flash.success(request, "Message envoyé.")
            return redirect("messaging:thread", pk=other.pk)
    else:
        form = NewConversationForm(recipients=recipients)
    return render(request, "messaging/new.html", {"form": form})


# --------------------------------------------------------------------------- #
# Chat de groupe (type WhatsApp)
# --------------------------------------------------------------------------- #
@internal_required
def chat_list(request):
    """Ancienne page « Discussions » → redirigée vers le hub unifié."""
    return redirect("messaging:inbox")


@login_required
def group_thread(request, pk):
    """Envoi d'un message de groupe ; affichage délégué au hub unifié."""
    group = get_object_or_404(ChatGroup, pk=pk)
    if request.user not in group.members.all():
        raise PermissionDenied("Vous ne faites pas partie de ce groupe.")
    if request.method == "POST":
        form = GroupMessageForm(request.POST, request.FILES)
        if form.is_valid() and (form.cleaned_data.get("body") or form.cleaned_data.get("attachment")):
            m = form.save(commit=False)
            m.group = group
            m.sender = request.user
            rid = request.POST.get("reply_to")
            if rid:
                m.reply_to = GroupMessage.objects.filter(pk=rid, group=group).first()
            m.save()
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                from django.http import JsonResponse
                return JsonResponse({"ok": True, "id": m.id})
        elif request.headers.get("X-Requested-With") == "XMLHttpRequest":
            from django.http import JsonResponse
            return JsonResponse({"ok": False}, status=400)
    return redirect(_hub("g%d" % group.pk))


@login_required
def group_message_delete(request, pk):
    """Supprime un message de groupe POUR TOUT LE MONDE (expéditeur ou admin du groupe).
    Laisse une trace « Ce message a été supprimé »."""
    m = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
    if request.user not in m.group.members.all():
        raise PermissionDenied("Accès refusé.")
    if not can_delete_group_message(request.user, m):
        raise PermissionDenied("Seul l'expéditeur ou un admin du groupe peut supprimer pour tous.")
    gid = m.group_id
    if request.method == "POST":
        m.deleted_for_all = True
        m.body = ""
        if m.attachment:
            m.attachment.delete(save=False)
            m.attachment = None
        m.save()
        flash.success(request, "Message supprimé pour tout le monde.")
    return redirect(_hub("g%d" % gid))


@login_required
def group_message_edit(request, pk):
    """Modifie le texte d'un message de groupe (expéditeur, dans les 10 min)."""
    m = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
    if m.sender_id != request.user.id:
        raise PermissionDenied("Seul l'expéditeur peut modifier son message.")
    if request.method == "POST":
        if not m.within_edit_window:
            flash.error(request, "Le délai de modification (10 minutes) est dépassé.")
        else:
            body = (request.POST.get("body") or "").strip()
            if body:
                m.body = body
                m.edited_at = timezone.now()
                m.save(update_fields=["body", "edited_at"])
                flash.success(request, "Message modifié.")
    return redirect(_hub("g%d" % m.group_id))


@login_required
def group_message_delete_me(request, pk):
    """Supprime un message de groupe UNIQUEMENT pour soi (laisse une trace côté utilisateur)."""
    m = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
    if request.user not in m.group.members.all():
        raise PermissionDenied("Accès refusé.")
    if request.method == "POST":
        m.deleted_for.add(request.user)
        flash.success(request, "Message supprimé pour vous.")
    return redirect(_hub("g%d" % m.group_id))


def _call_room(call):
    import hashlib
    from django.conf import settings
    base = ("LPM-g-%d" % call.group_id) if call.group_id else \
        ("LPM-d-%d-%d" % tuple(sorted([call.caller_id, call.other_id])))
    return base + "-" + hashlib.sha1((settings.SECRET_KEY + base).encode()).hexdigest()[:10]


def _post_call_log(call):
    """Poste un message journal d'appel (📞) coloré selon le statut."""
    mode_fr = "vidéo" if call.mode == "video" else "audio"
    label = {"COMPLETED": "📞 Appel terminé", "MISSED": "📞 Appel manqué",
             "DECLINED": "📞 Appel refusé"}.get(call.status, "📞 Appel")
    dur = ""
    if call.answered_at and call.ended_at:
        s = int((call.ended_at - call.answered_at).total_seconds())
        dur = f" · {s // 60}:{s % 60:02d}"
    body = f"{label} ({mode_fr}){dur}"
    if call.group_id:
        GroupMessage.objects.create(group=call.group, sender=call.caller, body=body)
    else:
        Message.objects.create(sender=call.caller, recipient=call.other, body=body)


def _expire_stale_calls():
    """Les appels qui sonnent depuis > 45 s sans réponse deviennent « manqués »."""
    from datetime import timedelta
    from .models import Call
    limit = timezone.now() - timedelta(seconds=45)
    for c in Call.objects.filter(status=Call.Status.RINGING, created_at__lt=limit):
        c.status = Call.Status.MISSED
        c.ended_at = timezone.now()
        c.save(update_fields=["status", "ended_at"])
        _post_call_log(c)


@login_required
def call_start(request, kind, pk, mode):
    """Démarre un appel : crée l'enregistrement (RINGING) et ouvre la salle."""
    from django.http import Http404
    from .models import Call
    if mode not in ("audio", "video"):
        raise Http404()
    me = request.user
    if kind == "d":
        other = get_object_or_404(User, pk=pk)
        if not can_message(me, other):
            raise PermissionDenied("Appel non autorisé.")
        call = Call.objects.create(caller=me, other=other, mode=mode)
    elif kind == "g":
        group = get_object_or_404(ChatGroup, pk=pk)
        if me not in group.members.all():
            raise PermissionDenied("Appel non autorisé.")
        call = Call.objects.create(caller=me, group=group, mode=mode)
    else:
        raise Http404()
    call.room = _call_room(call)
    call.save(update_fields=["room"])
    return redirect("messaging:call", call_id=call.pk)


def _call_participant(call, user):
    if call.group_id:
        return user in call.group.members.all()
    return user.id in (call.caller_id, call.other_id)


@login_required
def call(request, call_id):
    """Page d'appel (Jitsi). Le fait d'ouvrir = rejoindre (passe en « en cours »)."""
    from .models import Call
    call = get_object_or_404(Call, pk=call_id)
    if not _call_participant(call, request.user):
        raise PermissionDenied("Vous ne participez pas à cet appel.")
    # Un participant autre que l'appelant qui ouvre la page = appel décroché.
    if request.user.id != call.caller_id and call.status == Call.Status.RINGING:
        call.status = Call.Status.ONGOING
        call.answered_at = timezone.now()
        call.save(update_fields=["status", "answered_at"])
    title = call.group.name if call.group_id else (call.other.get_full_name() or call.other.username)
    back = _hub(("g%d" % call.group_id) if call.group_id else ("u%d" % call.other_id))
    return render(request, "messaging/call.html", {
        "room": call.room, "title": title, "mode": call.mode, "back": back, "call": call,
        "is_caller": request.user.id == call.caller_id})


@csrf_exempt
@login_required
def call_end(request, call_id):
    """Fin d'appel (quitté). Marque terminé/manqué et journalise une seule fois.

    CSRF-exempt pour autoriser navigator.sendBeacon() à la fermeture de l'onglet."""
    from .models import Call
    call = get_object_or_404(Call, pk=call_id)
    if not _call_participant(call, request.user):
        raise PermissionDenied()
    if request.method == "POST" and call.ended_at is None:
        call.ended_at = timezone.now()
        call.status = Call.Status.COMPLETED if call.answered_at else Call.Status.MISSED
        call.save(update_fields=["status", "ended_at"])
        _post_call_log(call)
    from django.http import JsonResponse
    return JsonResponse({"ok": True})


@login_required
def call_decline(request, call_id):
    from .models import Call
    call = get_object_or_404(Call, pk=call_id)
    if not _call_participant(call, request.user):
        raise PermissionDenied()
    if request.method == "POST" and call.ended_at is None:
        call.status = Call.Status.DECLINED
        call.ended_at = timezone.now()
        call.save(update_fields=["status", "ended_at"])
        _post_call_log(call)
    from django.http import JsonResponse
    return JsonResponse({"ok": True})


@login_required
def incoming_call(request):
    """JSON : appel entrant qui me concerne (sonne, < 45 s, je ne suis pas l'appelant)."""
    from datetime import timedelta
    from django.http import JsonResponse
    from .models import Call
    _expire_stale_calls()
    me = request.user
    recent = timezone.now() - timedelta(seconds=45)
    qs = (Call.objects.filter(status=Call.Status.RINGING, created_at__gte=recent)
          .exclude(caller=me).select_related("caller", "other", "group"))
    for c in qs:
        if _call_participant(c, me):
            who = c.group.name if c.group_id else (c.caller.get_full_name() or c.caller.username)
            return JsonResponse({"call": {
                "id": c.pk, "mode": c.mode,
                "from": c.caller.get_full_name() or c.caller.username,
                "title": who, "is_group": bool(c.group_id),
                "join": reverse("messaging:call", args=[c.pk]),
                "decline": reverse("messaging:call_decline", args=[c.pk]),
            }})
    return JsonResponse({"call": None})


def _conv_canon(kind, me_id, pk):
    if kind == "d":
        a, b = sorted([me_id, int(pk)])
        return "d:%d:%d" % (a, b)
    return "g:%s" % pk


def _msg_json(m, me, is_group):
    att = {}
    if m.attachment:
        att = {"url": m.attachment.url, "ext": (m.ext or "").upper(),
               "is_audio": m.is_audio, "is_image": m.is_image, "is_video": m.is_video}
    return {
        "id": m.id, "mine": m.sender_id == me.id,
        "name": m.sender.get_full_name() or m.sender.username,
        "initials": m.sender.display_initials,
        "avatar": (m.sender.avatar.url if getattr(m.sender, "avatar", None) else ""),
        "body": m.body or "", "time": timezone.localtime(m.created_at).strftime("%H:%M"),
        "is_call": (m.body or "").startswith("📞"),
        "is_group": is_group, "att": att,
        "is_forwarded": m.is_forwarded,
        "is_system": getattr(m, "is_system", False),
    }


@login_required
def conv_poll(request, kind, pk):
    """JSON : nouveaux messages (après ?after=), saisie en cours et présence."""
    import time as _time
    from django.core.cache import cache
    from django.http import Http404, JsonResponse
    _expire_stale_calls()  # tout appel qui sonne depuis > 45 s sans réponse → manqué
    me = request.user
    after = int(request.GET.get("after") or 0)
    if kind == "d":
        other = get_object_or_404(User, pk=pk)
        if not can_message(me, other):
            raise PermissionDenied()
        new = (Message.objects.filter(
            (Q(sender=me, recipient=other) | Q(sender=other, recipient=me)), id__gt=after)
            .select_related("sender").order_by("id"))
        cut = clear_cutoffs(me).get(other.id)
        if cut:  # ne ré-affiche jamais l'historique effacé après un rechargement
            new = new.filter(created_at__gt=cut)
        Message.objects.filter(sender=other, recipient=me, is_read=False).update(is_read=True)
        online = other.is_online
        presence = "en ligne" if online else "hors ligne"
        is_group = False
    elif kind == "g":
        group = get_object_or_404(ChatGroup, pk=pk)
        if me not in group.members.all():
            raise PermissionDenied()
        new = (GroupMessage.objects.filter(group=group, id__gt=after)
               .select_related("sender").order_by("id"))
        online = group.members.filter(last_seen__gte=timezone.now() - __import__("datetime").timedelta(minutes=3)).exclude(pk=me.pk).count()
        presence = f"{online} en ligne" if online else ""
        is_group = True
    else:
        raise Http404()
    # Exclut de l'affichage live les messages que j'ai supprimés pour moi.
    msgs = [_msg_json(m, me, is_group) for m in new if me not in m.deleted_for.all()]
    # Ids des messages « supprimés pour tout le monde » → tombstone live chez les autres.
    if kind == "d":
        deleted_all = list(Message.objects.filter(
            (Q(sender=me, recipient=other) | Q(sender=other, recipient=me)), deleted_for_all=True
        ).values_list("id", flat=True))
    else:
        deleted_all = list(GroupMessage.objects.filter(
            group=group, deleted_for_all=True).values_list("id", flat=True))
    # Saisie en cours (autres participants).
    canon = _conv_canon(kind, me.id, pk)
    typers = []
    d = cache.get("typing:" + canon) or {}
    now = _time.time()
    for uid, exp in d.items():
        if exp > now and uid != me.id:
            u = User.objects.filter(pk=uid).first()
            if u:
                typers.append(u.get_full_name() or u.username)
    return JsonResponse({"messages": msgs, "typing": typers, "online": bool(online),
                         "presence": presence, "deleted_all": deleted_all})


@login_required
def typing_ping(request, kind, pk):
    """Signale que l'utilisateur est en train d'écrire (TTL ~6 s)."""
    import time as _time
    from django.core.cache import cache
    from django.http import JsonResponse
    canon = _conv_canon(kind, request.user.id, pk)
    key = "typing:" + canon
    d = cache.get(key) or {}
    d[request.user.id] = _time.time() + 6
    cache.set(key, d, 30)
    return JsonResponse({"ok": True})


@login_required
def react(request, kind, pk):
    """Ajoute/retire une réaction emoji à un message (kind='d' direct, 'g' groupe)."""
    from .models import Reaction
    emoji = (request.POST.get("emoji") or "")[:8]
    if kind == "d":
        msg = get_object_or_404(Message, pk=pk)
        if request.user.id not in (msg.sender_id, msg.recipient_id):
            raise PermissionDenied("Accès refusé.")
        existing = Reaction.objects.filter(user=request.user, message=msg).first()
        target = {"message": msg}
        conv = "u%d" % (msg.recipient_id if msg.sender_id == request.user.id else msg.sender_id)
    else:
        msg = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
        if request.user not in msg.group.members.all():
            raise PermissionDenied("Accès refusé.")
        existing = Reaction.objects.filter(user=request.user, group_message=msg).first()
        target = {"group_message": msg}
        conv = "g%d" % msg.group_id
    if request.method == "POST" and emoji:
        if existing and existing.emoji == emoji:
            existing.delete()            # même emoji → on retire
        elif existing:
            existing.emoji = emoji        # autre emoji → on remplace
            existing.save(update_fields=["emoji"])
        else:
            Reaction.objects.create(user=request.user, emoji=emoji, **target)
    return redirect(_hub(conv))


@login_required
def pin_message(request, kind, pk):
    """Épingle/désépingle un message dans la conversation (max 3)."""
    if kind == "d":
        msg = get_object_or_404(Message, pk=pk)
        if request.user.id not in (msg.sender_id, msg.recipient_id):
            raise PermissionDenied("Accès refusé.")
        scope = Message.objects.filter(
            Q(sender_id=msg.sender_id, recipient_id=msg.recipient_id)
            | Q(sender_id=msg.recipient_id, recipient_id=msg.sender_id))
        conv = "u%d" % (msg.recipient_id if msg.sender_id == request.user.id else msg.sender_id)
    else:
        msg = get_object_or_404(GroupMessage.objects.select_related("group"), pk=pk)
        if request.user not in msg.group.members.all():
            raise PermissionDenied("Accès refusé.")
        scope = GroupMessage.objects.filter(group=msg.group)
        conv = "g%d" % msg.group_id
    if request.method == "POST":
        if not msg.is_pinned and scope.filter(is_pinned=True).count() >= 3:
            flash.error(request, "Maximum 3 messages épinglés par conversation.")
        else:
            msg.is_pinned = not msg.is_pinned
            msg.save(update_fields=["is_pinned"])
    return redirect(_hub(conv))


@login_required
def pin_conversation(request, conv):
    """Épingle/désépingle une conversation (directe 'u<id>' ou groupe 'g<id>')."""
    me = request.user
    if conv[:1] == "u" and conv[1:].isdigit():
        other = get_object_or_404(User, pk=int(conv[1:]))
        existing = ConversationPin.objects.filter(user=me, other=other).first()
        if request.method == "POST":
            existing.delete() if existing else ConversationPin.objects.create(user=me, other=other)
    elif conv[:1] == "g" and conv[1:].isdigit():
        group = get_object_or_404(ChatGroup, pk=int(conv[1:]))
        existing = ConversationPin.objects.filter(user=me, group=group).first()
        if request.method == "POST":
            existing.delete() if existing else ConversationPin.objects.create(user=me, group=group)
    return redirect(_hub(conv))


@login_required
def group_manage(request, pk):
    """Infos & participants du groupe.

    • Tout membre peut consulter la liste des participants (#3).
    • Un administrateur du groupe peut renommer, ajouter/retirer des membres,
      et nommer/retirer d'autres administrateurs (#4).
    • Le CEO / l'admin peut ajouter des clients (externes) au groupe (#1).
    """
    group = get_object_or_404(ChatGroup, pk=pk)
    me = request.user
    if me not in group.members.all():
        raise PermissionDenied("Vous ne faites pas partie de ce groupe.")
    is_admin = is_group_admin(me, group)
    if group.is_general:
        flash.info(request, "Le canal général est géré automatiquement (tout le personnel).")
        return redirect("messaging:group", pk=pk)

    if request.method == "POST":
        if not is_admin:
            raise PermissionDenied("Réservé à un administrateur du groupe.")
        action = request.POST.get("action")
        if action == "rename":
            name = (request.POST.get("name") or "").strip()
            if name:
                group.name = name
                group.description = (request.POST.get("description") or "").strip()
                group.save()
                flash.success(request, "Groupe mis à jour.")
        elif action == "add":
            ids = request.POST.getlist("members")
            qs = User.objects.filter(pk__in=ids, is_active=True)
            if not me.is_ceo:  # seuls CEO/admin peuvent ajouter des externes (clients)
                qs = qs.filter(role__in=INTRANET_ROLES)
            users = list(qs)
            group.members.add(*users)
            _notify_added_to_group(group, me, users)
            flash.success(request, f"{len(users)} membre(s) ajouté(s).")
        elif action == "promote":
            u = get_object_or_404(User, pk=request.POST.get("user"))
            if u in group.members.all() and not group.admins.filter(pk=u.pk).exists():
                group.admins.add(u)
                _notify_promoted_admin(group, me, u)
                flash.success(request, f"{u.get_full_name() or u.username} est désormais administrateur.")
        elif action == "demote":
            u = get_object_or_404(User, pk=request.POST.get("user"))
            group.admins.remove(u)
            flash.success(request, f"{u.get_full_name() or u.username} n'est plus administrateur.")
        return redirect("messaging:group_manage", pk=pk)

    member_ids = group.members.values_list("pk", flat=True)
    addable = User.objects.filter(is_active=True).exclude(pk__in=member_ids)
    if me.is_ceo:  # CEO/admin : peut ajouter clients/partenaires/etc.
        addable = addable.filter(role__in=INTRANET_ROLES | EXTRANET_ROLES)
    else:
        addable = addable.filter(role__in=INTRANET_ROLES)
    # L'administrateur principal (super admin) reste masqué de la liste d'ajout.
    if not me.is_admin_lpm:
        addable = addable.exclude(role=Role.ADMIN).exclude(is_superuser=True)
    admin_ids = set(group.admins.values_list("pk", flat=True))
    return render(request, "messaging/group_manage.html", {
        "group": group, "members": group.members.order_by("first_name", "last_name"),
        "addable": addable.order_by("first_name", "last_name"),
        "is_admin": is_admin, "admin_ids": admin_ids, "can_add_clients": me.is_ceo})


@login_required
def group_member_remove(request, pk, user_pk):
    """Retire un membre du groupe (admin du groupe)."""
    group = get_object_or_404(ChatGroup, pk=pk)
    if not is_group_admin(request.user, group) or group.is_general:
        raise PermissionDenied("Action non autorisée.")
    if request.method == "POST":
        u = get_object_or_404(User, pk=user_pk)
        group.members.remove(u)
        group.admins.remove(u)  # retiré des admins s'il l'était
        flash.success(request, "Membre retiré.")
    return redirect("messaging:group_manage", pk=pk)


@login_required
def group_delete(request, pk):
    """Supprime complètement un groupe (admin du groupe ; jamais le canal général)."""
    group = get_object_or_404(ChatGroup, pk=pk)
    if not is_group_admin(request.user, group):
        raise PermissionDenied("Réservé à l'administrateur du groupe.")
    if group.is_general:
        raise PermissionDenied("Le canal général ne peut pas être supprimé.")
    if request.method == "POST":
        group.delete()
        flash.success(request, "Discussion supprimée.")
    return redirect("messaging:chat")


@login_required
def group_leave(request, pk):
    """Quitter un groupe (sauf le canal général)."""
    group = get_object_or_404(ChatGroup, pk=pk)
    if group.is_general:
        flash.info(request, "Vous ne pouvez pas quitter le canal général.")
        return redirect("messaging:group", pk=pk)
    if request.method == "POST":
        group.members.remove(request.user)
        flash.success(request, f"Vous avez quitté « {group.name} ».")
    return redirect("messaging:chat")


@internal_required
def group_create(request):
    from accounts.models import User
    # Le CEO / l'admin peut constituer un groupe mixte avec des clients (externes).
    roles = (INTRANET_ROLES | EXTRANET_ROLES) if request.user.is_ceo else INTRANET_ROLES
    member_qs = User.objects.filter(role__in=roles, is_active=True).exclude(pk=request.user.pk)
    if not request.user.is_admin_lpm:  # masque l'administrateur principal
        member_qs = member_qs.exclude(role=Role.ADMIN).exclude(is_superuser=True)
    if request.method == "POST":
        form = GroupForm(request.POST, member_qs=member_qs)
        if form.is_valid():
            grp = form.save(commit=False)
            grp.created_by = request.user
            grp.save()
            form.save_m2m()
            grp.members.add(request.user)  # le créateur est toujours membre
            _notify_added_to_group(grp, request.user, list(grp.members.exclude(pk=request.user.pk)))
            flash.success(request, f"Groupe « {grp.name} » créé.")
            return redirect("messaging:group", pk=grp.pk)
    else:
        form = GroupForm(member_qs=member_qs)
    return render(request, "messaging/group_form.html", {"form": form})
