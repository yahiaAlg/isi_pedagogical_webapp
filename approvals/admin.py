from django.contrib import admin

from .models import ApprovalRequest, Notification


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("created_at", "requester", "kind", "status", "formation", "reviewed_by")
    list_filter = ("kind", "status")
    search_fields = ("requester__username", "proposed_title", "formation_label")
    date_hierarchy = "created_at"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "recipient", "kind", "title", "is_read")
    list_filter = ("kind", "is_read")
    search_fields = ("recipient__username", "title")
