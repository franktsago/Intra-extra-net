from django import forms

from accounts.forms import StyledFormMixin
from accounts.models import EXTRANET_ROLES, INTRANET_ROLES, Role, User

from .models import (
    ClientRequest, Creative, CreativeComment, CreativeVersion,
    ExtranetMessage, Project, ProjectFile, Ticket, TicketReply,
)


def _person_label(user):
    """Affiche le nom de la personne (avec l'organisation pour un externe)."""
    name = user.get_full_name() or user.username
    if user.organization:
        return f"{name} — {user.organization}"
    return name


class ProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "reference", "client", "internal_lead", "description",
                  "status", "progress", "start_date", "deadline"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Client / partenaire : uniquement les comptes externes actifs.
        self.fields["client"].queryset = (
            User.objects.filter(role__in=EXTRANET_ROLES, is_active=True)
            .order_by("first_name", "last_name")
        )
        self.fields["client"].label_from_instance = _person_label
        # Chargé de compte LPM : uniquement le personnel interne actif.
        leads = User.objects.filter(role__in=INTRANET_ROLES, is_active=True)
        # Le super administrateur reste masqué de la liste (sauf pour lui-même).
        if not getattr(viewer, "is_admin_lpm", False):
            leads = leads.exclude(role=Role.ADMIN).exclude(is_superuser=True)
        self.fields["internal_lead"].queryset = leads.order_by("first_name", "last_name")
        self.fields["internal_lead"].label_from_instance = _person_label


class ProjectFileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ProjectFile
        fields = ["title", "kind", "file"]


class MessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ExtranetMessage
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Votre message…"})}


class TicketForm(StyledFormMixin, forms.ModelForm):
    """Ouverture d'un ticket par le client."""

    class Meta:
        model = Ticket
        fields = ["kind", "subject", "project", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, client=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Le client ne peut rattacher qu'un de SES projets (facultatif).
        qs = Project.objects.all()
        if client is not None:
            qs = qs.filter(client=client)
        self.fields["project"].queryset = qs
        self.fields["project"].required = False


class TicketReplyForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = TicketReply
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 3, "placeholder": "Votre réponse…"})}


class CreativeForm(StyledFormMixin, forms.ModelForm):
    """Création d'un visuel par LPM (avec son premier fichier)."""

    file = forms.FileField(label="Visuel (V1)")
    note = forms.CharField(label="Note", max_length=255, required=False)

    class Meta:
        model = Creative
        fields = ["project", "title"]


class CreativeVersionForm(StyledFormMixin, forms.ModelForm):
    """Nouvelle version d'un visuel."""

    class Meta:
        model = CreativeVersion
        fields = ["file", "note"]


class CreativeCommentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = CreativeComment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Votre commentaire…"})}


class ClientRequestForm(StyledFormMixin, forms.ModelForm):
    """Formulaire intelligent de demande (campagne, devis, création, événement)."""

    class Meta:
        model = ClientRequest
        fields = ["kind", "title", "details", "budget", "deadline"]
        widgets = {
            "details": forms.Textarea(attrs={"rows": 4,
                "placeholder": "Décrivez votre besoin : objectifs, cibles, contraintes…"}),
            "deadline": forms.DateInput(attrs={"type": "date"}),
        }
