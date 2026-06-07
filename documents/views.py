"""Gestion documentaire : dépôt, recherche, téléchargement, archivage."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, F
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import ActivityLog, Role
from accounts.utils import internal_required, log_activity, role_required

from .forms import DocumentForm
from .models import Document, DocumentCategory


@internal_required
def document_list(request):
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "")
    show_archived = request.GET.get("archived") == "1"

    docs = Document.objects.select_related("category", "uploaded_by")
    docs = docs.filter(is_archived=show_archived)
    if q:
        docs = docs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if cat:
        docs = docs.filter(category_id=cat)

    # Filtrage par visibilité selon le rôle.
    visible = [d for d in docs if d.can_view(request.user)]
    page = Paginator(visible, 12).get_page(request.GET.get("page"))
    return render(request, "documents/list.html", {
        "page_obj": page, "q": q, "cat": cat, "show_archived": show_archived,
        "categories": DocumentCategory.objects.all(),
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def document_upload(request):
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES, viewer=request.user)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            # Le marquage confidentiel est réservé à RH/CEO/admin.
            if not request.user.is_rh:
                doc.is_confidential = False
            # Visibilité « Mon équipe » : le déposant devient le responsable propriétaire.
            if doc.visibility == Document.Visibility.TEAM:
                doc.team_owner = request.user
            doc.save()
            log_activity(request, ActivityLog.Action.CREATE, f"Dépôt du document « {doc.title} »")
            messages.success(request, "Document déposé avec succès.")
            return redirect("documents:list")
    else:
        form = DocumentForm(viewer=request.user)
    return render(request, "documents/form.html", {"form": form})


@internal_required
def document_view(request, pk):
    """Lecture en ligne d'un document (visionneuse). Confidentiel = filigrane + verrous."""
    doc = get_object_or_404(Document, pk=pk)
    if not doc.can_view(request.user):
        raise PermissionDenied("Vous n'avez pas accès à ce document.")
    return render(request, "documents/view.html", {"doc": doc})


@internal_required
def document_raw(request, pk):
    """Sert le fichier en ligne (inline) pour l'affichage dans la visionneuse."""
    doc = get_object_or_404(Document, pk=pk)
    if not doc.can_view(request.user):
        raise PermissionDenied("Vous n'avez pas accès à ce document.")
    resp = FileResponse(doc.file.open("rb"), as_attachment=False, filename=doc.filename)
    if doc.is_confidential:
        resp["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        resp["X-Content-Type-Options"] = "nosniff"
    return resp


@internal_required
def document_download(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if not doc.can_view(request.user):
        raise PermissionDenied("Vous n'avez pas accès à ce document.")
    # Document confidentiel : téléchargement interdit (lecture en ligne uniquement).
    if doc.is_confidential:
        messages.error(request, "Ce document est confidentiel : lecture en ligne uniquement, "
                                "téléchargement désactivé.")
        return redirect("documents:view", pk=pk)
    Document.objects.filter(pk=pk).update(download_count=F("download_count") + 1)
    log_activity(request, ActivityLog.Action.DOWNLOAD, f"Téléchargement : {doc.title}")
    return FileResponse(doc.file.open("rb"), as_attachment=True, filename=doc.filename)


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def document_archive(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    # Un document confidentiel ne peut être (dés)archivé que par RH/CEO/admin.
    if doc.is_confidential and not request.user.is_rh:
        messages.error(request, "Action réservée à la direction RH pour un document confidentiel.")
        return redirect("documents:list")
    doc.is_archived = not doc.is_archived
    doc.save(update_fields=["is_archived"])
    messages.info(request, "Document archivé." if doc.is_archived else "Document désarchivé.")
    return redirect("documents:list")


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    # Confidentiel → suppression réservée à RH/CEO/admin.
    if doc.is_confidential and not request.user.is_rh:
        messages.error(request, "Seuls le CEO, la RH ou l'administrateur peuvent supprimer un document confidentiel.")
        return redirect("documents:list")
    if request.method == "POST":
        title = doc.title
        doc.delete()
        log_activity(request, ActivityLog.Action.DELETE, f"Suppression du document « {title} »")
        messages.success(request, f"Document « {title} » supprimé.")
        return redirect("documents:list")
    return render(request, "documents/confirm_delete.html", {"doc": doc})
