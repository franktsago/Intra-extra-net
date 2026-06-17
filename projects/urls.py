from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.project_list, name="list"),
    path("nouveau/", views.project_edit, name="create"),
    path("<int:pk>/", views.project_detail, name="detail"),
    path("<int:pk>/modifier/", views.project_edit, name="edit"),
    path("<int:pk>/phase/<int:phase_id>/<str:status>/", views.phase_set, name="phase_set"),
    path("<int:pk>/media/", views.media_upload, name="media_upload"),
    path("<int:pk>/media/<int:media_id>/supprimer/", views.media_delete, name="media_delete"),
    path("backlog/", views.ticket_list, name="ticket_list"),
    path("ticket/nouveau/", views.ticket_edit, name="ticket_create"),
    path("ticket/<int:pk>/modifier/", views.ticket_edit, name="ticket_edit"),
    path("benchmarks/", views.benchmark_list, name="benchmark_list"),
    path("benchmark/nouveau/", views.benchmark_edit, name="benchmark_create"),
    path("benchmark/<int:pk>/modifier/", views.benchmark_edit, name="benchmark_edit"),
]
