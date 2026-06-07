from django.contrib import admin

from .models import (
    Attendance, Candidate, Contract, Evaluation, Interview, JobOpening, Mission,
    Objective, PayrollSetting, SalaryAdjustment,
)


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ("employee", "type", "start_date", "end_date", "salary", "is_active")
    list_filter = ("type", "is_active")
    search_fields = ("employee__user__first_name", "employee__user__last_name")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "check_in", "check_out", "status")
    list_filter = ("status", "date")
    date_hierarchy = "date"


class CandidateInline(admin.TabularInline):
    model = Candidate
    extra = 0


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    list_display = ("title", "department", "positions", "status")
    list_filter = ("status",)
    inlines = [CandidateInline]


class InterviewInline(admin.TabularInline):
    model = Interview
    extra = 0


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ("full_name", "opening", "status", "rating")
    list_filter = ("status",)
    search_fields = ("full_name", "email")
    inlines = [InterviewInline]


class ObjectiveInline(admin.TabularInline):
    model = Objective
    extra = 2


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ("employee", "period", "status", "score")
    list_filter = ("status",)
    inlines = [ObjectiveInline]


@admin.register(Mission)
class MissionAdmin(admin.ModelAdmin):
    list_display = ("employee", "start_date", "end_date", "destination", "created_by")
    list_filter = ("start_date",)
    search_fields = ("employee__user__first_name", "employee__user__last_name", "destination")
    date_hierarchy = "start_date"


@admin.register(PayrollSetting)
class PayrollSettingAdmin(admin.ModelAdmin):
    list_display = ("late_coefficient", "updated_by", "updated_at")


@admin.register(SalaryAdjustment)
class SalaryAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "month", "amount", "reason", "set_by")
    list_filter = ("month",)
    search_fields = ("employee__user__first_name", "employee__user__last_name")
