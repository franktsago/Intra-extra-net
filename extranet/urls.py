from django.urls import path

from . import views

app_name = "extranet"

urlpatterns = [
    path("", views.extranet_home, name="home"),
    path("suivi/", views.project_progress, name="progress"),
    path("campagnes/", views.campaigns, name="campaigns"),
    path("rapports/", views.reports, name="reports"),
    path("validations/", views.validations, name="validations"),
    path("telechargements/", views.downloads, name="downloads"),
    path("galerie/", views.gallery, name="gallery"),
    path("reclamations/", views.tickets, name="tickets"),
    path("reclamations/<int:pk>/", views.ticket_detail, name="ticket"),
    path("demandes/", views.requests_view, name="requests"),
    path("demandes/<int:pk>/<str:decision>/", views.request_decide, name="request_decide"),
    path("creations/", views.creatives, name="creatives"),
    path("creations/nouvelle/", views.creative_create, name="creative_create"),
    path("creations/<int:pk>/", views.creative_detail, name="creative"),
    path("projet/nouveau/", views.project_edit, name="create"),
    path("projet/<int:pk>/", views.project_detail, name="project"),
    path("projet/<int:pk>/modifier/", views.project_edit, name="edit"),
    path("projet/<int:pk>/supprimer/", views.project_delete, name="delete"),
    path("fichier/<int:pk>/<str:decision>/", views.file_validate, name="file_validate"),

    # Espace client : devis & factures
    path("mes-devis/", views.my_quotes, name="my_quotes"),
    path("devis/<int:pk>/", views.client_quote, name="client_quote"),
    path("devis/<int:pk>/pdf/", views.client_quote_pdf, name="client_quote_pdf"),
    path("devis/<int:pk>/decision/<str:decision>/", views.client_quote_decide, name="client_quote_decide"),
    path("mes-factures/", views.my_invoices, name="my_invoices"),
    path("facture/<int:pk>/", views.client_invoice, name="client_invoice"),
    path("facture/<int:pk>/payer/", views.client_invoice_pay, name="client_invoice_pay"),
    path("facture/<int:pk>/pdf/", views.client_invoice_pdf, name="client_invoice_pdf"),
]
