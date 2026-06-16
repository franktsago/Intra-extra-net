"""Vues du module employés : annuaire, fiches, organigramme, départements."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import ActivityLog, Role
from accounts.utils import hide_superadmin, internal_required, log_activity, role_required

from .forms import DepartmentForm, EmployeeForm
from .models import Department, Employee


@internal_required
def employee_list(request):
    q = request.GET.get("q", "").strip()
    dept = request.GET.get("dept", "")
    # Inclure les comptes désactivés / sortis des effectifs (masqués par défaut).
    show_inactive = request.GET.get("inactifs") == "1"
    employees = (Employee.objects.select_related("user")
                 .prefetch_related("departments", "positions"))
    employees = hide_superadmin(employees, request.user, user_field="user")
    if not show_inactive:
        # Un employé désactivé (compte inactif ou sorti des effectifs) n'apparaît plus.
        employees = employees.filter(user__is_active=True).exclude(
            status=Employee.Status.TERMINATED)
    if q:
        employees = employees.filter(
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q)
            | Q(matricule__icontains=q) | Q(user__email__icontains=q)
            | Q(positions__title__icontains=q)
        )
    if dept:
        employees = employees.filter(departments__id=dept)
    employees = employees.distinct()
    page = Paginator(employees, 12).get_page(request.GET.get("page"))
    return render(request, "employees/list.html", {
        "page_obj": page, "q": q, "dept": dept, "show_inactive": show_inactive,
        "departments": Department.objects.all(),
    })


@internal_required
def employee_detail(request, pk):
    employee = get_object_or_404(
        Employee.objects.select_related("user", "manager__user")
        .prefetch_related("departments", "positions"), pk=pk
    )
    has_contract_file = employee.contracts.exclude(file="").exclude(file__isnull=True).exists()
    latest_contract = employee.contracts.order_by("-is_active", "-start_date").first()
    return render(request, "employees/detail.html", {
        "employee": employee,
        "subordinates": employee.subordonnes.select_related("user"),
        "has_contract_file": has_contract_file,
        "latest_contract": latest_contract,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def attestation_travail(request, pk):
    """Attestation de travail (PDF) — réservée aux NON-stagiaires (CDI/CDD/Temporaire)."""
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse
    from hr.attestation_pdf import attestation_travail_pdf
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=pk)
    if employee.is_intern:
        raise PermissionDenied("Attestation de travail réservée aux salariés (CDI/CDD/Temporaire). "
                               "Pour un stagiaire, utilisez l'attestation de stage.")
    pdf = attestation_travail_pdf(employee, signer=request.user)
    log_activity(request, ActivityLog.Action.DOWNLOAD,
                 f"Attestation de travail — {employee.full_name}")
    return FileResponse(pdf, as_attachment=True,
                        filename=f"attestation-travail-{employee.matricule}.pdf",
                        content_type="application/pdf")


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def attestation_stage(request, pk):
    """Attestation de stage (PDF) — réservée aux STAGIAIRES."""
    from django.core.exceptions import PermissionDenied
    from django.http import FileResponse
    from hr.attestation_pdf import attestation_stage_pdf
    employee = get_object_or_404(Employee.objects.select_related("user"), pk=pk)
    if not employee.is_intern:
        raise PermissionDenied("Attestation de stage réservée aux stagiaires. "
                               "Pour un salarié, utilisez l'attestation de travail.")
    pdf = attestation_stage_pdf(employee, signer=request.user)
    log_activity(request, ActivityLog.Action.DOWNLOAD,
                 f"Attestation de stage — {employee.full_name}")
    return FileResponse(pdf, as_attachment=True,
                        filename=f"attestation-stage-{employee.matricule}.pdf",
                        content_type="application/pdf")


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def contract_download(request, pk):
    """Téléchargement du contrat de travail signé (fichier joint) — RH / CEO / admin."""
    from django.http import FileResponse, Http404
    employee = get_object_or_404(Employee, pk=pk)
    contract = (employee.contracts.exclude(file="").exclude(file__isnull=True)
                .order_by("-is_active", "-start_date").first())
    if not contract or not contract.file:
        raise Http404("Aucun contrat signé n'est disponible pour cet employé.")
    log_activity(request, ActivityLog.Action.DOWNLOAD,
                 f"Contrat de travail — {employee.full_name}")
    return FileResponse(contract.file.open("rb"), as_attachment=True,
                        filename=f"contrat-{employee.matricule}{_ext(contract.file.name)}")


def _ext(name):
    import os
    return os.path.splitext(name)[1] or ".pdf"


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def employee_edit(request, pk=None):
    employee = get_object_or_404(Employee, pk=pk) if pk else None
    if request.method == "POST":
        form = EmployeeForm(request.POST, instance=employee, viewer=request.user)
        if form.is_valid():
            obj = form.save()
            from .models import attach_new_relations
            attach_new_relations(obj, request.POST.getlist("new_departments"),
                                 request.POST.getlist("new_positions"))
            action = ActivityLog.Action.UPDATE if pk else ActivityLog.Action.CREATE
            log_activity(request, action, f"Fiche employé : {obj.full_name}")
            messages.success(request, "Fiche employé enregistrée.")
            return redirect("employees:detail", pk=obj.pk)
    else:
        form = EmployeeForm(instance=employee, viewer=request.user)
    return render(request, "employees/form.html", {"form": form, "employee": employee})


@internal_required
def org_chart(request):
    """Organigramme : départements et leurs effectifs."""
    from django.db.models import Prefetch
    visible_emps = hide_superadmin(
        Employee.objects.filter(user__is_active=True)
        .exclude(status=Employee.Status.TERMINATED)
        .select_related("user").prefetch_related("positions"),
        request.user, user_field="user")
    departments = Department.objects.select_related("manager").prefetch_related(
        Prefetch("employees", queryset=visible_emps)
    )
    return render(request, "employees/org_chart.html", {"departments": departments})


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def department_list(request):
    if request.method == "POST":
        form = DepartmentForm(request.POST, viewer=request.user)
        if form.is_valid():
            obj = form.save()
            log_activity(request, ActivityLog.Action.CREATE, f"Département créé : {obj.name}")
            messages.success(request, "Département créé.")
            return redirect("employees:departments")
    else:
        form = DepartmentForm(viewer=request.user)
    return render(request, "employees/departments.html", {
        "departments": Department.objects.select_related("manager").all(), "form": form,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def department_edit(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        form = DepartmentForm(request.POST, instance=department, viewer=request.user)
        if form.is_valid():
            obj = form.save()
            log_activity(request, ActivityLog.Action.UPDATE, f"Département modifié : {obj.name}")
            messages.success(request, "Département mis à jour.")
            return redirect("employees:departments")
    else:
        form = DepartmentForm(instance=department, viewer=request.user)
    return render(request, "employees/departments.html", {
        "departments": Department.objects.select_related("manager").all(),
        "form": form, "editing": department,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH)
def department_delete(request, pk):
    department = get_object_or_404(Department, pk=pk)
    if request.method == "POST":
        name = department.name
        department.delete()
        log_activity(request, ActivityLog.Action.DELETE, f"Département supprimé : {name}")
        messages.success(request, "Département supprimé.")
        return redirect("employees:departments")
    return render(request, "employees/department_confirm_delete.html", {"department": department})
