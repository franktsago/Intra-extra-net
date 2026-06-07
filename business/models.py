"""Module Commercial & Finance : CRM, pipeline, devis, factures, paiements.

Couvre le flux « de la prospection à l'encaissement » (sales-to-cash) et
alimente le tableau de bord exécutif de la Direction Générale.
Montants en FCFA. TVA Cameroun par défaut : 19,25 %.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

TVA_DEFAULT = Decimal("19.25")


# --------------------------------------------------------------------------- #
# CRM
# --------------------------------------------------------------------------- #
class Client(models.Model):
    class Kind(models.TextChoices):
        PROSPECT = "PROSPECT", "Prospect"
        CLIENT = "CLIENT", "Client"

    name = models.CharField("Nom / Société", max_length=200)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.PROSPECT)
    contact_name = models.CharField("Personne de contact", max_length=150, blank=True)
    email = models.EmailField("Email", blank=True)
    phone = models.CharField("Téléphone", max_length=40, blank=True)
    sector = models.CharField("Secteur d'activité", max_length=120, blank=True)
    city = models.CharField("Ville", max_length=80, blank=True, default="Douala")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="clients_geres", verbose_name="Commercial en charge",
    )
    extranet_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="fiche_client", verbose_name="Compte extranet lié",
    )
    notes = models.TextField("Notes", blank=True)
    is_active = models.BooleanField("Actif", default=True)
    # Validation par la Direction (CEO) des fiches créées par un responsable.
    is_validated = models.BooleanField("Validé par la Direction", default=True)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="clients_valides", verbose_name="Validé par",
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Client / Prospect"
        verbose_name_plural = "Clients & prospects"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Opportunity(models.Model):
    class Stage(models.TextChoices):
        NEW = "NEW", "Nouveau"
        QUALIFIED = "QUALIFIED", "Qualifié"
        PROPOSAL = "PROPOSAL", "Proposition"
        NEGOTIATION = "NEGOTIATION", "Négociation"
        WON = "WON", "Gagné"
        LOST = "LOST", "Perdu"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="opportunities")
    title = models.CharField("Intitulé", max_length=200)
    amount = models.DecimalField("Montant estimé (FCFA)", max_digits=14, decimal_places=0, default=0)
    stage = models.CharField("Étape", max_length=12, choices=Stage.choices, default=Stage.NEW)
    probability = models.PositiveSmallIntegerField("Probabilité (%)", default=20)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="opportunites", verbose_name="Commercial",
    )
    expected_close = models.DateField("Clôture prévue", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Opportunité"
        verbose_name_plural = "Opportunités (pipeline)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} — {self.client.name}"

    @property
    def is_open(self):
        return self.stage not in {self.Stage.WON, self.Stage.LOST}


# --------------------------------------------------------------------------- #
# Devis
# --------------------------------------------------------------------------- #
class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        INTERNAL = "INTERNAL", "Validation interne"
        SENT = "SENT", "Envoyé au client"
        CHANGES = "CHANGES", "Modifications demandées"
        SIGNED = "SIGNED", "Signé / Accepté"
        REFUSED = "REFUSED", "Refusé"

    number = models.CharField("N° devis", max_length=30, unique=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="quotes")
    title = models.CharField("Objet", max_length=200)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField("Date d'émission", default=timezone.localdate)
    valid_until = models.DateField("Valable jusqu'au", null=True, blank=True)
    tax_rate = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default=TVA_DEFAULT)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
        related_name="devis", verbose_name="Établi par",
    )
    notes = models.TextField("Conditions / Notes", blank=True)
    # Signature électronique (acceptation en ligne par le client).
    signed_by_name = models.CharField("Signé par", max_length=150, blank=True)
    signed_at = models.DateTimeField("Signé le", null=True, blank=True)
    signed_ip = models.GenericIPAddressField("IP de signature", null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Devis"
        verbose_name_plural = "Devis"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Devis #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            self.number = f"DEV-{self.issue_date:%Y}-{self.pk:04d}"
            super().save(update_fields=["number"])

    @property
    def subtotal(self):
        return sum((line.total for line in self.lines.all()), Decimal("0"))

    @property
    def tax_amount(self):
        return (self.subtotal * self.tax_rate / Decimal("100")).quantize(Decimal("1"))

    @property
    def total(self):
        return self.subtotal + self.tax_amount

    @property
    def status_color(self):
        return {"DRAFT": "slate", "INTERNAL": "amber", "SENT": "sky",
                "CHANGES": "orange", "SIGNED": "emerald", "REFUSED": "red"}.get(self.status, "slate")


class QuoteEvent(models.Model):
    """Historique des validations / actions sur un devis (traçabilité)."""

    class Action(models.TextChoices):
        SENT = "SENT", "Envoyé au client"
        SIGNED = "SIGNED", "Accepté et signé"
        REFUSED = "REFUSED", "Refusé par le client"
        CHANGES = "CHANGES", "Modifications demandées"
        UPDATED = "UPDATED", "Mise à jour interne"

    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="events")
    action = models.CharField("Action", max_length=10, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="quote_events", verbose_name="Par",
    )
    comment = models.TextField("Commentaire", blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Événement de devis"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} — {self.quote.number}"

    @property
    def color(self):
        return {"SENT": "sky", "SIGNED": "emerald", "REFUSED": "red",
                "CHANGES": "orange", "UPDATED": "slate"}.get(self.action, "slate")

    @property
    def icon(self):
        return {"SENT": "fa-paper-plane", "SIGNED": "fa-circle-check",
                "REFUSED": "fa-circle-xmark", "CHANGES": "fa-pen",
                "UPDATED": "fa-rotate"}.get(self.action, "fa-circle")


def log_quote_event(quote, action, actor=None, comment=""):
    """Enregistre une entrée d'historique pour un devis."""
    if actor is not None and not getattr(actor, "is_authenticated", False):
        actor = None
    return QuoteEvent.objects.create(quote=quote, action=action, actor=actor, comment=comment)


