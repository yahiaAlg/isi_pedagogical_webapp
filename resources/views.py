from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q

from .models import (
    Trainer,
    Room,
    Local,
    Equipment,
    EquipmentAllocation,
    AssetCategory,
    PedagogicalAsset,
)
from .forms import (
    TrainerForm,
    RoomForm,
    LocalForm,
    EquipmentForm,
    PedagogicalAssetForm,
    AssetRestockForm,
    AssetReturnForm,
)

# 'sessions_total' avoids clash with @property session_count on Trainer model
TRAINER_SORT_MAP = {
    "last_name": "last_name",
    "specialty": "specialty",
    "employment_type": "employment_type",
    "session_count": "sessions_total",
    "is_active": "is_active",
}
ROOM_SORT = {"name": "name", "capacity": "capacity", "is_active": "is_active"}
LOCAL_SORT = {"name": "name", "local_type": "local_type", "is_active": "is_active"}
EQUIPMENT_SORT = {"name": "name", "category": "category", "status": "status"}
ASSET_SORT = {
    "name": "name",
    "category": "category__name",
    "quantity_in_stock": "quantity_in_stock",
}


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

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(first_name_ar__icontains=q)
            | Q(last_name_ar__icontains=q)
            | Q(specialty__icontains=q)
            | Q(email__icontains=q)
            | Q(phone__icontains=q)
        )
    employment_type = request.GET.get("employment_type", "").strip()
    if employment_type:
        qs = qs.filter(employment_type=employment_type)
    sessions_min = request.GET.get("sessions_min", "").strip()
    if sessions_min.isdigit():
        qs = qs.filter(sessions_total__gte=int(sessions_min))
    sessions_max = request.GET.get("sessions_max", "").strip()
    if sessions_max.isdigit():
        qs = qs.filter(sessions_total__lte=int(sessions_max))

    qs = qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "resources/trainer_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
            "employment_choices": Trainer.EMPLOYMENT_CHOICES,
            "filters": {
                "q": q,
                "employment_type": employment_type,
                "sessions_min": sessions_min,
                "sessions_max": sessions_max,
            },
        },
    )


@login_required
def trainer_detail(request, pk):
    trainer = get_object_or_404(Trainer, pk=pk)
    sessions = trainer.session_set.all().order_by("-date_start")[:10]
    # Spec §new — full règlement (installment) history across all of this
    # trainer's session cycles, most recent first.
    from formations.models import TrainerPayment

    payments = (
        TrainerPayment.objects.filter(session__trainer=trainer)
        .select_related("session", "session__formation", "confirmed_by")
        .order_by("-paid_at")
    )
    # Spec §new — session cycles for this trainer that are terminated and
    # still owe a règlement, so we can offer a direct "add payment" shortcut
    # instead of leaving the payment history as a dead-end empty state.
    unpaid_sessions = [
        s
        for s in trainer.session_set.filter(
            is_primary=True, status__in=["completed", "archived"]
        )
        .select_related("formation")
        .order_by("-date_start")
        if s.trainer_cost is not None and s.trainer_payment_status != "paid"
    ]
    return render(
        request,
        "resources/trainer_detail.html",
        {
            "trainer": trainer,
            "sessions": sessions,
            "payments": payments,
            "unpaid_sessions": unpaid_sessions,
        },
    )


@login_required
def trainer_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:trainer_list")
    if request.method == "POST":
        form = TrainerForm(request.POST, request.FILES)
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
        form = TrainerForm(request.POST, request.FILES, instance=trainer)
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
    rooms = Room.objects.filter(is_active=True)

    q = request.GET.get("q", "").strip()
    if q:
        rooms = rooms.filter(Q(name__icontains=q) | Q(equipment_notes__icontains=q))
    capacity_min = request.GET.get("capacity_min", "").strip()
    if capacity_min.isdigit():
        rooms = rooms.filter(capacity__gte=int(capacity_min))
    capacity_max = request.GET.get("capacity_max", "").strip()
    if capacity_max.isdigit():
        rooms = rooms.filter(capacity__lte=int(capacity_max))

    rooms = rooms.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "resources/room_list.html",
        {
            "rooms": list(rooms),
            "sort": sort_key,
            "dir": dir_,
            "filters": {
                "q": q,
                "capacity_min": capacity_min,
                "capacity_max": capacity_max,
            },
        },
    )


