from django.contrib import admin

from .models import Phase, Project, ProjectMedia


class PhaseInline(admin.TabularInline):
    model = Phase
    extra = 0


class MediaInline(admin.TabularInline):
    model = ProjectMedia
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "client", "manager", "status", "progress")
    list_filter = ("kind", "status")
    search_fields = ("name", "code", "client__name")
    autocomplete_fields = ("client", "manager")
    filter_horizontal = ("team",)
    inlines = [PhaseInline, MediaInline]
