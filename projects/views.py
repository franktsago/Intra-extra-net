"""Vues du module Projets & Événements."""

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from accounts.utils import internal_required, role_required

from .forms import MediaForm, ProjectForm
from .models import Phase, Project

manager_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


def user_department_ids(user):
    """Départements pilotés par l'utilisateur (membre de la fiche ou responsable).

    Délègue au helper partagé `employees.department_ids_for` pour rester cohérent
    avec le cloisonnement des tâches."""
    from employees.models import department_ids_for
    return department_ids_for(user)


@internal_required
def project_list(request):
    """Projets rattachés aux départements : chaque département gère les siens.

    • RH / CEO / admin : vue d'ensemble de tous les départements (filtrable).
    • Responsable ET son équipe : uniquement les projets de leur(s) département(s)
      d'appartenance (plus, le cas échéant, ceux qu'ils pilotent/où ils sont membres).
    """
    from employees.models import Department
    user = request.user
    kind = request.GET.get("kind", "")
    dept = request.GET.get("dept", "")
    qs = Project.objects.select_related("client", "manager", "department")

    cross = user.is_rh  # is_rh inclut CEO + admin → seule vision d'ensemble
    departments = None
    if cross:
        departments = Department.objects.all()
        if dept:
            qs = qs.filter(department_id=dept)
    else:
        # Manager comme membre d'équipe : limités à leur(s) département(s).
        dept_ids = user_department_ids(user)
        qs = qs.filter(
            Q(department_id__in=dept_ids) | Q(manager=user) | Q(team=user)
        ).distinct()

    if kind:
        qs = qs.filter(kind=kind)
    title = {"EVENT": "Événements", "CAMPAIGN": "Campagnes"}.get(kind, "Projets par département")
    return render(request, "projects/list.html", {
        "projects": qs, "kind": kind, "title": title, "dept": dept,
        "kinds": Project.Kind.choices, "departments": departments, "cross": cross,
    })


@internal_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("client", "manager").prefetch_related(
            "phases", "team", "media__uploaded_by", "tasks__assigned_to"), pk=pk)
    return render(request, "projects/detail.html", {
        "project": project,
        "can_edit": request.user.is_manager,
        "media_form": MediaForm(),
    })


@manager_required
def project_edit(request, pk=None):
    project = get_object_or_404(Project, pk=pk) if pk else None
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project, viewer=request.user)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Projet enregistré.")
            return redirect("projects:detail", pk=obj.pk)
    else:
        form = ProjectForm(instance=project, viewer=request.user)
    return render(request, "projects/form.html", {"form": form, "project": project})


@internal_required
def phase_set(request, pk, phase_id, status):
    project = get_object_or_404(Project, pk=pk)
    phase = get_object_or_404(Phase, pk=phase_id, project=project)
    if status in Phase.Status.values:
        phase.status = status
        phase.save(update_fields=["status"])
        messages.success(request, f"Phase « {phase.name} » mise à jour.")
    return redirect("projects:detail", pk=pk)


@internal_required
def media_upload(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        form = MediaForm(request.POST, request.FILES)
        if form.is_valid():
            m = form.save(commit=False)
            m.project = project
            m.uploaded_by = request.user
            m.save()
            messages.success(request, "Média ajouté au rapport du projet.")
    return redirect("projects:detail", pk=pk)


# ---------------------------------------------------------------------------
# Backlog & Tickets
# ---------------------------------------------------------------------------
@internal_required
def ticket_list(request):
    from .models import Ticket
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "")
    qs = Ticket.objects.select_related("project", "reported_by", "assigned_to")
    if kind:
        qs = qs.filter(kind=kind)
    if status:
        qs = qs.filter(status=status)
    return render(request, "projects/ticket_list.html", {
        "tickets": qs, "kind": kind, "status": status,
        "kinds": Ticket.Kind.choices, "statuses": Ticket.Status.choices,
    })


@internal_required
def ticket_edit(request, pk=None):
    from .models import Ticket
    from .forms import TicketForm
    obj = get_object_or_404(Ticket, pk=pk) if pk else None
    if request.method == "POST":
        form = TicketForm(request.POST, instance=obj)
        if form.is_valid():
            t = form.save(commit=False)
            if not obj:
                t.reported_by = request.user
            t.save()
            messages.success(request, "Ticket enregistré.")
            return redirect("projects:ticket_list")
    else:
        form = TicketForm(instance=obj)
    return render(request, "projects/ticket_form.html", {"form": form, "obj": obj})


# ---------------------------------------------------------------------------
# Benchmarks & Veille
# ---------------------------------------------------------------------------
@internal_required
def benchmark_list(request):
    from .models import Benchmark
    cat = request.GET.get("cat", "")
    qs = Benchmark.objects.select_related("added_by")
    if cat:
        qs = qs.filter(category=cat)
    return render(request, "projects/benchmark_list.html", {
        "benchmarks": qs, "cat": cat, "categories": Benchmark.Category.choices,
    })


@internal_required
def benchmark_edit(request, pk=None):
    from .models import Benchmark
    from .forms import BenchmarkForm
    obj = get_object_or_404(Benchmark, pk=pk) if pk else None
    if request.method == "POST":
        form = BenchmarkForm(request.POST, instance=obj)
        if form.is_valid():
            b = form.save(commit=False)
            if not obj:
                b.added_by = request.user
            b.save()
            messages.success(request, "Benchmark enregistré.")
            return redirect("projects:benchmark_list")
    else:
        form = BenchmarkForm(instance=obj)
    return render(request, "projects/benchmark_form.html", {"form": form, "obj": obj})
