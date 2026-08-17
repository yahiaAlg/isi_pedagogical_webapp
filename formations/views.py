from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone

from .models import (
    Category,
    Branch,
    Specialty,
    Formation,
    Session,
    Participant,
    TrainerPayment,
)
from clients.models import Client
from resources.models import Trainer
from .forms import (
    CategoryForm,
    BranchForm,
    SpecialtyForm,
    FormationForm,
    SessionForm,
    ParticipantForm,
    SessionStatusForm,
    AttendanceForm,
    ScoreForm,
    ExamScoreForm,
    ParticipantImportForm,
    SessionAssetDeliveryForm,
    SessionAssetReturnForm,
    TrainerPaymentForm,
)
from .utils import (
    sync_evaluation_scores,
    auto_fill_exam_scores,
    validate_session_transition,
    import_participants_from_file,
    check_scheduling_conflicts,
    has_scheduling_conflicts,
    equipment_is_blocked,
    get_idle_equipment,
    build_session_number,
)


def _log_equipment_allocations(session, user):
    """Spec §new — keep the allocation history in sync whenever a session's
    equipment M2M is saved from the session form (create/edit), not just
    from the session-detail check/uncheck toggle."""
    from resources.models import EquipmentAllocation

    current_ids = set(session.equipment.values_list("pk", flat=True))
    open_allocs = EquipmentAllocation.objects.filter(
        session=session, released_at__isnull=True
    )
    already_logged_ids = set(open_allocs.values_list("equipment_id", flat=True))

    if not session.room_id:
        # No room (on-site session) — nothing to log an allocation against.
        return

    for eq in session.equipment.filter(pk__in=(current_ids - already_logged_ids)):
        EquipmentAllocation.objects.create(
            equipment=eq, room=session.room, session=session, allocated_by=user
        )
    for alloc in open_allocs.exclude(equipment_id__in=current_ids):
        alloc.release(by=user)


# ===========================================================================
# Category
# ===========================================================================

CATEGORY_SORT_MAP = {"name": "name", "formation_count": "formations_total"}


@login_required
def category_list(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    sort = request.GET.get("sort", "name")
    dir_ = request.GET.get("dir", "asc")
    if sort not in CATEGORY_SORT_MAP:
        sort = "name"
    db_field = CATEGORY_SORT_MAP[sort]
    categories = Category.objects.annotate(formations_total=Count("formation"))
    q = request.GET.get("q", "").strip()
    if q:
        categories = categories.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(formation__title__icontains=q)
        ).distinct()
    categories = categories.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "formations/category_list.html",
        {"categories": categories, "sort": sort, "dir": dir_, "filters": {"q": q}},
    )


@login_required
def category_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:category_list")
    if request.method == "POST":
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Catégorie "{category.name}" créée.')
            return redirect("formations:category_list")
    else:
        form = CategoryForm()
    return render(
        request,
        "formations/category_form.html",
        {"form": form, "title": "Nouvelle catégorie"},
    )


@login_required
def category_edit(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:category_list")
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Catégorie "{category.name}" modifiée.')
            return redirect("formations:category_list")
    else:
        form = CategoryForm(instance=category)
    return render(
        request,
        "formations/category_form.html",
        {"form": form, "category": category, "title": "Modifier catégorie"},
    )


@login_required
def category_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:category_list")
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f'Catégorie "{name}" supprimée.')
    return redirect("formations:category_list")


# ===========================================================================
# Branch (§2.0a — planned catalog hierarchy)
# ===========================================================================


