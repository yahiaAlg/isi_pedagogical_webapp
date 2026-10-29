from django.urls import path

from . import views

app_name = "sync"

urlpatterns = [
    path("", views.status, name="status"),
    path("run/", views.run_now, name="run"),
    path("retry/", views.retry_failed, name="retry"),
    path("import-existing/", views.import_existing, name="import_existing"),
    path("session/<int:session_pk>/import/", views.import_into_session, name="import_into_session"),
]
