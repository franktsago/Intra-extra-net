from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from stock.models import (
    BorrowRequest, MaintenanceItem, PostEventReconciliation,
    StockItem, StockMovement, StockSupplier,
)


def _item(**kwargs):
    defaults = dict(
        name="Article test", category=StockItem.Category.IT,
        quantity=5, min_quantity=2, unit="unité",
        status=StockItem.Status.GOOD,
    )
    defaults.update(kwargs)
    return StockItem.objects.create(**defaults)


class StockAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        from employees.models import Department, Employee
        cls.mgr = User.objects.create_user("mgr_stock", password="x", role=Role.MANAGER)
        cls.emp = User.objects.create_user("emp_stock", password="x", role=Role.EMPLOYE)
        cls.ext = User.objects.create_user("ext_stock", password="x", role=Role.CLIENT)
        # Le responsable qui gère le magasin appartient au département Logistique.
        cls.dep_log = Department.objects.create(name="Logistique", code="LOG")
        Employee.objects.get(user=cls.mgr).departments.set([cls.dep_log])
        # Un responsable d'un autre département ne doit PAS pouvoir modifier le magasin.
        cls.mgr_other = User.objects.create_user("mgr_other_stock", password="x", role=Role.MANAGER)
        Employee.objects.get(user=cls.mgr_other).departments.set(
            [Department.objects.create(name="Marketing", code="MKT")])

    def test_item_create_403_pour_manager_hors_logistique(self):
        self.client.force_login(self.mgr_other)
        self.assertEqual(self.client.get(reverse("stock:item_create")).status_code, 403)

    # ---- Hub ----
    def test_hub_200_pour_interne(self):
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("stock:hub")).status_code, 200)

    def test_hub_redirige_externe(self):
        self.client.force_login(self.ext)
        self.assertEqual(self.client.get(reverse("stock:hub")).status_code, 302)

    # ---- Dashboard (managers seulement) ----
    def test_dashboard_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:hub") + "?s=dashboard").status_code, 200)

    def test_dashboard_200_pour_employe(self):
        # L'onglet est caché dans la sidebar mais la vue reste accessible (lecture seule)
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:hub") + "?s=dashboard").status_code, 200)

    # ---- Articles ----
    def test_item_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:item_create")).status_code, 403)

    def test_item_create_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:item_create")).status_code, 200)

    def test_item_detail_200_pour_interne(self):
        item = _item()
        for u in (self.emp, self.mgr):
            self.client.force_login(u)
            self.assertEqual(self.client.get(reverse("stock:item_detail", args=[item.pk])).status_code, 200)

    def test_item_edit_403_pour_employe(self):
        item = _item()
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:item_edit", args=[item.pk])).status_code, 403)

    # ---- Mouvements ----
    def test_movement_add_403_pour_employe(self):
        item = _item()
        self.client.force_login(self.emp)
        r = self.client.post(reverse("stock:movement_add", args=[item.pk]),
                             {"kind": "IN", "quantity": 1, "reason": "test"})
        self.assertEqual(r.status_code, 403)

    def test_movement_add_redirect_pour_manager(self):
        item = _item()
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("stock:movement_add", args=[item.pk]),
                             {"kind": "IN", "quantity": 3, "reason": "approvisionnement"})
        self.assertRedirects(r, reverse("stock:item_detail", args=[item.pk]))
        item.refresh_from_db()
        self.assertEqual(item.quantity, 8)  # 5 + 3

    # ---- Réconciliation post-événement ----
    def test_recevt_tab_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:hub") + "?s=recevt").status_code, 200)

    def test_reconciliation_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        r = self.client.post(reverse("stock:reconciliation_create"), {})
        self.assertEqual(r.status_code, 403)

    def test_reconciliation_create_pour_manager(self):
        item = _item()
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("stock:reconciliation_create"), {
            "event_name": "Gala test", "event_date": "2026-06-01",
            "item": item.pk, "qty_out": 2, "qty_returned": 2,
            "return_state": PostEventReconciliation.ReturnState.GOOD,
            "action": PostEventReconciliation.Action.OK,
        })
        self.assertRedirects(r, "/stock/?s=recevt")
        self.assertEqual(PostEventReconciliation.objects.count(), 1)

    def test_reconciliation_edit_403_pour_employe(self):
        item = _item()
        recon = PostEventReconciliation.objects.create(
            event_name="E", event_date=date.today(), item=item,
            qty_out=1, qty_returned=1, responsible=self.mgr)
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:reconciliation_edit", args=[recon.pk])).status_code, 403)

    def test_reconciliation_delete_pour_manager(self):
        item = _item()
        recon = PostEventReconciliation.objects.create(
            event_name="E", event_date=date.today(), item=item,
            qty_out=1, qty_returned=1, responsible=self.mgr)
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("stock:reconciliation_delete", args=[recon.pk]))
        self.assertRedirects(r, "/stock/?s=recevt")
        self.assertFalse(PostEventReconciliation.objects.filter(pk=recon.pk).exists())

    # ---- Maintenance ----
    def test_maintenance_tab_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:hub") + "?s=maintenance").status_code, 200)

    def test_maintenance_create_403_pour_employe(self):
        self.client.force_login(self.emp)
        r = self.client.post(reverse("stock:maintenance_create"), {})
        self.assertEqual(r.status_code, 403)

    def test_maintenance_create_pour_manager(self):
        item = _item()
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("stock:maintenance_create"), {
            "item": item.pk, "problem": "Panne test",
            "detected_at": "2026-06-01",
            "recommended_action": MaintenanceItem.RecommendedAction.DIAGNOSE,
            "status": MaintenanceItem.Status.PENDING,
        })
        self.assertRedirects(r, "/stock/?s=maintenance")
        self.assertEqual(MaintenanceItem.objects.count(), 1)

    def test_maintenance_resolve_pour_manager(self):
        item = _item()
        fiche = MaintenanceItem.objects.create(
            item=item, problem="Panne", detected_at=date.today(),
            responsible=self.mgr, status=MaintenanceItem.Status.PENDING)
        self.client.force_login(self.mgr)
        r = self.client.post(reverse("stock:maintenance_resolve", args=[fiche.pk]),
                             {"status": "RESOLVED"})
        self.assertRedirects(r, "/stock/?s=maintenance")
        fiche.refresh_from_db()
        self.assertEqual(fiche.status, MaintenanceItem.Status.RESOLVED)

    def test_maintenance_edit_403_pour_employe(self):
        item = _item()
        fiche = MaintenanceItem.objects.create(
            item=item, problem="Panne", detected_at=date.today(),
            responsible=self.mgr, status=MaintenanceItem.Status.PENDING)
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:maintenance_edit", args=[fiche.pk])).status_code, 403)

    # ---- Emprunts ----
    def test_borrow_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:borrow_list")).status_code, 200)

    def test_borrow_list_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:borrow_list")).status_code, 403)

    def test_borrow_create_pour_employe(self):
        item = _item()
        self.client.force_login(self.emp)
        r = self.client.post(reverse("stock:borrow_create", args=[item.pk]), {
            "item": item.pk, "quantity": 1, "purpose": "Test emprunt",
            "start_date": "2026-06-20", "end_date": "2026-06-22",
        })
        self.assertRedirects(r, reverse("stock:item_detail", args=[item.pk]))
        self.assertEqual(BorrowRequest.objects.count(), 1)
        self.assertEqual(BorrowRequest.objects.first().status, BorrowRequest.Status.PENDING)

    def test_borrow_decide_403_pour_employe(self):
        item = _item()
        br = BorrowRequest.objects.create(item=item, requested_by=self.emp, quantity=1)
        self.client.force_login(self.emp)
        r = self.client.post(reverse("stock:borrow_decide", args=[br.pk, "approve"]))
        self.assertEqual(r.status_code, 403)

    # ---- Commandes ----
    def test_order_list_200_pour_manager(self):
        self.client.force_login(self.mgr)
        self.assertEqual(self.client.get(reverse("stock:order_list")).status_code, 200)

    def test_order_list_403_pour_employe(self):
        self.client.force_login(self.emp)
        self.assertEqual(self.client.get(reverse("stock:order_list")).status_code, 403)

    def test_order_list_redirige_externe(self):
        self.client.force_login(self.ext)
        self.assertEqual(self.client.get(reverse("stock:order_list")).status_code, 302)


