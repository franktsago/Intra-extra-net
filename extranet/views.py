"""Portail extranet : espace client/partenaire, projets, fichiers, messagerie.

Cloisonnement : un utilisateur externe ne voit que SES projets ; les internes
(chargés de compte, admin) voient les projets qu'ils pilotent ou la totalité.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import EXTRANET_ROLES, Role, User
from accounts.utils import role_required
from notifications.models import Notification, notify

from .forms import (
    ClientRequestForm, CreativeCommentForm, CreativeForm, CreativeVersionForm,
    MessageForm, ProjectFileForm, ProjectForm, TicketForm, TicketReplyForm,
)
from .models import ClientRequest, Creative, CreativeVersion, Project, ProjectFile, Ticket


def _visible_projects(user):
    # L'administrateur principal ET le Directeur Général (CEO) voient tous les projets.
    if user.is_ceo:
        return Project.objects.all()
    if user.is_internal:
        return Project.objects.filter(internal_lead=user)
    return Project.objects.filter(client=user)


def _direction_users():
    """Comptes de la Direction Générale (CEO) + administrateur principal."""
    return User.objects.filter(role__in=[Role.CEO, Role.ADMIN], is_active=True)


def _project_correspondents(project, exclude=None):
    """Destinataires d'un message projet : chargé de compte + Direction (CEO).

    Si l'émetteur est interne, on inclut aussi le client propriétaire de l'espace.
    """
    recipients = set()
    if project.internal_lead_id:
        recipients.add(project.internal_lead)
    for u in _direction_users():
        recipients.add(u)
    # Quand un interne écrit, le client doit recevoir la notification.
    if exclude is not None and not exclude.is_external and project.client_id:
        recipients.add(project.client)
    recipients.discard(exclude)
    return recipients


@login_required
def extranet_home(request):
    user = request.user
    # L'extranet (gestion des espaces clients) est réservé aux responsables+ et aux
    # utilisateurs externes (leur portail). Un employé interne n'y a pas accès.
    if user.is_internal and not user.is_manager:
        from django.contrib import messages as _m
        _m.info(request, "L'espace Extranet est réservé aux responsables.")
        return redirect("dashboard:home")
    projects = _visible_projects(user).select_related("client", "internal_lead")
    from .models import ExtranetMessage, ProjectFile
    context = {
        "projects": projects, "is_external": user.is_external,
        "can_manage": user.is_manager,  # responsables, RH, admin
        "count_active": projects.filter(status=Project.Status.ACTIVE).count(),
        "count_done": projects.filter(status=Project.Status.DONE).count(),
        "count_files": ProjectFile.objects.filter(project__in=projects).count(),
        "count_msgs": ExtranetMessage.objects.filter(project__in=projects).count(),
        "recent_files": ProjectFile.objects.filter(project__in=projects).select_related("project").order_by("-created_at")[:5],
    }
    # Pour l'administration de l'extranet : liste des utilisateurs externes.
    if user.is_manager:
        context["external_users"] = (
            User.objects.filter(role__in=EXTRANET_ROLES).order_by("-is_active", "last_name")
        )
        context["count_externals"] = context["external_users"].count()
    # Actions requises (client) : devis à signer + documents à valider.
    if user.is_external:
        from business.models import Invoice, Quote
        from marketing.models import Campaign
        client_ids = _my_client_ids(user)
        context["pending_quotes"] = (
            Quote.objects.filter(client_id__in=client_ids, status=Quote.Status.SENT)
            .select_related("client")
        )
        context["pending_files"] = (
            ProjectFile.objects.filter(project__in=projects,
                                       direction=ProjectFile.Direction.TO_CLIENT,
                                       validation=ProjectFile.Validation.PENDING)
            .select_related("project")
        )
        context["report_count"] = ProjectFile.objects.filter(
            project__in=projects, kind=ProjectFile.Kind.REPORT).count()
        # Phrase de synthèse personnalisée.
        context["active_campaigns"] = Campaign.objects.filter(
            brand_id__in=client_ids, status=Campaign.Status.ACTIVE).count()
        context["pending_quotes_count"] = context["pending_quotes"].count()
        context["unpaid_invoices"] = Invoice.objects.filter(
            kind=Invoice.Kind.CLIENT, client_id__in=client_ids,
            status__in=[Invoice.Status.SENT, Invoice.Status.PARTIAL, Invoice.Status.OVERDUE]
        ).count()
        context["open_tickets"] = Ticket.objects.filter(client=user, status__in=[
            Ticket.Status.OPEN, Ticket.Status.IN_PROGRESS]).count()
    return render(request, "extranet/home.html", context)


@login_required
def file_validate(request, pk, decision):
    """Le client valide/rejette un document qui lui a été transmis."""
    f = get_object_or_404(ProjectFile.objects.select_related("project"), pk=pk)
    project = f.project
    is_client = project.client_id == request.user.id
    if not (is_client or request.user.is_admin_lpm):
        raise PermissionDenied("Seul le client peut valider ce document.")
    if f.direction == ProjectFile.Direction.TO_CLIENT and decision in {"approve", "reject"}:
        f.validation = (ProjectFile.Validation.APPROVED if decision == "approve"
                        else ProjectFile.Validation.REJECTED)
        f.save(update_fields=["validation"])
        if project.internal_lead:
            notify(project.internal_lead,
                   f"Document {f.get_validation_display().lower()} — {project.name}",
                   f"« {f.title} » a été {f.get_validation_display().lower()} par le client.",
                   Notification.Level.INFO, reverse("extranet:project", args=[project.pk]))
        messages.success(request, "Votre décision sur le document a été enregistrée.")
    return redirect("extranet:project", pk=project.pk)


@login_required
def project_detail(request, pk):
    project = get_object_or_404(Project, pk=pk)
    user = request.user
    # Les responsables/RH/admin (gestionnaires de l'extranet) accèdent à tous les
    # projets ; le client et le chargé de compte accèdent au leur.
    allowed = (user.is_manager or project.client_id == user.id
               or project.internal_lead_id == user.id)
    if not allowed:
        raise PermissionDenied("Vous n'avez pas accès à cet espace projet.")

    file_form = ProjectFileForm()
    msg_form = MessageForm()

    if request.method == "POST":
        if "send_message" in request.POST:
            msg_form = MessageForm(request.POST)
            if msg_form.is_valid():
                m = msg_form.save(commit=False)
                m.project = project
                m.sender = user
                m.save()
                # Destinataires extranet : responsable(s) du projet + Direction (CEO).
                for target in _project_correspondents(project, exclude=user):
                    notify(target, f"Nouveau message — {project.name}", m.body[:120],
                           Notification.Level.INFO, reverse("extranet:project", args=[project.pk]))
                return redirect("extranet:project", pk=pk)
        elif "upload_file" in request.POST:
            file_form = ProjectFileForm(request.POST, request.FILES)
            if file_form.is_valid():
                f = file_form.save(commit=False)
                f.project = project
                f.uploaded_by = user
                f.direction = (ProjectFile.Direction.FROM_CLIENT if user.is_external
                               else ProjectFile.Direction.TO_CLIENT)
                if user.is_external:
                    # Un client transmet un document, jamais un rapport officiel.
                    f.kind = ProjectFile.Kind.DOCUMENT
                f.save()
                messages.success(request, "Fichier partagé.")
                return redirect("extranet:project", pk=pk)

    return render(request, "extranet/project_detail.html", {
        "project": project,
        "files": project.files.select_related("uploaded_by"),
        "msgs": project.messages.select_related("sender"),
        "file_form": file_form, "msg_form": msg_form,
    })


@login_required
def project_progress(request, pk=None):
    """Suivi de l'avancement des projets du client (barre + statut + échéance)."""
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    projects = _visible_projects(user).select_related("client", "internal_lead").prefetch_related("files")
    return render(request, "extranet/progress.html", {
        "projects": projects, "is_external": user.is_external,
        "status_order": ["PENDING", "ACTIVE", "ON_HOLD", "DONE"],
    })


