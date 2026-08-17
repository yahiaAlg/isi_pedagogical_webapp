from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    path(
        "settings/pv-signatories/",
        views.pv_signatory_list,
        name="pv_signatory_list",
    ),
    path(
        "settings/pv-signatories/add/",
        views.pv_signatory_form,
        name="pv_signatory_add",
    ),
    path(
        "settings/pv-signatories/<int:pk>/edit/",
        views.pv_signatory_form,
        name="pv_signatory_edit",
    ),
    path(
        "settings/pv-signatories/<int:pk>/delete/",
        views.pv_signatory_delete,
        name="pv_signatory_delete",
    ),
    path(
        "settings/sequences/",
        views.sequence_counter_list,
        name="sequence_counter_list",
    ),
    path(
        "settings/sequences/<int:pk>/edit/",
        views.sequence_counter_edit,
        name="sequence_counter_edit",
    ),
    path(
        "settings/sequences/<str:kind>/period/",
        views.sequence_counter_period,
        name="sequence_counter_period",
    ),
    path(
        "settings/sequences/<int:pk>/activate/",
        views.sequence_counter_activate,
        name="sequence_counter_activate",
    ),
    # Spec §11.6 — public QR verification landing page (no login required)
    path("verify/<int:token>/", views.verify_attestation, name="verify_attestation"),
]
