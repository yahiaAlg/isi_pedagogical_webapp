from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Category, Formation, Session, Participant


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "color"]
    search_fields = ["name"]


@admin.register(Formation)
class FormationAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "title",
        "title_ar",
        "category",
        "duration_days",
        "duration_hours",
        "max_participants",
        "evaluation_type",
        "is_active",
    ]
    list_filter = ["category", "evaluation_type", "is_active", "produces_certificate"]
    search_fields = ["title", "title_ar", "code"]
    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Informations générales",
            {"fields": ("title", "title_ar", "code", "category", "description")},
        ),
        (
            "Configuration",
            {
                "fields": (
                    "duration_days",
                    "duration_hours",
                    "min_participants",
                    "max_participants",
                    "base_price",
                    "evaluation_type",
                    "passing_score",
                    "produces_certificate",
                )
            },
        ),
        ("Références légales", {"fields": ("accreditation_body", "legal_references")}),
        ("Statut", {"fields": ("is_active",)}),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.session_set.exists():
            readonly.extend(["code", "evaluation_type"])
        return readonly


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    # 'result' is a model @property — reference the admin callable 'get_result' instead
    readonly_fields = ["certificate_number", "certificate_issued", "get_result"]
    fields = [
        "first_name",
        "last_name",
        "first_name_ar",
        "last_name_ar",
        "job_title",
        "attended",
        "score_theory",
        "score_practice",
        "get_result",
    ]

    def get_result(self, obj):
        if obj.pk:
            result = obj.result
            colors = {
                "passed": "green",
                "failed": "red",
                "absent": "gray",
                "pending": "orange",
            }
            return format_html(
                '<span style="color: {};">{}</span>',
                colors.get(result, "black"),
                result.title(),
            )
        return "-"

    get_result.short_description = "Résultat"


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "formation",
        "client",
        "trainer",
        "date_start",
        "date_end",
        "get_participant_count",
        "get_fill_rate",
        "status",
    ]
    list_filter = ["status", "formation", "date_start", "location_type"]
    search_fields = [
        "reference",
        "formation__title",
        "client__name",
        "trainer__last_name",
    ]
    # Use admin callable names, not model @property names
    readonly_fields = [
        "reference",
        "get_participant_count",
        "get_fill_rate",
        "created_at",
        "updated_at",
    ]
    inlines = [ParticipantInline]

    fieldsets = (
        (
            "Formation",
            {"fields": ("formation", "reference", "specialty_code", "session_number")},
        ),
        (
            "Planification",
            {"fields": ("date_start", "date_end", "client", "trainer", "capacity")},
        ),
        ("Lieu", {"fields": ("location_type", "room", "external_location")}),
        ("Statut", {"fields": ("status", "cancellation_reason")}),
        ("Comité", {"fields": ("committee_members",)}),
        (
            "Statistiques",
            {
                "fields": ("get_participant_count", "get_fill_rate"),
                "classes": ("collapse",),
            },
        ),
    )

    def get_participant_count(self, obj):
        return obj.participant_count

    get_participant_count.short_description = "Participants"

    def get_fill_rate(self, obj):
        rate = obj.fill_rate
        color = "green" if rate >= 90 else "orange" if rate >= 60 else "red"
        return format_html('<span style="color: {};">{:.1f}%</span>', color, rate)

    get_fill_rate.short_description = "Taux remplissage"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.status in ["archived", "cancelled"]:
            readonly.extend(
                [
                    "formation",
                    "client",
                    "trainer",
                    "date_start",
                    "date_end",
                    "location_type",
                    "room",
                    "external_location",
                    "capacity",
                ]
            )
        return readonly


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = [
        "full_name",
        "full_name_ar",
        "session",
        "job_title",
        "attended",
        "score_theory",
        "score_practice",
        "get_result",
        "certificate_issued",
    ]
    list_filter = [
        "attended",
        "certificate_issued",
        "session__formation",
        "session__status",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "first_name_ar",
        "last_name_ar",
        "session__reference",
        "employer",
    ]
    # Use admin callable name 'get_result', not model @property 'result'
    readonly_fields = [
        "certificate_number",
        "certificate_issued",
        "get_result",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "session",
                    "first_name",
                    "last_name",
                    "first_name_ar",
                    "last_name_ar",
                )
            },
        ),
        (
            "Informations personnelles",
            {"fields": ("date_of_birth", "place_of_birth", "place_of_birth_ar")},
        ),
        (
            "Informations professionnelles",
            {"fields": ("job_title", "employer", "employer_client")},
        ),
        ("Contact", {"fields": ("phone", "email")}),
        (
            "Évaluation",
            {
                "fields": (
                    "attended",
                    "attendance_per_day",
                    "score_theory",
                    "score_practice",
                    "get_result",
                )
            },
        ),
        ("Certification", {"fields": ("certificate_number", "certificate_issued")}),
        ("Notes", {"fields": ("notes",)}),
    )

    def get_result(self, obj):
        result = obj.result
        colors = {
            "passed": "green",
            "failed": "red",
            "absent": "gray",
            "pending": "orange",
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(result, "black"),
            result.title(),
        )

    get_result.short_description = "Résultat"

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.session.status in ["archived", "cancelled"]:
            readonly.extend(
                [
                    "first_name",
                    "last_name",
                    "first_name_ar",
                    "last_name_ar",
                    "date_of_birth",
                    "place_of_birth",
                    "place_of_birth_ar",
                    "job_title",
                    "employer",
                    "employer_client",
                    "attended",
                    "score_theory",
                    "score_practice",
                ]
            )
        return readonly
