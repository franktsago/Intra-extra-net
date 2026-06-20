"""Expose le compteur de notifications non lues + la config temps réel (MQTT)."""

from django.conf import settings

from .models import Notification


def notifications_badge(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {"unread_count": 0, "recent_notifications": []}
    # Cloisonnement : on n'expose que les notifications du périmètre actif.
    audience = (Notification.Audience.EXTERNAL if request.user.is_external
                else Notification.Audience.INTERNAL)
    base = Notification.objects.filter(recipient=request.user, audience=audience)
    last_id = base.order_by("-id").values_list("id", flat=True).first() or 0
    return {
        "unread_count": base.filter(is_read=False).count(),
        "recent_notifications": list(base[:6]),
        # Config temps réel injectée dans le JS (cf. realtime.js).
        "rt_uid": request.user.id,
        "rt_name": request.user.get_full_name() or request.user.username,
        "rt_mqtt_url": settings.MQTT_WSS_URL if settings.MQTT_ENABLED else "",
        "rt_mqtt_prefix": settings.MQTT_TOPIC_PREFIX,
        "rt_last_notif_id": last_id,
    }
