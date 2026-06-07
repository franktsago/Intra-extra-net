from django.contrib import admin

from .models import (
    Holiday, LeaveApproval, LeaveBalanceAdjustment, LeaveRequest, LeaveType,
)


class LeaveApprovalInline(admin.TabularInline):
    model = LeaveApproval
    extra = 0
    readonly_fields = ("level", "role", "approver", "approved", "comment", "decided_at")


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_paid", "deducts_balance", "default_days", "legal_reference")


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ("date", "name")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "days_count", "status", "current_level", "reference")
    list_filter = ("status", "leave_type")
    search_fields = ("employee__user__first_name", "employee__user__last_name", "reference")
    date_hierarchy = "start_date"
    inlines = [LeaveApprovalInline]


@admin.register(LeaveBalanceAdjustment)
class AdjustmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "days", "reason", "created_by", "created_at")
