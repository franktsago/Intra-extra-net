from django.urls import path

from . import views

app_name = "conges"

urlpatterns = [
    path("", views.my_leaves, name="my"),
    path("absences/", views.absences, name="absences"),
    path("demande/", views.leave_create, name="create"),
    path("validation/", views.leave_queue, name="queue"),
    path("jours-feries/", views.holidays, name="holidays"),
    path("<int:pk>/", views.leave_detail, name="detail"),
    path("<int:pk>/annuler/", views.leave_cancel, name="cancel"),
    path("<int:pk>/supprimer/", views.leave_delete, name="leave_delete"),
    path("<int:pk>/decision/", views.leave_decide, name="decide"),
    path("<int:pk>/note-pdf/", views.leave_pdf, name="pdf"),
]
