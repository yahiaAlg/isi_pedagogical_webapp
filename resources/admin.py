from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import Room, Trainer, Local, Equipment
from .resources import RoomResource, LocalResource, EquipmentResource, TrainerResource


@admin.register(Room)
class RoomAdmin(ImportExportModelAdmin):
    resource_class = RoomResource
    list_display = ["name", "capacity", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Local)
class LocalAdmin(ImportExportModelAdmin):
    resource_class = LocalResource
    list_display = ["name", "local_type", "is_active"]
    list_filter = ["local_type", "is_active"]
    search_fields = ["name", "address"]


@admin.register(Equipment)
class EquipmentAdmin(ImportExportModelAdmin):
    resource_class = EquipmentResource
    list_display = ["name", "category", "status", "quantity", "room", "local"]
    list_filter = ["category", "status"]
    search_fields = ["name", "inventory_code"]


@admin.register(Trainer)
class TrainerAdmin(ImportExportModelAdmin):
    resource_class = TrainerResource
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
