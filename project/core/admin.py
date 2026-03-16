from django.contrib import admin
from .models import InstituteInfo

@admin.register(InstituteInfo)
class InstituteInfoAdmin(admin.ModelAdmin):
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
    )
    
    def has_add_permission(self, request):
        return not InstituteInfo.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False