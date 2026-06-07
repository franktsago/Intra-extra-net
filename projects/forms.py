from django import forms

from accounts.forms import StyledFormMixin

from .models import Project, ProjectMedia


class ProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "kind", "client", "manager", "team", "description",
                  "status", "start_date", "deadline", "budget", "spent",
                  "location", "event_date", "providers",
                  "attendees_expected", "attendees_actual"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "providers": forms.Textarea(attrs={"rows": 2}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
            "event_date": forms.DateInput(attrs={"type": "date"}),
            "team": forms.SelectMultiple(attrs={"size": 6}),
        }


class MediaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectMedia
        fields = ["file", "caption"]
