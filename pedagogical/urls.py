from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("clients/", include("clients.urls")),
    path("resources/", include("resources.urls")),
    path("formations/", include("formations.urls")),
    path("documents/", include("documents.urls")),
    path("reporting/", include("reporting.urls")),  # spec §18 — analytics app
    path("", include("core.urls")),
]

# NOTE: media (uploaded institute logo, generated documents, …) must be
# served in every environment, not just when DEBUG=True. WhiteNoise
# (configured for STATIC_URL) only serves files collected under
# STATIC_ROOT — it never serves MEDIA_ROOT — so without this, anything
# uploaded through Settings (e.g. the institute logo) 404s in production
# and silently fails to render on every print page that references
# `institute.logo.url`. This project is a small single-instance
# deployment, so serving media straight from Django is an acceptable
# trade-off; for very high traffic, front it with a dedicated
# static/media host or CDN instead.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
