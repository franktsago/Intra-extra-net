from django import forms

from accounts.forms import StyledFormMixin

from .models import Benchmark, Project, ProjectMedia, Ticket


class ProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "kind", "department", "client", "manager", "team", "description",
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

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].required = True
        # Un responsable (hors RH/CEO/admin) ne rattache un projet qu'à SON/SES
        # département(s) ; il en a un présélectionné par défaut.
        if viewer is not None and viewer.is_manager and not viewer.is_rh:
            from projects.views import user_department_ids
            from employees.models import Department
            ids = user_department_ids(viewer)
            if ids:
                self.fields["department"].queryset = Department.objects.filter(id__in=ids)
                if not self.instance.pk and len(ids) == 1:
                    self.fields["department"].initial = next(iter(ids))


class MediaForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectMedia
        fields = ["file", "caption"]


class TicketForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ["title", "kind", "status", "priority", "project", "description", "assigned_to"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class BenchmarkForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Benchmark
        fields = ["title", "category", "url", "summary", "rating", "tags"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 5})}
