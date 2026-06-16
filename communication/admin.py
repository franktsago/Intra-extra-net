from django.contrib import admin

from .models import (Comment, Event, EventParticipant, EventProject, EventReport,
                     EventSupplier, KeyMessage, News, Newsletter, PressReview)


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
admin.site.register(PressReview)
admin.site.register(KeyMessage)
admin.site.register(Newsletter)
admin.site.register(EventProject)
admin.site.register(EventSupplier)
admin.site.register(EventParticipant)
admin.site.register(EventReport)
