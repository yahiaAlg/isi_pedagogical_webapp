from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from .models import Category, Formation, Session, Participant
from .forms import (
    CategoryForm,
    FormationForm,
    SessionForm,
    ParticipantForm,
    SessionStatusForm,
    AttendanceForm,
    ScoreForm,
    ParticipantImportForm,
)
from .utils import validate_session_transition, import_participants_from_file


# ===========================================================================
# Category — Admin only (spec §9.2)
# ===========================================================================


@login_required
def category_list(request):
    if not request.user.profile.is_admin():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect("formations:formation_list")
    categories = Category.objects.all().order_by("name")
    return render(request, "formations/category_list.html", {"categories": categories})


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
        {
            "form": form,
            "title": "Nouvelle catégorie",
        },
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
        {
            "form": form,
            "category": category,
            "title": "Modifier catégorie",
        },
    )


# ===========================================================================
# Formation — Admin only for create/edit (spec §9.2)
# ===========================================================================


@login_required
def formation_list(request):
    formations = Formation.objects.select_related("category").order_by("title")
    paginator = Paginator(formations, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "formations/formation_list.html", {"page_obj": page_obj})


@login_required
def formation_detail(request, pk):
    formation = get_object_or_404(Formation, pk=pk)
    sessions = formation.session_set.order_by("-date_start")[:10]
    return render(
        request,
        "formations/formation_detail.html",
        {
            "formation": formation,
            "sessions": sessions,
        },
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
            return redirect("formations:formation_detail", pk=formation.pk)
    else:
        form = FormationForm()
    return render(
        request,
        "formations/formation_form.html",
        {
            "form": form,
            "title": "Nouvelle formation",
        },
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
        {
            "form": form,
            "formation": formation,
            "title": "Modifier formation",
        },
    )


# ===========================================================================
# Session — Staff + Admin (spec §9.2)
# ===========================================================================


@login_required
def session_list(request):
    sessions = Session.objects.select_related(
        "formation", "client", "trainer"
    ).order_by("-date_start")
    paginator = Paginator(sessions, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "formations/session_list.html", {"page_obj": page_obj})


@login_required
def session_detail(request, pk):
    session = get_object_or_404(Session, pk=pk)
    participants = session.participant_set.order_by("last_name", "first_name")
    return render(
        request,
        "formations/session_detail.html",
        {
            "session": session,
            "participants": participants,
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
            messages.success(request, f'Session "{session.reference}" créée.')
            return redirect("formations:session_detail", pk=session.pk)
    else:
        form = SessionForm()
    return render(
        request,
        "formations/session_form.html",
        {
            "form": form,
            "title": "Nouvelle session",
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
            session = form.save()
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
        },
    )


@login_required
def session_status(request, pk):
    """Status transition with validation (spec §12.2)."""
    session = get_object_or_404(Session, pk=pk)
    if not request.user.profile.can_manage_sessions():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)

    # Archive requires admin only
    if request.method == "POST":
        form = SessionStatusForm(request.POST, session=session)
        if form.is_valid():
            new_status = form.cleaned_data["new_status"]

            # Spec §12.2 — archived: Admin only
            if new_status == "archived" and not request.user.profile.is_admin():
                messages.error(request, "L'archivage est réservé aux administrateurs.")
                return redirect("formations:session_detail", pk=pk)

            # Business rule validation
            errors = validate_session_transition(session, new_status)
            if errors:
                for error in errors:
                    messages.error(request, error)
                return redirect("formations:session_detail", pk=pk)

            session.status = new_status
            if new_status == "cancelled":
                session.cancellation_reason = form.cleaned_data["cancellation_reason"]
            session.save()
            messages.success(
                request, f"Statut mis à jour : {session.get_status_display()}."
            )
            return redirect("formations:session_detail", pk=pk)
    else:
        form = SessionStatusForm(session=session)

    return render(
        request,
        "formations/session_status_form.html",
        {
            "form": form,
            "session": session,
        },
    )


@login_required
def session_attendance(request, pk):
    """Per-day attendance recording (spec §13.2)."""
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
        {
            "form": form,
            "session": session,
        },
    )


@login_required
def session_scores(request, pk):
    """Score entry (spec §9.2 — staff + trainers for own sessions)."""
    session = get_object_or_404(Session, pk=pk)
    profile = request.user.profile

    if not profile.can_edit_scores():
        messages.error(request, "Vous n'avez pas les permissions nécessaires.")
        return redirect("formations:session_detail", pk=pk)

    if request.method == "POST":
        form = ScoreForm(request.POST, session=session)
        if form.is_valid():
            eval_type = session.formation.evaluation_type
            for participant in session.participant_set.all():
                changed = []
                if eval_type in ["theory_only", "both"]:
                    score = form.cleaned_data.get(f"theory_{participant.id}")
                    participant.score_theory = score
                    changed.append("score_theory")
                if eval_type in ["practice_only", "both"]:
                    score = form.cleaned_data.get(f"practice_{participant.id}")
                    participant.score_practice = score
                    changed.append("score_practice")
                if changed:
                    participant.save(update_fields=changed)
            messages.success(request, "Notes enregistrées.")
            return redirect("formations:session_detail", pk=pk)
    else:
        form = ScoreForm(session=session)

    return render(
        request,
        "formations/session_scores.html",
        {
            "form": form,
            "session": session,
        },
    )


# ===========================================================================
# Participant — Staff + Admin (spec §9.2)
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
            participant.save()
            messages.success(request, f'Participant "{participant.full_name}" ajouté.')
            return redirect("formations:session_detail", pk=session_pk)
    else:
        form = ParticipantForm(session=session)

    return render(
        request,
        "formations/participant_form.html",
        {
            "form": form,
            "session": session,
            "title": "Nouveau participant",
        },
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
        participant.delete()
        messages.success(request, f'Participant "{name}" supprimé.')
        return redirect("formations:session_detail", pk=session.pk)

    return render(
        request,
        "formations/participant_confirm_delete.html",
        {
            "participant": participant,
            "session": session,
        },
    )


@login_required
def participant_import(request, session_pk):
    """
    CSV/Excel import with spec §13.3 rules:
    stop at capacity, skip duplicates, report 3 counts.
    """
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
        {
            "form": form,
            "session": session,
        },
    )


# ===========================================================================
# AJAX endpoints (spec §18 — minimal AJAX for attendance + scores)
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
# Fill rate + Participant list — sidebar views (added to match urls.py)
# ===========================================================================


@login_required
def fill_rate(request):
    """Fill-rate analytics table for all non-cancelled sessions."""
    sessions_qs = (
        Session.objects.select_related("formation", "client", "trainer")
        .exclude(status="cancelled")
        .order_by("-date_start")
    )

    session_list = list(sessions_qs)
    fill_rates = [s.fill_rate for s in session_list if s.capacity > 0]
    avg_fill_rate = round(sum(fill_rates) / len(fill_rates), 1) if fill_rates else 0
    full_sessions = sum(1 for s in session_list if s.available_spots == 0)
    total_participants = sum(s.participant_count for s in session_list)

    return render(
        request,
        "formations/fill_rate.html",
        {
            "sessions": session_list,
            "total_sessions": len(session_list),
            "avg_fill_rate": avg_fill_rate,
            "full_sessions": full_sessions,
            "total_participants": total_participants,
        },
    )


@login_required
def participant_list(request):
    """Cross-session participant list with search + result/cert filters."""
    from django.db.models import Q

    qs = Participant.objects.select_related(
        "session", "session__formation", "employer_client"
    ).order_by("-session__date_start", "last_name")

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

    # result is a @property — filter in Python after evaluating queryset
    result_filter = request.GET.get("result", "")
    if result_filter:
        qs = [p for p in qs if p.result == result_filter]

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "formations/participant_list.html",
        {
            "page_obj": page_obj,
        },
    )


# ===========================================================================
# Delete views — Admin only
# ===========================================================================


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
