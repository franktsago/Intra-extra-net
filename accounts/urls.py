from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("connexion/", views.LPMLoginView.as_view(), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),

    # Récupération de mot de passe
    path("mot-de-passe/oublie/", views.LPMPasswordResetView.as_view(), name="password_reset"),
    path("mot-de-passe/envoye/",
         auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
         name="password_reset_done"),
    path("mot-de-passe/reinitialiser/<uidb64>/<token>/",
         views.LPMPasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("mot-de-passe/termine/",
         auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
         name="password_reset_complete"),
    path("mot-de-passe/changer/", views.password_change, name="password_change"),

    # Profil
    path("profil/", views.profile, name="profile"),
    path("changer-role/<str:role>/", views.switch_role, name="switch_role"),

    # Gestion des utilisateurs (Admin / RH)
    path("utilisateurs/", views.user_list, name="user_list"),
    path("utilisateurs/nouveau/", views.user_create, name="user_create"),
    path("utilisateurs/<int:pk>/modifier/", views.user_edit, name="user_edit"),
    path("utilisateurs/<int:pk>/supprimer/", views.user_delete, name="user_delete"),
    path("journal/", views.activity_log, name="activity_log"),
]
