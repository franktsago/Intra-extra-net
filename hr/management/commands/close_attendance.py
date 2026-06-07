"""Clôture des présences d'une journée : marque « Absent » qui n'a pas pointé.

À planifier (cron / tâche planifiée) en fin de journée. Sans argument : aujourd'hui.
Exemple : python manage.py close_attendance --date 2026-06-04
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from hr.models import ensure_absences


class Command(BaseCommand):
    help = "Marque comme absents les employés (devant pointer) sans pointage pour la journée."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="Date AAAA-MM-JJ (défaut : aujourd'hui)")

    def handle(self, *args, **options):
        day = parse_date(options["date"]) if options.get("date") else timezone.localdate()
        if not day:
            self.stderr.write("Date invalide (format attendu : AAAA-MM-JJ).")
            return
        ensure_absences(day)
        self.stdout.write(self.style.SUCCESS(f"Présences clôturées pour le {day:%d/%m/%Y}."))
