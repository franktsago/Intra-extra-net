from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("diffuser/", views.broadcast, name="broadcast"),
    path("tout-lire/", views.mark_all_read, name="mark_all_read"),
    path("tout-supprimer/", views.clear_notifications, name="clear"),
    path("<int:pk>/supprimer/", views.delete_notification, name="delete"),
    path("<int:pk>/", views.open_notification, name="open"),
]
