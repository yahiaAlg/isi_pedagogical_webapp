from django.urls import path
from . import views

app_name = "resources"

urlpatterns = [
    path("trainers/", views.trainer_list, name="trainer_list"),
    path("trainers/create/", views.trainer_create, name="trainer_create"),
    path("trainers/<int:pk>/", views.trainer_detail, name="trainer_detail"),
    path("trainers/<int:pk>/edit/", views.trainer_edit, name="trainer_edit"),
    path("trainers/<int:pk>/delete/", views.trainer_delete, name="trainer_delete"),
    path("rooms/", views.room_list, name="room_list"),
    path("rooms/create/", views.room_create, name="room_create"),
    path("rooms/<int:pk>/edit/", views.room_edit, name="room_edit"),
    path("rooms/<int:pk>/delete/", views.room_delete, name="room_delete"),
]
