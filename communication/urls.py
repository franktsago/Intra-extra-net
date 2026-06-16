from django.urls import path

from . import views

app_name = "communication"

urlpatterns = [
    path("", views.news_list, name="list"),
    path("calendrier/", views.calendar, name="calendar"),
    path("evenement/nouveau/", views.event_create, name="event_create"),
    path("nouvelle/", views.news_edit, name="create"),
    # Validation des actualités (RH / CEO / admin)
    path("validation/", views.news_moderation, name="moderation"),
    path("<int:pk>/valider/", views.news_approve, name="approve"),
    path("<int:pk>/refuser/", views.news_reject, name="reject"),
    # Revue de presse — avant les patterns génériques slug/<int:pk>
    path("presse/", views.press_list, name="press_list"),
    path("presse/nouveau/", views.press_edit, name="press_create"),
    path("presse/<int:pk>/modifier/", views.press_edit, name="press_edit"),
    # Messages clés
    path("messages-cles/", views.key_messages, name="key_messages"),
    path("message-cle/nouveau/", views.key_message_edit, name="key_message_create"),
    path("message-cle/<int:pk>/modifier/", views.key_message_edit, name="key_message_edit"),
    # Newsletters
    path("newsletters/", views.newsletter_list, name="newsletter_list"),
    path("newsletter/nouvelle/", views.newsletter_edit, name="newsletter_create"),
    path("newsletter/<int:pk>/modifier/", views.newsletter_edit, name="newsletter_edit"),
    # Événementiel
    path("evenements/projets/", views.event_projects, name="event_projects"),
    path("evenement/projet/nouveau/", views.event_project_edit, name="event_project_create"),
    path("evenement/projet/<int:pk>/", views.event_project_detail, name="event_project_detail"),
    path("evenement/projet/<int:pk>/modifier/", views.event_project_edit, name="event_project_edit"),
    path("evenement/projet/<int:pk>/participant/", views.event_participant_add, name="event_participant_add"),
    path("evenement/projet/<int:pk>/bilan/", views.event_report_edit, name="event_report_edit"),
    # Patterns génériques — doivent rester en dernier
    path("<slug:slug>/", views.news_detail, name="detail"),
    path("<int:pk>/modifier/", views.news_edit, name="edit"),
    path("<int:pk>/supprimer/", views.news_delete, name="delete"),
]
