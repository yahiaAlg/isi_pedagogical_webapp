from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("settings/", views.settings_view, name="settings"),
    # Spec §11.6 — public QR verification landing page (no login required)
    path("verify/<int:token>/", views.verify_attestation, name="verify_attestation"),
]
