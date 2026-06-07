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
]
