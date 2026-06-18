from django import forms

from accounts.forms import StyledFormMixin

from .models import Document, DocumentCategory


class DocumentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Document
        fields = ["title", "category", "file", "description", "visibility", "is_confidential"]

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Seuls RH / CEO / admin peuvent marquer un document comme confidentiel.
        if not getattr(viewer, "is_rh", False):
            self.fields.pop("is_confidential", None)
        # Un employé (non responsable) ne peut partager que vers ses collègues,
        # son responsable, ou les deux.
        if viewer is not None and not getattr(viewer, "is_manager", False):
            share = {"COLLEAGUES", "MY_MANAGER", "COLL_MGR"}
            self.fields["visibility"].choices = [
                (v, l) for v, l in Document.Visibility.choices if v in share]
            self.fields["visibility"].initial = "MY_MANAGER"


class CategoryForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = DocumentCategory
        fields = ["name", "description"]
