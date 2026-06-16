from django.contrib import admin
from .models import (
    BorrowRequest, MaintenanceItem, PostEventReconciliation,
    PurchaseOrder, StockItem, StockMovement, StockSupplier,
)

@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ["mat_id", "name", "category", "status", "quantity", "location"]
    list_filter = ["category", "status"]
    search_fields = ["mat_id", "name", "serial_number", "brand_model"]

@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ["mvt_reference", "item", "kind", "quantity", "performed_at", "movement_status"]
    list_filter = ["kind", "movement_status"]

@admin.register(PostEventReconciliation)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display = ["event_name", "event_date", "item", "qty_out", "qty_returned", "return_state"]

@admin.register(MaintenanceItem)
class MaintenanceAdmin(admin.ModelAdmin):
    list_display = ["item", "status", "recommended_action", "detected_at", "estimated_cost"]
    list_filter = ["status", "recommended_action"]

admin.site.register(StockSupplier)
admin.site.register(BorrowRequest)
admin.site.register(PurchaseOrder)
