from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("employees", views.EmployeeViewSet, basename="employee")
router.register("leaves", views.LeaveViewSet, basename="leave")
router.register("tasks", views.TaskViewSet, basename="task")

app_name = "api"

urlpatterns = [
    path("token/", obtain_auth_token, name="token"),
    path("me/", views.me, name="me"),
    path("", include(router.urls)),
]
