from django.urls import path
from . import views

app_name = "stock"

urlpatterns = [
    # Hub tabulé (onglet via ?s=inventaire|mouvements|recevt|maintenance|alertes)
    path("", views.stock_hub, name="hub"),

    # Articles
    path("article/nouveau/", views.item_edit, name="item_create"),
    path("article/<int:pk>/", views.item_detail, name="item_detail"),
    path("article/<int:pk>/modifier/", views.item_edit, name="item_edit"),
    path("article/<int:pk>/mouvement/", views.movement_add, name="movement_add"),
    path("article/<int:pk>/emprunter/", views.borrow_create, name="borrow_create"),

    # Réconciliation post-événement
    path("recevt/nouvelle/", views.reconciliation_create, name="reconciliation_create"),
    path("recevt/<int:pk>/modifier/", views.reconciliation_edit, name="reconciliation_edit"),
    path("recevt/<int:pk>/supprimer/", views.reconciliation_delete, name="reconciliation_delete"),

    # Maintenance
    path("maintenance/nouvelle/", views.maintenance_create, name="maintenance_create"),
    path("maintenance/<int:pk>/modifier/", views.maintenance_edit, name="maintenance_edit"),
    path("maintenance/<int:pk>/statut/", views.maintenance_resolve, name="maintenance_resolve"),

    # Emprunts
    path("emprunts/", views.borrow_list, name="borrow_list"),
    path("emprunt/<int:pk>/<str:action>/", views.borrow_decide, name="borrow_decide"),

    # Commandes
    path("commandes/", views.order_list, name="order_list"),
    path("commandes/nouvelle/", views.order_edit, name="order_create"),
    path("commandes/<int:pk>/modifier/", views.order_edit, name="order_edit"),
]
