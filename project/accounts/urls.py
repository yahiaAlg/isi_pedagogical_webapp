from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/password/", views.password_change_view, name="password_change"),
    path("users/", views.user_list, name="user_list"),
    path("users/create/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.profile_view, name="user_profile"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
    path(
        "users/<int:pk>/password/",
        views.password_change_view,
        name="user_password_change",
    ),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
]
