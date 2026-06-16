from django.urls import path
from . import views

app_name = "rse"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("initiatives/", views.initiatives, name="initiatives"),
    path("initiative/nouvelle/", views.initiative_edit, name="initiative_create"),
    path("initiative/<int:pk>/modifier/", views.initiative_edit, name="initiative_edit"),
    path("rapports/", views.reports, name="reports"),
    path("rapport/nouveau/", views.report_edit, name="report_create"),
    path("rapport/<int:pk>/modifier/", views.report_edit, name="report_edit"),
    path("sensibilisation/", views.resources, name="resources"),
    path("fournisseurs/", views.suppliers, name="suppliers"),
]
