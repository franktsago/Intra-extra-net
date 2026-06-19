from django.contrib import admin

from .models import Call, CallSignal, Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created_at", "sender", "recipient", "is_read")
    list_filter = ("is_read",)
    search_fields = ("sender__username", "recipient__username", "body")
    date_hierarchy = "created_at"


@admin.register(Call)
class CallAdmin(admin.ModelAdmin):
    list_display = ("created_at", "caller", "other", "group", "mode", "status")
    list_filter = ("mode", "status")
    date_hierarchy = "created_at"


@admin.register(CallSignal)
class CallSignalAdmin(admin.ModelAdmin):
    list_display = ("id", "call", "sender", "kind", "created_at")
    list_filter = ("kind",)
