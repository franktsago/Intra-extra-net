"""Signaux : journal d'activité (connexions) + création auto de la fiche employé."""

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import INTRANET_ROLES, ActivityLog, Role, User
from .utils import get_client_ip


@receiver(post_save, sender=User)
def _ensure_employee_profile(sender, instance, created, **kwargs):
    """Crée automatiquement une fiche employé pour tout nouveau compte interne.

    Évite le message « Aucune fiche employé associée à votre compte ». Le compte
    système ADMIN (super admin) en est dispensé.
    """
    if not created:
        return
    if instance.role in INTRANET_ROLES and instance.role != Role.ADMIN:
        from employees.models import Employee
        if not Employee.objects.filter(user=instance).exists():
            # Le matricule est attribué automatiquement (séquence croissante) par Employee.save().
            defaults = {}
            if instance.role == Role.STAGIAIRE:
                defaults["contract_type"] = Employee.Contract.STAGE
            Employee.objects.create(user=instance, **defaults)


@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    from django.contrib.auth import get_user_model
    from django.utils import timezone
    get_user_model().objects.filter(pk=user.pk).update(last_seen=timezone.now())  # en ligne immédiat
    ActivityLog.objects.create(
        user=user, action=ActivityLog.Action.LOGIN,
        description="Connexion réussie",
        ip_address=get_client_ip(request) if request else None,
        path=request.path if request else "",
    )


@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    if user:
        from django.contrib.auth import get_user_model
        get_user_model().objects.filter(pk=user.pk).update(last_seen=None)  # hors ligne immédiat
        ActivityLog.objects.create(
            user=user, action=ActivityLog.Action.LOGOUT,
            description="Déconnexion",
            ip_address=get_client_ip(request) if request else None,
            path=request.path if request else "",
        )


@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request=None, **kwargs):
    ActivityLog.objects.create(
        user=None, action=ActivityLog.Action.LOGIN_FAILED,
        description=f"Échec — identifiant : {credentials.get('username', '?')}",
        ip_address=get_client_ip(request) if request else None,
        path=request.path if request else "",
    )