@login_required
def branch_list(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    branches = Branch.objects.annotate(specialties_total=Count("specialties"))
    q = request.GET.get("q", "").strip()
    if q:
        branches = branches.filter(
            Q(name__icontains=q)
            | Q(name_ar__icontains=q)
            | Q(abbreviation__icontains=q)
            | Q(specialties__title__icontains=q)
            | Q(specialties__formations__title__icontains=q)
        ).distinct()
    curriculum_type = request.GET.get("curriculum_type", "").strip()
    if curriculum_type:
        branches = branches.filter(curriculum_type=curriculum_type)
    return render(
        request,
        "formations/branch_list.html",
        {
            "branches": branches,
            "curriculum_choices": Branch.CURRICULUM_CHOICES,
            "filters": {"q": q, "curriculum_type": curriculum_type},
        },
    )


@login_required
def branch_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:branch_list")
    if request.method == "POST":
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save()
            messages.success(request, f'Branche "{branch.abbreviation}" créée.')
            return redirect("formations:branch_list")
    else:
        form = BranchForm()
    return render(
        request,
        "formations/branch_form.html",
        {"form": form, "title": "Nouvelle branche"},
    )


@login_required
def branch_edit(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:branch_list")
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            branch = form.save()
            messages.success(request, f'Branche "{branch.abbreviation}" modifiée.')
            return redirect("formations:branch_list")
    else:
        form = BranchForm(instance=branch)
    return render(
        request,
        "formations/branch_form.html",
        {"form": form, "branch": branch, "title": "Modifier branche"},
    )


@login_required
def branch_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:branch_list")
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == "POST":
        abbr = branch.abbreviation
        branch.delete()
        messages.success(request, f'Branche "{abbr}" supprimée.')
    return redirect("formations:branch_list")


# ===========================================================================
# Specialty (§2.0b — planned catalog hierarchy)
# ===========================================================================


@login_required
def specialty_list(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    specialties = Specialty.objects.select_related("branch").annotate(
        formations_total=Count("formations")
    )
    q = request.GET.get("q", "").strip()
    if q:
        specialties = specialties.filter(
            Q(title__icontains=q)
            | Q(title_ar__icontains=q)
            | Q(code__icontains=q)
            | Q(formations__title__icontains=q)
        ).distinct()
    branch = request.GET.get("branch", "").strip()
    if branch.isdigit():
        specialties = specialties.filter(branch_id=branch)
    return render(
        request,
        "formations/specialty_list.html",
        {
            "specialties": specialties,
            "branches": Branch.objects.order_by("name"),
            "filters": {"q": q, "branch": branch},
        },
    )


@login_required
def specialty_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:specialty_list")
    if request.method == "POST":
        form = SpecialtyForm(request.POST)
        if form.is_valid():
            specialty = form.save()
            messages.success(request, f'Spécialité "{specialty.reference_root}" créée.')
            return redirect("formations:specialty_list")
    else:
        form = SpecialtyForm()
    return render(
        request,
        "formations/specialty_form.html",
        {"form": form, "title": "Nouvelle spécialité"},
    )


@login_required
def specialty_edit(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:specialty_list")
    specialty = get_object_or_404(Specialty, pk=pk)
    if request.method == "POST":
        form = SpecialtyForm(request.POST, instance=specialty)
        if form.is_valid():
            specialty = form.save()
            messages.success(
                request, f'Spécialité "{specialty.reference_root}" modifiée.'
            )
            return redirect("formations:specialty_list")
    else:
        form = SpecialtyForm(instance=specialty)
    return render(
        request,
        "formations/specialty_form.html",
        {"form": form, "specialty": specialty, "title": "Modifier spécialité"},
    )


@login_required
def specialty_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:specialty_list")
    specialty = get_object_or_404(Specialty, pk=pk)
    if request.method == "POST":
        root = specialty.reference_root
        specialty.delete()
        messages.success(request, f'Spécialité "{root}" supprimée.')
    return redirect("formations:specialty_list")


# ===========================================================================
# Formation
# ===========================================================================

FORMATION_SORT_MAP = {
    "code": "code",
    "title": "title",
    "category__name": "category__name",
    "duration_days": "duration_days",
    "avg_price": "avg_price",
    "session_count": "sessions_total",
    "is_active": "is_active",
}


@login_required
def formation_list(request):
    sort = request.GET.get("sort", "title")
    dir_ = request.GET.get("dir", "asc")
    if sort not in FORMATION_SORT_MAP:
        sort = "title"
    db_field = FORMATION_SORT_MAP[sort]
    # Spec §new — price no longer lives on Formation: each session cycle
    # (primary session) carries its own market price. `avg_price` is a
    # plain SQL average of those cycle prices, used only for list-level
    # sort/filter (cheap, DB-side). The catalog/detail page instead uses
    # Formation.average_price, a participant-count-weighted average.
    qs = Formation.objects.select_related("category", "specialty").annotate(
        sessions_total=Count("session"),
        avg_price=Avg("session__base_price", filter=Q(session__is_primary=True)),
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(title_ar__icontains=q)
            | Q(code__icontains=q)
            | Q(description__icontains=q)
        )
    category = request.GET.get("category", "").strip()
    if category.isdigit():
        qs = qs.filter(category_id=category)
    branch = request.GET.get("branch", "").strip()
    if branch.isdigit():
        qs = qs.filter(specialty__branch_id=branch)
    specialty = request.GET.get("specialty", "").strip()
    if specialty.isdigit():
        qs = qs.filter(specialty_id=specialty)
    attestation_type = request.GET.get("attestation_type", "").strip()
    if attestation_type:
        qs = qs.filter(attestation_type=attestation_type)
    evaluation_type = request.GET.get("evaluation_type", "").strip()
    if evaluation_type:
        qs = qs.filter(evaluation_type=evaluation_type)
    is_active = request.GET.get("is_active", "").strip()
    if is_active == "yes":
        qs = qs.filter(is_active=True)
    elif is_active == "no":
        qs = qs.filter(is_active=False)
    # Spec §new — price now rolls up from session cycles (see avg_price
    # annotation above), so the min/max filter runs against that instead
    # of a removed Formation.base_price field.
    price_min = request.GET.get("price_min", "").strip()
    if price_min:
        qs = qs.filter(avg_price__gte=price_min)
    price_max = request.GET.get("price_max", "").strip()
    if price_max:
        qs = qs.filter(avg_price__lte=price_max)
    duration_min = request.GET.get("duration_min", "").strip()
    if duration_min.isdigit():
        qs = qs.filter(duration_days__gte=int(duration_min))
    duration_max = request.GET.get("duration_max", "").strip()
    if duration_max.isdigit():
        qs = qs.filter(duration_days__lte=int(duration_max))
    participants_min = request.GET.get("participants_min", "").strip()
    if participants_min.isdigit():
        qs = qs.filter(max_participants__gte=int(participants_min))
    participants_max = request.GET.get("participants_max", "").strip()
    if participants_max.isdigit():
        qs = qs.filter(min_participants__lte=int(participants_max))

    qs = qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/formation_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
            "categories": Category.objects.order_by("name"),
            "branches": Branch.objects.order_by("name"),
            "specialties": (
                Specialty.objects.select_related("branch").filter(branch_id=branch)
                if branch.isdigit()
                else Specialty.objects.select_related("branch")
            ).order_by("branch__abbreviation", "code"),
            "attestation_choices": Formation.ATTESTATION_TYPE_CHOICES,
            "evaluation_choices": Formation.EVALUATION_CHOICES,
            "filters": {
                "q": q,
                "category": category,
                "branch": branch,
                "specialty": specialty,
                "attestation_type": attestation_type,
                "evaluation_type": evaluation_type,
                "is_active": is_active,
                "price_min": price_min,
                "price_max": price_max,
                "duration_min": duration_min,
                "duration_max": duration_max,
                "participants_min": participants_min,
                "participants_max": participants_max,
            },
        },
    )


@login_required
def formation_detail(request, pk):
    formation = get_object_or_404(Formation, pk=pk)
    # Only primary sessions in the list (children are shown inside each primary)
    sessions = (
        formation.session_set.filter(is_primary=True)
        .select_related("client", "trainer")
        .order_by("-date_start")[:10]
    )
    return render(
        request,
        "formations/formation_detail.html",
        {"formation": formation, "sessions": sessions},
    )


@login_required
def formation_create(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    if request.method == "POST":
        form = FormationForm(request.POST)
        if form.is_valid():
            formation = form.save()
            messages.success(request, f'Formation "{formation.title}" créée.')
            # Spec §new — redirect to detail page after creation
            return redirect("formations:formation_detail", pk=formation.pk)
    else:
        form = FormationForm()
    return render(
        request,
        "formations/formation_form.html",
        {"form": form, "title": "Nouvelle formation"},
    )


@login_required
def formation_edit(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_detail", pk=pk)
    formation = get_object_or_404(Formation, pk=pk)
    if request.method == "POST":
        form = FormationForm(request.POST, instance=formation)
        if form.is_valid():
            formation = form.save()
            messages.success(request, f'Formation "{formation.title}" modifiée.')
            return redirect("formations:formation_detail", pk=formation.pk)
    else:
        form = FormationForm(instance=formation)
    return render(
        request,
        "formations/formation_form.html",
        {"form": form, "formation": formation, "title": "Modifier formation"},
    )


@login_required
def formation_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    formation = get_object_or_404(Formation, pk=pk)
    if request.method == "POST":
        if formation.session_set.filter(status__in=["planned", "in_progress"]).exists():
            messages.error(
                request,
                "Impossible de supprimer : des sessions actives ou planifiées existent.",
            )
            return redirect("formations:formation_list")
        title = formation.title
        formation.delete()
        messages.success(request, f'Formation "{title}" supprimée.')
    return redirect("formations:formation_list")


# ===========================================================================
# Formation — clear all sessions  (admin-only, destructive)
# ===========================================================================


@login_required
@require_POST
def formation_clear_sessions(request, pk):
    """
    Delete ALL sessions (and all their related data: participants, generated
    documents, child sessions) for a given formation.
    The formation itself is never touched.
    Admin-only. Requires the user to confirm by typing the formation code
    in the POST body (field: `confirm_code`).
    """
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_detail", pk=pk)

    formation = get_object_or_404(Formation, pk=pk)

    # Double-confirmation: the admin must type the formation code
    confirm_code = request.POST.get("confirm_code", "").strip().upper()
    if confirm_code != formation.code.upper():
        messages.error(
            request,
            f"Code de confirmation incorrect. "
            f"Saisissez exactement « {formation.code} » pour confirmer.",
        )
        return redirect("formations:formation_detail", pk=pk)

    sessions_qs = formation.session_set.all()
    session_count = sessions_qs.count()

    if session_count == 0:
        messages.info(request, "Aucune session à supprimer pour cette formation.")
        return redirect("formations:formation_detail", pk=pk)

    # Cascade deletes participants, generated documents, child sessions
    sessions_qs.delete()

    messages.success(
        request,
        f"✓ {session_count} session(s) et toutes leurs données associées ont été "
        f"supprimées pour la formation « {formation.title} ».",
    )
    return redirect("formations:formation_detail", pk=pk)


# ===========================================================================
# Formation AJAX API (for session form pre-population)
# ===========================================================================


@login_required
def formation_api_detail(request, pk):
    """
    Return formation data + last-session hints for session form auto-fill.
    Called via JS whenever the formation dropdown changes.
    """
    formation = get_object_or_404(Formation, pk=pk, is_active=True)
    last = (
        formation.session_set.filter(is_primary=True)
        .select_related("client", "trainer")
        .order_by("-date_start")
        .first()
    )
    today = timezone.localdate().isoformat()
    # Prefer the last trainer only if still qualified for this formation;
    # otherwise fall back to any trainer currently qualified for it.
    trainer = None
    if (
        last
        and last.trainer_id
        and formation.qualified_trainers.filter(pk=last.trainer_id).exists()
    ):
        trainer = last.trainer
    else:
        trainer = formation.qualified_trainers.filter(is_active=True).first()
    data = {
        "max_participants": formation.max_participants,
        "duration_days": formation.duration_days,
        "today": today,
        "last_client_id": last.client_id if last else None,
        "last_client_name": last.client.name if last else None,
        "last_trainer_id": trainer.pk if trainer else None,
        "last_trainer_name": trainer.full_name if trainer else None,
        "specialty_code": (
            formation.specialty.reference_root
            if formation.specialty_id
            else formation.code
        ),
    }
    return JsonResponse(data)


# ===========================================================================
# Session
# ===========================================================================

SESSION_SORT = {
    "reference",
    "formation__title",
    "date_start",
    "client__name",
    "trainer__last_name",
    "status",
}


@login_required
def session_list(request):
    sort = request.GET.get("sort", "date_start")
    dir_ = request.GET.get("dir", "desc")
    if sort not in SESSION_SORT:
        sort = "date_start"
    # Show only primary sessions in the main list (children are nested inside)
    qs = Session.objects.filter(is_primary=True).select_related(
        "formation", "client", "trainer"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(reference__icontains=q)
            | Q(formation__title__icontains=q)
            | Q(client__name__icontains=q)
            | Q(trainer__first_name__icontains=q)
            | Q(trainer__last_name__icontains=q)
            | Q(external_location__icontains=q)
            # Spec §new — invoice sequence associated with this session
            # cycle is one of the free-text search criteria.
            | Q(invoice_reference__icontains=q)
        )
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    location_type = request.GET.get("location_type", "").strip()
    if location_type:
        qs = qs.filter(location_type=location_type)
    formation = request.GET.get("formation", "").strip()
    if formation.isdigit():
        qs = qs.filter(formation_id=formation)
    client = request.GET.get("client", "").strip()
    if client.isdigit():
        qs = qs.filter(client_id=client)
    trainer = request.GET.get("trainer", "").strip()
    if trainer.isdigit():
        qs = qs.filter(trainer_id=trainer)
    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        qs = qs.filter(date_start__gte=date_from)
    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        qs = qs.filter(date_end__lte=date_to)
    capacity_min = request.GET.get("capacity_min", "").strip()
    if capacity_min.isdigit():
        qs = qs.filter(capacity__gte=int(capacity_min))
    capacity_max = request.GET.get("capacity_max", "").strip()
    if capacity_max.isdigit():
        qs = qs.filter(capacity__lte=int(capacity_max))

    qs = qs.order_by(sort if dir_ == "asc" else "-" + sort)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/session_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
            "status_choices": Session.STATUS_CHOICES,
            "location_choices": Session.LOCATION_CHOICES,
            "formations": Formation.objects.order_by("title"),
            "clients": Client.objects.filter(is_active=True).order_by("name"),
            "trainers": Trainer.objects.filter(is_active=True).order_by("last_name"),
            "filters": {
                "q": q,
                "status": status,
                "location_type": location_type,
                "formation": formation,
                "client": client,
                "trainer": trainer,
                "date_from": date_from,
                "date_to": date_to,
                "capacity_min": capacity_min,
                "capacity_max": capacity_max,
            },
        },
    )


@login_required
def session_detail(request, pk):
    session = get_object_or_404(Session, pk=pk)
    participants = session.participant_set.order_by("last_name", "first_name")
    child_sessions = []
    if session.is_primary:
        child_sessions = list(
            session.child_sessions.prefetch_related("participant_set").order_by(
                "date_start"
            )
        )

    # Spec §new — equipment homed in this room (inherently importable /
    # checkable for use in this session) + idle equipment from other rooms
    # (soft-warning suggestions, guarded by equipment_is_blocked).
    selected_ids = set(session.equipment.values_list("pk", flat=True))
    room_equipment = []
    idle_equipment = []
    if session.room_id:
        room_equipment = list(session.room.available_equipment)
        for item in room_equipment:
            item.checked = item.pk in selected_ids
        if session.status not in ["cancelled", "archived"]:
            idle_equipment = get_idle_equipment(session)

    # Spec §new — pedagogical assets (consumables) delivered to this
    # session so far, aggregated by asset, plus the delivery form.
    from resources.models import PedagogicalAsset

    delivery_filter = Q(movements__session=session, movements__movement_type="delivery")
    return_filter = Q(movements__session=session, movements__movement_type="return")
    asset_deliveries = (
        PedagogicalAsset.objects.filter(delivery_filter)
        .annotate(
            delivered_qty=Sum("movements__quantity", filter=delivery_filter),
            delivered_value=Sum("movements__total_price", filter=delivery_filter),
            returned_qty=Sum("movements__quantity", filter=return_filter),
        )
        .select_related("category")
        .distinct()
        .order_by("name")
    )
    asset_delivery_form = SessionAssetDeliveryForm()
    asset_return_form = SessionAssetReturnForm()

    # Spec §new — reserved equipment cost for this session (quantity ×
    # unit price snapshotted at allocation time).
    equipment_allocations = session.equipment_allocations.select_related("equipment")

    return render(
        request,
        "formations/session_detail.html",
        {
            "session": session,
            "participants": participants,
            "child_sessions": child_sessions,
            "room_equipment": room_equipment,
            "idle_equipment": idle_equipment,
            "selected_equipment_ids": selected_ids,
            "asset_deliveries": asset_deliveries,
            "asset_delivery_form": asset_delivery_form,
            "asset_return_form": asset_return_form,
            "equipment_allocations": equipment_allocations,
        },
    )


@login_required
@require_POST
def session_equipment_update(request, pk):
    """Spec §new — check/uncheck equipment used in this session from the
    session detail page. Adding equipment homed elsewhere is hard-blocked
    (guardrail) if it's still actively allocated to another room/session;
    otherwise it's allocated (logged) and released when unchecked."""
    from resources.models import Equipment, EquipmentAllocation

    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if not session.can_edit():
        messages.error(
            request,
            "Cette session est archivée ou annulée et ne peut pas être modifiée.",
        )
        return redirect("formations:session_detail", pk=pk)

    if not session.room_id:
        messages.error(request, "Aucune salle n'est associée à cette session.")
        return redirect("formations:session_detail", pk=pk)

    submitted_ids = {
        int(i) for i in request.POST.getlist("equipment_ids") if i.isdigit()
    }
    current_ids = set(session.equipment.values_list("pk", flat=True))

    added_count, blocked = 0, []
    for eq in Equipment.objects.filter(pk__in=(submitted_ids - current_ids)):
        if equipment_is_blocked(
            eq,
            room=session.room,
            date_start=session.date_start,
            date_end=session.date_end,
            exclude_pk=session.pk,
        ):
            blocked.append(eq.name)
            continue
        session.equipment.add(eq)
        EquipmentAllocation.objects.create(
            equipment=eq,
            room=session.room,
            session=session,
            allocated_by=request.user,
        )
        added_count += 1

    removed_ids = current_ids - submitted_ids
    for eq in Equipment.objects.filter(pk__in=removed_ids):
        session.equipment.remove(eq)
        alloc = EquipmentAllocation.objects.filter(
            equipment=eq, session=session, released_at__isnull=True
        ).first()
        if alloc:
            alloc.release(by=request.user)

    if added_count or removed_ids:
        messages.success(request, "Équipements de la session mis à jour.")
    if blocked:
        messages.warning(
            request,
            "Non ajoutés (déjà alloués ailleurs, à libérer d'abord) : "
            + ", ".join(blocked),
        )
    return redirect("formations:session_detail", pk=pk)


@login_required
@require_POST
def session_asset_deliver(request, pk):
    """Spec §new — deliver (consume) a pedagogical asset to this session.
    Hard-blocked if the requested quantity exceeds current stock (unlike
    the equipment soft-warning guardrail, this is a physical constraint)."""
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if not session.can_edit():
        messages.error(
            request,
            "Cette session est archivée ou annulée et ne peut pas être modifiée.",
        )
        return redirect("formations:session_detail", pk=pk)

    form = SessionAssetDeliveryForm(request.POST)
    if form.is_valid():
        asset = form.cleaned_data["asset"]
        quantity = form.cleaned_data["quantity"]
        note = form.cleaned_data.get("note", "")
        unit_price = form.cleaned_data.get("unit_price")
        try:
            asset.deliver(
                quantity,
                session=session,
                by=request.user,
                note=note,
                unit_price=unit_price,
            )
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(
                request,
                f'{quantity} {asset.get_unit_display()} de "{asset.name}" livré(s) à la session.',
            )
    else:
        for err in form.errors.values():
            messages.error(request, "; ".join(err))
    return redirect("formations:session_detail", pk=pk)


@login_required
@require_POST
def session_asset_return(request, pk):
    """Spec §new — return part of an asset delivered to this session
    (surplus not consumed, wrong item...) back to stock."""
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)

    form = SessionAssetReturnForm(request.POST)
    if form.is_valid():
        asset = form.cleaned_data["asset"]
        quantity = form.cleaned_data["quantity"]
        note = form.cleaned_data.get("note", "")
        try:
            asset.return_stock(quantity, session=session, by=request.user, note=note)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            messages.success(
                request,
                f'{quantity} {asset.get_unit_display()} de "{asset.name}" retourné(s) au stock.',
            )
    else:
        for err in form.errors.values():
            messages.error(request, "; ".join(err))
    return redirect("formations:session_detail", pk=pk)


@login_required
def room_equipment_api(request, pk):
    """AJAX — spec §new — equipment homed in a room, for auto-import when a
    room is selected on the session form."""
    from resources.models import Room

    room = get_object_or_404(Room, pk=pk)
    ids = list(room.available_equipment.values_list("pk", flat=True))
    return JsonResponse({"equipment_ids": ids})


@login_required
def trainer_default_cost_api(request, pk):
    """AJAX — spec §new — this trainer's default remuneration mode/amount,
    used to auto-fill (only fields left empty by the user) the trainer-cost
    section when a trainer is picked on the session form."""
    trainer = get_object_or_404(Trainer, pk=pk)
    return JsonResponse(
        {
            "cost_mode": trainer.default_cost_mode,
            "cost_percentage": (
                str(trainer.default_cost_percentage)
                if trainer.default_cost_percentage is not None
                else None
            ),
            "cost_amount": (
                str(trainer.default_cost_amount)
                if trainer.default_cost_amount is not None
                else None
            ),
        }
    )


@login_required
def session_create(request):
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_list")
    conflicts = None
    if request.method == "POST":
        form = SessionForm(request.POST)
        if form.is_valid():
            confirmed = request.POST.get("confirm_conflicts") == "1"
            conflicts = check_scheduling_conflicts(
                room=form.cleaned_data.get("room"),
                trainer=form.cleaned_data.get("trainer"),
                equipment_qs=form.cleaned_data.get("equipment"),
                date_start=form.cleaned_data.get("date_start"),
                date_end=form.cleaned_data.get("date_end"),
            )
            if has_scheduling_conflicts(conflicts) and not confirmed:
                # Spec — soft warning only: don't block, let the user
                # confirm-and-save anyway, or fix the conflict via the
                # quick actions (add another room/trainer) offered below.
                return render(
                    request,
                    "formations/session_form.html",
                    {
                        "form": form,
                        "title": "Nouvelle session",
                        "conflicts": conflicts,
                        "selected_equipment_ids": [
                            e.pk for e in form.cleaned_data.get("equipment") or []
                        ],
                    },
                )
            session = form.save()
            _log_equipment_allocations(session, request.user)
            messages.success(
                request,
                f'Session "{session.reference}" créée. Ajoutez maintenant les participants.',
            )
            return redirect("formations:session_detail", pk=session.pk)
    else:
        initial = {}
        # Spec §new — pre-populate when coming from formation detail
        formation_pk = request.GET.get("formation")
        if formation_pk:
            try:
                formation = Formation.objects.get(pk=formation_pk, is_active=True)
                initial["formation"] = formation
                initial["capacity"] = formation.max_participants
                today = timezone.localdate()
                initial["date_start"] = today
                initial["date_end"] = today
                # Spec §new — specialty code pre-filled from the formation's
                # specialty abbreviation (or its own code as a fallback).
                initial["specialty_code"] = (
                    formation.specialty.reference_root
                    if formation.specialty_id
                    else formation.code
                )[:20]
                # Pre-select last used client/trainer for this formation,
                # restricted to trainers actually qualified for it.
                qualified_trainer = formation.qualified_trainers.filter(
                    is_active=True
                ).first()
                last = (
                    formation.session_set.filter(is_primary=True)
                    .order_by("-date_start")
                    .first()
                )
                trainer = None
                if (
                    last
                    and last.trainer_id
                    and formation.qualified_trainers.filter(pk=last.trainer_id).exists()
                ):
                    trainer = last.trainer
                elif qualified_trainer:
                    trainer = qualified_trainer
                if trainer:
                    initial["trainer"] = trainer
                    # Spec §new — default the formateur's part from their
                    # own default cost mode/amount (still fully editable).
                    initial["trainer_cost_mode"] = trainer.default_cost_mode
                    initial["trainer_cost_percentage"] = trainer.default_cost_percentage
                    initial["trainer_cost_amount"] = trainer.default_cost_amount
                if last:
                    initial["client"] = last.client
                    initial["location_type"] = last.location_type
                    initial["room"] = last.room
                    initial["external_location"] = last.external_location
                    # Spec §new — carry forward the last cycle's price as a
                    # starting point (still fully editable): the market
                    # price fluctuates per cycle depending on demand, so
                    # this is only a suggestion, not a fixed catalog price.
                    initial["base_price"] = last.base_price
                    initial["price_mode"] = last.price_mode
                    # Spec §new — equipment homed in the room is inherently
                    # imported/pre-checked when creating a session there.
                    if last.room:
                        initial["equipment"] = list(last.room.available_equipment)
                # Spec §new — session code S-{formation}-{formateur}-{date}
                initial["session_number"] = build_session_number(
                    formation.code, trainer.last_name if trainer else "", today
                )
            except Formation.DoesNotExist:
                pass
        form = SessionForm(initial=initial)
    return render(
        request,
        "formations/session_form.html",
        {
            "form": form,
            "title": "Nouvelle session",
            "selected_equipment_ids": [],
        },
    )


@login_required
def session_edit(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if not session.can_edit():
        messages.error(
            request,
            "Cette session est archivée ou annulée et ne peut pas être modifiée.",
        )
        return redirect("formations:session_detail", pk=pk)
    if request.method == "POST":
        form = SessionForm(request.POST, instance=session)
        if form.is_valid():
            confirmed = request.POST.get("confirm_conflicts") == "1"
            conflicts = check_scheduling_conflicts(
                room=form.cleaned_data.get("room"),
                trainer=form.cleaned_data.get("trainer"),
                equipment_qs=form.cleaned_data.get("equipment"),
                date_start=form.cleaned_data.get("date_start"),
                date_end=form.cleaned_data.get("date_end"),
                exclude_pk=session.pk,
            )
            if has_scheduling_conflicts(conflicts) and not confirmed:
                return render(
                    request,
                    "formations/session_form.html",
                    {
                        "form": form,
                        "session": session,
                        "title": "Modifier session",
                        "conflicts": conflicts,
                        "selected_equipment_ids": [
                            e.pk for e in form.cleaned_data.get("equipment") or []
                        ],
                    },
                )
            session = form.save()
            _log_equipment_allocations(session, request.user)
            messages.success(request, f'Session "{session.reference}" modifiée.')
            return redirect("formations:session_detail", pk=session.pk)
    else:
        form = SessionForm(instance=session)
    return render(
        request,
        "formations/session_form.html",
        {
            "form": form,
            "session": session,
            "title": "Modifier session",
            "selected_equipment_ids": list(
                session.equipment.values_list("pk", flat=True)
            ),
        },
    )


@login_required
def session_status(request, pk):
    """Status transition with validation (spec §12.2)."""
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if request.method == "POST":
        form = SessionStatusForm(request.POST, session=session)
        if form.is_valid():
            new_status = form.cleaned_data["new_status"]
            if new_status == "archived" and not request.user.profile.is_admin():
                messages.error(request, "L'archivage est réservé aux administrateurs.")
                return redirect("formations:session_detail", pk=pk)
            errors = validate_session_transition(session, new_status)
            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect("formations:session_detail", pk=pk)
            session.status = new_status
            if new_status == "cancelled":
                session.cancellation_reason = form.cleaned_data["cancellation_reason"]
            session.save()
            # Propagate status to child sessions when completing/cancelling
            if (
                new_status in ["completed", "cancelled", "archived"]
                and session.is_primary
            ):
                session.child_sessions.update(status=new_status)
            if new_status == "completed" and session.is_primary:
                auto_fill_exam_scores(session)
            messages.success(
                request, f"Statut mis à jour : {session.get_status_display()}."
            )
            return redirect("formations:session_detail", pk=pk)
    else:
        form = SessionStatusForm(session=session)
    return render(
        request,
        "formations/session_status_form.html",
        {"form": form, "session": session},
    )


@login_required
def session_trainer_payment(request, pk):
    """Spec §new — record one installment towards the formateur's part
    (Session.trainer_cost) for a terminated cycle: amount + settlement
    mode + transaction reference (auto ESP-… for espèce) + optional
    scanned proof. A cycle can take several installments until its
    balance reaches zero (see Session.trainer_payment_status)."""
    session = get_object_or_404(Session, pk=pk)
    primary = session if session.is_primary else (session.parent_session or session)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if primary.status not in ["completed", "archived"]:
        messages.error(
            request,
            "Le règlement du formateur ne peut être confirmé qu'une fois le "
            "cycle terminé (statut Terminée ou Archivée).",
        )
        return redirect("formations:session_detail", pk=pk)
    if primary.trainer_payment_status == "paid":
        messages.info(
            request, "Le règlement du formateur est déjà soldé pour ce cycle."
        )
        return redirect("formations:session_detail", pk=pk)

    if request.method == "POST":
        form = TrainerPaymentForm(request.POST, request.FILES, session=primary)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.session = primary
            payment.confirmed_by = request.user
            payment.save()
            messages.success(
                request,
                f"Règlement enregistré — référence {payment.reference}.",
            )
            return redirect("formations:session_detail", pk=pk)
    else:
        form = TrainerPaymentForm(session=primary)
    return render(
        request,
        "formations/session_trainer_payment_form.html",
        {"form": form, "session": session, "primary": primary},
    )


@login_required
def trainer_payment_edit(request, pk):
    """Spec §new — let an administrator correct a previously recorded
    installment (amount, statut, mode, référence, justificatif, note)
    from the trainer's payment history. Reachable from both the session
    page and the trainer detail page."""
    payment = get_object_or_404(TrainerPayment, pk=pk)
    if not request.user.profile.is_admin():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=payment.session_id)
    primary = payment.session

    next_url = request.GET.get("next") or request.POST.get("next")

    if request.method == "POST":
        form = TrainerPaymentForm(
            request.POST, request.FILES, instance=payment, session=primary
        )
        if form.is_valid():
            updated = form.save(commit=False)
            updated.session = primary
            updated.save()
            messages.success(
                request, f"Règlement modifié — référence {updated.reference}."
            )
            if next_url:
                return redirect(next_url)
            return redirect("formations:session_detail", pk=primary.pk)
    else:
        form = TrainerPaymentForm(instance=payment, session=primary)
    return render(
        request,
        "formations/session_trainer_payment_form.html",
        {
            "form": form,
            "session": primary,
            "primary": primary,
            "payment": payment,
            "next_url": next_url,
        },
    )


@login_required
def session_attendance(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_edit_scores():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if request.method == "POST":
        form = AttendanceForm(request.POST, session=session)
        if form.is_valid():
            for field_name, value in form.cleaned_data.items():
                if field_name.startswith("participant_"):
                    participant_id = int(field_name.replace("participant_", ""))
                    try:
                        participant = session.participant_set.get(pk=participant_id)
                        participant.attended = value
                        participant.save(update_fields=["attended"])
                    except Participant.DoesNotExist:
                        pass
            messages.success(request, "Présences enregistrées.")
            return redirect("formations:session_detail", pk=pk)
    else:
        form = AttendanceForm(session=session)
    return render(
        request,
        "formations/session_attendance.html",
        {"form": form, "session": session},
    )


@login_required
def session_scores(request, pk):
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_edit_scores():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    # Spec — theory/practice marks are entered once for the whole formation,
    # after it finishes, not once per day/session. They live on the
    # primary-session participants only (same rule as the final exam score).
    if not session.is_primary:
        messages.info(
            request,
            "Les notes théorique/pratique se saisissent une seule fois, "
            "sur la session principale, après la fin de la formation.",
        )
        target = session.parent_session or session
        return redirect("formations:session_scores", pk=target.pk)
    if request.method == "POST":
        form = ScoreForm(request.POST, session=session)
        if form.is_valid():
            eval_type = session.formation.evaluation_type
            for participant in session.participant_set.all():
                sync_evaluation_scores(
                    participant,
                    score_theory=form.cleaned_data.get(f"theory_{participant.id}"),
                    score_practice=form.cleaned_data.get(f"practice_{participant.id}"),
                    set_theory=eval_type in ["theory_only", "both"],
                    set_practice=eval_type in ["practice_only", "both"],
                )
            messages.success(request, "Notes enregistrées.")
            return redirect("formations:session_detail", pk=pk)
    else:
        form = ScoreForm(session=session)
    return render(
        request, "formations/session_scores.html", {"form": form, "session": session}
    )


@login_required
def session_exam_scores(request, pk):
    """
    Spec §new — Enter/edit final exam scores for primary-session participants.
    Accessible only on primary sessions.
    """
    session = get_object_or_404(Session, pk=pk)
    if not session.is_primary:
        messages.error(
            request,
            "Les notes d'examen se saisissent uniquement sur la session principale.",
        )
        return redirect("formations:session_detail", pk=pk)
    if not request.user.profile.can_edit_scores():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)

    if request.method == "POST":
        form = ExamScoreForm(request.POST, session=session)
        if form.is_valid():
            for participant in session.participant_set.filter(attended=True):
                val = form.cleaned_data.get(f"exam_{participant.id}")
                participant.exam_score = val
                participant.save(update_fields=["exam_score"])
            # Also clear exam score for absent participants
            session.participant_set.filter(attended=False).update(exam_score=None)
            messages.success(request, "Notes d'examen enregistrées.")
            return redirect("formations:session_detail", pk=pk)
    else:
        form = ExamScoreForm(session=session)

    return render(
        request,
        "formations/session_exam_scores.html",
        {"form": form, "session": session},
    )


@login_required
def generate_session_group(request, pk):
    """
    Spec §new — Auto-generate child sessions (day 2 … N) from a primary session.
    Idempotent: regenerates if children already exist.
    """
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)
    if not session.is_primary:
        messages.error(
            request, "Seule la session principale peut générer les sessions suivantes."
        )
        return redirect("formations:session_detail", pk=pk)
    if session.participant_count == 0:
        messages.error(
            request,
            "Ajoutez au moins un participant avant de générer les sessions suivantes.",
        )
        return redirect("formations:session_detail", pk=pk)

    from .utils import generate_child_sessions

    created = generate_child_sessions(session)
    n = session.formation.duration_days
    if created:
        messages.success(
            request,
            f"{len(created)} session(s) générée(s) (jours 2–{n}) avec "
            f"{session.participant_count} participant(s) chacune. "
            f"Notes d'examen pré-remplies à {session.formation.max_score / 2:g} / {session.formation.max_score:g}. "
            f"La session principale est repassée à « Planifiée » et son numéro de "
            f"PV (le cas échéant) a été libéré — un nouveau sera attribué à partir "
            f"du compteur en cours au prochain PV imprimé.",
        )
    else:
        messages.info(
            request,
            "Cette formation ne comporte qu'une seule journée — aucune session supplémentaire à générer.",
        )
    return redirect("formations:session_detail", pk=pk)


