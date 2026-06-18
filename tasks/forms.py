from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import INTRANET_ROLES, User

from .models import Task


class TaskForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "project", "assigned_to", "priority", "due_date", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        # L'assignation d'une tâche est obligatoire.
        self.fields["assigned_to"].required = True
        qs = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
        # Un responsable (non RH/CEO/admin) n'affecte qu'aux membres de SON département.
        if viewer is not None and viewer.is_manager and not viewer.is_rh:
            from employees.models import department_colleagues_ids
            qs = qs.filter(id__in=department_colleagues_ids(viewer))
        # Le compte admin principal est masqué (sauf pour l'admin lui-même).
        qs = hide_superadmin(qs, viewer)
        self.fields["assigned_to"].queryset = qs.order_by("first_name", "last_name")


class EmployeeTaskForm(StyledFormMixin, forms.ModelForm):
    """Création par un employé : tâche pour lui-même, soumise à validation du responsable."""

    class Meta:
        model = Task
        fields = ["title", "description", "project", "priority", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }


class TaskStatusForm(StyledFormMixin, forms.ModelForm):
    """Formulaire restreint : l'employé ne change que le statut de SA tâche."""

    class Meta:
        model = Task
        fields = ["status"]
