"""Utilitaires partagés : journalisation et contrôle d'accès par rôle."""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import ActivityLog


def get_client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def hide_superadmin(qs, viewer, user_field=None):
    """Masque le compte super administrateur des listes vues par les autres.

    Le super admin (rôle ADMIN ou superuser) reste visible pour lui-même.
    `user_field` permet de filtrer un queryset dont le compte est sur une relation
    (ex. Employee → user_field="user").
    """
    from .models import Role
    if getattr(viewer, "is_admin_lpm", False):
        return qs
    if user_field:
        return (qs.exclude(**{f"{user_field}__role": Role.ADMIN})
                  .exclude(**{f"{user_field}__is_superuser": True}))
    return qs.exclude(role=Role.ADMIN).exclude(is_superuser=True)


def log_activity(request, action, description="", user=None):
    """Enregistre une entrée dans le journal d'activité."""
    ActivityLog.objects.create(
        user=user or (request.user if getattr(request, "user", None) and request.user.is_authenticated else None),
        action=action,
        description=description[:255],
        ip_address=get_client_ip(request),
        path=request.path[:255],
    )


def _redirect_external(request):
    """Redirige un utilisateur externe vers son espace sans afficher d'erreur."""
    from django.shortcuts import redirect
    if request.user.is_authenticated and not request.user.is_internal:
        return redirect("extranet:home")
    raise PermissionDenied("Accès réservé.")


def role_required(*roles):
    """Décorateur : restreint une vue aux rôles indiqués (l'admin passe toujours).

    Un utilisateur externe est redirigé vers l'extranet sans page d'erreur.
    Un interne sans le bon rôle reçoit un 403.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            u = request.user
            if not u.is_internal and not u.is_superuser:
                return _redirect_external(request)
            if u.effective_role in roles or u.is_admin_lpm:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("Accès réservé : vous n'avez pas les droits nécessaires.")

        return _wrapped

    return decorator


def internal_required(view_func):
    """Réserve une vue aux utilisateurs internes (intranet).

    Un utilisateur externe est redirigé vers son espace extranet sans page d'erreur.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        u = request.user
        if u.is_internal or u.is_superuser:
            return view_func(request, *args, **kwargs)
        return _redirect_external(request)

    return _wrapped
