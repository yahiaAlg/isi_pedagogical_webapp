from django.urls import path
from . import views

app_name = "resources"

urlpatterns = [
    # Trainer
    path("trainers/", views.trainer_list, name="trainer_list"),
    path("trainers/create/", views.trainer_create, name="trainer_create"),
    path("trainers/<int:pk>/", views.trainer_detail, name="trainer_detail"),
    path("trainers/<int:pk>/edit/", views.trainer_edit, name="trainer_edit"),
    # Room — full CRUD (admin-only write operations, spec §9.2)
    path("rooms/", views.room_list, name="room_list"),
    path("rooms/create/", views.room_create, name="room_create"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
]
