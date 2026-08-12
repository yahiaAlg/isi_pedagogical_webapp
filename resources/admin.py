from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Room, Trainer, Local, Equipment, EquipmentAllocation
from .resources import EquipmentResource, LocalResource, RoomResource, TrainerResource


@admin.register(EquipmentAllocation)
class EquipmentAllocationAdmin(admin.ModelAdmin):
    list_display = ["equipment", "room", "session", "allocated_at", "released_at"]
    list_filter = ["room"]
    search_fields = ["equipment__name", "room__name"]


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [RoomResource]
    list_display = ["name", "capacity", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Local)
class LocalAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [LocalResource]
    list_display = ["name", "local_type", "is_active"]
    list_filter = ["local_type", "is_active"]
    search_fields = ["name", "address"]


@admin.register(Equipment)
class EquipmentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [EquipmentResource]
    list_display = ["name", "category", "status", "quantity", "room", "local"]
    list_filter = ["category", "status"]
    search_fields = ["name", "inventory_code"]


@admin.register(Trainer)
class TrainerAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    resource_classes = [TrainerResource]
    list_display = ["full_name", "specialty", "employment_type", "phone", "is_active"]
    list_filter = ["employment_type", "is_active"]
    search_fields = [
        "first_name",
        "last_name",
        "first_name_ar",
        "last_name_ar",
        "specialty",
    ]
    filter_horizontal = ["qualifications"]  # M2M widget
    fieldsets = (
        (
            "Informations personnelles",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "first_name_ar",
                    "last_name_ar",
                )
            },
        ),
        (
            "Informations professionnelles",
            {"fields": ("specialty", "professional_address", "employment_type")},
        ),
        ("Formations qualifiées", {"fields": ("qualifications",)}),
        ("Contact", {"fields": ("phone", "email")}),
        ("Statut", {"fields": ("is_active",)}),
    )
