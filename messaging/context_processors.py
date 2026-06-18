"""Compteurs de messages / discussions non lus, disponibles dans tous les templates."""

from django.core.cache import cache

from .models import Message, unread_chat_count


def messages_badge(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_messages": 0, "unread_chat": 0}
    # Compteur direct : une seule requête (peu coûteux), gardé en temps réel.
    unread_messages = Message.objects.filter(recipient=user, is_read=False).count()
    # Compteur groupes : une requête par groupe → mis en cache 15 s pour alléger
    # chaque chargement de page (le détail reste exact sur la page Messagerie).
    ckey = f"badge_chat_{user.pk}"
    unread_chat = cache.get(ckey)
    if unread_chat is None:
        unread_chat = unread_chat_count(user)
        cache.set(ckey, unread_chat, 15)
    return {"unread_messages": unread_messages, "unread_chat": unread_chat}