@login_required
def reports(request):
    """Rapports transmis au client (fichiers de type Rapport)."""
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    projects = _visible_projects(user)
    report_files = (ProjectFile.objects
                    .filter(project__in=projects, kind=ProjectFile.Kind.REPORT)
                    .select_related("project", "uploaded_by")
                    .order_by("-created_at"))
    return render(request, "extranet/reports.html", {
        "reports": report_files, "is_external": user.is_external,
    })


@login_required
def validations(request):
    """Centre de validation client : devis à signer + documents à approuver."""
    user = request.user
    if not user.is_external and not user.is_admin_lpm:
        return redirect("extranet:home")
    from business.models import Quote
    quotes = (Quote.objects.filter(client_id__in=_my_client_ids(user), status=Quote.Status.SENT)
              .select_related("client"))
    projects = _visible_projects(user)
    files = (ProjectFile.objects.filter(project__in=projects,
                                        direction=ProjectFile.Direction.TO_CLIENT,
                                        validation=ProjectFile.Validation.PENDING)
             .select_related("project"))
    return render(request, "extranet/validations.html", {
        "quotes": quotes, "files": files,
    })


# --------------------------------------------------------------------------- #
# Campagnes du client (suivi temps réel)
# --------------------------------------------------------------------------- #
@login_required
def campaigns(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    from marketing.models import Campaign
    if user.is_ceo:
        qs = Campaign.objects.all()
    elif user.is_external:
        qs = Campaign.objects.filter(brand_id__in=_my_client_ids(user))
    else:
        qs = Campaign.objects.filter(manager=user)
    qs = qs.select_related("brand", "project").prefetch_related("project__phases")
    return render(request, "extranet/campaigns.html", {
        "campaigns": qs, "is_external": user.is_external,
    })


# --------------------------------------------------------------------------- #
# Centre de téléchargement unifié (avec recherche)
# --------------------------------------------------------------------------- #
@login_required
def downloads(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    q = request.GET.get("q", "").strip()
    cat = request.GET.get("cat", "")
    projects = _visible_projects(user)
    items = []
    # Documents & rapports de projet
    for f in ProjectFile.objects.filter(project__in=projects).select_related("project"):
        items.append({
            "title": f.title,
            "category": "Rapport" if f.kind == ProjectFile.Kind.REPORT else "Document",
            "date": f.created_at, "url": f.file.url, "icon": "fa-file-lines",
            "project": f.project.name,
        })
    if user.is_external:
        client_ids = _my_client_ids(user)
        from business.models import Invoice, Quote
        from marketing.models import MediaAsset
        from django.urls import reverse as _rev
        # Supports marketing (logos, affiches, flyers, vidéos, chartes)
        kind_label = dict(MediaAsset.Kind.choices)
        for a in MediaAsset.objects.filter(brand_id__in=client_ids).select_related("brand"):
            items.append({
                "title": a.title, "category": kind_label.get(a.kind, "Média"),
                "date": a.created_at, "url": a.file.url, "icon": "fa-image",
                "project": a.brand.name if a.brand else "",
            })
        # Devis (PDF)
        for qte in Quote.objects.filter(client_id__in=client_ids).exclude(
                status__in=[Quote.Status.DRAFT, Quote.Status.INTERNAL]):
            items.append({
                "title": f"Devis {qte.number}", "category": "Devis",
                "date": qte.issue_date, "url": _rev("extranet:client_quote_pdf", args=[qte.pk]),
                "icon": "fa-file-signature", "project": qte.title,
            })
        # Factures (PDF)
        for inv in Invoice.objects.filter(kind=Invoice.Kind.CLIENT, client_id__in=client_ids).exclude(
                status=Invoice.Status.DRAFT):
            items.append({
                "title": f"Facture {inv.number}", "category": "Facture",
                "date": inv.issue_date, "url": _rev("extranet:client_invoice_pdf", args=[inv.pk]),
                "icon": "fa-file-invoice-dollar", "project": inv.title,
            })
    # Catégories disponibles (calculées avant tout filtre).
    categories = sorted({it["category"] for it in items})
    # Filtres recherche + catégorie
    if q:
        ql = q.lower()
        items = [it for it in items if ql in it["title"].lower() or ql in (it["project"] or "").lower()]
    if cat:
        items = [it for it in items if it["category"] == cat]
    items.sort(key=lambda it: str(it["date"]), reverse=True)
    return render(request, "extranet/downloads.html", {
        "items": items, "q": q, "cat": cat, "categories": categories,
    })


# --------------------------------------------------------------------------- #
# Galerie photos / vidéos (activations terrain)
# --------------------------------------------------------------------------- #
@login_required
def gallery(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    from projects.models import ProjectMedia
    if user.is_ceo:
        media = ProjectMedia.objects.all()
    elif user.is_external:
        media = ProjectMedia.objects.filter(project__client_id__in=_my_client_ids(user))
    else:
        media = ProjectMedia.objects.filter(project__manager=user)
    media = media.select_related("project").order_by("-created_at")
    return render(request, "extranet/gallery.html", {"media": media})


# --------------------------------------------------------------------------- #
# Réclamations / tickets
# --------------------------------------------------------------------------- #
@login_required
def tickets(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    if user.is_external:
        qs = Ticket.objects.filter(client=user)
    else:
        qs = Ticket.objects.all()
    qs = qs.select_related("client", "project", "assigned_to")
    # Création (client uniquement).
    form = TicketForm(client=user if user.is_external else None)
    if request.method == "POST" and user.is_external:
        form = TicketForm(request.POST, client=user)
        if form.is_valid():
            t = form.save(commit=False)
            t.client = user
            t.save()
            for u in _direction_users():
                notify(u, f"Nouveau ticket {t.reference}",
                       f"{user.get_full_name() or user.username} : {t.subject}",
                       Notification.Level.INFO, reverse("extranet:ticket", args=[t.pk]))
            messages.success(request, f"Réclamation enregistrée ({t.reference}).")
            return redirect("extranet:ticket", pk=t.pk)
    return render(request, "extranet/tickets.html", {
        "tickets": qs, "form": form, "is_external": user.is_external,
    })


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(Ticket.objects.select_related("client", "project", "assigned_to"), pk=pk)
    user = request.user
    if not (user.is_manager or ticket.client_id == user.id):
        raise PermissionDenied("Ce ticket ne vous est pas accessible.")
    reply_form = TicketReplyForm()
    if request.method == "POST":
        if "reply" in request.POST:
            reply_form = TicketReplyForm(request.POST)
            if reply_form.is_valid():
                r = reply_form.save(commit=False)
                r.ticket = ticket
                r.author = user
                r.save()
                # Notifier l'autre partie.
                target = ticket.client if user.is_manager else (ticket.assigned_to or None)
                if user.is_manager and target:
                    notify(target, f"Réponse à votre ticket {ticket.reference}",
                           r.body[:120], Notification.Level.INFO,
                           reverse("extranet:ticket", args=[ticket.pk]))
                elif not user.is_manager:
                    for u in _direction_users():
                        notify(u, f"Nouveau message — ticket {ticket.reference}",
                               r.body[:120], Notification.Level.INFO,
                               reverse("extranet:ticket", args=[ticket.pk]))
                return redirect("extranet:ticket", pk=pk)
        elif "status" in request.POST and user.is_manager:
            new_status = request.POST.get("status")
            if new_status in Ticket.Status.values:
                ticket.status = new_status
                if not ticket.assigned_to:
                    ticket.assigned_to = user
                ticket.save(update_fields=["status", "assigned_to", "updated_at"])
                notify(ticket.client, f"Ticket {ticket.reference} — {ticket.get_status_display()}",
                       f"Votre ticket « {ticket.subject} » est maintenant : {ticket.get_status_display()}.",
                       Notification.Level.INFO, reverse("extranet:ticket", args=[ticket.pk]))
                messages.success(request, "Statut mis à jour.")
            return redirect("extranet:ticket", pk=pk)
    return render(request, "extranet/ticket_detail.html", {
        "ticket": ticket, "replies": ticket.replies.select_related("author"),
        "reply_form": reply_form, "statuses": Ticket.Status.choices,
    })


# --------------------------------------------------------------------------- #
# Demandes (nouvelle campagne / devis / création / événement)
# --------------------------------------------------------------------------- #
@login_required
def requests_view(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    if user.is_external:
        qs = ClientRequest.objects.filter(client=user)
    else:
        qs = ClientRequest.objects.all()
    qs = qs.select_related("client")
    form = ClientRequestForm()
    if request.method == "POST" and user.is_external:
        form = ClientRequestForm(request.POST)
        if form.is_valid():
            dem = form.save(commit=False)
            dem.client = user
            dem.save()
            for u in _direction_users():
                notify(u, "Nouvelle demande client",
                       f"{user.get_full_name() or user.username} — {dem.get_kind_display()} : {dem.title}",
                       Notification.Level.INFO, reverse("extranet:requests"))
            messages.success(request, "Votre demande a été transmise à nos équipes.")
            return redirect("extranet:requests")
    return render(request, "extranet/requests.html", {
        "demandes": qs, "form": form, "is_external": user.is_external,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def request_decide(request, pk, decision):
    dem = get_object_or_404(ClientRequest, pk=pk)
    mapping = {"review": ClientRequest.Status.IN_REVIEW,
               "accept": ClientRequest.Status.ACCEPTED,
               "decline": ClientRequest.Status.DECLINED}
    if request.method == "POST" and decision in mapping:
        dem.status = mapping[decision]
        dem.save(update_fields=["status"])
        notify(dem.client, f"Demande « {dem.title} » — {dem.get_status_display()}",
               f"Votre demande est maintenant : {dem.get_status_display()}.",
               Notification.Level.INFO, reverse("extranet:requests"))
        messages.success(request, "Demande mise à jour.")
    return redirect("extranet:requests")


# --------------------------------------------------------------------------- #
# Créations graphiques (validation par versions V1 → V2 → V3)
# --------------------------------------------------------------------------- #
def _visible_creatives(user):
    if user.is_ceo:
        return Creative.objects.all()
    if user.is_external:
        return Creative.objects.filter(project__client=user)
    return Creative.objects.filter(project__internal_lead=user)


@login_required
def creatives(request):
    user = request.user
    if user.is_internal and not user.is_manager:
        return redirect("dashboard:home")
    qs = (_visible_creatives(user).select_related("project")
          .prefetch_related("versions"))
    return render(request, "extranet/creatives.html", {
        "creatives": qs, "can_manage": user.is_manager,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def creative_create(request):
    user = request.user
    form = CreativeForm()
    form.fields["project"].queryset = _visible_projects(user)
    if request.method == "POST":
        form = CreativeForm(request.POST, request.FILES)
        form.fields["project"].queryset = _visible_projects(user)
        if form.is_valid():
            creative = form.save(commit=False)
            creative.created_by = user
            creative.save()
            CreativeVersion.objects.create(
                creative=creative, number=1, file=form.cleaned_data["file"],
                note=form.cleaned_data.get("note", ""), uploaded_by=user)
            if creative.project.client_id:
                notify(creative.project.client, "Nouveau visuel à valider",
                       f"« {creative.title} » (V1) attend votre avis.",
                       Notification.Level.INFO, reverse("extranet:creative", args=[creative.pk]))
            messages.success(request, "Création graphique publiée pour validation.")
            return redirect("extranet:creative", pk=creative.pk)
    return render(request, "extranet/creative_form.html", {"form": form})


@login_required
def creative_detail(request, pk):
    creative = get_object_or_404(Creative.objects.select_related("project"), pk=pk)
    user = request.user
    if not (user.is_manager or creative.project.client_id == user.id):
        raise PermissionDenied("Cette création ne vous est pas accessible.")
    current = creative.current_version
    if request.method == "POST":
        # Commentaire (client ou LPM)
        if "comment" in request.POST and current:
            cform = CreativeCommentForm(request.POST)
            if cform.is_valid():
                c = cform.save(commit=False)
                c.version = current
                c.author = user
                c.save()
                # Notifier l'autre partie.
                if user.is_external and creative.project.internal_lead:
                    notify(creative.project.internal_lead, f"Commentaire — {creative.title}",
                           c.body[:120], Notification.Level.INFO,
                           reverse("extranet:creative", args=[creative.pk]))
                elif not user.is_external and creative.project.client_id:
                    notify(creative.project.client, f"Commentaire — {creative.title}",
                           c.body[:120], Notification.Level.INFO,
                           reverse("extranet:creative", args=[creative.pk]))
            return redirect("extranet:creative", pk=pk)
        # Nouvelle version (LPM uniquement)
        if "add_version" in request.POST and user.is_manager:
            vform = CreativeVersionForm(request.POST, request.FILES)
            if vform.is_valid():
                v = vform.save(commit=False)
                v.creative = creative
                v.number = (current.number + 1) if current else 1
                v.uploaded_by = user
                v.save()
                creative.status = Creative.Status.IN_REVIEW
                creative.save(update_fields=["status"])
                if creative.project.client_id:
                    notify(creative.project.client, "Nouvelle version d'un visuel",
                           f"« {creative.title} » (V{v.number}) attend votre avis.",
                           Notification.Level.INFO, reverse("extranet:creative", args=[creative.pk]))
                messages.success(request, f"Version {v.number} publiée.")
            return redirect("extranet:creative", pk=pk)
        # Décision du client sur la version courante
        if "decide" in request.POST and creative.project.client_id == user.id and current:
            decision = request.POST.get("decide")
            if decision == "approve":
                current.status = CreativeVersion.Status.APPROVED
                current.save(update_fields=["status"])
                creative.status = Creative.Status.APPROVED
                creative.save(update_fields=["status"])
                msg = f"Le visuel « {creative.title} » (V{current.number}) a été validé."
            elif decision == "changes":
                current.status = CreativeVersion.Status.CHANGES
                current.save(update_fields=["status"])
                creative.status = Creative.Status.CHANGES
                creative.save(update_fields=["status"])
                msg = f"Des corrections sont demandées sur « {creative.title} » (V{current.number})."
            else:
                return redirect("extranet:creative", pk=pk)
            if creative.project.internal_lead:
                notify(creative.project.internal_lead, "Décision sur un visuel", msg,
                       Notification.Level.INFO, reverse("extranet:creative", args=[creative.pk]))
            messages.success(request, "Votre décision a été enregistrée.")
            return redirect("extranet:creative", pk=pk)
    return render(request, "extranet/creative_detail.html", {
        "creative": creative, "current": current,
        "versions": creative.versions.prefetch_related("comments__author"),
        "comment_form": CreativeCommentForm(), "version_form": CreativeVersionForm(),
        "can_manage": user.is_manager, "is_client": creative.project.client_id == user.id,
    })


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def project_edit(request, pk=None):
    project = get_object_or_404(Project, pk=pk) if pk else None
    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project, viewer=request.user)
        if form.is_valid():
            obj = form.save()
            messages.success(request, "Projet enregistré.")
            return redirect("extranet:project", pk=obj.pk)
    else:
        form = ProjectForm(instance=project, viewer=request.user)
    return render(request, "extranet/project_form.html", {"form": form, "project": project})


@role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if request.method == "POST":
        name = project.name
        project.delete()
        messages.success(request, f"Projet « {name} » supprimé.")
        return redirect("extranet:home")
    return render(request, "extranet/project_confirm_delete.html", {"project": project})


# --------------------------------------------------------------------------- #
# Espace client enrichi : devis, factures, paiements
# --------------------------------------------------------------------------- #
def _my_client_ids(user):
    """IDs des fiches CRM rattachées au compte extranet de l'utilisateur."""
    from business.models import Client as BClient
    return list(BClient.objects.filter(extranet_user=user).values_list("id", flat=True))


def _owns_quote(user, quote):
    return user.is_admin_lpm or quote.client.extranet_user_id == user.id


def _owns_invoice(user, invoice):
    return user.is_admin_lpm or (invoice.client and invoice.client.extranet_user_id == user.id)


@login_required
def my_quotes(request):
    from business.models import Quote
    quotes = (Quote.objects.filter(client_id__in=_my_client_ids(request.user))
              .exclude(status__in=[Quote.Status.DRAFT, Quote.Status.INTERNAL])
              .select_related("client"))
    return render(request, "extranet/my_quotes.html", {"quotes": quotes})


@login_required
def client_quote(request, pk):
    from business.models import Quote
    quote = get_object_or_404(Quote.objects.select_related("client"), pk=pk)
    if not _owns_quote(request.user, quote):
        raise PermissionDenied("Ce devis ne vous est pas destiné.")
    if quote.status in {Quote.Status.DRAFT, Quote.Status.INTERNAL}:
        raise PermissionDenied("Ce devis n'est pas encore disponible.")
    return render(request, "extranet/client_quote.html", {"quote": quote})


@login_required
def client_quote_decide(request, pk, decision):
    from django.utils import timezone
    from accounts.utils import get_client_ip
    from business.models import Quote
    from business.models import QuoteEvent, log_quote_event
    quote = get_object_or_404(Quote, pk=pk)
    if not _owns_quote(request.user, quote):
        raise PermissionDenied()
    if quote.status == Quote.Status.SENT and decision in {"accept", "refuse", "changes"}:
        if decision == "accept":
            # Signature électronique : nom saisi + horodatage + IP (valeur probante).
            signature = (request.POST.get("signature") or "").strip()
            if not signature:
                messages.error(request, "Veuillez saisir votre nom pour signer électroniquement le devis.")
                return redirect("extranet:client_quote", pk=pk)
            quote.status = Quote.Status.SIGNED
            quote.signed_by_name = signature
            quote.signed_at = timezone.now()
            quote.signed_ip = get_client_ip(request)
            quote.save(update_fields=["status", "signed_by_name", "signed_at", "signed_ip"])
            log_quote_event(quote, QuoteEvent.Action.SIGNED, request.user,
                            f"Signé électroniquement par {signature}")
        elif decision == "changes":
            comment = (request.POST.get("comment") or "").strip()
            if not comment:
                messages.error(request, "Merci de préciser les modifications souhaitées.")
                return redirect("extranet:client_quote", pk=pk)
            quote.status = Quote.Status.CHANGES
            quote.save(update_fields=["status"])
            log_quote_event(quote, QuoteEvent.Action.CHANGES, request.user, comment)
        else:
            quote.status = Quote.Status.REFUSED
            quote.save(update_fields=["status"])
            log_quote_event(quote, QuoteEvent.Action.REFUSED, request.user,
                            (request.POST.get("comment") or "").strip())
        if quote.status == Quote.Status.SIGNED and quote.client.kind != "CLIENT":
            quote.client.kind = "CLIENT"
            quote.client.save(update_fields=["kind"])
        # Notifier le commercial.
        if quote.owner:
            notify(quote.owner, f"Devis {quote.number} — {quote.get_status_display().lower()}",
                   f"{quote.client.name} a répondu à votre devis.", Notification.Level.INFO,
                   reverse("business:quote_detail", args=[quote.pk]))
        messages.success(request, "Merci, votre réponse a été enregistrée.")
    return redirect("extranet:client_quote", pk=pk)


@login_required
def client_quote_pdf(request, pk):
    from django.http import FileResponse
    from business.models import Quote
    from business.pdf import quote_pdf
    quote = get_object_or_404(Quote, pk=pk)
    if not _owns_quote(request.user, quote):
        raise PermissionDenied()
    return FileResponse(quote_pdf(quote), as_attachment=True,
                        filename=f"{quote.number}.pdf", content_type="application/pdf")


@login_required
def my_invoices(request):
    from business.models import Invoice
    invoices = (Invoice.objects.filter(kind=Invoice.Kind.CLIENT, client_id__in=_my_client_ids(request.user))
                .exclude(status=Invoice.Status.DRAFT).select_related("client"))
    for inv in invoices:
        inv.refresh_status()
    return render(request, "extranet/my_invoices.html", {"invoices": invoices})


@login_required
def client_invoice(request, pk):
    from business.forms import PaymentForm
    from business.models import Invoice
    invoice = get_object_or_404(Invoice.objects.select_related("client"), pk=pk)
    if not _owns_invoice(request.user, invoice):
        raise PermissionDenied("Cette facture ne vous est pas destinée.")
    invoice.refresh_status()
    pay_form = PaymentForm(initial={"amount": invoice.balance})
    # Limiter les moyens aux paiements mobiles côté client.
    pay_form.fields["method"].choices = [("MOMO", "MTN Mobile Money"), ("OM", "Orange Money")]
    return render(request, "extranet/client_invoice.html", {"invoice": invoice, "pay_form": pay_form})


@login_required
def client_invoice_pay(request, pk):
    from business.forms import PaymentForm
    from business.models import Invoice
    invoice = get_object_or_404(Invoice, pk=pk)
    if not _owns_invoice(request.user, invoice):
        raise PermissionDenied()
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            pay = form.save(commit=False)
            pay.invoice = invoice
            pay.recorded_by = request.user
            pay.save()
            invoice.refresh_status()
            if invoice.created_by:
                notify(invoice.created_by, f"Paiement reçu — {invoice.number}",
                       f"{pay.amount} FCFA via {pay.get_method_display()} (réf. {pay.reference}).",
                       Notification.Level.SUCCESS, reverse("business:invoice_detail", args=[invoice.pk]))
            messages.success(request, "Paiement enregistré. Merci ! Il sera confirmé par notre service financier.")
    return redirect("extranet:client_invoice", pk=pk)


@login_required
def client_invoice_pdf(request, pk):
    from django.http import FileResponse
    from business.models import Invoice
    from business.pdf import invoice_pdf
    invoice = get_object_or_404(Invoice, pk=pk)
    if not _owns_invoice(request.user, invoice):
        raise PermissionDenied()
    return FileResponse(invoice_pdf(invoice), as_attachment=True,
                        filename=f"{invoice.number}.pdf", content_type="application/pdf")
