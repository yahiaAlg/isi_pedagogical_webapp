from django.contrib import admin
from .models import Client

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ['name', 'name_ar', 'city', 'contact_person', 'phone', 'is_active']
    list_filter = ['is_active', 'city']
    search_fields = ['name', 'name_ar', 'contact_person']
    fieldsets = (
        ('Informations générales', {
            'fields': ('name', 'name_ar', 'address', 'city', 'phone', 'email', 'contact_person')
        }),
        ('Informations légales', {
            'fields': ('nif', 'nis', 'rc')
        }),
        ('Statut', {
            'fields': ('is_active',)
        }),
    )
    readonly_fields = []