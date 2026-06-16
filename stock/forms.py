from django import forms
from accounts.forms import StyledFormMixin
from .models import (
    BorrowRequest, MaintenanceItem, PostEventReconciliation,
    PurchaseOrder, StockItem, StockMovement,
)


class StockItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockItem
        exclude = ["reference", "mat_id"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class StockMovementForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ["kind", "quantity", "reason", "destination", "origin", "departure_state", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class BorrowRequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BorrowRequest
        exclude = ["requested_by", "status", "decided_by", "decided_at"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "return_note": forms.Textarea(attrs={"rows": 2}),
        }


class PurchaseOrderForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["supplier", "items", "total_amount", "status", "order_date", "expected_date", "received_date", "notes"]
        widgets = {
            "items": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "order_date": forms.DateInput(attrs={"type": "date"}),
            "expected_date": forms.DateInput(attrs={"type": "date"}),
            "received_date": forms.DateInput(attrs={"type": "date"}),
        }


class PostEventReconciliationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PostEventReconciliation
        exclude = ["responsible", "created_at"]
        widgets = {
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "comments": forms.Textarea(attrs={"rows": 2}),
        }


class MaintenanceItemForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MaintenanceItem
        exclude = ["responsible", "created_at"]
        widgets = {
            "problem": forms.Textarea(attrs={"rows": 3}),
            "comments": forms.Textarea(attrs={"rows": 2}),
            "detected_at": forms.DateInput(attrs={"type": "date"}),
        }