@login_required
def session_delete(request, pk):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:session_list")
    session = get_object_or_404(Session, pk=pk)
    if request.method == "POST":
        ref = session.reference
        session.delete()
        messages.success(request, f'Session "{ref}" supprimée.')
    return redirect("formations:session_list")


# ===========================================================================
# Participant
# ===========================================================================


@login_required
def participant_create(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=session_pk)
    if not session.can_add_participants():
        messages.error(
            request,
            "Impossible d'ajouter des participants : session terminée ou capacité atteinte.",
        )
        return redirect("formations:session_detail", pk=session_pk)
    if request.method == "POST":
        form = ParticipantForm(request.POST, session=session)
        if form.is_valid():
            participant = form.save(commit=False)
            participant.session = session
            participant.attended = True  # default present
            participant.save()
            messages.success(request, f'Participant "{participant.full_name}" ajouté.')
            # Stay on participant create to allow bulk adding
            if request.POST.get("add_another"):
                return redirect("formations:participant_create", session_pk=session_pk)
            return redirect("formations:session_detail", pk=session_pk)
    else:
        form = ParticipantForm(session=session)
    return render(
        request,
        "formations/participant_form.html",
        {"form": form, "session": session, "title": "Nouveau participant"},
    )


@login_required
def participant_edit(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    session = participant.session
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=session.pk)
    if not session.can_edit():
        messages.error(
            request, "Cette session est archivée et ne peut pas être modifiée."
        )
        return redirect("formations:session_detail", pk=session.pk)
    if request.method == "POST":
        form = ParticipantForm(request.POST, instance=participant, session=session)
        if form.is_valid():
            participant = form.save()
            messages.success(request, f'Participant "{participant.full_name}" modifié.')
            return redirect("formations:session_detail", pk=session.pk)
    else:
        form = ParticipantForm(instance=participant, session=session)
    return render(
        request,
        "formations/participant_form.html",
        {
            "form": form,
            "participant": participant,
            "session": session,
            "title": "Modifier participant",
        },
    )


