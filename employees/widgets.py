"""Widget : liste déroulante de cases à cocher (multi-sélection) + ajout d'un nouvel item."""

from django import forms


class CheckboxDropdown(forms.CheckboxSelectMultiple):
    """Sélection multiple présentée en menu déroulant repliable, avec ajout inline.

    Les nouveaux éléments saisis sont postés sous le nom `new_field` (liste),
    à traiter dans la vue (création + rattachement).
    """

    template_name = "widgets/checkbox_dropdown.html"

    def __init__(self, *args, new_field=None, placeholder="Ajouter…", **kwargs):
        self.new_field = new_field
        self.placeholder = placeholder
        super().__init__(*args, **kwargs)

    def get_context(self, name, value, attrs):
        ctx = super().get_context(name, value, attrs)
        ctx["widget"]["new_field"] = self.new_field or f"new_{name}"
        ctx["widget"]["placeholder"] = self.placeholder
        return ctx