def _apply_room_equipment(room, selected_qs, user):
    """Spec §new — sync `Equipment.room` from the RoomForm multi-select and
    log the change in `EquipmentAllocation` (home-room assignment, no
    session attached). Guardrail: an item actively allocated to a session
    elsewhere is skipped and reported back."""
    selected_ids = set(e.pk for e in selected_qs)
    currently_here = set(
        Equipment.objects.filter(room=room).values_list("pk", flat=True)
    )

    skipped = []
    for eq in Equipment.objects.filter(pk__in=(selected_ids - currently_here)):
        if eq.is_locked_elsewhere(room=room):
            skipped.append(eq.name)
            continue
        eq.room = room
        eq.local = None
        eq.save(update_fields=["room", "local"])
        EquipmentAllocation.objects.create(equipment=eq, room=room, allocated_by=user)

    for eq in Equipment.objects.filter(pk__in=(currently_here - selected_ids)):
        eq.room = None
        eq.save(update_fields=["room"])
        alloc = EquipmentAllocation.objects.filter(
            equipment=eq, room=room, session__isnull=True, released_at__isnull=True
        ).first()
        if alloc:
            alloc.release(by=user)
    return skipped


@login_required
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    equipment = room.equipment_set.all().order_by("name")
    history = EquipmentAllocation.objects.filter(room=room).select_related(
        "equipment", "session", "allocated_by", "released_by"
    )[:50]
    return render(
        request,
        "resources/room_detail.html",
        {"room": room, "equipment": equipment, "history": history},
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
            skipped = _apply_room_equipment(
                room, form.cleaned_data["equipment"], request.user
            )
            messages.success(request, f'Salle "{room.name}" créée avec succès.')
            if skipped:
                messages.warning(
                    request,
                    "Non ajoutés (alloués activement ailleurs) : " + ", ".join(skipped),
                )
            return redirect("resources:room_list")
        selected_equipment_ids = {
            e.pk for e in form.cleaned_data.get("equipment") or []
        }
    else:
        form = RoomForm()
        selected_equipment_ids = set()
    return render(
        request,
        "resources/room_form.html",
        {
            "form": form,
            "title": "Nouvelle salle",
            "selected_equipment_ids": selected_equipment_ids,
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
            skipped = _apply_room_equipment(
                room, form.cleaned_data["equipment"], request.user
            )
            messages.success(request, f'Salle "{room.name}" modifiée avec succès.')
            if skipped:
                messages.warning(
                    request,
                    "Non ajoutés (alloués activement ailleurs) : " + ", ".join(skipped),
                )
            return redirect("resources:room_list")
        selected_equipment_ids = {
            e.pk for e in form.cleaned_data.get("equipment") or []
        }
    else:
        form = RoomForm(instance=room)
        selected_equipment_ids = set(
            Equipment.objects.filter(room=room).values_list("pk", flat=True)
        )
    return render(
        request,
        "resources/room_form.html",
        {
            "form": form,
            "room": room,
            "title": "Modifier salle",
            "selected_equipment_ids": selected_equipment_ids,
        },
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


# ---------------------------------------------------------------------------
# Local (facility / premises) — spec §5.7 / §2.6b
# ---------------------------------------------------------------------------


@login_required
def local_list(request):
    sort_key = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort_key not in LOCAL_SORT:
        sort_key = "name"
    db_field = LOCAL_SORT[sort_key]
    locals_ = Local.objects.all()

    q = request.GET.get("q", "").strip()
    if q:
        locals_ = locals_.filter(
            Q(name__icontains=q) | Q(address__icontains=q) | Q(description__icontains=q)
        )
    local_type = request.GET.get("local_type", "").strip()
    if local_type:
        locals_ = locals_.filter(local_type=local_type)

    locals_ = locals_.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "resources/local_list.html",
        {
            "locals": list(locals_),
            "sort": sort_key,
            "dir": dir_,
            "local_type_choices": Local.LOCAL_TYPE_CHOICES,
            "filters": {"q": q, "local_type": local_type},
        },
    )


@login_required
def local_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:local_list")
    if request.method == "POST":
        form = LocalForm(request.POST)
        if form.is_valid():
            local = form.save()
            messages.success(request, f'Local "{local.name}" créé avec succès.')
            return redirect("resources:local_list")
    else:
        form = LocalForm()
    return render(
        request, "resources/local_form.html", {"form": form, "title": "Nouveau local"}
    )


@login_required
def local_edit(request, pk):
    local = get_object_or_404(Local, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:local_list")
    if request.method == "POST":
        form = LocalForm(request.POST, instance=local)
        if form.is_valid():
            local = form.save()
            messages.success(request, f'Local "{local.name}" modifié avec succès.')
            return redirect("resources:local_list")
    else:
        form = LocalForm(instance=local)
    return render(
        request,
        "resources/local_form.html",
        {"form": form, "local": local, "title": "Modifier local"},
    )


@login_required
def local_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("resources:local_list")
    local = get_object_or_404(Local, pk=pk)
    if request.method == "POST":
        name = local.name
        local.delete()
        messages.success(request, f'Local "{name}" supprimé.')
    return redirect("resources:local_list")


# ---------------------------------------------------------------------------
# Equipment — spec §5.7 / §2.6c
# ---------------------------------------------------------------------------


@login_required
def equipment_list(request):
    sort_key = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort_key not in EQUIPMENT_SORT:
        sort_key = "name"
    db_field = EQUIPMENT_SORT[sort_key]
    equipment_qs = Equipment.objects.select_related("room", "local")

    q = request.GET.get("q", "").strip()
    if q:
        equipment_qs = equipment_qs.filter(
            Q(name__icontains=q)
            | Q(inventory_code__icontains=q)
            | Q(notes__icontains=q)
        )
    category = request.GET.get("category", "").strip()
    if category:
        equipment_qs = equipment_qs.filter(category=category)
    status = request.GET.get("status", "").strip()
    if status:
        equipment_qs = equipment_qs.filter(status=status)
    quantity_min = request.GET.get("quantity_min", "").strip()
    if quantity_min.isdigit():
        equipment_qs = equipment_qs.filter(quantity__gte=int(quantity_min))
    quantity_max = request.GET.get("quantity_max", "").strip()
    if quantity_max.isdigit():
        equipment_qs = equipment_qs.filter(quantity__lte=int(quantity_max))
    acq_from = request.GET.get("acq_from", "").strip()
    if acq_from:
        equipment_qs = equipment_qs.filter(acquisition_date__gte=acq_from)
    acq_to = request.GET.get("acq_to", "").strip()
    if acq_to:
        equipment_qs = equipment_qs.filter(acquisition_date__lte=acq_to)

    equipment_qs = equipment_qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "resources/equipment_list.html",
        {
            "equipment_list": list(equipment_qs),
            "sort": sort_key,
            "dir": dir_,
            "category_choices": Equipment.CATEGORY_CHOICES,
            "status_choices": Equipment.STATUS_CHOICES,
            "filters": {
                "q": q,
                "category": category,
                "status": status,
                "quantity_min": quantity_min,
                "quantity_max": quantity_max,
                "acq_from": acq_from,
                "acq_to": acq_to,
            },
        },
    )


@login_required
def equipment_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:equipment_list")
    if request.method == "POST":
        form = EquipmentForm(request.POST)
        if form.is_valid():
            equipment = form.save()
            messages.success(
                request, f'Équipement "{equipment.name}" créé avec succès.'
            )
            return redirect("resources:equipment_list")
    else:
        form = EquipmentForm()
    return render(
        request,
        "resources/equipment_form.html",
        {"form": form, "title": "Nouvel équipement"},
    )


@login_required
def equipment_edit(request, pk):
    equipment = get_object_or_404(Equipment, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:equipment_list")
    if request.method == "POST":
        form = EquipmentForm(request.POST, instance=equipment)
        if form.is_valid():
            equipment = form.save()
            messages.success(
                request, f'Équipement "{equipment.name}" modifié avec succès.'
            )
            return redirect("resources:equipment_list")
    else:
        form = EquipmentForm(instance=equipment)
    return render(
        request,
        "resources/equipment_form.html",
        {"form": form, "equipment": equipment, "title": "Modifier équipement"},
    )


@login_required
def equipment_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("resources:equipment_list")
    equipment = get_object_or_404(Equipment, pk=pk)
    if request.method == "POST":
        name = equipment.name
        equipment.delete()
        messages.success(request, f'Équipement "{name}" supprimé.')
    return redirect("resources:equipment_list")


# ---------------------------------------------------------------------------
# Pedagogical assets — spec §new (consumable IT/office/other supplies,
# refilled via `restock` and depleted via `deliver` — tracked in
# `AssetMovement`, mirroring the `EquipmentAllocation` audit-trail pattern
# used for reusable equipment).
# ---------------------------------------------------------------------------


@login_required
def asset_list(request):
    sort_key = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort_key not in ASSET_SORT:
        sort_key = "name"
    db_field = ASSET_SORT[sort_key]
    assets = PedagogicalAsset.objects.select_related("category").filter(is_active=True)

    q = request.GET.get("q", "").strip()
    if q:
        assets = assets.filter(
            Q(name__icontains=q) | Q(reference__icontains=q) | Q(notes__icontains=q)
        )
    category = request.GET.get("category", "").strip()
    if category.isdigit():
        assets = assets.filter(category_id=int(category))
    stock_state = request.GET.get("stock_state", "").strip()
    if stock_state == "exhausted":
        assets = assets.filter(quantity_in_stock=0)
    elif stock_state == "low":
        assets = assets.filter(
            quantity_in_stock__gt=0, quantity_in_stock__lte=models.F("minimum_stock")
        )

    assets = assets.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "resources/asset_list.html",
        {
            "assets": list(assets),
            "sort": sort_key,
            "dir": dir_,
            "categories": AssetCategory.objects.all(),
            "filters": {"q": q, "category": category, "stock_state": stock_state},
        },
    )


@login_required
def asset_detail(request, pk):
    asset = get_object_or_404(PedagogicalAsset, pk=pk)
    movements = asset.movements.select_related("session", "performed_by")[:50]
    restock_form = AssetRestockForm()
    return_form = AssetReturnForm()
    return render(
        request,
        "resources/asset_detail.html",
        {
            "asset": asset,
            "movements": movements,
            "restock_form": restock_form,
            "return_form": return_form,
        },
    )


@login_required
def asset_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:asset_list")
    if request.method == "POST":
        form = PedagogicalAssetForm(request.POST)
        if form.is_valid():
            asset = form.save(commit=False)
            asset.quantity_in_stock = 0
            asset.save()
            initial_qty = request.POST.get("initial_stock", "").strip()
            if initial_qty.isdigit() and int(initial_qty) > 0:
                asset.restock(int(initial_qty), by=request.user, note="Stock initial")
            messages.success(request, f'Actif "{asset.name}" créé avec succès.')
            return redirect("resources:asset_detail", pk=asset.pk)
    else:
        form = PedagogicalAssetForm()
    return render(
        request,
        "resources/asset_form.html",
        {"form": form, "title": "Nouvel actif pédagogique"},
    )


@login_required
def asset_edit(request, pk):
    asset = get_object_or_404(PedagogicalAsset, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:asset_detail", pk=asset.pk)
    if request.method == "POST":
        form = PedagogicalAssetForm(request.POST, instance=asset)
        if form.is_valid():
            asset = form.save()
            messages.success(request, f'Actif "{asset.name}" modifié avec succès.')
            return redirect("resources:asset_detail", pk=asset.pk)
    else:
        form = PedagogicalAssetForm(instance=asset)
    return render(
        request,
        "resources/asset_form.html",
        {"form": form, "asset": asset, "title": "Modifier l'actif"},
    )


@login_required
def asset_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("resources:asset_list")
    asset = get_object_or_404(PedagogicalAsset, pk=pk)
    if request.method == "POST":
        name = asset.name
        asset.delete()
        messages.success(request, f'Actif "{name}" supprimé.')
    return redirect("resources:asset_list")


@login_required
def asset_restock(request, pk):
    """Spec §new — refill an asset's stock (hard-tracked via AssetMovement)."""
    asset = get_object_or_404(PedagogicalAsset, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:asset_detail", pk=asset.pk)
    if request.method == "POST":
        form = AssetRestockForm(request.POST)
        if form.is_valid():
            asset.restock(
                form.cleaned_data["quantity"],
                by=request.user,
                note=form.cleaned_data.get("note", ""),
                unit_price=form.cleaned_data.get("unit_price"),
            )
            messages.success(
                request,
                f'{form.cleaned_data["quantity"]} {asset.get_unit_display()} '
                f'ajouté(s) au stock de "{asset.name}".',
            )
        else:
            messages.error(request, "Quantité invalide.")
    return redirect("resources:asset_detail", pk=asset.pk)


@login_required
def asset_return(request, pk):
    """Spec §new — return previously delivered stock (surplus not used,
    wrong item, etc.). Increases stock back and logs a distinct 'return'
    movement so it's never confused with a fresh supplier restock."""
    asset = get_object_or_404(PedagogicalAsset, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("resources:asset_detail", pk=asset.pk)
    if request.method == "POST":
        form = AssetReturnForm(request.POST)
        if form.is_valid():
            asset.return_stock(
                form.cleaned_data["quantity"],
                by=request.user,
                note=form.cleaned_data.get("note", ""),
                unit_price=form.cleaned_data.get("unit_price"),
            )
            messages.success(
                request,
                f'{form.cleaned_data["quantity"]} {asset.get_unit_display()} '
                f'retourné(s) au stock de "{asset.name}".',
            )
        else:
            messages.error(request, "Quantité invalide.")
    return redirect("resources:asset_detail", pk=asset.pk)
