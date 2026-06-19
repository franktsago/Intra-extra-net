from django import forms

from accounts.forms import CheckboxDropdown as SimpleCheckboxDropdown
from accounts.forms import StyledFormMixin
from accounts.models import INTRANET_ROLES, User

from .models import Department, Employee, Position
from .widgets import CheckboxDropdown


class EmployeeForm(StyledFormMixin, forms.ModelForm):
    # Informations du compte utilisateur lié, éditables directement depuis l'annuaire.
    first_name = forms.CharField(label="Prénom", max_length=150, required=False)
    last_name = forms.CharField(label="Nom", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)
    phone = forms.CharField(label="Téléphone", max_length=30, required=False)

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
    # Identité (compte) en tête, avant les champs RH.
    field_order = ["user", "first_name", "last_name", "email", "phone", "gender",
                   "birth_date", "departments", "positions", "manager", "hire_date",
                   "contract_type", "status", "cnps_number", "address", "city",
                   "emergency_contact", "emergency_contact_phone",
                   "emergency_contact2", "emergency_contact2_phone"]

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
            # Pré-remplit l'identité depuis le compte lié.
            u = self.instance.user
            self.fields["first_name"].initial = u.first_name
            self.fields["last_name"].initial = u.last_name
            self.fields["email"].initial = u.email
            self.fields["phone"].initial = u.phone
        # Personne à contacter (1re ligne) obligatoire.
        self.fields["emergency_contact"].required = True
        self.fields["emergency_contact_phone"].required = True

    def save(self, commit=True):
        emp = super().save(commit=commit)
        # Répercute les modifications d'identité sur le compte utilisateur lié.
        user = emp.user
        if user:
            user.first_name = self.cleaned_data.get("first_name", user.first_name)
            user.last_name = self.cleaned_data.get("last_name", user.last_name)
            user.email = self.cleaned_data.get("email", user.email)
            user.phone = self.cleaned_data.get("phone", user.phone)
            if commit:
                user.save(update_fields=["first_name", "last_name", "email", "phone"])
        if commit:
            # La date d'embauche pilote la date de début du contrat actif (item 2) :
            # elles restent toujours égales.
            active = emp.contracts.filter(is_active=True).order_by("-start_date").first()
            if active and active.start_date != emp.hire_date:
                active.start_date = emp.hire_date
                active.save(update_fields=["start_date"])
        return emp


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
    managers = forms.ModelMultipleChoiceField(
        label="Responsables", required=False, queryset=None,
        widget=SimpleCheckboxDropdown(placeholder="Sélectionner les responsables…", noun="responsable"),
        help_text="Un département peut avoir plusieurs responsables.",
    )

    class Meta:
        model = Department
        fields = ["name", "code", "description", "parent"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.utils import hide_superadmin
        qs = hide_superadmin(
            User.objects.filter(role__in=INTRANET_ROLES, is_active=True), viewer
        ).order_by("first_name", "last_name")
        self.fields["managers"].queryset = qs
        if self.instance and self.instance.pk:
            init = list(self.instance.managers.all())
            if not init and self.instance.manager_id:
                init = [self.instance.manager]
            self.fields["managers"].initial = init

    def save(self, commit=True):
        dept = super().save(commit=False)
        mgrs = list(self.cleaned_data.get("managers", []))
        # Le responsable principal (compat/affichage) = 1er sélectionné.
        dept.manager = mgrs[0] if mgrs else None
        if commit:
            dept.save()
            dept.managers.set(mgrs)
        return dept


class PositionForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Position
        fields = ["title", "department"]
