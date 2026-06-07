from django import forms

from accounts.forms import StyledFormMixin
from accounts.utils import hide_superadmin

from .models import Campaign, MediaAsset, Post


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
