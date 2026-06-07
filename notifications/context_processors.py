"""Expose le compteur de notifications non lues à tous les templates."""

from .models import Notification


def notifications_badge(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_count": 0, "recent_notifications": []}
    # Cloisonnement : on n'expose que les notifications du périmètre actif.
    audience = (Notification.Audience.EXTERNAL if request.user.is_external
                else Notification.Audience.INTERNAL)
    base = Notification.objects.filter(recipient=request.user, audience=audience)
    return {
        "unread_count": base.filter(is_read=False).count(),
        "recent_notifications": list(base[:6]),
    }
