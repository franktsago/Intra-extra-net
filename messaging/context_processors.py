"""Compteurs de messages / discussions non lus, disponibles dans tous les templates."""

from .models import Message, unread_chat_count


def messages_badge(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"unread_messages": 0, "unread_chat": 0}
    data = {"unread_messages": Message.objects.filter(recipient=user, is_read=False).count()}
    # Les groupes peuvent désormais inclure des externes (clients) : on compte pour tous.
    data["unread_chat"] = unread_chat_count(user)
    return data
