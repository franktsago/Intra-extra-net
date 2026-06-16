from django import forms

from accounts.forms import StyledFormMixin
from accounts.utils import hide_superadmin

from .models import (
    Candidate, Contract, Evaluation, Interview, JobOpening, Mission, Objective,
    OnboardingPlan,
)


class ContractForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            "employee", "type", "title", "start_date", "end_date",
            # Identité salarié (pour le contrat généré)
            "birth_info", "nationality", "id_number",
            # Conditions
            "work_location", "probation_months", "duties", "work_schedule",
            # Rémunération
            "salary", "transport_allowance", "housing_allowance",
            "performance_allowance", "other_allowances", "pay_day",
            "place_signed",
            # Document signé + statut
            "file", "is_active",
        ]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "duties": forms.Textarea(attrs={"rows": 3,
                      "placeholder": "Une mission par ligne…"}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].queryset = hide_superadmin(
            self.fields["employee"].queryset, viewer, user_field="user")
        # Champs facultatifs (le contrat reste créable même incomplet).
        for name in ("title", "end_date", "birth_info", "nationality", "id_number",
                     "work_location", "duties", "work_schedule", "other_allowances",
                     "place_signed", "file"):
            self.fields[name].required = False
        self.fields["start_date"].help_text = (
            "Égale à la date d'embauche de l'employé : la modifier met à jour la fiche.")

    def save(self, commit=True):
        contract = super().save(commit=commit)
        # La date de début d'un contrat actif aligne la date d'embauche de la fiche
        # employé (item 2) : les deux valeurs restent cohérentes partout.
        if commit and contract.is_active and contract.employee_id and contract.start_date:
            emp = contract.employee
            if emp.hire_date != contract.start_date:
                emp.hire_date = contract.start_date
                emp.save(update_fields=["hire_date"])
        return contract


class JobOpeningForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = JobOpening
        fields = ["title", "department", "description", "positions", "status"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class CandidateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Candidate
        fields = ["full_name", "email", "phone", "cv", "rating", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class InterviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Interview
        fields = ["scheduled_at", "interviewer", "mode", "feedback", "recommendation"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "feedback": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interviewer"].queryset = hide_superadmin(
            self.fields["interviewer"].queryset, viewer)


class EvaluationForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Evaluation
        fields = ["employee", "period", "comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Un responsable (non RH/CEO/admin) n'évalue que les membres de SON équipe.
        if viewer is not None and viewer.is_manager and not viewer.is_rh:
            from employees.models import Employee
            self.fields["employee"].queryset = Employee.objects.filter(manager__user=viewer)
        # Le compte admin principal est masqué de la liste (sauf pour l'admin).
        self.fields["employee"].queryset = hide_superadmin(
            self.fields["employee"].queryset, viewer, user_field="user")


class MissionForm(StyledFormMixin, forms.ModelForm):
    """Enregistrement d'une mission par RH/CEO/admin pour n'importe quel interne."""

    class Meta:
        model = Mission
        fields = ["employee", "start_date", "end_date", "destination", "objet"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "objet": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from employees.models import Employee
        # Toute personne interne en activité peut partir en mission (employé, RH,
        # responsable, CEO) ; on masque le super-admin de la liste.
        qs = Employee.objects.filter(status=Employee.Status.ACTIVE).select_related("user")
        self.fields["employee"].queryset = hide_superadmin(qs, viewer, user_field="user")

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La date de fin doit être postérieure ou égale au début.")
        return cleaned


ObjectiveFormSet = forms.inlineformset_factory(
    Evaluation, Objective, fields=["label", "kpi", "weight", "rating", "comment"],
    extra=4, can_delete=True)


class OnboardingPlanForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = OnboardingPlan
        fields = ["name", "description", "role_target"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
