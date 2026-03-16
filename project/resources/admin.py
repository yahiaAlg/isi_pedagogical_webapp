from django.contrib import admin
from .models import Room, Trainer


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ["name", "capacity", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name"]


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
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
