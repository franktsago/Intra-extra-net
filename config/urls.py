"""Routage racine — Intranet & Extranet LPM Consulting Group."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("dashboard.urls")),
    path("compte/", include("accounts.urls")),
    path("employes/", include("employees.urls")),
    path("documents/", include("documents.urls")),
    path("actualites/", include("communication.urls")),
    path("conges/", include("conges.urls")),
    path("taches/", include("tasks.urls")),
    path("discipline/", include("disciplinary.urls")),
    path("notifications/", include("notifications.urls")),
    path("messagerie/", include("messaging.urls")),
    path("commercial/", include("business.urls")),
    path("projets/", include("projects.urls")),
    path("marketing/", include("marketing.urls")),
    path("rh/", include("hr.urls")),
    path("extranet/", include("extranet.urls")),
    path("api/", include("api.urls")),
]

# Personnalisation de l'en-tête de l'admin Django.
admin.site.site_header = "Administration — LPM Consulting Group"
admin.site.site_title = "Intranet LPM"
admin.site.index_title = "Tableau d'administration"

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
