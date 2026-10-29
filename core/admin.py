from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import InstituteInfo, PVDefaultSignatory, SequenceCounter
from .resources import InstituteInfoResource, PVDefaultSignatoryResource

@admin.register(InstituteInfo)
class InstituteInfoAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [InstituteInfoResource]
    fieldsets = (
        ('Informations générales', {
            'fields': ('name_fr', 'name_ar', 'logo', 'address', 'phone', 'email')
        }),
        ('Informations légales', {
            'fields': ('nif', 'nis', 'rc', 'article_imposition', 'rib')
        }),
        ('Agrément', {
            'fields': ('accreditation_number', 'accreditation_date', 'if_number')
        }),
        ('Pied de page', {
            'fields': ('footer_fr', 'footer_ar')
        }),
        ('Notifications', {
            'fields': ('pv_notification_recipients',)
        }),
    )
    
    def has_add_permission(self, request):
        return not InstituteInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PVDefaultSignatory)
class PVDefaultSignatoryAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [PVDefaultSignatoryResource]
    list_display = ("full_name", "role", "order", "is_active")
    list_editable = ("order", "is_active")
    ordering = ("order", "id")


@admin.register(SequenceCounter)
class SequenceCounterAdmin(admin.ModelAdmin):
    """
    Fallback/superuser view of the same counters editable from
    Paramètres → Numérotation des documents. Editing `last_value` here
    has the same effect: the next call to SequenceCounter.next_value()
    for this (kind, period_key) increments from whatever is saved.
    """

    list_display = ("kind", "period_key", "last_value", "updated_at")
    list_filter = ("kind",)
    list_editable = ("last_value",)
    ordering = ("kind", "-period_key")
    search_fields = ("period_key",)
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Rows are created automatically by next_value()/the Paramètres
        # page as needed; manual ad-hoc rows would just create dead
        # counters that no allocator ever reads from.
        return False