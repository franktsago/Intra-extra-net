"""Gestion des tâches — cloisonnement par département (comme les projets).

  • Responsable ET son équipe : ne voient que les tâches de leur(s) département(s).
  • Employé : peut **changer le statut** de ses propres tâches ; une tâche qu'il
    crée est soumise à validation de son responsable.
  • RH / CEO / Admin : vision d'ensemble (toutes les tâches).
"""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required
from employees.models import (
    Employee, department_colleagues_ids, department_ids_for,
)
from notifications.models import Notification, notify

from .forms import EmployeeTaskForm, TaskForm, TaskStatusForm
from .models import Task

lead_required = role_required(Role.MANAGER, Role.RH, Role.CEO, Role.ADMIN)


def _manager_user_of(user):
    """Responsable à qui adresser une tâche à valider.

    Priorité au responsable hiérarchique (Employee.manager) ; à défaut, le
    responsable du/des département(s) de l'employé (cloisonnement par département)."""
    emp = Employee.objects.filter(user=user).select_related("manager__user").first()
    if emp and emp.manager and emp.manager.user_id:
        return emp.manager.user
    # Repli : responsable de département.
    from employees.models import Department, department_ids_for
    dept = (Department.objects.filter(id__in=department_ids_for(user), manager__isnull=False)
            .exclude(manager=user).select_related("manager").first())
    return dept.manager if dept else None


def _task_in_user_departments(user, task):
    """La tâche relève-t-elle d'un département de l'utilisateur ? (via les personnes
    concernées : assignée ou créatrice)."""
    dept_users = department_colleagues_ids(user)
    return task.assigned_to_id in dept_users or task.created_by_id in dept_users


def can_manage_task(user, task):
    """Peut créer/modifier/supprimer la tâche : RH+ partout ; un responsable
    uniquement pour les tâches de son/ses département(s)."""
    if user.is_rh:  # RH, CEO, admin
        return True
    if not user.is_manager:
        return False
    return task.created_by_id == user.id or _task_in_user_departments(user, task)


def can_change_status(user, task):
    # On ne peut faire évoluer le statut qu'une fois la tâche validée.
    if not task.is_approved:
        return False
    return task.assigned_to_id == user.id or can_manage_task(user, task)


def can_view_task(user, task):
    if user.is_rh or task.assigned_to_id == user.id or task.created_by_id == user.id:
        return True
    # Visible si la tâche relève d'un département de l'utilisateur (équipe comprise).
    return _task_in_user_departments(user, task)


@internal_required
def task_board(request):
    user = request.user
    scope = request.GET.get("scope", "mine")
    if user.is_rh:
        base = Task.objects.all()
    else:
        # Responsable comme équipe : tâches rattachées à leur(s) département(s),
        # via la personne assignée ou créatrice.
        ids = department_colleagues_ids(user)
        base = Task.objects.filter(Q(assigned_to_id__in=ids) | Q(created_by_id__in=ids))
    base = base.select_related("assigned_to", "created_by").distinct()

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
        "team_label": "Toutes" if user.is_rh else "Mon département",
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
