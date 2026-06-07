from django.contrib import admin

from .models import DisciplinaryRecord


@admin.register(DisciplinaryRecord)
class DisciplinaryAdmin(admin.ModelAdmin):
    list_display = ("employee", "sanction_type", "status", "fault_date", "notified_at")
    list_filter = ("sanction_type", "status")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "facts")
