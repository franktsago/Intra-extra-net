from django import forms

from accounts.forms import StyledFormMixin

from .models import ChatGroup, GroupMessage, Message


class MessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Message
        fields = ["body", "attachment"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Écrire un message…"})}


class NewConversationForm(StyledFormMixin, forms.Form):
    recipient = forms.ChoiceField(label="Destinataire")
    body = forms.CharField(
        label="Message", widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Votre message…"})
    )
    attachment = forms.FileField(label="Pièce jointe", required=False)

    def __init__(self, *args, recipients=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "— Choisir un destinataire —")]
        for u in (recipients or []):
            label = (u.get_full_name() or u.username) + f" ({u.get_role_display()})"
            choices.append((u.pk, label))
        self.fields["recipient"].choices = choices


class GroupForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ChatGroup
        fields = ["name", "description", "members"]
        widgets = {"members": forms.SelectMultiple(attrs={"size": 10})}

    def __init__(self, *args, member_qs=None, **kwargs):
        super().__init__(*args, **kwargs)
        if member_qs is not None:
            self.fields["members"].queryset = member_qs


class GroupMessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = GroupMessage
        fields = ["body", "attachment"]
        widgets = {"body": forms.Textarea(attrs={"rows": 1, "placeholder": "Écrire au groupe…"})}
