from django.urls import path

from . import views

app_name = "approvals"

urlpatterns = [
    # Requests
    path("requests/", views.request_list, name="request_list"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/new/formation/", views.request_formation_create, name="request_formation_create"),
    path(
        "requests/formation/<int:formation_pk>/edit/",
        views.request_formation_edit,
        name="request_formation_edit",
    ),
    path("requests/<int:pk>/approve/", views.request_approve, name="request_approve"),
    path("requests/<int:pk>/reject/", views.request_reject, name="request_reject"),
    path("requests/<int:pk>/cancel/", views.request_cancel, name="request_cancel"),
    # Bell
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/feed/", views.notification_feed, name="notification_feed"),
    path("notifications/read-all/", views.notification_read_all, name="notification_read_all"),
    path("notifications/<int:pk>/open/", views.notification_open, name="notification_open"),
]
