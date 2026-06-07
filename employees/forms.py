from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import INTRANET_ROLES, User

from .models import Department, Employee, Position
from .widgets import CheckboxDropdown


class EmployeeForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "user", "gender", "birth_date", "departments", "positions",
            "manager", "hire_date", "contract_type", "status", "cnps_number",
            "address", "city", "emergency_contact", "emergency_contact_phone",
            "emergency_contact2", "emergency_contact2_phone",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "departments": CheckboxDropdown(new_field="new_departments",
                                            placeholder="Nouveau département…"),
            "positions": CheckboxDropdown(new_field="new_positions",
                                          placeholder="Nouveau poste…"),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        # Comptes internes sans fiche employé (+ le compte courant en édition).
        linked = Employee.objects.exclude(pk=self.instance.pk).values_list("user_id", flat=True)
        qs = User.objects.filter(role__in=INTRANET_ROLES).exclude(pk__in=linked)
        qs = hide_superadmin(qs, viewer)  # admin principal masqué (sauf pour lui-même)
        self.fields["user"].queryset = qs.order_by("first_name", "last_name")
        self.fields["user"].label = "Compte utilisateur"
        self.fields["manager"].queryset = hide_superadmin(
            self.fields["manager"].queryset, viewer, user_field="user")
        if self.instance and self.instance.pk:
            # On ne change pas le compte lié d'une fiche existante.
            self.fields["user"].disabled = True
        # Personne à contacter (1re ligne) obligatoire.
        self.fields["emergency_contact"].required = True
        self.fields["emergency_contact_phone"].required = True


_MONTHS = [
    (1, "Janvier"), (2, "Février"), (3, "Mars"), (4, "Avril"), (5, "Mai"),
    (6, "Juin"), (7, "Juillet"), (8, "Août"), (9, "Septembre"), (10, "Octobre"),
    (11, "Novembre"), (12, "Décembre"),
]
# Année « sentinelle » bissextile (gère le 29/02) — on ne conserve que jour + mois.
BIRTH_SENTINEL_YEAR = 2000


class EmployeeProfileForm(StyledFormMixin, forms.ModelForm):
    """Champs RH d'une fiche employé (hors compte/matricule) — pour la création de compte."""

    birth_day = forms.ChoiceField(
        label="Jour de naissance", required=False,
        choices=[("", "—")] + [(d, d) for d in range(1, 32)])
    birth_month = forms.ChoiceField(
        label="Mois de naissance", required=False,
        choices=[("", "—")] + _MONTHS)

    class Meta:
        model = Employee
        fields = ["gender", "positions", "departments", "manager",
                  "hire_date", "contract_type", "status", "cnps_number", "address",
                  "city", "emergency_contact", "emergency_contact_phone",
                  "emergency_contact2", "emergency_contact2_phone"]
        widgets = {
            "hire_date": forms.DateInput(attrs={"type": "date"}),
            "departments": CheckboxDropdown(new_field="new_departments",
                                            placeholder="Nouveau département…"),
            "positions": CheckboxDropdown(new_field="new_positions",
                                          placeholder="Nouveau poste…"),
        }
    # Jour/mois de naissance + « Fonction / poste » avant « Départements ».
    field_order = ["gender", "birth_day", "birth_month", "positions", "departments",
                   "manager", "hire_date", "contract_type", "status", "cnps_number",
                   "address", "city", "emergency_contact", "emergency_contact_phone",
                   "emergency_contact2", "emergency_contact2_phone"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        self.fields["manager"].queryset = hide_superadmin(
            self.fields["manager"].queryset, viewer, user_field="user")
        self.fields["positions"].label = "Fonction / poste"
        for f in self.fields.values():
            f.required = False  # profil optionnel à la création
        # …sauf la personne à contacter (1re ligne) qui est obligatoire.
        self.fields["emergency_contact"].required = True
        self.fields["emergency_contact_phone"].required = True
        # Pré-remplissage jour/mois si la fiche a déjà une date.
        if self.instance and self.instance.pk and self.instance.birth_date:
            self.fields["birth_day"].initial = self.instance.birth_date.day
            self.fields["birth_month"].initial = self.instance.birth_date.month

    def save(self, commit=True):
        from datetime import date
        emp = super().save(commit=False)
        d, m = self.cleaned_data.get("birth_day"), self.cleaned_data.get("birth_month")
        if d and m:
            emp.birth_date = date(BIRTH_SENTINEL_YEAR, int(m), int(d))
        if commit:
            emp.save()
            self.save_m2m()
        return emp


class DepartmentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "code", "description", "manager", "parent"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        self.fields["manager"].queryset = hide_superadmin(
            self.fields["manager"].queryset, viewer)


class PositionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "department"]
