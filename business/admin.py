from django.contrib import admin

from .models import (
    Client, Invoice, InvoiceLine, Opportunity, Payment, Quote, QuoteEvent, QuoteLine,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "contact_name", "phone", "owner", "is_active")
    list_filter = ("kind", "is_active", "sector")
    search_fields = ("name", "contact_name", "email", "phone")


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "amount", "stage", "probability", "owner", "expected_close")
    list_filter = ("stage",)
    search_fields = ("title", "client__name")


class QuoteLineInline(admin.TabularInline):
    model = QuoteLine
    extra = 2


class QuoteEventInline(admin.TabularInline):
    model = QuoteEvent
    extra = 0
    readonly_fields = ("action", "actor", "comment", "created_at")


@admin.register(Quote)
class QuoteAdmin(admin.ModelAdmin):
    list_display = ("number", "client", "title", "status", "issue_date", "total")
    list_filter = ("status",)
    search_fields = ("number", "client__name", "title")
    inlines = [QuoteLineInline, QuoteEventInline]


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 2


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "kind", "client", "title", "status", "issue_date", "total", "balance")
    list_filter = ("kind", "status")
    search_fields = ("number", "client__name", "supplier_name", "title")
    inlines = [InvoiceLineInline, PaymentInline]


admin.site.register(Payment)
