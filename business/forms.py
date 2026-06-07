from django import forms

from accounts.forms import StyledFormMixin
from accounts.utils import hide_superadmin

from .models import (
    Client, Invoice, InvoiceLine, Opportunity, Payment, Quote, QuoteLine,
)


class ClientForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "kind", "contact_name", "email", "phone", "sector",
                  "city", "owner", "extranet_user", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = hide_superadmin(
            self.fields["owner"].queryset, viewer)


class OpportunityForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = ["client", "title", "amount", "stage", "probability", "owner", "expected_close"]
        widgets = {"expected_close": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["owner"].queryset = hide_superadmin(
            self.fields["owner"].queryset, viewer)


class QuoteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Quote
        fields = ["client", "title", "issue_date", "valid_until", "tax_rate", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "valid_until": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class InvoiceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["kind", "client", "supplier_name", "title", "issue_date",
                  "due_date", "tax_rate", "notes"]
        widgets = {
            "issue_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class PaymentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "method", "reference", "paid_at"]
        widgets = {"paid_at": forms.DateInput(attrs={"type": "date"})}


_line_widget = {
    "designation": forms.TextInput(attrs={"placeholder": "Désignation"}),
}

QuoteLineFormSet = forms.inlineformset_factory(
    Quote, QuoteLine, fields=["designation", "quantity", "unit_price"],
    extra=4, can_delete=True, widgets=_line_widget)

InvoiceLineFormSet = forms.inlineformset_factory(
    Invoice, InvoiceLine, fields=["designation", "quantity", "unit_price"],
    extra=4, can_delete=True, widgets=_line_widget)
