from django import forms

from accounts.forms import StyledFormMixin

from .models import Holiday, LeaveRequest


class LeaveRequestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3, "placeholder": "Motif (facultatif)"}),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            raise forms.ValidationError("La date de fin doit être postérieure à la date de début.")
        return data


class DecisionForm(StyledFormMixin, forms.Form):
    decision = forms.ChoiceField(
        choices=[("approve", "Valider"), ("reject", "Refuser")],
        widget=forms.RadioSelect,
        label="Décision",
    )
    comment = forms.CharField(
        label="Commentaire", required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class HolidayForm(StyledFormMixin, forms.ModelForm):
    AUDIENCE_CHOICES = [
        ("INTERNAL", "Le personnel uniquement (intranet)"),
        ("BOTH", "Le personnel + les clients (intranet & extranet)"),
    ]
    audience = forms.ChoiceField(
        label="Notifier", choices=AUDIENCE_CHOICES, initial="INTERNAL",
        widget=forms.RadioSelect,
        help_text="Choisissez qui est averti de ce jour chômé.",
    )

    class Meta:
        model = Holiday
        fields = ["date", "name"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}
