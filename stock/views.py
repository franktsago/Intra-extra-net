"""Vues Magasin de stockage - hub tabule, inventaire, mouvements, maintenance, post-evt."""

from django.contrib import messages
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import Role
from accounts.utils import internal_required, role_required

from .forms import (
    BorrowRequestForm, MaintenanceItemForm, PostEventReconciliationForm,
    PurchaseOrderForm, StockItemForm, StockMovementForm,
)
from .models import (
    BorrowRequest, MaintenanceItem, PostEventReconciliation,
    PurchaseOrder, StockItem, StockMovement, StockSupplier,
)

mgr_required = role_required(Role.ADMIN, Role.CEO, Role.RH, Role.MANAGER)


# ---------------------------------------------------------------------------
# HUB TABULE
# ---------------------------------------------------------------------------

@internal_required
def stock_hub(request):
    """Hub tabule : Inventaire, Mouvements, Post-Evt, Maintenance, Alertes."""
    tab = request.GET.get("s", "inventaire")
    ctx = {"active_tab": tab}

    # KPIs globaux (toujours calcules)
    all_items = StockItem.objects.select_related("supplier")
    total_items = all_items.count()
    total_qty = all_items.aggregate(s=Sum("quantity"))["s"] or 0
    hs_count = all_items.filter(status=StockItem.Status.OUT_OF_SERVICE).count()
    bon_pct = (
        round(all_items.filter(status__in=["NEW", "GOOD"]).count() / total_items * 100)
        if total_items else 0
    )
    low_stock_items = [i for i in all_items if i.is_low_stock]
    pending_borrows = BorrowRequest.objects.filter(status=BorrowRequest.Status.PENDING).count()
    open_maintenance = MaintenanceItem.objects.exclude(
        status__in=[MaintenanceItem.Status.RESOLVED, MaintenanceItem.Status.SCRAPPED]
    ).count()

    ctx.update({
        "total_items": total_items, "total_qty": total_qty,
        "hs_count": hs_count, "bon_pct": bon_pct,
        "low_stock_items": low_stock_items,
        "pending_borrows": pending_borrows,
        "open_maintenance": open_maintenance,
    })

    # Contenu selon l'onglet actif
    if tab == "dashboard":
        from django.db.models import DecimalField, ExpressionWrapper
        # Repartition par categorie
        cat_stats = []
        for val, label in StockItem.Category.choices:
            qs = all_items.filter(category=val)
            count = qs.count()
            if count:
                qty = qs.aggregate(s=Sum("quantity"))["s"] or 0
                valeur = sum(
                    (i.quantity * i.estimated_value)
                    for i in qs if i.estimated_value
                )
                cat_stats.append({
                    "label": label, "value": val,
                    "count": count, "qty": qty, "valeur": int(valeur),
                    "pct": round(count / total_items * 100) if total_items else 0,
                })
        cat_stats.sort(key=lambda x: x["count"], reverse=True)
        # Repartition par etat
        status_stats = []
        for val, label in StockItem.Status.choices:
            count = all_items.filter(status=val).count()
            if count:
                status_stats.append({
                    "label": label, "value": val, "count": count,
                    "pct": round(count / total_items * 100) if total_items else 0,
                })
        # Valeur totale estimee
        total_valeur = sum(
            (i.quantity * i.estimated_value)
            for i in all_items if i.estimated_value
        )
        # Derniers mouvements (7)
        recent_mvts = StockMovement.objects.select_related(
            "item", "performed_by"
        ).order_by("-performed_at")[:7]
        # Top articles par valeur
        top_valeur = sorted(
            [i for i in all_items if i.estimated_value],
            key=lambda i: i.quantity * i.estimated_value,
            reverse=True,
        )[:5]
        ctx.update({
            "cat_stats": cat_stats,
            "status_stats": status_stats,
            "total_valeur": int(total_valeur),
            "recent_mvts": recent_mvts,
            "top_valeur": top_valeur,
        })

    if tab == "inventaire":
        cat_filter = request.GET.get("cat", "")
        state_filter = request.GET.get("etat", "")
        items = all_items
        if cat_filter:
            items = items.filter(category=cat_filter)
        if state_filter:
            items = items.filter(status=state_filter)
        ctx.update({
            "items": items, "cat_filter": cat_filter, "state_filter": state_filter,
            "categories": StockItem.Category.choices,
            "statuses": StockItem.Status.choices,
        })

    if tab == "mouvements":
        kind_filter = request.GET.get("type", "")
        mvts = StockMovement.objects.select_related(
            "item", "performed_by", "store_manager"
        ).order_by("-performed_at")
        if kind_filter:
            mvts = mvts.filter(kind=kind_filter)
        ctx.update({
            "mouvements": mvts[:200],
            "kind_filter": kind_filter,
            "kinds": StockMovement.Kind.choices,
        })

    if tab == "recevt":
        recons = PostEventReconciliation.objects.select_related(
            "item", "responsible"
        ).order_by("-event_date")
        ctx["reconciliations"] = recons
        ctx["recon_form"] = PostEventReconciliationForm()

    if tab == "maintenance":
        status_filter = request.GET.get("statut", "")
        fiches = MaintenanceItem.objects.select_related(
            "item", "responsible"
        ).order_by("-detected_at")
        if status_filter:
            fiches = fiches.filter(status=status_filter)
        ctx.update({
            "fiches": fiches,
            "maintenance_form": MaintenanceItemForm(),
            "status_filter": status_filter,
            "maintenance_statuses": MaintenanceItem.Status.choices,
        })

    if tab == "alertes":
        alertes = []
        for item in low_stock_items:
            alertes.append({
                "type": "Stock critique", "level": "high",
                "desc": f"{item.name} : qte = {item.quantity} (seuil = {item.min_quantity})",
                "action": "Prevoir achat ou maintenance",
            })
        for item in all_items.filter(status=StockItem.Status.OUT_OF_SERVICE):
            alertes.append({
                "type": "Materiel HS", "level": "high",
                "desc": f"{item.name} ({item.mat_id or item.reference}) est hors service",
                "action": "Consulter la fiche de maintenance",
            })
        for fiche in MaintenanceItem.objects.filter(
            status=MaintenanceItem.Status.PENDING
        ).select_related("item")[:10]:
            alertes.append({
                "type": "Maintenance en attente", "level": "medium",
                "desc": f"{fiche.item} - {fiche.problem[:80]}",
                "action": fiche.get_recommended_action_display(),
            })
        for recon in PostEventReconciliation.objects.filter(
            qty_returned__lt=F("qty_out")
        ).select_related("item")[:10]:
            if recon.discrepancy > 0:
                alertes.append({
                    "type": "Ecart post-evenement", "level": "medium",
                    "desc": f"{recon.event_name} - {recon.item} : ecart de {recon.discrepancy}",
                    "action": recon.get_action_display(),
                })
        ctx["alertes"] = alertes

    return render(request, "stock/hub.html", ctx)


