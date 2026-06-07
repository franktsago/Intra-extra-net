from django.contrib import admin

from .models import Document, DocumentCategory


@admin.register(DocumentCategory)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "visibility", "is_archived", "download_count", "created_at")
    list_filter = ("visibility", "is_archived", "category")
    search_fields = ("title", "description")
