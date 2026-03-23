from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count

from .models import Trainer, Room
from .forms import TrainerForm, RoomForm

# 'sessions_total' avoids clash with @property session_count on Trainer model
TRAINER_SORT_MAP = {
    "last_name": "last_name",
    "specialty": "specialty",
    "employment_type": "employment_type",
    "session_count": "sessions_total",
    "is_active": "is_active",
}
ROOM_SORT = {"name": "name", "capacity": "capacity", "is_active": "is_active"}


@login_required
def trainer_list(request):
    sort = request.GET.get("sort", "last_name")
    dir_ = request.GET.get("dir", "asc")
    if sort not in TRAINER_SORT_MAP:
        sort = "last_name"
    db_field = TRAINER_SORT_MAP[sort]
    qs = Trainer.objects.filter(is_active=True).annotate(
        sessions_total=Count("session")
    )
    qs = qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "resources/trainer_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
        },
    )


@login_required
def trainer_detail(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    sessions = trainer.session_set.all().order_by("-date_start")[:10]
    return render(
        request,
        "resources/trainer_detail.html",
        {"trainer": trainer, "sessions": sessions},
    )


@login_required
def trainer_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:trainer_list")
    if request.method == "POST":
        form = TrainerForm(request.POST)
        if form.is_valid():
            trainer = form.save()
            messages.success(
                request, f'Formateur "{trainer.full_name}" créé avec succès.'
            )
            return redirect("resources:trainer_detail", pk=trainer.pk)
    else:
        form = TrainerForm()
    return render(
        request,
        "resources/trainer_form.html",
        {"form": form, "title": "Nouveau formateur"},
    )


@login_required
def trainer_edit(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:trainer_detail", pk=trainer.pk)
    if request.method == "POST":
        form = TrainerForm(request.POST, instance=trainer)
        if form.is_valid():
            trainer = form.save()
            messages.success(
                request, f'Formateur "{trainer.full_name}" modifié avec succès.'
            )
            return redirect("resources:trainer_detail", pk=trainer.pk)
    else:
        form = TrainerForm(instance=trainer)
    return render(
        request,
        "resources/trainer_form.html",
        {"form": form, "trainer": trainer, "title": "Modifier formateur"},
    )


@login_required
def trainer_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("resources:trainer_list")
    trainer = get_object_or_404(Trainer, pk=pk)
    if request.method == "POST":
        name = trainer.full_name
        trainer.delete()
        messages.success(request, f'Formateur "{name}" supprimé.')
    return redirect("resources:trainer_list")


@login_required
def room_list(request):
    sort_key = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort_key not in ROOM_SORT:
        sort_key = "name"
    db_field = ROOM_SORT[sort_key]
    rooms = Room.objects.filter(is_active=True).order_by(
        db_field if dir_ == "asc" else "-" + db_field
    )
    return render(
        request,
        "resources/room_list.html",
        {"rooms": list(rooms), "sort": sort_key, "dir": dir_},
    )


@login_required
def room_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:room_list")
    if request.method == "POST":
        form = RoomForm(request.POST)
        if form.is_valid():
            room = form.save()
            messages.success(request, f'Salle "{room.name}" créée avec succès.')
            return redirect("resources:room_list")
    else:
        form = RoomForm()
    return render(
        request, "resources/room_form.html", {"form": form, "title": "Nouvelle salle"}
    )


@login_required
def room_edit(request, pk):
    room = get_object_or_404(Room, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:room_list")
    if request.method == "POST":
        form = RoomForm(request.POST, instance=room)
        if form.is_valid():
            room = form.save()
            messages.success(request, f'Salle "{room.name}" modifiée avec succès.')
            return redirect("resources:room_list")
    else:
        form = RoomForm(instance=room)
    return render(
        request,
        "resources/room_form.html",
        {"form": form, "room": room, "title": "Modifier salle"},
    )


@login_required
def room_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("resources:room_list")
    room = get_object_or_404(Room, pk=pk)
    if request.method == "POST":
        name = room.name
        room.delete()
        messages.success(request, f'Salle "{name}" supprimée.')
    return redirect("resources:room_list")
