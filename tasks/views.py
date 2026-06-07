"""Gestion des tâches — permissions par rôle.

  • Employé : consulte SES tâches (et celles de son équipe en lecture seule),
    et peut **changer le statut** de ses propres tâches.
  • Chef d'équipe (responsable) : crée, modifie, supprime et change le statut
    des tâches de son équipe.
  • RH / CEO / Admin : accès complet.
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required
from employees.models import Employee
from notifications.models import Notification, notify

from .forms import EmployeeTaskForm, TaskForm, TaskStatusForm
from .models import Task

lead_required = role_required(Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN)


def _manager_user_of(user):
    """Compte du responsable hiérarchique de l'utilisateur (pour la validation)."""
    emp = Employee.objects.filter(user=user).select_related("manager__user").first()
    return emp.manager.user if emp and emp.manager else None


def _subordinate_user_ids(user):
    return list(Employee.objects.filter(manager__user=user).values_list("user_id", flat=True))


def _team_user_ids(user):
    """Collègues partageant le même responsable (équipe de l'employé) + soi-même."""
    me = Employee.objects.filter(user=user).select_related("manager").first()
    ids = {user.id}
    if me and me.manager_id:
        ids.update(Employee.objects.filter(manager_id=me.manager_id).values_list("user_id", flat=True))
    return list(ids)


def can_manage_task(user, task):
    """Peut créer/modifier/supprimer la tâche (chef d'équipe concerné, RH+)."""
    if user.is_rh:  # RH, CEO, admin
        return True
    if not user.is_manager:
        return False
    return (task.created_by_id == user.id
            or (task.assigned_to_id and task.assigned_to_id in _subordinate_user_ids(user)))


def can_change_status(user, task):
    # On ne peut faire évoluer le statut qu'une fois la tâche validée.
    if not task.is_approved:
        return False
    return task.assigned_to_id == user.id or can_manage_task(user, task)


def can_view_task(user, task):
    if user.is_rh or can_change_status(user, task):
        return True
    return task.assigned_to_id in _team_user_ids(user)


@internal_required
def task_board(request):
    user = request.user
    scope = request.GET.get("scope", "mine")
    if user.is_rh:
        base = Task.objects.all()
    elif user.is_manager:
        ids = _subordinate_user_ids(user) + [user.id]
        base = Task.objects.filter(Q(assigned_to_id__in=ids) | Q(created_by=user))
    else:
        base = Task.objects.filter(assigned_to_id__in=_team_user_ids(user))
    base = base.select_related("assigned_to", "created_by")

    if scope == "mine":
        tasks = base.filter(assigned_to=user)
    else:
        tasks = base
    columns = {
        "TODO": tasks.filter(status=Task.Status.TODO),
        "IN_PROGRESS": tasks.filter(status=Task.Status.IN_PROGRESS),
        "DONE": tasks.filter(status=Task.Status.DONE),
    }
    return render(request, "tasks/board.html", {
        "columns": columns, "scope": scope,
        "can_create": True,
        "team_label": "Toutes" if user.is_rh else ("Mon équipe"),
    })


@internal_required
def task_create(request):
    user = request.user
    is_lead = user.is_manager  # responsable / RH / CEO / admin
    if request.method == "POST":
        form = TaskForm(request.POST, viewer=user) if is_lead else EmployeeTaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = user
            if is_lead:
                task.is_approved = True
            else:
                # Employé : tâche pour lui-même, en attente de validation du responsable.
                task.assigned_to = user
                task.is_approved = False
            task.save()
            if is_lead:
                if task.assigned_to and task.assigned_to != user:
                    notify(task.assigned_to, "Nouvelle tâche assignée", task.title,
                           Notification.Level.INFO, reverse("tasks:detail", args=[task.pk]))
                    messages.success(request,
                                     f"Tâche créée et assignée à {task.assigned_to.get_full_name() or task.assigned_to.username}.")
                    # La tâche est assignée à un membre de l'équipe : on bascule sur la vue
                    # « équipe » sinon le responsable ne la verrait pas (filtre « Mes tâches »).
                    return redirect(reverse("tasks:board") + "?scope=all")
                messages.success(request, "Tâche créée.")
            else:
                mgr = _manager_user_of(user)
                notify(mgr, "Tâche à valider",
                       f"{user.get_full_name() or user.username} propose la tâche « {task.title} ».",
                       Notification.Level.INFO, reverse("tasks:detail", args=[task.pk]))
                messages.success(request, "Tâche créée. Elle sera active après validation de votre responsable.")
            return redirect("tasks:board")
    else:
        form = TaskForm(viewer=user) if is_lead else EmployeeTaskForm()
    return render(request, "tasks/form.html", {"form": form, "is_lead": is_lead})


@internal_required
def task_approve(request, pk, decision):
    """Le responsable valide (ou rejette) une tâche proposée par un employé."""
    task = get_object_or_404(Task, pk=pk)
    if not can_manage_task(request.user, task):
        raise PermissionDenied("Seul le responsable peut valider cette tâche.")
    if decision == "approve":
        task.is_approved = True
        task.approved_by = request.user
        task.save(update_fields=["is_approved", "approved_by"])
        notify(task.assigned_to, "Tâche validée ✅",
               f"Votre tâche « {task.title} » a été validée. Vous pouvez la traiter.",
               Notification.Level.SUCCESS, reverse("tasks:detail", args=[task.pk]))
        messages.success(request, "Tâche validée.")
    else:
        owner = task.assigned_to
        title = task.title
        task.delete()
        notify(owner, "Tâche refusée", f"La tâche « {title} » n'a pas été retenue.",
               Notification.Level.WARNING)
        messages.info(request, "Tâche refusée et supprimée.")
        return redirect("tasks:board")
    return redirect("tasks:detail", pk=pk)


@internal_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("assigned_to", "created_by", "project"), pk=pk)
    user = request.user
    if not can_view_task(user, task):
        raise PermissionDenied("Vous ne pouvez consulter que les tâches de votre équipe.")

    manage = can_manage_task(user, task)
    status_only = (not manage) and can_change_status(user, task)
    pending = not task.is_approved
    can_approve = pending and manage

    if request.method == "POST":
        if manage:
            form = TaskForm(request.POST, instance=task, viewer=user)
        elif status_only:
            form = TaskStatusForm(request.POST, instance=task)
        else:
            raise PermissionDenied("Lecture seule : vous ne pouvez pas modifier cette tâche.")
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.status == Task.Status.DONE and not obj.completed_at:
                obj.completed_at = timezone.now()
            obj.save()
            messages.success(request, "Tâche mise à jour.")
            return redirect("tasks:detail", pk=pk)
    else:
        form = TaskForm(instance=task, viewer=user) if manage else (TaskStatusForm(instance=task) if status_only else None)

    return render(request, "tasks/detail.html", {
        "task": task, "form": form, "can_manage": manage,
        "status_only": status_only, "read_only": form is None,
        "pending": pending, "can_approve": can_approve,
    })


@internal_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not can_manage_task(request.user, task):
        raise PermissionDenied("Seul le chef d'équipe peut supprimer cette tâche.")
    if request.method == "POST":
        task.delete()
        messages.success(request, "Tâche supprimée.")
        return redirect("tasks:board")
    return render(request, "tasks/confirm_delete.html", {"task": task})
