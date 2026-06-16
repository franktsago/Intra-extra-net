from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = "business"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="business:client_list", permanent=False)),
    path("direction/", views.executive, name="executive"),

    # CRM
    path("clients/", views.client_list, name="client_list"),
    path("clients/nouveau/", views.client_edit, name="client_create"),
    path("clients/<int:pk>/", views.client_detail, name="client_detail"),
    path("clients/<int:pk>/modifier/", views.client_edit, name="client_edit"),
    path("clients/<int:pk>/valider/", views.client_validate, name="client_validate"),
    path("pipeline/", views.pipeline, name="pipeline"),
    path("opportunite/nouvelle/", views.opportunity_edit, name="opportunity_create"),
    path("opportunite/<int:pk>/", views.opportunity_edit, name="opportunity_edit"),

    # Devis
    path("devis/", views.quote_list, name="quote_list"),
    path("devis/nouveau/", views.quote_edit, name="quote_create"),
    path("devis/<int:pk>/", views.quote_detail, name="quote_detail"),
    path("devis/<int:pk>/modifier/", views.quote_edit, name="quote_edit"),
    path("devis/<int:pk>/statut/<str:action>/", views.quote_status, name="quote_status"),
    path("devis/<int:pk>/facturer/", views.quote_to_invoice, name="quote_to_invoice"),
    path("devis/<int:pk>/pdf/", views.quote_pdf, name="quote_pdf"),

    # Factures
    path("factures/", views.invoice_list, name="invoice_list"),
    path("factures/nouvelle/", views.invoice_edit, name="invoice_create"),
    path("factures/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("factures/<int:pk>/modifier/", views.invoice_edit, name="invoice_edit"),
    path("factures/<int:pk>/emettre/", views.invoice_issue, name="invoice_issue"),
    path("factures/<int:pk>/paiement/", views.invoice_payment, name="invoice_payment"),
    path("factures/<int:pk>/pdf/", views.invoice_pdf, name="invoice_pdf"),
]
