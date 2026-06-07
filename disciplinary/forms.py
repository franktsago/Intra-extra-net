from django import forms

from accounts.forms import StyledFormMixin

from .models import DisciplinaryRecord


class DisciplinaryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DisciplinaryRecord
        fields = [
            "employee", "sanction_type", "status", "facts", "fault_date",
            "hearing_date", "employee_defense", "suspension_days", "suspension_start",
            "notified_at",
        ]
        widgets = {
            "facts": forms.Textarea(attrs={"rows": 4}),
            "employee_defense": forms.Textarea(attrs={"rows": 3}),
            "fault_date": forms.DateInput(attrs={"type": "date"}),
            "hearing_date": forms.DateInput(attrs={"type": "date"}),
            "suspension_start": forms.DateInput(attrs={"type": "date"}),
            "notified_at": forms.DateInput(attrs={"type": "date"}),
        }
