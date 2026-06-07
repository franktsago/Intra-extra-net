from django.urls import path

from . import views

app_name = "employees"

urlpatterns = [
    path("", views.employee_list, name="list"),
    path("organigramme/", views.org_chart, name="org_chart"),
    path("departements/", views.department_list, name="departments"),
    path("departements/<int:pk>/modifier/", views.department_edit, name="department_edit"),
    path("departements/<int:pk>/supprimer/", views.department_delete, name="department_delete"),
    path("nouveau/", views.employee_edit, name="create"),
    path("<int:pk>/", views.employee_detail, name="detail"),
    path("<int:pk>/modifier/", views.employee_edit, name="edit"),
    path("<int:pk>/attestation-travail/", views.attestation_travail, name="attestation_travail"),
    path("<int:pk>/attestation-stage/", views.attestation_stage, name="attestation_stage"),
    path("<int:pk>/contrat/", views.contract_download, name="contract_download"),
]
