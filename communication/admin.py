from django.contrib import admin

from .models import Comment, Event, News


@admin.register(News)
class NewsAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_pinned", "is_published", "author", "created_at")
    list_filter = ("category", "is_pinned", "is_published")
    search_fields = ("title", "content")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "start", "location")
    list_filter = ("kind",)


admin.site.register(Comment)
