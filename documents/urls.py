from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("", views.document_list, name="list"),
    path("deposer/", views.document_upload, name="upload"),
    path("<int:pk>/lire/", views.document_view, name="view"),
    path("<int:pk>/flux/", views.document_raw, name="raw"),
    path("<int:pk>/telecharger/", views.document_download, name="download"),
    path("<int:pk>/archiver/", views.document_archive, name="archive"),
    path("<int:pk>/supprimer/", views.document_delete, name="delete"),
]
