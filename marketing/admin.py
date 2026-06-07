from django.contrib import admin

from .models import Campaign, MediaAsset, Post


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "brand", "channel", "status", "start_date", "manager")
    list_filter = ("channel", "status")
    search_fields = ("name", "brand__name")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "platform", "scheduled_at", "status", "author")
    list_filter = ("platform", "status")
    search_fields = ("title", "content")
    date_hierarchy = "scheduled_at"


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "kind", "created_at")
    list_filter = ("kind",)
    search_fields = ("title", "tags")
