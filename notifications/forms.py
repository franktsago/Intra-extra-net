"""Formulaire de diffusion d'une notification/annonce vers le personnel ou les clients."""

from django import forms

from accounts.forms import StyledFormMixin, role_choices_for
from accounts.models import EXTRANET_ROLES, INTRANET_ROLES, Role

from .models import Notification


class BroadcastForm(StyledFormMixin, forms.Form):
    TARGETS = [
        ("INTERNAL", "Le personnel (intranet)"),
        ("EXTERNAL", "Les clients & partenaires (extranet)"),
        ("BOTH", "Tout le monde (personnel + clients)"),
    ]

    title = forms.CharField(label="Titre", max_length=200)
    message = forms.CharField(
        label="Message", widget=forms.Textarea(attrs={"rows": 4}), max_length=500
    )
    target = forms.ChoiceField(label="Destinataires", choices=TARGETS,
                               widget=forms.RadioSelect, initial="INTERNAL")
    level = forms.ChoiceField(label="Niveau", choices=Notification.Level.choices,
                              initial=Notification.Level.INFO)
    roles = forms.MultipleChoiceField(
        label="Affiner par rôle (optionnel)", required=False,
        widget=forms.CheckboxSelectMultiple,
        choices=Role.choices,
        help_text="Laissez vide pour diffuser à l'ensemble du périmètre choisi.",
    )
    url = forms.CharField(label="Lien (optionnel)", max_length=300, required=False,
                          help_text="Chemin interne, ex. /actualites/")

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtre de ciblage : on masque seulement ADMIN (le CEO reste ciblable).
        self.fields["roles"].choices = role_choices_for(viewer, restrict_ceo=False)

    def recipient_roles(self):
        """Ensemble des rôles ciblés selon le périmètre + l'affinage éventuel."""
        target = self.cleaned_data["target"]
        if target == "INTERNAL":
            base = set(INTRANET_ROLES)
        elif target == "EXTERNAL":
            base = set(EXTRANET_ROLES)
        else:
            base = set(INTRANET_ROLES) | set(EXTRANET_ROLES)
        chosen = set(self.cleaned_data.get("roles") or [])
        if chosen:
            base &= chosen
        return base
