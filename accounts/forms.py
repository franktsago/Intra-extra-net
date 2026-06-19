"""Formulaires d'authentification et de gestion des utilisateurs."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.forms import PasswordChangeForm as DjPasswordChangeForm

from .models import Role, User


class CheckboxDropdown(forms.CheckboxSelectMultiple):
    """Liste déroulante contenant des cases à cocher (multi-sélection compacte).

    Réutilisable partout : passer `placeholder` (texte au repos) et `noun`
    (« membre », « rôle »…) pour le compteur de sélection.
    """
    template_name = "includes/checkbox_dropdown.html"

    def __init__(self, *args, placeholder="Sélectionner…", noun="élément", **kwargs):
        self.placeholder = placeholder
        self.noun = noun
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["placeholder"] = self.placeholder
        ctx["widget"]["noun"] = self.noun
        return ctx


def role_choices_for(viewer, instance=None, restrict_ceo=True):
    """Choix de rôles proposés selon le niveau du créateur.

    Hiérarchie d'attribution (création/édition de comptes, restrict_ceo=True) :
      • Administrateur principal → tous les rôles (y compris ADMIN) ;
      • CEO → tout sauf ADMIN (peut nommer un CEO) ;
      • RH → tout sauf ADMIN et CEO.
    Le rôle déjà porté par le compte édité est conservé (pour ne pas perdre la valeur).
    `restrict_ceo=False` (ex. filtre de diffusion) : on n'enlève que ADMIN.
    """
    is_admin = getattr(viewer, "is_admin_lpm", False)
    is_ceo = getattr(viewer, "is_ceo", False)
    inst_role = getattr(instance, "role", None) if instance is not None else None

    def keep(value):
        if value == Role.ADMIN:
            return is_admin or inst_role == Role.ADMIN
        if value == Role.CEO and restrict_ceo:
            return is_ceo or inst_role == Role.CEO
        return True

    return [(v, label) for v, label in Role.choices if keep(v)]

# Classe CSS commune appliquée aux champs (cohérence visuelle).
INPUT = (
    "w-full rounded-lg border border-slate-300 px-3 py-2.5 text-slate-800 "
    "shadow-sm focus:border-[#0073DE] focus:ring-2 focus:ring-[#0196F2]/30 "
    "focus:outline-none transition"
)


FILE_INPUT = (
    "w-full text-sm text-slate-600 rounded-lg border border-slate-300 cursor-pointer "
    "file:mr-3 file:py-2.5 file:px-4 file:border-0 file:bg-lpm/10 file:text-lpm "
    "file:font-medium file:cursor-pointer hover:file:bg-lpm/20"
)


class StyledFormMixin:
    """Applique automatiquement les classes CSS aux widgets."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, (forms.CheckboxSelectMultiple, forms.RadioSelect)):
                # Listes de cases à cocher / boutons radio : petites cases, pas de
                # bordure pleine largeur sur chaque option.
                w.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300 text-[#0073DE]")
            elif isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "h-4 w-4 rounded border-slate-300 text-[#0073DE]")
            elif isinstance(w, (forms.ClearableFileInput, forms.FileInput)):
                w.attrs.setdefault("class", FILE_INPUT)
            else:
                w.attrs.setdefault("class", INPUT)


class LoginForm(StyledFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Identifiant",
        widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "Nom d'utilisateur"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={"placeholder": "••••••••"}),
    )


class UserCreateForm(StyledFormMixin, UserCreationForm):
    """Création d'un compte par un administrateur."""

    first_name = forms.CharField(label="Prénom", max_length=150)
    last_name = forms.CharField(label="Nom", max_length=150)
    email = forms.EmailField(label="Email")

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "role", "phone", "organization"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = role_choices_for(viewer)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.must_change_password = True
        if commit:
            user.save()
        return user


class UserEditForm(StyledFormMixin, forms.ModelForm):
    extra_roles = forms.MultipleChoiceField(
        label="Rôles supplémentaires", required=False, choices=Role.choices,
        widget=CheckboxDropdown(placeholder="Sélectionner les rôles…", noun="rôle"),
        help_text="Permet à l'utilisateur de basculer entre plusieurs fonctions.",
    )
    linked_accounts = forms.ModelMultipleChoiceField(
        label="Comptes liés (même personne)", required=False,
        queryset=User.objects.none(),
        widget=CheckboxDropdown(placeholder="Sélectionner les comptes…", noun="compte"),
        help_text="Autres comptes de la MÊME personne : elle pourra basculer de "
                  "l'un à l'autre sans se reconnecter. Chaque action reste tracée.",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "role", "phone",
                  "organization", "avatar", "is_active"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = role_choices_for(viewer, self.instance)
        self.fields["role"].choices = choices
        self.fields["extra_roles"].choices = choices
        if self.instance and self.instance.pk and self.instance.secondary_roles:
            self.fields["extra_roles"].initial = [
                r.strip() for r in self.instance.secondary_roles.split(",") if r.strip()]
        # Le lien de comptes (accès sans mot de passe) est réservé au super admin.
        if getattr(viewer, "is_admin_lpm", False) and self.instance and self.instance.pk:
            self.fields["linked_accounts"].queryset = (
                User.objects.exclude(pk=self.instance.pk).order_by("last_name", "first_name"))
            self.fields["linked_accounts"].initial = self.instance.linked_accounts.all()
        else:
            self.fields.pop("linked_accounts")

    def save(self, commit=True):
        user = super().save(commit=False)
        extra = [r for r in self.cleaned_data.get("extra_roles", []) if r != user.role]
        user.secondary_roles = ",".join(extra)
        if commit:
            user.save()
            if "linked_accounts" in self.fields:
                user.linked_accounts.set(self.cleaned_data.get("linked_accounts", []))
            self._sync_employee_status(user)
        return user

    @staticmethod
    def _sync_employee_status(user):
        """Répercute la (dés)activation du compte sur la fiche employé.

        Désactiver un compte le sort des effectifs (statut « Sorti ») ; le
        réactiver le replace « En activité » s'il en était sorti. Ainsi un
        employé désactivé disparaît partout (annuaire, effectifs, statistiques)."""
        emp = getattr(user, "employee", None)
        if not emp:
            return
        from employees.models import Employee
        if not user.is_active and emp.status != Employee.Status.TERMINATED:
            emp.status = Employee.Status.TERMINATED
            emp.save(update_fields=["status"])
        elif user.is_active and emp.status == Employee.Status.TERMINATED:
            emp.status = Employee.Status.ACTIVE
            emp.save(update_fields=["status"])


class ProfileForm(StyledFormMixin, forms.ModelForm):
    """Édition de son propre profil.

    Un employé ou un responsable ne peut PAS modifier son identité (nom, prénom,
    email, téléphone) : ces champs sont grisés. Seules la RH et la Direction
    peuvent les changer (ici ou via l'annuaire)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "avatar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        u = self.instance
        if u and u.pk and not getattr(u, "is_rh", False):
            for name in ("first_name", "last_name", "email", "phone"):
                f = self.fields[name]
                f.disabled = True  # ignore toute valeur soumise + grise le champ
                f.help_text = "Modifiable uniquement par la RH."
                f.widget.attrs["class"] = (f.widget.attrs.get("class", "")
                                           + " bg-slate-100 cursor-not-allowed").strip()


class SignatureForm(StyledFormMixin, forms.ModelForm):
    """Signature manuscrite + cachet — réservé aux signataires (RH/CEO/admin)."""

    class Meta:
        model = User
        fields = ["signature", "stamp"]


class PasswordChangeForm(StyledFormMixin, DjPasswordChangeForm):
    pass
