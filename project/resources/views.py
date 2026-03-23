from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator

from .models import Trainer, Room
from .forms import TrainerForm, RoomForm


# ---------------------------------------------------------------------------
# Trainer views
# ---------------------------------------------------------------------------


@login_required
def trainer_list(request):
    trainers = Trainer.objects.filter(is_active=True).order_by("last_name")
    paginator = Paginator(trainers, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "resources/trainer_list.html", {"page_obj": page_obj})


@login_required
def trainer_detail(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    sessions = trainer.session_set.all().order_by("-date_start")[:10]
    return render(
        request,
        "resources/trainer_detail.html",
        {
            "trainer": trainer,
            "sessions": sessions,
        },
    )


@login_required
def trainer_create(request):
    # spec §9.2 — "Manage trainer directory: Admin only"
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
        {
            "form": form,
            "title": "Nouveau formateur",
        },
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
        {
            "form": form,
            "trainer": trainer,
            "title": "Modifier formateur",
        },
    )


# ---------------------------------------------------------------------------
# Room views
# ---------------------------------------------------------------------------


@login_required
def room_list(request):
    rooms = Room.objects.filter(is_active=True).order_by("name")
    return render(request, "resources/room_list.html", {"rooms": rooms})


@login_required
def room_create(request):
    # spec §9.2 — room management is part of "System settings / Manage trainer directory"
    # restricted to Admin
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
        request,
        "resources/room_form.html",
        {
            "form": form,
            "title": "Nouvelle salle",
        },
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
        {
            "form": form,
            "room": room,
            "title": "Modifier salle",
        },
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
