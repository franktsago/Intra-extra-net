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

    # KPI Dashboard
    path("kpi/", views.kpi_dashboard, name="kpi_dashboard"),
    # Leads / Prospects
    path("leads/", views.lead_list, name="lead_list"),
    path("lead/nouveau/", views.lead_edit, name="lead_create"),
    path("lead/<int:pk>/modifier/", views.lead_edit, name="lead_edit"),
    # Marketing Digital
    path("digital/", views.digital_hub, name="digital_hub"),
    path("seo/", views.seo_list, name="seo_list"),
    path("seo/nouveau/", views.seo_edit, name="seo_create"),
    path("seo/<int:pk>/modifier/", views.seo_edit, name="seo_edit"),
    path("ads/", views.ads_list, name="ads_list"),
    path("ads/nouvelle/", views.ads_edit, name="ads_create"),
    path("ads/<int:pk>/modifier/", views.ads_edit, name="ads_edit"),
    path("email/", views.email_list, name="email_list"),
    path("email/nouvelle/", views.email_edit, name="email_create"),
    path("email/<int:pk>/modifier/", views.email_edit, name="email_edit"),
    path("ab-tests/", views.abtest_list, name="abtest_list"),
    path("ab-test/nouveau/", views.abtest_edit, name="abtest_create"),
    path("ab-test/<int:pk>/modifier/", views.abtest_edit, name="abtest_edit"),
]
