from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("nouveau/", views.new_message, name="new"),
    path("message/<int:pk>/supprimer/", views.message_delete, name="message_delete"),
    path("message/<int:pk>/modifier/", views.message_edit, name="message_edit"),
    path("message/<int:pk>/supprimer-pour-moi/", views.message_delete_me, name="message_delete_me"),
    path("discussions/message/<int:pk>/modifier/", views.group_message_edit, name="group_message_edit"),
    path("discussions/message/<int:pk>/supprimer-pour-moi/", views.group_message_delete_me, name="group_message_delete_me"),
    path("reaction/<str:kind>/<int:pk>/", views.react, name="react"),
    path("transferer/<str:kind>/<int:pk>/", views.forward, name="forward"),
    # Temps réel (polling) + appels
    path("flux/<str:kind>/<int:pk>/", views.conv_poll, name="conv_poll"),
    path("ecrit/<str:kind>/<int:pk>/", views.typing_ping, name="typing_ping"),
    path("appel/entrant/", views.incoming_call, name="incoming_call"),
    path("appel/start/<str:kind>/<int:pk>/<str:mode>/", views.call_start, name="call_start"),
    path("appel/<int:call_id>/", views.call, name="call"),
    path("appel/<int:call_id>/fin/", views.call_end, name="call_end"),
    path("appel/<int:call_id>/refuser/", views.call_decline, name="call_decline"),
    path("appel/<int:call_id>/signal/", views.call_signal, name="call_signal"),
    path("epingler-message/<str:kind>/<int:pk>/", views.pin_message, name="pin_message"),
    path("epingler/<str:conv>/", views.pin_conversation, name="pin_conversation"),
    # Chat de groupe (placé avant <int:pk> pour éviter les collisions)
    path("discussions/", views.chat_list, name="chat"),
    path("discussions/nouveau-groupe/", views.group_create, name="group_create"),
    path("discussions/<int:pk>/", views.group_thread, name="group"),
    path("discussions/<int:pk>/parametres/", views.group_manage, name="group_manage"),
    path("discussions/<int:pk>/supprimer/", views.group_delete, name="group_delete"),
    path("discussions/<int:pk>/quitter/", views.group_leave, name="group_leave"),
    path("discussions/<int:pk>/membre/<int:user_pk>/retirer/", views.group_member_remove, name="group_member_remove"),
    path("discussions/message/<int:pk>/supprimer/", views.group_message_delete, name="group_message_delete"),
    path("<int:pk>/", views.thread, name="thread"),
    path("<int:pk>/supprimer/", views.thread_delete, name="thread_delete"),
]
