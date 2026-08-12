from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import InstituteInfo, PVDefaultSignatory
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