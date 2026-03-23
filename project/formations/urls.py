from django.urls import path
from . import views

app_name = "formations"

urlpatterns = [
    # Category
    path("categories/", views.category_list, name="category_list"),
    path("categories/create/", views.category_create, name="category_create"),
    path("categories/<int:pk>/edit/", views.category_edit, name="category_edit"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    # Formation
    path("formations/", views.formation_list, name="formation_list"),
    path("formations/create/", views.formation_create, name="formation_create"),
    path("formations/<int:pk>/", views.formation_detail, name="formation_detail"),
    path("formations/<int:pk>/edit/", views.formation_edit, name="formation_edit"),
    path(
        "formations/<int:pk>/delete/", views.formation_delete, name="formation_delete"
    ),
    # Session
    path("sessions/", views.session_list, name="session_list"),
    path("sessions/create/", views.session_create, name="session_create"),
    path("sessions/<int:pk>/", views.session_detail, name="session_detail"),
    path("sessions/<int:pk>/edit/", views.session_edit, name="session_edit"),
    path("sessions/<int:pk>/status/", views.session_status, name="session_status"),
    path(
        "sessions/<int:pk>/attendance/",
        views.session_attendance,
        name="session_attendance",
    ),
    path("sessions/<int:pk>/scores/", views.session_scores, name="session_scores"),
    path("sessions/<int:pk>/delete/", views.session_delete, name="session_delete"),
    # Fill rate + cross-session participants
    path("fill-rate/", views.fill_rate, name="fill_rate"),
    path("participants/", views.participant_list, name="participant_list"),
    # Participant CRUD
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
        "participants/<int:pk>/edit/", views.participant_edit, name="participant_edit"
    ),
    path(
        "participants/<int:pk>/delete/",
        views.participant_delete,
        name="participant_delete",
    ),
    # AJAX
    path(
        "participants/<int:pk>/toggle-attendance/",
        views.toggle_attendance,
        name="toggle_attendance",
    ),
    path(
        "participants/<int:pk>/update-score/", views.update_score, name="update_score"
    ),
]
