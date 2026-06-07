from django.urls import path

from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.task_board, name="board"),
    path("nouvelle/", views.task_create, name="create"),
    path("<int:pk>/", views.task_detail, name="detail"),
    path("<int:pk>/valider/<str:decision>/", views.task_approve, name="approve"),
    path("<int:pk>/supprimer/", views.task_delete, name="delete"),
]
