from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import INTRANET_ROLES, User

from .models import Task


class CheckboxDropdown(forms.CheckboxSelectMultiple):
    """Liste déroulante contenant des cases à cocher (multi-sélection compacte)."""
    template_name = "tasks/checkbox_dropdown.html"


class TaskForm(StyledFormMixin, forms.ModelForm):
    # En création (multi=True), un responsable assigne à PLUSIEURS membres : UNE
    # SEULE tâche partagée est créée (statut commun à tous les assignés).
    assignees = forms.ModelMultipleChoiceField(
        label="Assigner à", queryset=User.objects.none(), required=False,
        widget=CheckboxDropdown,
        help_text="Cochez un ou plusieurs membres. La tâche est commune : son statut est partagé.",
    )

    class Meta:
        model = Task
        fields = ["title", "description", "project", "assigned_to", "priority", "due_date", "status"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer=None, multi=False, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        qs = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
        # Un responsable (non RH/CEO/admin) n'affecte qu'aux membres de SON département.
        if viewer is not None and viewer.is_manager and not viewer.is_rh:
            from employees.models import department_colleagues_ids
            qs = qs.filter(id__in=department_colleagues_ids(viewer))
        # Le compte admin principal est masqué (sauf pour l'admin lui-même).
        qs = hide_superadmin(qs, viewer).order_by("first_name", "last_name")
        if multi:
            # Création : assignation multiple obligatoire.
            self.fields.pop("assigned_to")
            self.fields["assignees"].queryset = qs
            self.fields["assignees"].required = True
        else:
            # Édition : un seul assigné (la tâche existe déjà).
            self.fields.pop("assignees")
            self.fields["assigned_to"].required = True
            self.fields["assigned_to"].queryset = qs


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
