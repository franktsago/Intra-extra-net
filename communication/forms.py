from django import forms

from accounts.forms import StyledFormMixin

from .models import Comment, Event, News


class NewsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = News
        fields = ["title", "category", "summary", "content", "image", "is_pinned", "is_published"]
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}


class CommentForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Comment
        fields = ["body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 2, "placeholder": "Votre commentaire…"})}


class EventForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "kind", "start", "end", "location", "description"]
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