class QuoteLine(models.Model):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    designation = models.CharField("Désignation", max_length=255)
    quantity = models.DecimalField("Quantité", max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField("Prix unitaire (FCFA)", max_digits=14, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Ligne de devis"

    def __str__(self):
        return self.designation

    @property
    def total(self):
        return (self.quantity * self.unit_price).quantize(Decimal("1"))


# --------------------------------------------------------------------------- #
# Factures & Paiements
# --------------------------------------------------------------------------- #
class Invoice(models.Model):
    class Kind(models.TextChoices):
        CLIENT = "CLIENT", "Facture client"
        SUPPLIER = "SUPPLIER", "Facture fournisseur"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Brouillon"
        SENT = "SENT", "Émise"
        PARTIAL = "PARTIAL", "Partiellement payée"
        PAID = "PAID", "Payée"
        OVERDUE = "OVERDUE", "Échue impayée"
        CANCELLED = "CANCELLED", "Annulée"

    number = models.CharField("N° facture", max_length=30, unique=True, blank=True)
    kind = models.CharField("Type", max_length=10, choices=Kind.choices, default=Kind.CLIENT)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.PROTECT, related_name="invoices")
    supplier_name = models.CharField("Fournisseur", max_length=200, blank=True)
    quote = models.ForeignKey(Quote, null=True, blank=True, on_delete=models.SET_NULL, related_name="invoices")
    title = models.CharField("Objet", max_length=200)
    status = models.CharField("Statut", max_length=10, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField("Date", default=timezone.localdate)
    due_date = models.DateField("Échéance", null=True, blank=True)
    tax_rate = models.DecimalField("TVA (%)", max_digits=5, decimal_places=2, default=TVA_DEFAULT)
    notes = models.TextField("Notes", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="factures")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ["-created_at"]

    def __str__(self):
        return self.number or f"Facture #{self.pk}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.number:
            prefix = "FAC" if self.kind == self.Kind.CLIENT else "FF"
            self.number = f"{prefix}-{self.issue_date:%Y}-{self.pk:04d}"
            super().save(update_fields=["number"])

    @property
    def subtotal(self):
        return sum((line.total for line in self.lines.all()), Decimal("0"))

    @property
    def tax_amount(self):
        return (self.subtotal * self.tax_rate / Decimal("100")).quantize(Decimal("1"))

    @property
    def total(self):
        return self.subtotal + self.tax_amount

    @property
    def amount_paid(self):
        return sum((p.amount for p in self.payments.all()), Decimal("0"))

    @property
    def balance(self):
        return self.total - self.amount_paid

    def refresh_status(self, save=True):
        if self.status in {self.Status.DRAFT, self.Status.CANCELLED}:
            return
        paid = self.amount_paid
        if paid <= 0:
            new = self.Status.OVERDUE if (self.due_date and self.due_date < timezone.localdate()) else self.Status.SENT
        elif paid < self.total:
            new = self.Status.PARTIAL
        else:
            new = self.Status.PAID
        if new != self.status:
            self.status = new
            if save:
                self.save(update_fields=["status"])

    @property
    def status_color(self):
        return {"DRAFT": "slate", "SENT": "sky", "PARTIAL": "amber",
                "PAID": "emerald", "OVERDUE": "red", "CANCELLED": "slate"}.get(self.status, "slate")


class InvoiceLine(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    designation = models.CharField("Désignation", max_length=255)
    quantity = models.DecimalField("Quantité", max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField("Prix unitaire (FCFA)", max_digits=14, decimal_places=0, default=0)

    class Meta:
        verbose_name = "Ligne de facture"

    def __str__(self):
        return self.designation

    @property
    def total(self):
        return (self.quantity * self.unit_price).quantize(Decimal("1"))


class Payment(models.Model):
    class Method(models.TextChoices):
        CASH = "CASH", "Espèces"
        BANK = "BANK", "Virement bancaire"
        MOMO = "MOMO", "MTN Mobile Money"
        OM = "OM", "Orange Money"
        CHEQUE = "CHEQUE", "Chèque"

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField("Montant (FCFA)", max_digits=14, decimal_places=0)
    method = models.CharField("Moyen de paiement", max_length=10, choices=Method.choices, default=Method.MOMO)
    reference = models.CharField("Référence transaction", max_length=80, blank=True)
    paid_at = models.DateField("Date", default=timezone.localdate)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="paiements_saisis")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.amount} FCFA — {self.get_method_display()}"
