"""API REST externe (lecture) — authentification par token.

Obtenir un token : POST /api/token/ {username, password} → {"token": "..."}.
Puis header : Authorization: Token <token>.
"""

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.utils import hide_superadmin
from conges.models import LeaveRequest
from employees.models import Employee
from tasks.models import Task

from .serializers import (
    EmployeeSerializer, LeaveRequestSerializer, MeSerializer, TaskSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    """Profil de l'utilisateur authentifié."""
    return Response(MeSerializer(request.user).data)


class EmployeeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = EmployeeSerializer

    def get_queryset(self):
        user = self.request.user
        qs = (Employee.objects.select_related("user", "manager__user")
              .prefetch_related("departments", "positions"))
        if not user.is_manager:
            # Un employé ne voit que sa propre fiche.
            return qs.filter(user=user)
        qs = hide_superadmin(qs, user, user_field="user")
        if user.is_rh:
            return qs
        # Un responsable : son équipe + lui-même.
        return qs.filter(manager__user=user) | qs.filter(user=user)


class LeaveViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = LeaveRequestSerializer

    def get_queryset(self):
        user = self.request.user
        qs = LeaveRequest.objects.select_related("employee__user", "leave_type")
        if user.is_rh:
            return qs
        if user.is_manager:
            return qs.filter(employee__manager__user=user) | qs.filter(employee__user=user)
        return qs.filter(employee__user=user)


class TaskViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        from django.db.models import Q
        user = self.request.user
        qs = Task.objects.select_related("assigned_to", "project")
        if user.is_rh:
            return qs
        return qs.filter(Q(assigned_to=user) | Q(created_by=user)).distinct()
