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
from django.urls import reverse


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
            # Déconnexion par inactivité UNIQUEMENT si un délai (> 0) est configuré.
            if self.timeout > 0 and last and (now - last) > self.timeout:
                logout(request)
                messages.info(
                    request,
                    "Votre session a expiré après une période d'inactivité. "
                    "Veuillez vous reconnecter.",
                )
            else:
                # Performance : on ne réécrit la session qu'au plus 1×/minute →
                # évite une écriture en base à chaque requête.
                if not last or (now - last) > 60:
                    request.session["last_activity"] = now
                # Session persistante : prolonge le cookie (fenêtre glissante) au
                # plus 1×/jour, pour que l'utilisateur actif ne soit jamais déconnecté.
                if self.timeout <= 0 and (now - request.session.get("expiry_bumped", 0)) > 86400:
                    request.session["expiry_bumped"] = now
                    try:
                        request.session.set_expiry(getattr(settings, "SESSION_COOKIE_AGE", 60 * 60 * 24 * 60))
                    except Exception:
                        pass
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

        response = self.get_response(request)

        # Traçabilité : toute MODIFICATION (POST réussi) effectuée sous un compte
        # basculé laisse une trace de la personne d'origine dans le journal.
        try:
            if (user is not None and user.is_authenticated
                    and request.method == "POST"
                    and request.session.get("switch_origin_id")
                    and response.status_code in (200, 301, 302)
                    and request.path != reverse("accounts:logout")):
                from .models import ActivityLog
                from .utils import get_client_ip
                ActivityLog.objects.create(
                    user=user, action=ActivityLog.Action.UPDATE,
                    description=(f"Modification via compte lié — origine : "
                                 f"{request.session.get('switch_origin_name', '')}")[:255],
                    ip_address=get_client_ip(request), path=request.path[:255])
        except Exception:
            pass
        return response
