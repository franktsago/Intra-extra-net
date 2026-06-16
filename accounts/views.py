"""Vues : connexion, profil, gestion des utilisateurs, journal d'activité."""

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, PasswordResetView, PasswordResetConfirmView,
)
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy

from .forms import (
    LoginForm, PasswordChangeForm, ProfileForm, UserCreateForm, UserEditForm,
)
from .models import ActivityLog, Role, User
from .utils import hide_superadmin, log_activity, role_required


class LPMLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        user = self.request.user
        if user.must_change_password:
            return reverse_lazy("accounts:password_change")
        if user.is_external:
            return reverse_lazy("extranet:home")
        return reverse_lazy("dashboard:home")


class LPMPasswordResetView(PasswordResetView):
    template_name = "accounts/password_reset.html"
    email_template_name = "accounts/password_reset_email.html"
    success_url = reverse_lazy("accounts:password_reset_done")


class LPMPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


@login_required
def password_change(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été mis à jour.")
            return redirect("extranet:home" if user.is_external else "dashboard:home")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/password_change.html", {"form": form})


@login_required
def profile(request):
    from .forms import SignatureForm
    user = request.user
    form = ProfileForm(instance=user)
    sig_form = SignatureForm(instance=user) if user.can_sign else None

    if request.method == "POST":
        if "save_signature" in request.POST and user.can_sign:
            sig_form = SignatureForm(request.POST, request.FILES, instance=user)
            if sig_form.is_valid():
                sig_form.save()
                messages.success(request, "Signature et cachet enregistrés.")
                return redirect("accounts:profile")
        else:
            form = ProfileForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, "Profil mis à jour.")
                return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form, "sig_form": sig_form})


@login_required
def switch_role(request, role):
    """Bascule le rôle actif (pour les utilisateurs ayant plusieurs fonctions)."""
    if role in request.user.available_roles:
        request.session["active_role"] = role
        label = dict(Role.choices).get(role, role)
        messages.success(request, f"Vous agissez désormais en tant que : {label}.")
    return redirect("dashboard:home")


# --------------------------------------------------------------------------- #
# Gestion des utilisateurs (Admin / RH)
# --------------------------------------------------------------------------- #
@role_required(Role.ADMIN, Role.CEO, Role.RH)
def user_list(request):
    q = request.GET.get("q", "").strip()
    scope = request.GET.get("scope", "")
    # Le compte super-admin reste masqué pour les autres (RH/CEO).
    # select_related sur la fiche employé → affichage du type de contrat.
    users = hide_superadmin(User.objects.select_related("employee"), request.user)
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q)
            | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    if scope == "intranet":
        users = users.filter(role__in=[Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER, Role.EMPLOYE, Role.STAGIAIRE])
    elif scope == "extranet":
        users = users.filter(role__in=[Role.CLIENT, Role.PARTENAIRE, Role.FOURNISSEUR, Role.CONSULTANT])
    page = Paginator(users, 15).get_page(request.GET.get("page"))
    return render(request, "accounts/user_list.html",
                  {"page_obj": page, "q": q, "scope": scope})


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def user_create(request):
    from employees.forms import EmployeeProfileForm
    from employees.models import Employee, attach_new_relations
    if request.method == "POST":
        from accounts.models import INTRANET_ROLES
        form = UserCreateForm(request.POST, viewer=request.user)
        profile = EmployeeProfileForm(request.POST, viewer=request.user)
        form_ok = form.is_valid()
        # Le profil employé (dont la personne à contacter obligatoire) n'est exigé
        # que pour un compte interne ; un compte externe (client/partenaire) n'en a pas.
        will_be_internal = form_ok and form.cleaned_data.get("role") in INTRANET_ROLES
        profile_ok = profile.is_valid() if will_be_internal else True
        if form_ok and profile_ok:
            user = form.save(commit=False)
            user.created_by = request.user
            user.save()
            # Profil RH (uniquement pour les comptes internes).
            if user.is_internal:
                emp = Employee.objects.filter(user=user).first()
                if emp:
                    profile = EmployeeProfileForm(request.POST, instance=emp, viewer=request.user)
                    if profile.is_valid():
                        profile.save()  # départements/postes existants cochés
                    attach_new_relations(emp, request.POST.getlist("new_departments"),
                                         request.POST.getlist("new_positions"))
            log_activity(request, ActivityLog.Action.CREATE,
                         f"Création du compte {user.username} ({user.get_role_display()})")
            messages.success(
                request,
                f"Compte « {user.username} » créé. L'utilisateur devra changer "
                "son mot de passe à la première connexion.",
            )
            return redirect("accounts:user_list")
    else:
        form = UserCreateForm(viewer=request.user)
        profile = EmployeeProfileForm(viewer=request.user)
    return render(request, "accounts/user_form.html",
                  {"form": form, "profile": profile, "creating": True})


def _account_scope_block(actor, target):
    """Raison (message) pour laquelle `actor` ne peut pas gérer `target`, sinon None.

    Hiérarchie : l'admin principal et le CEO sont « au-dessus » de la RH ;
    les comptes clients/partenaires sont réservés à la Direction.
    """
    if (target.is_superuser or target.role == Role.ADMIN) and not actor.is_admin_lpm:
        return "Ce compte ne peut être géré que par l'administrateur principal."
    if target.role == Role.CEO and not actor.is_ceo:
        return "Un compte au-dessus de votre niveau (Direction) n'est pas modifiable."
    if target.is_external and not actor.is_ceo:
        return "La RH ne peut pas gérer les comptes clients/partenaires. Réservé à la Direction."
    return None


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def user_edit(request, pk):
    obj = get_object_or_404(User, pk=pk)
    block = _account_scope_block(request.user, obj)
    if block:
        messages.error(request, block)
        return redirect("accounts:user_list")
    if request.method == "POST":
        form = UserEditForm(request.POST, request.FILES, instance=obj, viewer=request.user)
        if form.is_valid():
            form.save()
            log_activity(request, ActivityLog.Action.UPDATE, f"Modification du compte {obj.username}")
            messages.success(request, "Compte mis à jour.")
            return redirect("accounts:user_list")
    else:
        form = UserEditForm(instance=obj, viewer=request.user)
    return render(request, "accounts/user_form.html", {"form": form, "obj": obj, "creating": False})


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def user_delete(request, pk):
    """Suppression d'un compte par l'admin, le CEO ou la RH (selon la hiérarchie)."""
    obj = get_object_or_404(User, pk=pk)
    error = None
    if obj.pk == request.user.pk:
        error = "Vous ne pouvez pas supprimer votre propre compte."
    elif obj.is_superuser:
        error = "Impossible de supprimer un super administrateur. Retirez d'abord ce statut."
    else:
        error = _account_scope_block(request.user, obj)
    if request.method == "POST":
        if error:
            messages.error(request, error)
            return redirect("accounts:user_list")
        username = obj.username
        # Désactivation alternative proposée dans le template ; ici suppression définitive.
        log_activity(request, ActivityLog.Action.DELETE, f"Suppression du compte {username}")
        obj.delete()
        messages.success(request, f"Le compte « {username} » a été supprimé.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_confirm_delete.html", {"obj": obj, "error": error})


@role_required(Role.ADMIN)
def activity_log(request):
    logs = ActivityLog.objects.select_related("user")
    action = request.GET.get("action", "")
    if action:
        logs = logs.filter(action=action)
    page = Paginator(logs, 30).get_page(request.GET.get("page"))
    return render(request, "accounts/activity_log.html",
                  {"page_obj": page, "actions": ActivityLog.Action.choices, "action": action})
