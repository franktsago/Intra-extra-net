from django.urls import path

from . import views

app_name = "marketing"

urlpatterns = [
    path("", views.campaign_list, name="campaign_list"),
    path("campagne/nouvelle/", views.campaign_edit, name="campaign_create"),
    path("campagne/<int:pk>/", views.campaign_detail, name="campaign_detail"),
    path("campagne/<int:pk>/modifier/", views.campaign_edit, name="campaign_edit"),

    path("calendrier/", views.calendar, name="calendar"),
    path("publication/nouvelle/", views.post_edit, name="post_create"),
    path("publication/<int:pk>/modifier/", views.post_edit, name="post_edit"),
    path("publication/<int:pk>/<str:action>/", views.post_status, name="post_status"),

    path("mediatheque/", views.library, name="library"),
    path("mediatheque/upload/", views.media_upload, name="media_upload"),
]