@login_required
def participant_delete(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    session = participant.session
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=session.pk)
    if not session.can_edit():
        messages.error(
            request, "Cette session est archivée et ne peut pas être modifiée."
        )
        return redirect("formations:session_detail", pk=session.pk)
    if request.method == "POST":
        name = participant.full_name
        # Also delete corresponding copies in child sessions
        if session.is_primary and participant.source_participant is None:
            participant.copies.all().delete()
        participant.delete()
        messages.success(request, f'Participant "{name}" supprimé.')
        return redirect("formations:session_detail", pk=session.pk)
    return render(
        request,
        "formations/participant_confirm_delete.html",
        {"participant": participant, "session": session},
    )


@login_required
def participant_import(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=session_pk)
    if not session.can_add_participants():
        messages.error(request, "Capacité atteinte ou session non modifiable.")
        return redirect("formations:session_detail", pk=session_pk)
    if request.method == "POST":
        form = ParticipantImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = import_participants_from_file(session, request.FILES["file"])
                messages.success(
                    request,
                    f"{result['imported']} importé(s), "
                    f"{result['duplicates']} doublon(s) ignoré(s), "
                    f"{result['rejected']} rejeté(s) (capacité).",
                )
                for err in result["errors"]:
                    messages.warning(request, f"Ligne {err['row']}: {err['message']}")
            except Exception as e:
                messages.error(request, f"Erreur de lecture du fichier: {str(e)}")
            return redirect("formations:session_detail", pk=session_pk)
    else:
        form = ParticipantImportForm()
    return render(
        request,
        "formations/participant_import.html",
        {"form": form, "session": session},
    )


