"""Workflow de gestion des congés — circuit de validation multi-niveaux.

Le circuit dépend du rôle du DEMANDEUR (voir conges.models.VALIDATION_CHAINS) :
  • Employé          → Responsable → RH
  • Responsable      → RH → CEO
  • RH               → CEO
  • CEO              → Administrateur principal
À chaque niveau approuvé, on avance ; au dernier niveau, le congé est approuvé,
une référence est générée et la note PDF devient téléchargeable.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, Role, User
from accounts.utils import internal_required, log_activity, role_required
from employees.models import Employee
from notifications.models import Notification, notify

from .forms import DecisionForm, HolidayForm, LeaveRequestForm
from .models import Holiday, LeaveApproval, LeaveRequest, solde_conges


def _get_employee(user):
    return Employee.objects.filter(user=user).select_related("manager__user").first()


def _validator_users(leave):
    """Utilisateurs à notifier / habilités pour le niveau courant."""
    from accounts.models import users_with_role
    role = leave.current_role
    if role is None:
        return []
    if role == Role.MANAGER:
        mgr = leave.employee.manager
        if mgr and mgr.user.is_active:
            users = [mgr.user]
        else:
            # À défaut de responsable, le RH prend le relais.
            users = list(users_with_role(Role.RH))
    else:
        # Inclut les valideurs dont la fonction est un rôle SECONDAIRE (multi-rôles).
        users = list(users_with_role(role))
    # Aux niveaux Direction/Administration (ex. congés de la RH, d'un responsable
    # ou du CEO), on informe aussi le CEO et l'administrateur principal, qui
    # peuvent toujours valider.
    if role in (Role.CEO, Role.ADMIN):
        users += list(users_with_role(Role.CEO))
        users += list(User.objects.filter(role=Role.ADMIN))
        users += list(User.objects.filter(is_superuser=True))
    # Dédoublonnage en conservant l'ordre.
    seen, out = set(), []
    for u in users:
        if u and u.id not in seen:
            seen.add(u.id)
            out.append(u)
    return out


def _can_act(user, leave):
    """L'utilisateur peut-il décider à l'étape courante de ce congé ?"""
    if leave.status != LeaveRequest.Status.PENDING:
        return False
    role = leave.current_role
    if role is None:
        return False
    if user.is_admin_lpm:  # l'admin principal peut débloquer n'importe quel niveau
        return True
    # Rôles que l'utilisateur peut endosser (principal + secondaires), pour qu'un
    # valideur multi-rôles puisse agir sans devoir d'abord basculer de rôle.
    avail = set(user.available_roles)
    if role == Role.MANAGER:
        mgr = leave.employee.manager
        return bool(mgr and mgr.user_id == user.id) or bool({Role.RH, Role.CEO} & avail)
    if role == Role.RH:
        return Role.RH in avail or user.is_ceo
    if role == Role.CEO:
        return Role.CEO in avail or user.is_admin_lpm
    if role == Role.ADMIN:
        return user.is_admin_lpm
    return False


def _notify_current(leave):
    role = leave.current_role
    label = dict(Role.choices).get(role, role)
    for u in _validator_users(leave):
        notify(u, "Congé à valider",
               f"{leave.employee.full_name} — demande du {leave.start_date:%d/%m} au "
               f"{leave.end_date:%d/%m} ({leave.days_count} j). Validation {label} attendue.",
               Notification.Level.INFO, reverse("conges:detail", args=[leave.pk]))


@internal_required
def absences(request):
    """Vue partagée à TOUT le personnel : qui est en congé et qui est en mission."""
    from datetime import timedelta
    from hr.models import Mission
    today = timezone.localdate()
    horizon = today + timedelta(days=14)

    on_leave = (LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED, start_date__lte=today, end_date__gte=today)
        .select_related("employee__user", "leave_type").order_by("end_date"))
    on_mission = (Mission.objects.filter(start_date__lte=today, end_date__gte=today)
                  .select_related("employee__user").order_by("end_date"))
    upcoming_leave = (LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED, start_date__gt=today, start_date__lte=horizon)
        .select_related("employee__user", "leave_type").order_by("start_date"))
    upcoming_mission = (Mission.objects.filter(start_date__gt=today, start_date__lte=horizon)
                        .select_related("employee__user").order_by("start_date"))
    return render(request, "conges/absences.html", {
        "today": today, "on_leave": on_leave, "on_mission": on_mission,
        "upcoming_leave": upcoming_leave, "upcoming_mission": upcoming_mission})


@role_required(Role.RH, Role.CEO, Role.ADMIN)
def leave_delete(request, pk):
    """Supprime un congé (RH/CEO/admin) — disparaît pour tout le monde."""
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if request.method == "POST":
        leave.delete()
        messages.success(request, "Congé supprimé.")
    return redirect(request.POST.get("next") or "conges:absences")


@internal_required
def my_leaves(request):
    employee = _get_employee(request.user)
    context = {"employee": employee}
    if employee:
        context["requests"] = employee.leave_requests.select_related("leave_type")
        context["balance"] = solde_conges(employee)
    return render(request, "conges/my_leaves.html", context)


@internal_required
def leave_create(request):
    employee = _get_employee(request.user)
    if not employee:
        messages.error(request, "Aucune fiche employé n'est associée à votre compte. Contactez le service RH.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = employee
            leave.status = LeaveRequest.Status.PENDING
            leave.current_level = 0
            leave.save()
            if leave.current_role is None:
                # Aucun validateur (ex. admin principal) → approbation immédiate.
                _finalize_approved(leave, request)
            else:
                _notify_current(leave)
                first = dict(Role.choices).get(leave.current_role, "")
                messages.success(
                    request,
                    f"Demande soumise ({leave.days_count} jours ouvrables). "
                    f"Premier validateur : {first}.",
                )
            return redirect("conges:my")
    else:
        form = LeaveRequestForm()
    return render(request, "conges/form.html", {
        "form": form, "balance": solde_conges(employee), "employee": employee,
    })


@internal_required
def leave_detail(request, pk):
    leave = get_object_or_404(
        LeaveRequest.objects.select_related("employee__user", "leave_type")
        .prefetch_related("approvals__approver"), pk=pk)
    user = request.user
    is_owner = leave.employee.user_id == user.id
    if not (is_owner or user.can_validate_leave):
        raise PermissionDenied("Accès non autorisé à cette demande.")
    return render(request, "conges/detail.html", {
        "leave": leave, "is_owner": is_owner,
        "steps": leave.steps(),
        "can_decide": _can_act(user, leave),
    })


@internal_required
def leave_cancel(request, pk):
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if leave.employee.user_id != request.user.id:
        raise PermissionDenied()
    if leave.status == LeaveRequest.Status.PENDING:
        leave.status = LeaveRequest.Status.CANCELLED
        leave.save(update_fields=["status"])
        messages.info(request, "Demande annulée.")
    return redirect("conges:my")


def _finalize_approved(leave, request):
    from notifications.models import notify_internal_staff
    from .models import sync_leave_status
    leave.status = LeaveRequest.Status.APPROVED
    leave.decided_at = timezone.now()
    if not leave.reference:
        leave.reference = f"CONGE-{timezone.localdate():%Y}-{leave.pk:04d}"
    leave.save()
    # Si le congé couvre déjà aujourd'hui, l'employé passe « En congé » immédiatement.
    sync_leave_status()
    notify(leave.employee.user, "Congé approuvé",
           f"Votre congé du {leave.start_date:%d/%m} au {leave.end_date:%d/%m} est validé. "
           "La note de congé (PDF) est téléchargeable.",
           Notification.Level.SUCCESS, reverse("conges:detail", args=[leave.pk]))
    # Annonce à tout le personnel (sauf l'intéressé, déjà notifié).
    notify_internal_staff(
        "Congé approuvé",
        f"{leave.employee.full_name} sera en congé du {leave.start_date:%d/%m/%Y} "
        f"au {leave.end_date:%d/%m/%Y}.",
        Notification.Level.INFO, reverse("conges:absences"),
        exclude=leave.employee.user)


@role_required(Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN)
def leave_queue(request):
    pending = (LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
               .select_related("employee__user", "employee__manager__user", "leave_type"))
    queue = [lr for lr in pending if _can_act(request.user, lr)]
    return render(request, "conges/queue.html", {"queue": queue})


@role_required(Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN)
def leave_decide(request, pk):
    leave = get_object_or_404(
        LeaveRequest.objects.select_related("employee__user", "employee__manager__user"), pk=pk)
    if not _can_act(request.user, leave):
        raise PermissionDenied("Vous ne pouvez pas décider de cette demande à ce stade.")

    if request.method == "POST":
        form = DecisionForm(request.POST)
        if form.is_valid():
            decision = form.cleaned_data["decision"]
            comment = form.cleaned_data["comment"]
            owner = leave.employee.user
            role = leave.current_role

            # Enregistrer la décision (traçabilité).
            LeaveApproval.objects.create(
                leave=leave, level=leave.current_level, role=role,
                approver=request.user, approved=(decision == "approve"), comment=comment,
            )

            if decision == "approve":
                leave.current_level += 1
                if leave.current_role is None:
                    _finalize_approved(leave, request)
                    messages.success(request, "Congé approuvé. La note (PDF) est disponible.")
                else:
                    leave.save(update_fields=["current_level"])
                    _notify_current(leave)
                    nxt = dict(Role.choices).get(leave.current_role, "")
                    notify(owner, "Congé : étape validée",
                           f"Niveau validé. Prochain validateur : {nxt}.",
                           Notification.Level.INFO, reverse("conges:detail", args=[leave.pk]))
                    messages.success(request, f"Validé. Transmis au niveau suivant : {nxt}.")
            else:
                leave.status = LeaveRequest.Status.REJECTED
                leave.decided_at = timezone.now()
                leave.save(update_fields=["status", "decided_at"])
                notify(owner, "Congé refusé", comment or "Demande refusée.",
                       Notification.Level.ERROR, reverse("conges:detail", args=[leave.pk]))
                messages.info(request, "Demande refusée.")
            return redirect("conges:queue")
    else:
        form = DecisionForm()
    return render(request, "conges/decide.html", {"leave": leave, "form": form})


@internal_required
def leave_pdf(request, pk):
    """Note de congé (PDF) — accessible au demandeur et au RH/CEO/admin. Tracé."""
    leave = get_object_or_404(
        LeaveRequest.objects.select_related("employee__user", "leave_type")
        .prefetch_related("approvals__approver"), pk=pk)
    user = request.user
    is_owner = leave.employee.user_id == user.id
    if not (is_owner or user.is_rh):
        raise PermissionDenied("Accès réservé au demandeur et au service RH.")
    if leave.status != LeaveRequest.Status.APPROVED:
        raise PermissionDenied("La note n'est disponible que pour un congé approuvé.")

    from .pdf import leave_note_pdf
    pdf = leave_note_pdf(leave)
    log_activity(request, ActivityLog.Action.DOWNLOAD,
                 f"Téléchargement note de congé {leave.reference} — {leave.employee.full_name}")
    return FileResponse(pdf, as_attachment=True,
                        filename=f"{leave.reference or 'note-conge'}.pdf",
                        content_type="application/pdf")


@internal_required
def holidays(request):
    # Consultation ouverte à tout le personnel ; ajout réservé RH/CEO/admin.
    can_manage = request.user.is_rh
    if request.method == "POST":
        if not can_manage:
            messages.error(request, "Seul le service RH peut ajouter un jour férié.")
            return redirect("conges:holidays")
        form = HolidayForm(request.POST)
        if form.is_valid():
            holiday = form.save()
            from accounts.models import EXTRANET_ROLES, INTRANET_ROLES
            # Notification du personnel (intranet).
            staff = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
            for u in staff:
                notify(u, "Nouveau jour férié",
                       f"{holiday.name} — {holiday.date:%d/%m/%Y} (chômé). "
                       "Il est exclu du décompte des congés.",
                       Notification.Level.INFO, reverse("conges:holidays"))
            sent = staff.count()
            # Notification des clients (extranet) si demandé.
            if form.cleaned_data.get("audience") == "BOTH":
                clients = User.objects.filter(role__in=EXTRANET_ROLES, is_active=True)
                for u in clients:
                    notify(u, "Information — jour férié",
                           f"Le {holiday.date:%d/%m/%Y}, nos bureaux seront fermés "
                           f"({holiday.name}). Merci de votre compréhension.",
                           Notification.Level.INFO)
                sent += clients.count()
                messages.success(request,
                    f"Jour férié ajouté. {staff.count()} collaborateur(s) et {clients.count()} client(s) notifié(s).")
            else:
                messages.success(request, f"Jour férié ajouté. {sent} collaborateur(s) notifié(s).")
            return redirect("conges:holidays")
    else:
        form = HolidayForm()
    return render(request, "conges/holidays.html", {
        "holidays": Holiday.objects.all(), "form": form, "can_manage": can_manage})
