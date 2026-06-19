from django.contrib import admin

from .models import Department, Employee, Position


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "manager", "parent", "headcount")
    search_fields = ("name", "code")
    filter_horizontal = ("managers",)


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("title", "department")
    list_filter = ("department",)
    search_fields = ("title",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("matricule", "full_name", "department_names", "position_titles", "contract_type", "status")
    list_filter = ("status", "contract_type", "departments")
    search_fields = ("matricule", "user__first_name", "user__last_name", "user__email")
    autocomplete_fields = ("user", "manager")
    filter_horizontal = ("departments", "positions")
    readonly_fields = ("matricule",)  # attribué automatiquement, non modifiable
