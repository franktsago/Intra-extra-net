"""Vues RSE."""
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from accounts.utils import internal_required, role_required
from accounts.models import Role
from .forms import RSEIndicatorForm, RSEInitiativeForm, RSEReportForm, RSEResourceForm
from .models import RSEIndicator, RSEInitiative, RSEReport, RSEResource, RSESupplier

mgr_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


@mgr_required
def dashboard(request):
    indicators = RSEIndicator.objects.order_by("category", "name")
    initiatives = RSEInitiative.objects.select_related("responsible").order_by("-created_at")[:6]
    active_count = RSEInitiative.objects.filter(status=RSEInitiative.Status.ACTIVE).count()
    resources = RSEResource.objects.filter(published=True)[:4]
    reports = RSEReport.objects.filter(published=True).order_by("-year")[:3]
    by_cat = {}
    for ind in indicators:
        by_cat.setdefault(ind.get_category_display(), []).append(ind)
    return render(request, "rse/dashboard.html", {
        "by_cat": by_cat, "initiatives": initiatives, "active_count": active_count,
        "resources": resources, "reports": reports,
    })


@internal_required
def initiatives(request):
    qs = RSEInitiative.objects.select_related("responsible").order_by("-created_at")
    return render(request, "rse/initiatives.html", {"initiatives": qs})


@mgr_required
def initiative_edit(request, pk=None):
    obj = get_object_or_404(RSEInitiative, pk=pk) if pk else None
    if request.method == "POST":
        form = RSEInitiativeForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Initiative enregistrée.")
            return redirect("rse:initiatives")
    else:
        form = RSEInitiativeForm(instance=obj)
    return render(request, "rse/initiative_form.html", {"form": form, "obj": obj})


@mgr_required
def reports(request):
    qs = RSEReport.objects.order_by("-year")
    return render(request, "rse/reports.html", {"reports": qs})


@mgr_required
def report_edit(request, pk=None):
    obj = get_object_or_404(RSEReport, pk=pk) if pk else None
    if request.method == "POST":
        form = RSEReportForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            r = form.save(commit=False)
            if not obj:
                r.created_by = request.user
            r.save()
            messages.success(request, "Rapport enregistré.")
            return redirect("rse:reports")
    else:
        form = RSEReportForm(instance=obj)
    return render(request, "rse/report_form.html", {"form": form, "obj": obj})


@internal_required
def resources(request):
    qs = RSEResource.objects.filter(published=True)
    return render(request, "rse/resources.html", {"resources": qs})


@mgr_required
def suppliers(request):
    qs = RSESupplier.objects.order_by("-score")
    return render(request, "rse/suppliers.html", {"suppliers": qs})
