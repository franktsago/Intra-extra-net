"""Module disciplinaire (RH / Direction) — procédure camerounaise."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, Role
from accounts.utils import internal_required, log_activity, role_required
from notifications.models import Notification, notify

from .forms import DisciplinaryForm
from .models import DisciplinaryRecord
from .pdf import sanction_pdf


@role_required(Role.RH, Role.CEO, Role.ADMIN)
def record_list(request):
    records = DisciplinaryRecord.objects.select_related("employee__user")
    return render(request, "disciplinary/list.html", {"records": records})


@role_required(Role.RH, Role.CEO, Role.ADMIN)
def record_edit(request, pk=None):
    record = get_object_or_404(DisciplinaryRecord, pk=pk) if pk else None
    if request.method == "POST":
        form = DisciplinaryForm(request.POST, instance=record)
        if form.is_valid():
            obj = form.save(commit=False)
            if not record:
                obj.decided_by = request.user
            obj.save()
            # Référence + notification dès que la sanction est notifiée.
            if obj.status == DisciplinaryRecord.Status.NOTIFIED:
                if not obj.reference:
                    obj.reference = f"SANCT-{timezone.localdate():%Y}-{obj.pk:04d}"
                    obj.save(update_fields=["reference"])
                notify(obj.employee.user, "Notification d'une décision disciplinaire",
                       f"{obj.get_sanction_type_display()} — référence {obj.reference}. "
                       "Le document officiel est disponible.",
                       Notification.Level.WARNING, reverse("disciplinary:detail", args=[obj.pk]))
            messages.success(request, "Dossier disciplinaire enregistré.")
            return redirect("disciplinary:detail", pk=obj.pk)
    else:
        form = DisciplinaryForm(instance=record)
    return render(request, "disciplinary/form.html", {"form": form, "record": record})


@role_required(Role.RH, Role.CEO, Role.ADMIN)
def record_detail(request, pk):
    record = get_object_or_404(DisciplinaryRecord.objects.select_related("employee__user"), pk=pk)
    return render(request, "disciplinary/detail.html", {"record": record})


@internal_required
def record_pdf(request, pk):
    """Télécharge la lettre de sanction (PDF). Accès : RH/admin et l'employé concerné.

    Téléchargement tracé dans le journal d'activité.
    """
    record = get_object_or_404(DisciplinaryRecord.objects.select_related("employee__user", "decided_by"), pk=pk)
    user = request.user
    is_concerned = record.employee.user_id == user.id
    if not (is_concerned or user.is_rh):
        raise PermissionDenied("Accès réservé au RH et à l'employé concerné.")
    if record.status not in {DisciplinaryRecord.Status.NOTIFIED, DisciplinaryRecord.Status.CLOSED}:
        raise PermissionDenied("Le document n'est disponible qu'après notification.")

    pdf = sanction_pdf(record)
    log_activity(request, ActivityLog.Action.DOWNLOAD,
                 f"Téléchargement {record.get_sanction_type_display()} {record.reference} — {record.employee.full_name}")
    filename = f"{record.reference or 'sanction'}.pdf"
    return FileResponse(pdf, as_attachment=True, filename=filename, content_type="application/pdf")
