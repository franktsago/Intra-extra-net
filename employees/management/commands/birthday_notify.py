"""Notifications d'anniversaire (planifiable, mais aussi déclenché automatiquement chaque jour).

  • J‑3 : alerte au RH, CEO, admin et au responsable de la personne ;
  • Jour‑J : message chaleureux à tout le personnel + un mot personnel à l'intéressé(e).
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from employees.birthday import send_birthday_notifications


class Command(BaseCommand):
    help = "Envoie les notifications d'anniversaire (J-3 a l'encadrement, jour-J a tout le personnel)."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Forcer la date AAAA-MM-JJ (tests).")

    def handle(self, *args, **options):
        today = parse_date(options["date"]) if options.get("date") else timezone.localdate()
        sent_day, sent_pre = send_birthday_notifications(today)
        self.stdout.write(self.style.SUCCESS(
            f"Anniversaires : {sent_day} message(s) jour-J, {sent_pre} alerte(s) J-3."))
