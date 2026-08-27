from django.urls import path
from . import views

app_name = "formations"

urlpatterns = [
    # ── Category ──────────────────────────────────────────────────────────
    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    # ── Branch (§2.0a) ───────────────────────────────────────────────────────
    path("branches/", views.branch_list, name="branch_list"),
    path("branches/create/", views.branch_create, name="branch_create"),
    path("branches/<int:pk>/edit/", views.branch_edit, name="branch_edit"),
    path("branches/<int:pk>/delete/", views.branch_delete, name="branch_delete"),
    # ── Specialty (§2.0b) ────────────────────────────────────────────────────
    path("specialties/", views.specialty_list, name="specialty_list"),
    path("specialties/create/", views.specialty_create, name="specialty_create"),
    path("specialties/<int:pk>/edit/", views.specialty_edit, name="specialty_edit"),
    path(
        "specialties/<int:pk>/delete/",
        views.specialty_delete,
        name="specialty_delete",
    ),
    # ── Formation ─────────────────────────────────────────────────────────
    path("formations/", views.formation_list, name="formation_list"),
    path("formations/create/", views.formation_create, name="formation_create"),
    path("formations/<int:pk>/", views.formation_detail, name="formation_detail"),
    path("formations/<int:pk>/edit/", views.formation_edit, name="formation_edit"),
    path(
        "formations/<int:pk>/delete/", views.formation_delete, name="formation_delete"
    ),
    path(
        "formations/<int:pk>/clear-sessions/",
        views.formation_clear_sessions,
        name="formation_clear_sessions",
    ),
    # AJAX — session form pre-population
    path("api/formation/<int:pk>/", views.formation_api_detail, name="formation_api"),
    path(
        "api/session-reference-preview/",
        views.session_reference_preview_api,
        name="session_reference_preview_api",
    ),
    # ── Session ───────────────────────────────────────────────────────────
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/create/", views.session_create, name="session_create"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path(
        "sessions/<int:pk>/equipment/",
        views.session_equipment_update,
        name="session_equipment_update",
    ),
    path(
        "api/room/<int:pk>/equipment/",
        views.room_equipment_api,
        name="room_equipment_api",
    ),
    path(
        "api/trainer/<int:pk>/default-cost/",
        views.trainer_default_cost_api,
        name="trainer_default_cost_api",
    ),
    path(
        "sessions/<int:pk>/assets/deliver/",
        views.session_asset_deliver,
        name="session_asset_deliver",
    ),
    path(
        "sessions/<int:pk>/assets/return/",
        views.session_asset_return,
        name="session_asset_return",
    ),
    path("sessions/<int:pk>/status/", views.session_status, name="session_status"),
    path(
        "sessions/<int:pk>/trainer-payment/",
        views.session_trainer_payment,
        name="session_trainer_payment",
    ),
    path(
        "trainer-payments/<int:pk>/edit/",
        views.trainer_payment_edit,
        name="trainer_payment_edit",
    ),
    path(
        "sessions/<int:pk>/attendance/",
        views.session_attendance,
        name="session_attendance",
    ),
    path("sessions/<int:pk>/scores/", views.session_scores, name="session_scores"),
    path(
        "sessions/<int:pk>/exam-scores/",
        views.session_exam_scores,
        name="session_exam_scores",
    ),
    path(
        "sessions/<int:pk>/generate-group/",
        views.generate_session_group,
        name="generate_session_group",
    ),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    # ── Fill rate + cross-session participants ─────────────────────────────
    path("fill-rate/", views.fill_rate, name="fill_rate"),
    path("participants/", views.participant_list, name="participant_list"),
    # ── Participant CRUD ───────────────────────────────────────────────────
    path(
        "sessions/<int:session_pk>/participants/create/",
        views.participant_create,
        name="participant_create",
    ),
    path(
        "sessions/<int:session_pk>/participants/import/",
        views.participant_import,
        name="participant_import",
    ),
    path(
        "sessions/<int:session_pk>/participants/export/",
        views.participant_export,
        name="participant_export",
    ),
    path(
        "participants/<int:pk>/edit/", views.participant_edit, name="participant_edit"
    ),
    path(
        "participants/<int:pk>/delete/",
        views.participant_delete,
        name="participant_delete",
    ),
    # ── AJAX ───────────────────────────────────────────────────────────────
    path(
        "participants/<int:pk>/toggle-attendance/",
        views.toggle_attendance,
        name="toggle_attendance",
    ),
    path(
        "participants/<int:pk>/update-score/", views.update_score, name="update_score"
    ),
]
