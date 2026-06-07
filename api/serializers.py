"""Sérialiseurs de l'API REST externe (lecture)."""

from rest_framework import serializers

from conges.models import LeaveRequest
from employees.models import Employee
from tasks.models import Task


class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField()
    role = serializers.CharField(source="effective_role")
    role_display = serializers.CharField(source="effective_role_display")
    is_internal = serializers.BooleanField()
    is_external = serializers.BooleanField()

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username


class EmployeeSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    email = serializers.EmailField(read_only=True)
    phone = serializers.CharField(read_only=True)
    departments = serializers.CharField(source="department_names", read_only=True)
    positions = serializers.CharField(source="position_titles", read_only=True)
    manager = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "full_name", "matricule", "email", "phone", "departments",
                  "positions", "manager", "hire_date", "contract_type", "status"]

    def get_manager(self, obj):
        return obj.manager.full_name if obj.manager else None


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee = serializers.CharField(source="employee.full_name", read_only=True)
    leave_type = serializers.CharField(source="leave_type.name", read_only=True)
    current_role = serializers.CharField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = ["id", "employee", "leave_type", "start_date", "end_date",
                  "days_count", "status", "current_role", "reference", "created_at"]


class TaskSerializer(serializers.ModelSerializer):
    assigned_to = serializers.SerializerMethodField()
    project = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = ["id", "title", "description", "status", "priority", "due_date",
                  "project", "assigned_to", "is_approved", "created_at"]

    def get_assigned_to(self, obj):
        u = obj.assigned_to
        return (u.get_full_name() or u.username) if u else None

    def get_project(self, obj):
        return obj.project.name if obj.project else None
