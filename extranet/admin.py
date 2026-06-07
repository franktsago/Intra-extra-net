from django.contrib import admin

from .models import (
    ClientRequest, Creative, CreativeComment, CreativeVersion,
    ExtranetMessage, Project, ProjectFile, Ticket, TicketReply,
)


class ProjectFileInline(admin.TabularInline):
    model = ProjectFile
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "reference", "client", "internal_lead", "status", "progress")
    list_filter = ("status",)
    search_fields = ("name", "reference")
    inlines = [ProjectFileInline]


admin.site.register(ExtranetMessage)


class TicketReplyInline(admin.TabularInline):
    model = TicketReply
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "subject", "client", "kind", "status", "assigned_to", "created_at")
    list_filter = ("status", "kind")
    search_fields = ("reference", "subject", "description")
    inlines = [TicketReplyInline]


@admin.register(ClientRequest)
class ClientRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "client", "kind", "status", "budget", "created_at")
    list_filter = ("status", "kind")
    search_fields = ("title", "details")


class CreativeVersionInline(admin.TabularInline):
    model = CreativeVersion
    extra = 0


@admin.register(Creative)
class CreativeAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "status", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("title",)
    inlines = [CreativeVersionInline]


admin.site.register(CreativeComment)
