from django.urls import path

from . import views

app_name = "hr"

urlpatterns = [
    path("", views.hub, name="hub"),
    path("statistiques/", views.stats, name="stats"),
    # Contrats
    path("contrats/", views.contract_list, name="contracts"),
    path("contrats/nouveau/", views.contract_edit, name="contract_create"),
    path("contrats/<int:pk>/modifier/", views.contract_edit, name="contract_edit"),
    path("contrats/<int:pk>/generer/", views.contract_generate, name="contract_generate"),
    # Présences / pointage
    path("pointage/", views.my_attendance, name="pointage"),
    path("pointage/<str:action>/", views.clock, name="clock"),
    path("anniversaires/", views.birthdays, name="birthdays"),
    path("presences/", views.attendance_today, name="attendance"),
    path("presences/definir-lieu/", views.set_office, name="set_office"),
    path("presences/export/", views.attendance_export, name="attendance_export"),
    path("presences/parametres/", views.attendance_settings, name="attendance_settings"),
    path("paie/incidences/", views.payroll_impacts, name="payroll_impacts"),
    path("paie/incidences/export/", views.payroll_export, name="payroll_export"),
    # Missions
    path("missions/", views.mission_list, name="missions"),
    path("missions/nouvelle/", views.mission_create, name="mission_create"),
    path("missions/<int:pk>/ordre-pdf/", views.mission_pdf, name="mission_pdf"),
    path("missions/<int:pk>/supprimer/", views.mission_delete, name="mission_delete"),
    # Recrutement
    path("recrutement/", views.opening_list, name="openings"),
    path("recrutement/nouvelle/", views.opening_edit, name="opening_create"),
    path("recrutement/<int:pk>/", views.opening_detail, name="opening_detail"),
    path("recrutement/<int:pk>/modifier/", views.opening_edit, name="opening_edit"),
    path("candidat/<int:pk>/", views.candidate_detail, name="candidate_detail"),
    path("candidat/<int:pk>/statut/<str:status>/", views.candidate_status, name="candidate_status"),
    # Évaluation
    path("evaluations/", views.evaluation_list, name="evaluations"),
    path("evaluations/nouvelle/", views.evaluation_edit, name="evaluation_create"),
    path("evaluations/<int:pk>/", views.evaluation_detail, name="evaluation_detail"),
    path("evaluations/<int:pk>/modifier/", views.evaluation_edit, name="evaluation_edit"),
    path("evaluations/<int:pk>/statut/<str:status>/", views.evaluation_status, name="evaluation_status"),
    # Onboarding
    path("onboarding/", views.onboarding_list, name="onboarding"),
    path("onboarding/nouveau/", views.onboarding_plan_edit, name="onboarding_create"),
    path("onboarding/<int:pk>/modifier/", views.onboarding_plan_edit, name="onboarding_edit"),
]
