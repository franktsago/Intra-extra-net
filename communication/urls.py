from django.urls import path

from . import views

app_name = "communication"

urlpatterns = [
    path("", views.news_list, name="list"),
    path("calendrier/", views.calendar, name="calendar"),
    path("evenement/nouveau/", views.event_create, name="event_create"),
    path("nouvelle/", views.news_edit, name="create"),
    path("<slug:slug>/", views.news_detail, name="detail"),
    path("<int:pk>/modifier/", views.news_edit, name="edit"),
    path("<int:pk>/supprimer/", views.news_delete, name="delete"),
]
