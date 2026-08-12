from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path(
        "settings/committee-members/save/",
        views.committee_member_add,
        name="committee_member_add",
    ),
    path(
        "settings/committee-members/<int:pk>/delete/",
        views.committee_member_delete,
        name="committee_member_delete",
    ),
    # Spec §11.6 — public QR verification landing page (no login required)
    path("verify/<int:token>/", views.verify_attestation, name="verify_attestation"),
]
