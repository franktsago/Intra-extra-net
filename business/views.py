"""Vues Commercial & Finance + tableau de bord exécutif (Direction Générale)."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.models import ActivityLog, Role, User
from accounts.utils import log_activity, role_required
from notifications.models import Notification, notify

from .forms import (
    ClientForm, InvoiceForm, InvoiceLineFormSet, OpportunityForm, PaymentForm,
    QuoteForm, QuoteLineFormSet,
)
from .models import Client, Invoice, Opportunity, Quote

# Accès au module commercial : direction, RH, responsables.
biz_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)
exec_required = role_required(Role.ADMIN, Role.CEO)


def _needs_ceo_validation(user):
    """Un responsable « simple » (ni RH, ni CEO, ni admin) requiert la validation CEO."""
    return user.is_manager and not user.is_rh


def _direction_users():
    return User.objects.filter(role__in=[Role.CEO, Role.ADMIN], is_active=True)


def _notify_direction(title, message, url=""):
    for u in _direction_users():
        notify(u, title, message, Notification.Level.INFO, url)


# --------------------------------------------------------------------------- #
# CRM
# --------------------------------------------------------------------------- #
@biz_required
def client_list(request):
    q = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    qs = Client.objects.select_related("owner")
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(contact_name__icontains=q) | Q(email__icontains=q))
    if kind:
        qs = qs.filter(kind=kind)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "business/client_list.html", {"page_obj": page, "q": q, "kind": kind})


@biz_required
def client_edit(request, pk=None):
    obj = get_object_or_404(Client, pk=pk) if pk else None
    if request.method == "POST":
        form = ClientForm(request.POST, instance=obj, viewer=request.user)
        if form.is_valid():
            c = form.save(commit=False)
            if not obj:  # création
                if not c.owner:
                    c.owner = request.user
                if _needs_ceo_validation(request.user):
                    c.is_validated = False
                    c.save()
                    _notify_direction(
                        "Client à valider",
                        f"{request.user.get_full_name() or request.user.username} a créé la fiche « {c.name} ».",
                        reverse("business:client_detail", args=[c.pk]))
                    messages.success(request, "Fiche client créée. En attente de validation de la Direction.")
                    return redirect("business:client_detail", pk=c.pk)
            c.save()
            messages.success(request, "Fiche client enregistrée.")
            return redirect("business:client_detail", pk=c.pk)
    else:
        form = ClientForm(instance=obj, viewer=request.user)
    return render(request, "business/client_form.html", {"form": form, "obj": obj})


@biz_required
def client_detail(request, pk):
    client = get_object_or_404(Client, pk=pk)
    return render(request, "business/client_detail.html", {
        "client": client,
        "quotes": client.quotes.all()[:10],
        "invoices": client.invoices.all()[:10],
        "opportunities": client.opportunities.all()[:10],
        "can_validate": request.user.is_ceo,
    })


@exec_required
def client_validate(request, pk):
    """La Direction (CEO/admin) valide une fiche client créée par un responsable."""
    client = get_object_or_404(Client, pk=pk)
    if request.method == "POST" and not client.is_validated:
        client.is_validated = True
        client.validated_by = request.user
        client.save(update_fields=["is_validated", "validated_by"])
        if client.owner:
            notify(client.owner, "Client validé",
                   f"La fiche « {client.name} » a été validée par la Direction.",
                   Notification.Level.SUCCESS, reverse("business:client_detail", args=[client.pk]))
        messages.success(request, "Fiche client validée.")
    return redirect("business:client_detail", pk=pk)


@biz_required
def pipeline(request):
    columns = []
    for code, label in Opportunity.Stage.choices:
        if code == "LOST":
            continue
        opps = Opportunity.objects.filter(stage=code).select_related("client")
        columns.append({"code": code, "label": label, "opps": opps,
                        "total": sum(o.amount for o in opps)})
    return render(request, "business/pipeline.html", {"columns": columns})


@biz_required
def opportunity_edit(request, pk=None):
    obj = get_object_or_404(Opportunity, pk=pk) if pk else None
    if request.method == "POST":
        form = OpportunityForm(request.POST, instance=obj, viewer=request.user)
        if form.is_valid():
            o = form.save(commit=False)
            if not obj and not o.owner:
                o.owner = request.user
            o.save()
            messages.success(request, "Opportunité enregistrée.")
            return redirect("business:pipeline")
    else:
        form = OpportunityForm(instance=obj, viewer=request.user)
    return render(request, "business/opportunity_form.html", {"form": form, "obj": obj})


# --------------------------------------------------------------------------- #
# Devis
# --------------------------------------------------------------------------- #
@biz_required
def quote_list(request):
    qs = Quote.objects.select_related("client", "owner")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "business/quote_list.html", {
        "page_obj": page, "status": status, "statuses": Quote.Status.choices})


@biz_required
def quote_edit(request, pk=None):
    quote = get_object_or_404(Quote, pk=pk) if pk else None
    if request.method == "POST":
        form = QuoteForm(request.POST, instance=quote)
        formset = QuoteLineFormSet(request.POST, instance=quote)
        if form.is_valid() and formset.is_valid():
            q = form.save(commit=False)
            if not quote:
                q.owner = request.user
            q.save()
            formset.instance = q
            formset.save()
            messages.success(request, "Devis enregistré.")
            return redirect("business:quote_detail", pk=q.pk)
    else:
        form = QuoteForm(instance=quote)
        formset = QuoteLineFormSet(instance=quote)
    return render(request, "business/quote_form.html", {"form": form, "formset": formset, "quote": quote})


@biz_required
def quote_detail(request, pk):
    quote = get_object_or_404(Quote.objects.select_related("client", "owner"), pk=pk)
    return render(request, "business/quote_detail.html", {"quote": quote})


@biz_required
def quote_status(request, pk, action):
    quote = get_object_or_404(Quote, pk=pk)
    flow = {"internal": Quote.Status.INTERNAL, "send": Quote.Status.SENT,
            "sign": Quote.Status.SIGNED, "refuse": Quote.Status.REFUSED,
            "draft": Quote.Status.DRAFT}
    # L'envoi au client d'un devis établi par un responsable requiert la validation CEO.
    if action == "send" and _needs_ceo_validation(request.user):
        quote.status = Quote.Status.INTERNAL
        quote.save(update_fields=["status"])
        from .models import QuoteEvent, log_quote_event
        log_quote_event(quote, QuoteEvent.Action.UPDATED, request.user, "Soumis à la validation de la Direction")
        _notify_direction("Devis à valider",
                          f"{request.user.get_full_name() or request.user.username} demande l'envoi du devis {quote.number}.",
                          reverse("business:quote_detail", args=[quote.pk]))
        messages.info(request, "Devis soumis à la validation de la Direction avant envoi au client.")
        return redirect("business:quote_detail", pk=pk)
    if action in flow:
        quote.status = flow[action]
        quote.save(update_fields=["status"])
        if quote.status == Quote.Status.SIGNED and quote.client.kind != Client.Kind.CLIENT:
            quote.client.kind = Client.Kind.CLIENT
            quote.client.save(update_fields=["kind"])
        # Traçabilité : on journalise l'envoi (et la re-soumission après modifications).
        from .models import QuoteEvent, log_quote_event
        event_map = {"send": QuoteEvent.Action.SENT, "sign": QuoteEvent.Action.SIGNED,
                     "refuse": QuoteEvent.Action.REFUSED}
        if action in event_map:
            log_quote_event(quote, event_map[action], request.user)
        messages.success(request, f"Devis « {quote.number} » : statut mis à jour.")
    return redirect("business:quote_detail", pk=pk)


@biz_required
def quote_to_invoice(request, pk):
    quote = get_object_or_404(Quote, pk=pk)
    inv = Invoice.objects.create(
        kind=Invoice.Kind.CLIENT, client=quote.client, quote=quote,
        title=quote.title, status=Invoice.Status.DRAFT, tax_rate=quote.tax_rate,
        created_by=request.user)
    for line in quote.lines.all():
        inv.lines.create(designation=line.designation, quantity=line.quantity,
                         unit_price=line.unit_price)
    messages.success(request, f"Facture {inv.number} créée à partir du devis {quote.number}.")
    return redirect("business:invoice_detail", pk=inv.pk)


@biz_required
def quote_pdf(request, pk):
    quote = get_object_or_404(Quote.objects.select_related("client", "owner"), pk=pk)
    from .pdf import quote_pdf as build
    log_activity(request, ActivityLog.Action.DOWNLOAD, f"Téléchargement devis {quote.number}")
    return FileResponse(build(quote), as_attachment=True,
                        filename=f"{quote.number}.pdf", content_type="application/pdf")


# --------------------------------------------------------------------------- #
# Factures & paiements
# --------------------------------------------------------------------------- #
@biz_required
def invoice_list(request):
    qs = Invoice.objects.select_related("client")
    status = request.GET.get("status", "")
    kind = request.GET.get("kind", "")
    if status:
        qs = qs.filter(status=status)
    if kind:
        qs = qs.filter(kind=kind)
    for inv in qs:
        inv.refresh_status()
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "business/invoice_list.html", {
        "page_obj": page, "status": status, "kind": kind, "statuses": Invoice.Status.choices})


@biz_required
def invoice_edit(request, pk=None):
    invoice = get_object_or_404(Invoice, pk=pk) if pk else None
    if request.method == "POST":
        form = InvoiceForm(request.POST, instance=invoice)
        formset = InvoiceLineFormSet(request.POST, instance=invoice)
        if form.is_valid() and formset.is_valid():
            inv = form.save(commit=False)
            if not invoice:
                inv.created_by = request.user
            inv.save()
            formset.instance = inv
            formset.save()
            messages.success(request, "Facture enregistrée.")
            return redirect("business:invoice_detail", pk=inv.pk)
    else:
        form = InvoiceForm(instance=invoice)
        formset = InvoiceLineFormSet(instance=invoice)
    return render(request, "business/invoice_form.html", {"form": form, "formset": formset, "invoice": invoice})


@biz_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("client", "quote"), pk=pk)
    invoice.refresh_status()
    pay_form = PaymentForm(initial={"amount": invoice.balance})
    return render(request, "business/invoice_detail.html", {"invoice": invoice, "pay_form": pay_form})


@biz_required
def invoice_issue(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    # L'émission d'une facture par un responsable requiert la validation de la Direction.
    if _needs_ceo_validation(request.user):
        _notify_direction("Facture à valider",
                          f"{request.user.get_full_name() or request.user.username} demande l'émission de la facture {invoice.number}.",
                          reverse("business:invoice_detail", args=[invoice.pk]))
        messages.info(request, "Facture soumise à la validation de la Direction avant émission.")
        return redirect("business:invoice_detail", pk=pk)
    if invoice.status == Invoice.Status.DRAFT:
        invoice.status = Invoice.Status.SENT
        invoice.save(update_fields=["status"])
        invoice.refresh_status()
        messages.success(request, "Facture émise.")
    return redirect("business:invoice_detail", pk=pk)


@biz_required
def invoice_payment(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == "POST":
        form = PaymentForm(request.POST)
        if form.is_valid():
            pay = form.save(commit=False)
            pay.invoice = invoice
            pay.recorded_by = request.user
            pay.save()
            if invoice.status == Invoice.Status.DRAFT:
                invoice.status = Invoice.Status.SENT
                invoice.save(update_fields=["status"])
            invoice.refresh_status()
            messages.success(request, f"Paiement de {pay.amount} FCFA enregistré ({pay.get_method_display()}).")
    return redirect("business:invoice_detail", pk=pk)


@biz_required
def invoice_pdf(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("client"), pk=pk)
    from .pdf import invoice_pdf as build
    log_activity(request, ActivityLog.Action.DOWNLOAD, f"Téléchargement facture {invoice.number}")
    return FileResponse(build(invoice), as_attachment=True,
                        filename=f"{invoice.number}.pdf", content_type="application/pdf")


# --------------------------------------------------------------------------- #
# Tableau de bord exécutif — Direction Générale
# --------------------------------------------------------------------------- #
@exec_required
def executive(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    from .models import Payment
    client_invoices = list(Invoice.objects.filter(kind=Invoice.Kind.CLIENT).exclude(status=Invoice.Status.CANCELLED))

    ca_mois = sum(i.total for i in client_invoices if i.issue_date >= month_start)
    encaisse_mois = sum(p.amount for p in Payment.objects.filter(
        paid_at__gte=month_start, invoice__kind=Invoice.Kind.CLIENT))

    creances = 0
    overdue = 0
    for i in client_invoices:
        i.refresh_status()
        creances += i.balance
        if i.status == Invoice.Status.OVERDUE:
            overdue += i.balance

    open_opps = Opportunity.objects.exclude(stage__in=[Opportunity.Stage.WON, Opportunity.Stage.LOST])
    pipeline_total = sum(o.amount for o in open_opps)
    pipeline_pondere = int(sum(o.amount * o.probability / 100 for o in open_opps))

    # Évolution sur 12 mois : CA facturé et encaissements.
    from datetime import date as _date
    _MOIS = ["jan", "fév", "mar", "avr", "mai", "juin", "juil", "août", "sep", "oct", "nov", "déc"]
    series = []  # [(année, mois)] des 12 derniers mois
    y, m = today.year, today.month
    for _ in range(12):
        series.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    series.reverse()
    ca_map = {ym: 0 for ym in series}
    enc_map = {ym: 0 for ym in series}
    for i in client_invoices:
        ym = (i.issue_date.year, i.issue_date.month)
        if ym in ca_map:
            ca_map[ym] += int(i.total)
    for p in Payment.objects.filter(invoice__kind=Invoice.Kind.CLIENT).only("amount", "paid_at"):
        ym = (p.paid_at.year, p.paid_at.month)
        if ym in enc_map:
            enc_map[ym] += int(p.amount)
    chart_labels = [f"{_MOIS[mo-1]} {yr % 100:02d}" for (yr, mo) in series]
    chart_ca = [ca_map[ym] for ym in series]
    chart_enc = [enc_map[ym] for ym in series]

    quotes = Quote.objects.all()
    top = []
    for c in Client.objects.filter(kind=Client.Kind.CLIENT):
        ca = sum(i.total for i in c.invoices.exclude(status=Invoice.Status.CANCELLED))
        if ca:
            top.append({"client": c, "ca": ca})
    top.sort(key=lambda x: x["ca"], reverse=True)

    return render(request, "business/executive.html", {
        "ca_mois": ca_mois, "encaisse_mois": encaisse_mois,
        "creances": creances, "overdue": overdue,
        "pipeline_total": pipeline_total, "pipeline_pondere": pipeline_pondere,
        "devis_signes": quotes.filter(status=Quote.Status.SIGNED).count(),
        "devis_envoyes": quotes.filter(status=Quote.Status.SENT).count(),
        "nb_clients": Client.objects.filter(kind=Client.Kind.CLIENT).count(),
        "nb_prospects": Client.objects.filter(kind=Client.Kind.PROSPECT).count(),
        "top_clients": top[:6],
        "recent_invoices": client_invoices[:6],
        "month_label": today.strftime("%m/%Y"),
        "chart_labels": chart_labels, "chart_ca": chart_ca, "chart_enc": chart_enc,
    })