class StockModelTest(TestCase):
    def test_mat_id_auto_genere(self):
        item = _item()
        self.assertTrue(item.mat_id.startswith("MAT-"))

    def test_mvt_reference_auto_genere(self):
        item = _item()
        mv = StockMovement.objects.create(
            item=item, kind=StockMovement.Kind.IN, quantity=1,
            performed_by=User.objects.create_user("u_mvt", password="x", role=Role.MANAGER))
        self.assertTrue(mv.mvt_reference.startswith("MVT-"))

    def test_is_low_stock(self):
        item = _item(quantity=1, min_quantity=3)
        self.assertTrue(item.is_low_stock)
        item.quantity = 5
        self.assertFalse(item.is_low_stock)

    def test_reconciliation_discrepancy(self):
        item = _item()
        mgr = User.objects.create_user("u_rec", password="x", role=Role.MANAGER)
        r = PostEventReconciliation.objects.create(
            event_name="E", event_date=date.today(), item=item,
            qty_out=5, qty_returned=3, responsible=mgr)
        self.assertEqual(r.discrepancy, 2)

    def test_mat_id_unique_null(self):
        """Deux articles sans mat_id explicite recoivent des IDs distincts."""
        a = _item(name="A")
        b = _item(name="B")
        self.assertNotEqual(a.mat_id, b.mat_id)