@login_required
def participant_export(request, session_pk):
    """Export the session's participants to .xlsx, using the same column
    headers accepted by `import_participants_from_file` so the file can be
    edited and re-imported (plus read-only Présence/Résultat/Note columns)."""
    import openpyxl
    from openpyxl.styles import Font

    session = get_object_or_404(Session, pk=session_pk)

    headers = [
        "Prénom",
        "Nom",
        "Prénom AR",
        "Nom AR",
        "Date naissance",
        "Lieu naissance",
        "Lieu naissance AR",
        "Fonction",
        "Employeur",
        "Téléphone",
        "Email",
        "Présence",
        "Résultat",
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Participants"
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)

    result_labels = {
        "passed": "Admis",
        "failed": "Échoué",
        "pending": "En attente",
        "absent": "Absent",
        "present": "Présent",
    }

    for p in session.participant_set.all().order_by("last_name", "first_name"):
        ws.append(
            [
                p.first_name,
                p.last_name,
                p.first_name_ar,
                p.last_name_ar,
                p.date_of_birth.strftime("%d/%m/%Y") if p.date_of_birth else "",
                p.place_of_birth,
                p.place_of_birth_ar,
                p.job_title,
                p.employer,
                p.phone,
                p.email,
                "Présent" if p.attended else "Absent",
                result_labels.get(p.result, p.result),
            ]
        )

    for col in ws.columns:
        width = max((len(str(c.value)) for c in col if c.value), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 12), 35)

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    filename = f"participants_{session.reference.replace('/', '-')}.xlsx"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


