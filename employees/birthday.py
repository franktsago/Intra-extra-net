"""Logique des notifications d'anniversaire (réutilisée par la commande et le runner quotidien).

  • J‑3 : alerte au RH, CEO, admin et au responsable de la personne ;
  • Jour‑J : message chaleureux à tout le personnel + un mot personnel à l'intéressé(e).

Idempotent : ne renvoie pas deux fois la même notification le même jour.
"""

from datetime import timedelta

from django.utils import timezone

from accounts.models import INTRANET_ROLES, Role, User
from notifications.models import Notification, notify


def send_birthday_notifications(today=None):
    """Envoie les notifications d'anniversaire. Retourne (jour_J, J‑3)."""
    from employees.models import Employee
    today = today or timezone.localdate()
    in3 = today + timedelta(days=3)
    sent_day = sent_pre = 0

    management = list(User.objects.filter(
        role__in=[Role.RH, Role.CEO, Role.ADMIN], is_active=True))
    employees = (Employee.objects.filter(status=Employee.Status.ACTIVE)
                 .select_related("user", "manager__user")
                 .exclude(birth_date__isnull=True))

    for emp in employees:
        if not emp.user.is_active:
            continue
        md = (emp.birth_date.month, emp.birth_date.day)

        # ----- Jour J : message chaleureux à tout le personnel -----
        if md == (today.month, today.day):
            already = Notification.objects.filter(
                recipient=emp.user, created_at__date=today,
                title__startswith="Joyeux anniversaire").exists()
            if already:
                continue
            prenom = emp.user.first_name or emp.full_name
            staff = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
            for u in staff:
                if u.id == emp.user_id:
                    notify(u, f"Joyeux anniversaire, {prenom} ! 🎉🎂",
                           f"Cher(e) {prenom}, toute la famille LPM vous souhaite un merveilleux "
                           "anniversaire 🥳. Merci pour tout ce que vous apportez. Belle journée "
                           "à vous, pleine de joie ! 🎂🎈",
                           Notification.Level.SUCCESS)
                else:
                    notify(u, f"🎂 Anniversaire de {emp.full_name}",
                           f"Aujourd'hui, {emp.full_name} fête son anniversaire 🎉. "
                           "Pensez à lui souhaiter !",
                           Notification.Level.INFO)
            sent_day += 1

        # ----- J‑3 : alerte à l'encadrement -----
        elif md == (in3.month, in3.day):
            recipients = set(management)
            if emp.manager and emp.manager.user.is_active:
                recipients.add(emp.manager.user)
            recipients.discard(emp.user)
            already = Notification.objects.filter(
                recipient__in=recipients, created_at__date=today,
                title__startswith=f"Anniversaire à venir — {emp.full_name}").exists()
            if already:
                continue
            for u in recipients:
                notify(u, f"Anniversaire à venir — {emp.full_name}",
                       f"{emp.full_name} fêtera son anniversaire le {in3:%d/%m} (dans 3 jours). "
                       "Pensez à organiser une attention 🎁.",
                       Notification.Level.INFO)
            sent_pre += 1

    return sent_day, sent_pre
