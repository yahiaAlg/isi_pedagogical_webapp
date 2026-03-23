from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.db.models import Count, Q
from django.utils import timezone

from .models import Category, Formation, Session, Participant
from .forms import (
    CategoryForm,
    FormationForm,
    SessionForm,
    ParticipantForm,
    SessionStatusForm,
    AttendanceForm,
    ScoreForm,
    ExamScoreForm,
    ParticipantImportForm,
)
from .utils import validate_session_transition, import_participants_from_file


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
    categories = categories.order_by(db_field if dir_ == "asc" else "-" + db_field)
    return render(
        request,
        "formations/category_list.html",
        {"categories": categories, "sort": sort, "dir": dir_},
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
# Formation
# ===========================================================================

FORMATION_SORT_MAP = {
    "code": "code",
    "title": "title",
    "category__name": "category__name",
    "duration_days": "duration_days",
    "base_price": "base_price",
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
    qs = Formation.objects.select_related("category").annotate(
        sessions_total=Count("session")
    )
    qs = qs.order_by(db_field if dir_ == "asc" else "-" + db_field)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/formation_list.html",
        {"page_obj": page_obj, "sort": sort, "dir": dir_},
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
    data = {
        "max_participants": formation.max_participants,
        "duration_days": formation.duration_days,
        "today": today,
        "last_client_id": last.client_id if last else None,
        "last_client_name": last.client.name if last else None,
        "last_trainer_id": last.trainer_id if last else None,
        "last_trainer_name": last.trainer.full_name if last else None,
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
    qs = qs.order_by(sort if dir_ == "asc" else "-" + sort)
    page_obj = Paginator(qs, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/session_list.html",
        {"page_obj": page_obj, "sort": sort, "dir": dir_},
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
    return render(
        request,
        "formations/session_detail.html",
        {
            "session": session,
            "participants": participants,
            "child_sessions": child_sessions,
        },
    )


@login_required
def session_create(request):
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_list")
    if request.method == "POST":
        form = SessionForm(request.POST)
        if form.is_valid():
            session = form.save()
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
                # Pre-select last used client/trainer for this formation
                last = (
                    formation.session_set.filter(is_primary=True)
                    .order_by("-date_start")
                    .first()
                )
                if last:
                    initial["client"] = last.client
                    initial["trainer"] = last.trainer
                    initial["location_type"] = last.location_type
                    initial["room"] = last.room
                    initial["external_location"] = last.external_location
            except Formation.DoesNotExist:
                pass
        form = SessionForm(initial=initial)
    return render(
        request,
        "formations/session_form.html",
        {"form": form, "title": "Nouvelle session"},
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
            session = form.save()
            messages.success(request, f'Session "{session.reference}" modifiée.')
            return redirect("formations:session_detail", pk=session.pk)
    else:
        form = SessionForm(instance=session)
    return render(
        request,
        "formations/session_form.html",
        {"form": form, "session": session, "title": "Modifier session"},
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
    if request.method == "POST":
        form = ScoreForm(request.POST, session=session)
        if form.is_valid():
            eval_type = session.formation.evaluation_type
            for participant in session.participant_set.all():
                changed = []
                if eval_type in ["theory_only", "both"]:
                    participant.score_theory = form.cleaned_data.get(
                        f"theory_{participant.id}"
                    )
                    changed.append("score_theory")
                if eval_type in ["practice_only", "both"]:
                    participant.score_practice = form.cleaned_data.get(
                        f"practice_{participant.id}"
                    )
                    changed.append("score_practice")
                if changed:
                    participant.save(update_fields=changed)
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
            f"Notes d'examen pré-remplies à {session.formation.max_score / 2:g} / {session.formation.max_score:g}.",
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
    changed = []
    if eval_type in ["theory_only", "both"] and "score_theory" in request.POST:
        try:
            val = request.POST["score_theory"]
            participant.score_theory = float(val) if val else None
            changed.append("score_theory")
        except ValueError:
            return JsonResponse({"error": "Note théorique invalide"}, status=400)
    if eval_type in ["practice_only", "both"] and "score_practice" in request.POST:
        try:
            val = request.POST["score_practice"]
            participant.score_practice = float(val) if val else None
            changed.append("score_practice")
        except ValueError:
            return JsonResponse({"error": "Note pratique invalide"}, status=400)
    if changed:
        participant.save(update_fields=changed)
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
    result_filter = request.GET.get("result", "")
    if result_filter:
        qs = [p for p in qs if p.result == result_filter]
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "formations/participant_list.html",
        {"page_obj": page_obj, "sort": sort, "dir": dir_},
    )
