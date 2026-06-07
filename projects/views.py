"""Vues du module Projets & Événements."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import Role
from accounts.utils import internal_required, role_required

from .forms import MediaForm, ProjectForm
from .models import Phase, Project

manager_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


@internal_required
def project_list(request):
    kind = request.GET.get("kind", "")
    qs = Project.objects.select_related("client", "manager")
    if kind:
        qs = qs.filter(kind=kind)
    title = {"EVENT": "Événements", "CAMPAIGN": "Campagnes"}.get(kind, "Projets & événements")
    return render(request, "projects/list.html", {
        "projects": qs, "kind": kind, "title": title,
        "kinds": Project.Kind.choices,
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
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Projet enregistré.")
            return redirect("projects:detail", pk=obj.pk)
    else:
        form = ProjectForm(instance=project)
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
