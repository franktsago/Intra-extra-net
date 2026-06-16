from django import forms

from accounts.forms import StyledFormMixin

from .models import RSEIndicator, RSEInitiative, RSEReport, RSEResource


class RSEIndicatorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RSEIndicator
        fields = ["category", "name", "value", "unit", "target", "year", "source", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}


class RSEInitiativeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RSEInitiative
        fields = ["title", "description", "category", "status", "start_date", "end_date", "responsible", "impact"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "impact": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class RSEReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RSEReport
        fields = ["year", "title", "content", "published", "document"]
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}


class RSEResourceForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = RSEResource
        fields = ["title", "kind", "content", "file", "published"]
        widgets = {"content": forms.Textarea(attrs={"rows": 5})}
