from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sender", "recipient", "is_read")
    list_filter = ("is_read",)
    search_fields = ("sender__username", "recipient__username", "body")
    date_hierarchy = "created_at"