# ===========================================================================
# AJAX
# ===========================================================================


@login_required
@require_POST
def toggle_attendance(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if not request.user.profile.can_edit_scores():
        return JsonResponse({"error": "Permission refusée"}, status=403)
    day_key = request.POST.get("day_key")
    present = request.POST.get("present", "true").lower() == "true"
    if day_key:
        participant.set_attendance_for_day(day_key, present)
    else:
        participant.attended = present
        participant.save(update_fields=["attended"])
    return JsonResponse(
        {
            "participant_id": participant.pk,
            "attended": participant.attended,
            "result": participant.result,
        }
    )


@login_required
@require_POST
def update_score(request, pk):
    participant = get_object_or_404(Participant, pk=pk)
    if not request.user.profile.can_edit_scores():
        return JsonResponse({"error": "Permission refusée"}, status=403)
    eval_type = participant.session.formation.evaluation_type
    kwargs = {}
    if eval_type in ["theory_only", "both"] and "score_theory" in request.POST:
        try:
            val = request.POST["score_theory"]
            kwargs["score_theory"] = float(val) if val else None
            kwargs["set_theory"] = True
        except ValueError:
            return JsonResponse({"error": "Note théorique invalide"}, status=400)
    if eval_type in ["practice_only", "both"] and "score_practice" in request.POST:
        try:
            val = request.POST["score_practice"]
            kwargs["score_practice"] = float(val) if val else None
            kwargs["set_practice"] = True
        except ValueError:
            return JsonResponse({"error": "Note pratique invalide"}, status=400)
    primary = sync_evaluation_scores(participant, **kwargs)
    # Reflect the value on whichever record the request came from (may be
    # a day copy) so the AJAX response updates the field the user is on.
    participant.refresh_from_db(fields=["score_theory", "score_practice"])
    return JsonResponse(
        {
            "participant_id": participant.pk,
            "score_theory": str(participant.score_theory or ""),
            "score_practice": str(participant.score_practice or ""),
            "result": participant.result,
        }
    )


# ===========================================================================
# Fill rate + cross-session participant list
# ===========================================================================


@login_required
def fill_rate(request):
    sessions_qs = (
        Session.objects.filter(is_primary=True)
        .select_related("formation", "client", "trainer")
        .exclude(status="cancelled")
        .order_by("-date_start")
    )
    session_list = list(sessions_qs)
    fill_rates = [s.fill_rate for s in session_list if s.capacity > 0]
    avg_fill_rate = round(sum(fill_rates) / len(fill_rates), 1) if fill_rates else 0
    return render(
        request,
        "formations/fill_rate.html",
        {
            "sessions": session_list,
            "total_sessions": len(session_list),
            "avg_fill_rate": avg_fill_rate,
            "full_sessions": sum(1 for s in session_list if s.available_spots == 0),
            "total_participants": sum(s.participant_count for s in session_list),
        },
    )


PARTICIPANT_SORT = {
    "last_name": "last_name",
    "session__reference": "session__reference",
    "session__formation__title": "session__formation__title",
    "job_title": "job_title",
    "employer": "employer",
    "attended": "attended",
    "certificate_issued": "certificate_issued",
}


@login_required
def participant_list(request):
    sort = request.GET.get("sort", "last_name")
    dir_ = request.GET.get("dir", "asc")
    if sort not in PARTICIPANT_SORT:
        sort = "last_name"
    db_field = PARTICIPANT_SORT[sort]

    # Only primary session participants in the global list
    qs = (
        Participant.objects.filter(session__is_primary=True)
        .select_related("session", "session__formation", "employer_client")
        .order_by(db_field if dir_ == "asc" else "-" + db_field)
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(first_name_ar__icontains=q)
            | Q(last_name_ar__icontains=q)
            | Q(employer__icontains=q)
            | Q(session__reference__icontains=q)
        )
    cert = request.GET.get("cert", "")
    if cert == "yes":
        qs = qs.filter(certificate_issued=True)
    elif cert == "no":
        qs = qs.filter(certificate_issued=False)
    gender = request.GET.get("gender", "").strip()
    if gender:
        qs = qs.filter(gender=gender)
    attended = request.GET.get("attended", "").strip()
    if attended == "yes":
        qs = qs.filter(attended=True)
    elif attended == "no":
        qs = qs.filter(attended=False)
    formation = request.GET.get("formation", "").strip()
    if formation.isdigit():
        qs = qs.filter(session__formation_id=formation)
    session_ref = request.GET.get("session", "").strip()
    if session_ref:
        qs = qs.filter(session__reference__icontains=session_ref)
    dob_from = request.GET.get("dob_from", "").strip()
    if dob_from:
        qs = qs.filter(date_of_birth__gte=dob_from)
    dob_to = request.GET.get("dob_to", "").strip()
    if dob_to:
        qs = qs.filter(date_of_birth__lte=dob_to)

    result_filter = request.GET.get("result", "")
    if result_filter:
        qs = [p for p in qs if p.result == result_filter]

    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/participant_list.html",
        {
            "page_obj": page_obj,
            "sort": sort,
            "dir": dir_,
            "gender_choices": Participant.GENDER_CHOICES,
            "formations": Formation.objects.order_by("title"),
            "filters": {
                "q": q,
                "cert": cert,
                "result": result_filter,
                "gender": gender,
                "attended": attended,
                "formation": formation,
                "session": session_ref,
                "dob_from": dob_from,
                "dob_to": dob_to,
            },
        },
    )
