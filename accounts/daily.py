"""Tâches quotidiennes déclenchées automatiquement (sans cron) une fois par jour.

Déclenché par le middleware au premier accès authentifié de la journée.
Chaque sous-tâche est idempotente, donc une double exécution est sans effet.
"""

from django.core.cache import cache
from django.utils import timezone


def run_daily_maintenance():
    """Exécute les tâches du jour : absences + notifications d'anniversaire."""
    today = timezone.localdate()
    key = f"daily_maintenance_{today.isoformat()}"
    # cache.add renvoie False si la clé existe déjà → on ne lance qu'une fois/jour/process.
    if not cache.add(key, True, 60 * 60 * 26):
        return
    try:
        from hr.models import ensure_absences
        ensure_absences(today)
    except Exception:
        pass
    try:
        from employees.birthday import send_birthday_notifications
        send_birthday_notifications(today)
    except Exception:
        pass
    try:
        from hr.models import notify_ending_contracts
        notify_ending_contracts(today)
    except Exception:
        pass
