from django.contrib import admin

from .models import RemoteClient, RosterEntry, SyncJob


@admin.register(SyncJob)
class SyncJobAdmin(admin.ModelAdmin):
    list_display = ("kind", "object_id", "status", "attempts", "updated_at", "last_error")
    list_filter = ("status", "kind")
    actions = ["retry"]

    @admin.action(description="Remettre en attente (réessayer)")
    def retry(self, request, queryset):
        queryset.update(status=SyncJob.PENDING, attempts=0)


@admin.register(RosterEntry)
class RosterEntryAdmin(admin.ModelAdmin):
    list_display = ("display_name", "client", "offering_title", "enrollment_status", "participant", "note")
    list_filter = ("enrollment_status",)
    search_fields = ("first_name", "last_name", "first_name_ar", "last_name_ar", "client__name")
    raw_id_fields = ("client", "formation", "participant")


@admin.register(RemoteClient)
class RemoteClientAdmin(admin.ModelAdmin):
    list_display = ("ext_id", "client", "is_individual", "created_client", "synced_at")
    raw_id_fields = ("client",)
