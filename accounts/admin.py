from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjUserAdmin

from .models import ActivityLog, User


@admin.register(User)
class UserAdmin(DjUserAdmin):
    list_display = ("username", "get_full_name", "role", "email", "is_active", "is_external")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "first_name", "last_name", "email", "organization")
    fieldsets = DjUserAdmin.fieldsets + (
        ("LPM — Rôle & profil", {"fields": ("role", "phone", "avatar", "organization",
                                            "must_change_password", "created_by")}),
    )

    @admin.display(boolean=True, description="Externe")
    def is_external(self, obj):
        return obj.is_external


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "description", "ip_address")
    list_filter = ("action", "created_at")
    search_fields = ("user__username", "description", "ip_address")
    date_hierarchy = "created_at"
    readonly_fields = ("user", "action", "description", "ip_address", "path", "created_at")

    def has_add_permission(self, request):
        return False
