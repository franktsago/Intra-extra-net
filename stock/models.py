"""Magasin LPM : inventaire, mouvements, emprunts, commandes, maintenance, réconciliation post-événement."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class StockSupplier(models.Model):
    name = models.CharField("Nom", max_length=200)
    contact_name = models.CharField("Contact", max_length=200, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Téléphone", max_length=30, blank=True)
    address = models.TextField("Adresse", blank=True)
    notes = models.TextField("Notes", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Fournisseur"
        ordering = ["name"]

    def __str__(self):
        return self.name


class StockItem(models.Model):

    class Category(models.TextChoices):
        EVENEMENT = "EVENEMENT", "Événement"
        TECHNIQUE = "TECHNIQUE", "Technique / Son-Lumière"
        IT = "IT", "Informatique"
        MOBILIER = "MOBILIER", "Mobilier"
        CONSOMMABLE = "CONSOMMABLE", "Consommable"
        BUREAUTIQUE = "BUREAUTIQUE", "Fournitures bureau"
        EQUIPMENT = "EQUIPMENT", "Équipement général"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        NEW = "NEW", "Neuf"
        GOOD = "GOOD", "Bon état"
        USED = "USED", "Usé"
        REPAIR = "REPAIR", "En réparation"
        OUT_OF_SERVICE = "OUT_OF_SERVICE", "Hors service (HS)"

    mat_id = models.CharField("ID Matériel", max_length=20, unique=True, blank=True, null=True)
    name = models.CharField("Désignation", max_length=200)
    category = models.CharField("Catégorie", max_length=12, choices=Category.choices, default=Category.OTHER)
    brand_model = models.CharField("Marque / Modèle", max_length=200, blank=True)
    serial_number = models.CharField("N° Série", max_length=100, blank=True)
    quantity = models.IntegerField("Quantité totale", default=0)
    min_quantity = models.IntegerField("Seuil d'alerte", default=0)
    unit = models.CharField("Unité", max_length=30, default="unité")
    status = models.CharField("État", max_length=15, choices=Status.choices, default=Status.GOOD)
    location = models.CharField("Localisation (rayonnage/zone)", max_length=100, blank=True)
    estimated_value = models.DecimalField("Valeur estimée (FCFA)", max_digits=12, decimal_places=0, null=True, blank=True)
    image = models.ImageField("Photo", upload_to="stock/items/", blank=True, null=True)
    description = models.TextField("Commentaires", blank=True)
    supplier = models.ForeignKey(
        StockSupplier, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="items", verbose_name="Fournisseur",
    )
    unit_price = models.DecimalField("Prix unitaire (FCFA)", max_digits=12, decimal_places=0, null=True, blank=True)
    reference = models.CharField("Référence interne", max_length=50, unique=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Article"
        ordering = ["category", "name"]

    def __str__(self):
        prefix = self.mat_id or self.reference
        return f"{prefix} — {self.name}" if prefix else self.name

    @property
    def is_low_stock(self):
        return self.min_quantity > 0 and self.quantity <= self.min_quantity

    @property
    def status_color(self):
        return {
            "NEW": "emerald", "GOOD": "blue", "USED": "amber",
            "REPAIR": "orange", "OUT_OF_SERVICE": "red",
        }.get(self.status, "slate")

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = StockItem.objects.filter(reference__startswith=f"ART-{year}-").order_by("reference").last()
            seq = 1
            if last and last.reference:
                try:
                    seq = int(last.reference.split("-")[-1]) + 1
                except ValueError:
                    pass
            self.reference = f"ART-{year}-{seq:04d}"
        if not self.mat_id:
            last = StockItem.objects.filter(mat_id__startswith="MAT-").order_by("mat_id").last()
            seq = 1
            if last and last.mat_id:
                try:
                    seq = int(last.mat_id.split("-")[-1]) + 1
                except ValueError:
                    pass
            self.mat_id = f"MAT-{seq:03d}"
        if self.mat_id == "":
            self.mat_id = None
        super().save(*args, **kwargs)


class StockMovement(models.Model):

    class Kind(models.TextChoices):
        IN = "IN", "Entrée"
        OUT = "OUT", "Sortie"
        ADJUSTMENT = "ADJUSTMENT", "Ajustement"
        TRANSFER = "TRANSFER", "Transfert"
        BORROW = "BORROW", "Emprunt"
        RETURN = "RETURN", "Retour"

    class MovementStatus(models.TextChoices):
        PENDING = "PENDING", "En attente"
        VALIDATED = "VALIDATED", "Validé"
        CANCELLED = "CANCELLED", "Annulé"

    mvt_reference = models.CharField("Référence", max_length=20, unique=True, blank=True, null=True)
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="movements", verbose_name="Article")
    kind = models.CharField("Type", max_length=10, choices=Kind.choices)
    quantity = models.IntegerField("Quantité")
    reason = models.CharField("Motif", max_length=200, blank=True)
    destination = models.CharField("Destination / Utilisateur", max_length=200, blank=True)
    origin = models.CharField("Provenance", max_length=200, blank=True)
    departure_state = models.CharField("État départ", max_length=50, blank=True)
    return_state = models.CharField("État retour", max_length=50, blank=True)
    store_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="managed_movements", verbose_name="Responsable magasin",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="stock_movements", verbose_name="Utilisateur",
    )
    performed_at = models.DateTimeField("Date", default=timezone.now)
    movement_status = models.CharField(
        "Statut", max_length=10, choices=MovementStatus.choices, default=MovementStatus.PENDING,
    )
    notes = models.TextField("Commentaires", blank=True)

    class Meta:
        verbose_name = "Mouvement de stock"
        ordering = ["-performed_at"]

    def __str__(self):
        return f"{self.mvt_reference or self.pk} — {self.get_kind_display()} {self.quantity}× {self.item}"

    def save(self, *args, **kwargs):
        if not self.mvt_reference:
            last = StockMovement.objects.filter(mvt_reference__startswith="MVT-").order_by("mvt_reference").last()
            seq = 1
            if last and last.mvt_reference:
                try:
                    seq = int(last.mvt_reference.split("-")[-1]) + 1
                except ValueError:
                    pass
            self.mvt_reference = f"MVT-{seq:04d}"
        if self.mvt_reference == "":
            self.mvt_reference = None
        super().save(*args, **kwargs)


class PostEventReconciliation(models.Model):

    class ReturnState(models.TextChoices):
        GOOD = "GOOD", "Bon"
        USED = "USED", "Usé"
        DAMAGED = "DAMAGED", "Endommagé"
        MISSING = "MISSING", "Manquant"

    class Action(models.TextChoices):
        OK = "OK", "RAS"
        REPAIR = "REPAIR", "Réparer"
        REPLACE = "REPLACE", "Remplacer"
        INVESTIGATE = "INVESTIGATE", "Enquêter"

    event_name = models.CharField("Événement", max_length=200)
    event_date = models.DateField("Date de l'événement")
    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="reconciliations", verbose_name="Matériel")
    qty_out = models.IntegerField("Qté sortie")
    qty_returned = models.IntegerField("Qté revenue", default=0)
    return_state = models.CharField("État retour", max_length=10, choices=ReturnState.choices, default=ReturnState.GOOD)
    action = models.CharField("Action", max_length=12, choices=Action.choices, default=Action.OK)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="reconciliations", verbose_name="Responsable",
    )
    comments = models.TextField("Commentaires", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Réconciliation post-événement"
        ordering = ["-event_date"]

    def __str__(self):
        return f"{self.event_name} — {self.item}"

    @property
    def discrepancy(self):
        return self.qty_out - self.qty_returned


class MaintenanceItem(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        RESOLVED = "RESOLVED", "Résolu"
        SCRAPPED = "SCRAPPED", "Mis au rebut"

    class RecommendedAction(models.TextChoices):
        DIAGNOSE = "DIAGNOSE", "Diagnostiquer"
        REPAIR = "REPAIR", "Réparer"
        SCRAP = "SCRAP", "Jeter / Rebut"
        WAIT = "WAIT", "Attendre"
        REPLACE = "REPLACE", "Remplacer"

    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="maintenance_items", verbose_name="Matériel")
    problem = models.TextField("Problème constaté")
    detected_at = models.DateField("Date de détection", default=timezone.now)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="maintenance_items", verbose_name="Responsable",
    )
    recommended_action = models.CharField(
        "Action recommandée", max_length=10, choices=RecommendedAction.choices, default=RecommendedAction.DIAGNOSE,
    )
    estimated_cost = models.DecimalField("Coût estimé (FCFA)", max_digits=12, decimal_places=0, null=True, blank=True)
    status = models.CharField("Statut", max_length=12, choices=Status.choices, default=Status.PENDING)
    comments = models.TextField("Commentaires", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Fiche de maintenance"
        ordering = ["-detected_at"]

    def __str__(self):
        return f"{self.item} — {self.problem[:50]}"


class BorrowRequest(models.Model):

    class Status(models.TextChoices):
        PENDING = "PENDING", "En attente"
        APPROVED = "APPROVED", "Approuvée"
        REJECTED = "REJECTED", "Refusée"
        RETURNED = "RETURNED", "Retourné"

    item = models.ForeignKey(StockItem, on_delete=models.CASCADE, related_name="borrow_requests", verbose_name="Article")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="borrow_requests", verbose_name="Demandeur",
    )
    quantity = models.IntegerField("Quantité", default=1)
    purpose = models.CharField("Objet / Motif", max_length=300, blank=True)
    requested_at = models.DateTimeField("Demandé le", auto_now_add=True)
    start_date = models.DateField("Date de début", null=True, blank=True)
    end_date = models.DateField("Date de fin", null=True, blank=True)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="borrow_decisions", verbose_name="Décidé par",
    )
    decided_at = models.DateTimeField("Décidé le", null=True, blank=True)
    return_note = models.TextField("Note de retour", blank=True)

    class Meta:
        verbose_name = "Demande d'emprunt"
        ordering = ["-requested_at"]

    def __str__(self):
        return f"Emprunt {self.item} par {self.requested_by}"


class PurchaseOrder(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SENT = "SENT", "Envoyée"
        RECEIVED = "RECEIVED", "Reçue"
        CANCELLED = "CANCELLED", "Annulée"

    reference = models.CharField("Référence", max_length=50, unique=True, blank=True)
    supplier = models.ForeignKey(
        StockSupplier, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="orders", verbose_name="Fournisseur",
    )
    items = models.TextField("Articles commandés")
    total_amount = models.DecimalField("Montant total (FCFA)", max_digits=14, decimal_places=0, default=0)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField("Date de commande", default=timezone.now)
    expected_date = models.DateField("Date de livraison prévue", null=True, blank=True)
    received_date = models.DateField("Date de réception", null=True, blank=True)
    notes = models.TextField("Notes", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="purchase_orders", verbose_name="Créé par",
    )

    class Meta:
        verbose_name = "Bon de commande"
        ordering = ["-order_date"]

    def __str__(self):
        return self.reference or f"Commande #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            year = timezone.now().year
            last = PurchaseOrder.objects.filter(reference__startswith=f"CMD-{year}-").order_by("reference").last()
            seq = 1
            if last and last.reference:
                try:
                    seq = int(last.reference.split("-")[-1]) + 1
                except ValueError:
                    pass
            self.reference = f"CMD-{year}-{seq:04d}"
        super().save(*args, **kwargs)
