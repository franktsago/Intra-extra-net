"""Middleware : déconnexion automatique par inactivité + traçabilité.

Implémente l'exigence du cahier des charges « Déconnexion automatique après
inactivité » et alimente le journal d'activité pour les pages sensibles.
"""

import time

from django.conf import settings
from django.contrib.auth import logout
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render


class FriendlyErrorMiddleware:
    """Affiche des pages d'erreur soignées (403 / 404) au lieu des pages techniques,
    en développement comme en production."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Page 404 (URL non résolue) → version soignée, même en développement.
        if (response.status_code == 404
                and "text/html" in response.get("Content-Type", "")):
            return render(request, "404.html", status=404)
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, Http404):
            return render(request, "404.html", status=404)
        if isinstance(exception, PermissionDenied):
            return render(request, "403.html", status=403)
        return None


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.timeout = getattr(settings, "SESSION_EXPIRE_SECONDS", 1800)

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = int(time.time())
            last = request.session.get("last_activity")
            if last and (now - last) > self.timeout:
                logout(request)
                messages.info(
                    request,
                    "Votre session a expiré après une période d'inactivité. "
                    "Veuillez vous reconnecter.",
                )
            else:
                # Performance : on ne réécrit la session qu'au plus 1×/minute
                # (précision suffisante pour un délai d'inactivité de 30 min) →
                # évite une écriture en base à chaque requête.
                if not last or (now - last) > 60:
                    request.session["last_activity"] = now
                # Présence « en ligne » : met à jour last_seen au plus une fois/25 s.
                if now - request.session.get("last_seen_ts", 0) > 25:
                    request.session["last_seen_ts"] = now
                    try:
                        from django.contrib.auth import get_user_model
                        from django.utils import timezone
                        get_user_model().objects.filter(pk=user.pk).update(last_seen=timezone.now())
                    except Exception:
                        pass
                # Applique le rôle actif choisi par l'utilisateur (multi-rôles).
                active = request.session.get("active_role")
                if active and active in user.available_roles:
                    user._active_role = active
                # Tâches quotidiennes automatiques (anniversaires, absences) — 1×/jour.
                if getattr(user, "is_internal", False):
                    try:
                        from .daily import run_daily_maintenance
                        run_daily_maintenance()
                    except Exception:
                        pass
        return self.get_response(request)