# ---------------------------------------------------------------------------
# ARTICLES
# ---------------------------------------------------------------------------

@internal_required
def item_detail(request, pk):
    item = get_object_or_404(StockItem.objects.select_related("supplier"), pk=pk)
    movements = item.movements.select_related(
        "performed_by", "store_manager"
    ).order_by("-performed_at")[:30]
    borrows = item.borrow_requests.select_related("requested_by").order_by("-requested_at")[:10]
    maintenance = item.maintenance_items.order_by("-detected_at")[:5]
    reconciliations = item.reconciliations.order_by("-event_date")[:5]
    return render(request, "stock/item_detail.html", {
        "item": item, "movements": movements, "borrows": borrows,
        "maintenance": maintenance, "reconciliations": reconciliations,
        "move_form": StockMovementForm(),
        "borrow_form": BorrowRequestForm(),
    })


@mgr_required
def item_edit(request, pk=None):
    obj = get_object_or_404(StockItem, pk=pk) if pk else None
    if request.method == "POST":
        form = StockItemForm(request.POST, request.FILES, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Article enregistre.")
            return redirect("stock:hub")
    else:
        form = StockItemForm(instance=obj)
    return render(request, "stock/item_form.html", {"form": form, "obj": obj})


# ---------------------------------------------------------------------------
# MOUVEMENTS
# ---------------------------------------------------------------------------

@mgr_required
def movement_add(request, pk):
    item = get_object_or_404(StockItem, pk=pk)
    if request.method == "POST":
        form = StockMovementForm(request.POST)
        if form.is_valid():
            mv = form.save(commit=False)
            mv.item = item
            mv.performed_by = request.user
            mv.store_manager = request.user
            mv.movement_status = StockMovement.MovementStatus.VALIDATED
            if mv.kind == StockMovement.Kind.IN:
                item.quantity += mv.quantity
            elif mv.kind in (StockMovement.Kind.OUT, StockMovement.Kind.BORROW):
                item.quantity = max(0, item.quantity - mv.quantity)
            elif mv.kind == StockMovement.Kind.RETURN:
                item.quantity += mv.quantity
            elif mv.kind == StockMovement.Kind.ADJUSTMENT:
                item.quantity = mv.quantity
            item.save(update_fields=["quantity"])
            mv.save()
            messages.success(request, f"Mouvement {mv.mvt_reference} enregistre.")
    return redirect("stock:item_detail", pk=pk)


# ---------------------------------------------------------------------------
# RECONCILIATION POST-EVENEMENT
# ---------------------------------------------------------------------------

@mgr_required
def reconciliation_create(request):
    if request.method == "POST":
        form = PostEventReconciliationForm(request.POST)
        if form.is_valid():
            r = form.save(commit=False)
            r.responsible = request.user
            r.save()
            messages.success(request, "Reconciliation enregistree.")
    return redirect("/stock/?s=recevt")


@mgr_required
def reconciliation_edit(request, pk):
    obj = get_object_or_404(PostEventReconciliation, pk=pk)
    if request.method == "POST":
        form = PostEventReconciliationForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Reconciliation mise a jour.")
            return redirect("/stock/?s=recevt")
    else:
        form = PostEventReconciliationForm(instance=obj)
    return render(request, "stock/reconciliation_form.html", {"form": form, "obj": obj})


@mgr_required
def reconciliation_delete(request, pk):
    obj = get_object_or_404(PostEventReconciliation, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Fiche supprimee.")
    return redirect("/stock/?s=recevt")


# ---------------------------------------------------------------------------
# MAINTENANCE
# ---------------------------------------------------------------------------

@mgr_required
def maintenance_create(request):
    if request.method == "POST":
        form = MaintenanceItemForm(request.POST)
        if form.is_valid():
            m = form.save(commit=False)
            m.responsible = request.user
            m.save()
            messages.success(request, "Fiche de maintenance creee.")
    return redirect("/stock/?s=maintenance")


@mgr_required
def maintenance_edit(request, pk):
    obj = get_object_or_404(MaintenanceItem, pk=pk)
    if request.method == "POST":
        form = MaintenanceItemForm(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Fiche mise a jour.")
            return redirect("/stock/?s=maintenance")
    else:
        form = MaintenanceItemForm(instance=obj)
    return render(request, "stock/maintenance_form.html", {"form": form, "obj": obj})


@mgr_required
def maintenance_resolve(request, pk):
    obj = get_object_or_404(MaintenanceItem, pk=pk)
    if request.method == "POST":
        new_status = request.POST.get("status", MaintenanceItem.Status.RESOLVED)
        if new_status in dict(MaintenanceItem.Status.choices):
            obj.status = new_status
            obj.save(update_fields=["status"])
            messages.success(request, "Statut mis a jour.")
    return redirect("/stock/?s=maintenance")


# ---------------------------------------------------------------------------
# EMPRUNTS
# ---------------------------------------------------------------------------

@internal_required
def borrow_create(request, pk):
    item = get_object_or_404(StockItem, pk=pk)
    if request.method == "POST":
        form = BorrowRequestForm(request.POST)
        if form.is_valid():
            br = form.save(commit=False)
            br.item = item
            br.requested_by = request.user
            br.save()
            messages.success(request, "Demande d'emprunt soumise.")
    return redirect("stock:item_detail", pk=pk)


@mgr_required
def borrow_decide(request, pk, action):
    br = get_object_or_404(BorrowRequest, pk=pk)
    if request.method == "POST" and action in ("approve", "reject", "return"):
        br.status = {
            "approve": BorrowRequest.Status.APPROVED,
            "reject": BorrowRequest.Status.REJECTED,
            "return": BorrowRequest.Status.RETURNED,
        }[action]
        br.decided_by = request.user
        br.decided_at = timezone.now()
        br.save()
        messages.success(request, "Decision enregistree.")
    return redirect("stock:borrow_list")


@mgr_required
def borrow_list(request):
    borrows = BorrowRequest.objects.select_related(
        "item", "requested_by", "decided_by"
    ).order_by("-requested_at")
    return render(request, "stock/borrow_list.html", {"borrows": borrows})


# ---------------------------------------------------------------------------
# COMMANDES
# ---------------------------------------------------------------------------

@mgr_required
def order_list(request):
    orders = PurchaseOrder.objects.select_related(
        "supplier", "created_by"
    ).order_by("-order_date")
    suppliers = StockSupplier.objects.all()
    return render(request, "stock/order_list.html", {"orders": orders, "suppliers": suppliers})


@mgr_required
def order_edit(request, pk=None):
    obj = get_object_or_404(PurchaseOrder, pk=pk) if pk else None
    if request.method == "POST":
        form = PurchaseOrderForm(request.POST, instance=obj)
        if form.is_valid():
            o = form.save(commit=False)
            if not obj:
                o.created_by = request.user
            o.save()
            messages.success(request, "Commande enregistree.")
            return redirect("stock:order_list")
    else:
        form = PurchaseOrderForm(instance=obj)
    return render(request, "stock/order_form.html", {"form": form, "obj": obj})
