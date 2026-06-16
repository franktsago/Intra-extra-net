from django import forms

from accounts.forms import StyledFormMixin
from accounts.utils import hide_superadmin

from .models import ABTest, AdCampaign, Campaign, EmailCampaign, Lead, MediaAsset, Post, SEOKeyword


class CampaignForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Campaign
        fields = ["name", "brand", "project", "channel", "status", "objectives",
                  "budget", "start_date", "end_date", "manager",
                  "target_reach", "actual_reach", "leads"]
        widgets = {
            "objectives": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, viewer=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["manager"].queryset = hide_superadmin(
            self.fields["manager"].queryset, viewer)


class PostForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Post
        fields = ["brand", "campaign", "platform", "title", "content", "media", "scheduled_at"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 4}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class MediaAssetForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MediaAsset
        fields = ["title", "brand", "kind", "file", "tags"]


class LeadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["first_name", "last_name", "company", "email", "phone",
                  "source", "status", "campaign", "notes", "last_contact"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "last_contact": forms.DateInput(attrs={"type": "date"}),
        }


class SEOKeywordForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SEOKeyword
        fields = ["keyword", "url", "position", "previous_position",
                  "search_volume", "difficulty", "notes", "updated_at", "campaign"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "updated_at": forms.DateInput(attrs={"type": "date"}),
        }


class AdCampaignForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = AdCampaign
        fields = ["name", "platform", "status", "campaign", "budget", "spent",
                  "impressions", "clicks", "conversions", "start_date", "end_date", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class EmailCampaignForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = EmailCampaign
        fields = ["subject", "preview_text", "content", "status", "campaign",
                  "scheduled_at", "recipients_count", "opens", "clicks", "unsubscribes"]
        widgets = {
            "content": forms.Textarea(attrs={"rows": 6}),
            "scheduled_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class ABTestForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ABTest
        fields = ["name", "hypothesis", "variant_a", "variant_b", "metric",
                  "status", "winner", "result", "start_date", "end_date"]
        widgets = {
            "hypothesis": forms.Textarea(attrs={"rows": 3}),
            "variant_a": forms.Textarea(attrs={"rows": 3}),
            "variant_b": forms.Textarea(attrs={"rows": 3}),
            "result": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }
