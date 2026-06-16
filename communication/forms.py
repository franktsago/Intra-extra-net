from django import forms

from accounts.forms import StyledFormMixin

from .models import (Comment, Event, EventParticipant, EventProject, EventReport,
                     KeyMessage, News, Newsletter, PressReview)


class NewsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = News
        # La visibilité est pilotée par la modération (mod_status), pas par un champ libre.
        fields = ["title", "category", "summary", "content", "image", "is_pinned"]
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


class PressReviewForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = PressReview
        fields = ["title", "source", "media_type", "tone", "url", "excerpt", "published_at"]
        widgets = {
            "excerpt": forms.Textarea(attrs={"rows": 4}),
            "published_at": forms.DateInput(attrs={"type": "date"}),
        }


class KeyMessageForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = KeyMessage
        fields = ["category", "title", "content", "audience", "is_active"]
        widgets = {"content": forms.Textarea(attrs={"rows": 6})}


class NewsletterForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Newsletter
        fields = ["subject", "content", "status", "recipients_count", "opens"]
        widgets = {"content": forms.Textarea(attrs={"rows": 8})}


class EventProjectForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventProject
        fields = ["name", "event", "brief", "location", "date", "budget", "status", "responsible", "retro_planning", "notes"]
        widgets = {
            "brief": forms.Textarea(attrs={"rows": 4}),
            "retro_planning": forms.Textarea(attrs={"rows": 4}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "date": forms.DateInput(attrs={"type": "date"}),
        }


class EventParticipantForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventParticipant
        fields = ["first_name", "last_name", "email", "phone", "company", "status", "badge_printed", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class EventReportForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EventReport
        fields = ["summary", "participants_count", "budget_spent", "feedback", "kpis", "learnings", "photos_url"]
        widgets = {
            "summary": forms.Textarea(attrs={"rows": 4}),
            "feedback": forms.Textarea(attrs={"rows": 3}),
            "kpis": forms.Textarea(attrs={"rows": 3}),
            "learnings": forms.Textarea(attrs={"rows": 3}),
        }
