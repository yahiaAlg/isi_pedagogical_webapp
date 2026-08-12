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

# Media files (institute logo, etc.) must be served regardless of DEBUG:
# this project has no separate media host / nginx alias for MEDIA_ROOT, so
# without this the uploaded logo 404s in production and never shows up on
# the printed documents (PV, attestations, ...), even though the upload
# itself succeeds and InstituteInfo.logo.url is correct.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
