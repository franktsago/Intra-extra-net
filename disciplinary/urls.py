from django.urls import path

from . import views

app_name = "disciplinary"

urlpatterns = [
    path("", views.record_list, name="list"),
    path("nouveau/", views.record_edit, name="create"),
    path("<int:pk>/", views.record_detail, name="detail"),
    path("<int:pk>/modifier/", views.record_edit, name="edit"),
    path("<int:pk>/document-pdf/", views.record_pdf, name="pdf"),
]
