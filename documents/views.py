import logging

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied

from formations.models import Session, Participant
from .models import GeneratedDocument, HotEvaluation, EmployeeMissionOrder
from .forms import (
    AttendanceSheetForm,
    AttestationGenerationForm,
    CommitteeForm,
    HotEvaluationForm,
    EmployeeMissionOrderForm,
)
from .utils import check_document_requirements
from .notifications import notify_pv_generated

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_available_document_types(session):
    # Spec v2.2 — Final Nominal List (Doc 07) is a post-session document: it
    # carries each participant's exam result and is generated immediately
    # before the Deliberation Report, which it feeds into.
    pre = ["candidate_list", "attendance_sheet", "mission_order"]
    post = [
        "evaluation_list",
        "nominal_list",
        "deliberation_report",
        "evaluation_sheet",
        "attestation",
    ]
    if session.status in ("planned", "in_progress") and session.participant_count > 0:
        return pre
    if session.status == "completed":
        return pre + post
    return []


# ---------------------------------------------------------------------------
# Dashboard / history
# ---------------------------------------------------------------------------


@login_required
def document_dashboard(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    available_docs = get_available_document_types(session)
    existing_docs = GeneratedDocument.objects.filter(
        session=session, is_latest=True
    ).select_related("participant")
    docs_by_type = {}
    for doc in existing_docs:
        key = doc.doc_type
        if doc.day_number:
            key += f"_day_{doc.day_number}"
        if doc.participant:
            key += f"_participant_{doc.participant.pk}"
        docs_by_type[key] = doc

    return render(
        request,
        "documents/dashboard.html",
        {
            "session": session,
            "available_docs": available_docs,
            "docs_by_type": docs_by_type,
            "participants": session.participant_set.all(),
        },
    )


@login_required
def document_history(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    documents = (
        GeneratedDocument.objects.filter(session=session)
        .select_related("participant", "generated_by")
        .order_by("-generated_at")
    )
    return render(
        request, "documents/history.html", {"session": session, "documents": documents}
    )


# ---------------------------------------------------------------------------
# Generate views — now redirect to print views
# ---------------------------------------------------------------------------


@login_required
def generate_candidate_list_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    # Spec — a blank/manual version can always be printed, even before
    # candidates are registered, for on-site completion by hand.
    blank_mode = request.GET.get("mode") == "blank"
    if not blank_mode:
        errors = check_document_requirements(session, "candidate_list")
        if errors:
            messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
            return redirect("documents:dashboard", session_pk=session.pk)
    url = reverse("documents:print_candidate_list", kwargs={"session_pk": session.pk})
    if blank_mode:
        url += "?mode=blank"
    return redirect(url)


@login_required
def generate_attendance_sheet_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    # Spec — a blank/manual version (all days can share one blank sheet)
    # skips the day-picker and participant requirement entirely.
    if request.GET.get("mode") == "blank":
        url = reverse(
            "documents:print_attendance_sheet", kwargs={"session_pk": session_pk}
        )
        day_number = request.GET.get("day", 1)
        return redirect(f"{url}?day={day_number}&mode=blank")

    if request.method == "POST":
        form = AttendanceSheetForm(request.POST, session=session)
        if form.is_valid():
            day_number = form.cleaned_data["day_number"]
            errors = check_document_requirements(session, "attendance_sheet")
            if errors:
                messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
                return redirect("documents:dashboard", session_pk=session.pk)
            url = reverse(
                "documents:print_attendance_sheet", kwargs={"session_pk": session_pk}
            )
            return redirect(f"{url}?day={day_number}")
    else:
        form = AttendanceSheetForm(session=session)

    day_range = range(1, session.duration_days + 1)
    return render(
        request,
        "documents/attendance_sheet_form.html",
        {
            "form": form,
            "session": session,
            "day_range": day_range,
        },
    )


@login_required
def generate_mission_order_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "mission_order")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)
    return redirect("documents:print_mission_order", session_pk=session.pk)


@login_required
def generate_nominal_list_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "nominal_list")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)
    return redirect("documents:print_nominal_list", session_pk=session.pk)


@login_required
def generate_evaluation_list_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "evaluation_list")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)
    return redirect("documents:print_evaluation_list", session_pk=session.pk)


@login_required
def generate_deliberation_report_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    if not session.committee_members or len(session.committee_members) < 2:
        return redirect("documents:set_committee", session_pk=session.pk)
    errors = check_document_requirements(session, "deliberation_report")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    # Allocate the PV number now (no-op if the nominal list already did) so
    # it's already fixed by the time the notification email goes out.
    session.assign_pv_number()
    notify_pv_generated(session, generated_by=request.user, request=request)

    return redirect("documents:print_deliberation_report", session_pk=session.pk)


@login_required
def set_committee_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_manage_sessions():
        raise PermissionDenied()

    from core.models import PVDefaultSignatory

    if request.method == "POST":
        form = CommitteeForm(request.POST, session=session)
        if form.is_valid():
            session.committee_members = form.cleaned_data["committee_members"]
            session.save(update_fields=["committee_members"])
            messages.success(request, "Membres du comité mis à jour.")
            return redirect("documents:dashboard", session_pk=session.pk)
    else:
        form = CommitteeForm(session=session)

    # Build the initial rows shown in the dynamic table:
    # 1) existing committee members already saved on this session (if any)
    # 2) otherwise: default signatories from Settings (e.g. directors) +
    #    the trainer pulled live from the session (never from Settings) +
    #    one blank row for the client's company representative (always
    #    typed fresh on each PV, never stored as a default).
    if session.committee_members:
        initial_rows = session.committee_members
    else:
        initial_rows = [
            {"name": s.full_name, "role": s.role}
            for s in PVDefaultSignatory.objects.filter(is_active=True)
        ]
        initial_rows.append(
            {"name": session.trainer.full_name, "role": "أستاذ"}
        )
        initial_rows.append({"name": "", "role": "ممثل الشركة المتعاقد معها"})

    return render(
        request,
        "documents/committee_form.html",
        {"form": form, "session": session, "initial_rows": initial_rows},
    )


@login_required
def generate_evaluation_sheet_view(request, participant_pk):
    participant = get_object_or_404(Participant, pk=participant_pk)
    session = participant.session
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "evaluation_sheet", participant)
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    # Nothing transcribed yet for this candidate's paper survey -> send
    # the operator to fill it in first; the dedicated print view (blank
    # or filled) is reached from there / from the dashboard afterwards.
    evaluation = getattr(participant, "hot_evaluation", None)
    if not evaluation or not evaluation.is_complete:
        return redirect(
            "documents:evaluation_sheet_form", participant_pk=participant.pk
        )
    return redirect(
        "documents:print_evaluation_sheet", participant_pk=participant.pk
    )


@login_required
def evaluation_sheet_form_view(request, participant_pk):
    """
    Transcription screen for the paper « Fiche d'évaluation à chaud » —
    enter what the candidate ticked by hand so the filled print view can
    reproduce it. The blank version (for printing and handing to the
    candidate in the first place) doesn't need this form at all — see
    documents:print_evaluation_sheet?mode=blank.
    """
    participant = get_object_or_404(Participant, pk=participant_pk)
    session = participant.session
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "evaluation_sheet", participant)
    if errors:
        messages.error(request, f"Impossible de saisir: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    evaluation, _ = HotEvaluation.objects.get_or_create(participant=participant)

    if request.method == "POST":
        form = HotEvaluationForm(request.POST, instance=evaluation)
        if form.is_valid():
            evaluation = form.save(commit=False)
            evaluation.filled_by = request.user
            evaluation.save()
            messages.success(
                request,
                f"Fiche d'évaluation à chaud de {participant.full_name} enregistrée.",
            )
            return redirect(
                "documents:print_evaluation_sheet", participant_pk=participant.pk
            )
    else:
        form = HotEvaluationForm(instance=evaluation)

    return render(
        request,
        "documents/evaluation_sheet_form.html",
        {"form": form, "participant": participant, "session": session},
    )


@login_required
def generate_attestation_view(request, participant_pk):
    participant = get_object_or_404(Participant, pk=participant_pk)
    session = participant.session
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()
    errors = check_document_requirements(session, "attestation", participant)
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    # Same pattern as every other generate_*_view: no server-side PDF file,
    # just hand off to the HTML print view (documents/print/attestation.html)
    # — the certificate number gets auto-assigned there, and the browser's
    # own Print / Save-as-PDF produces the document.
    return redirect("documents:print_attestation", participant_pk=participant.pk)


@login_required
def generate_batch_attestations_view(request, session_pk):

    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    if request.method == "POST":
        form = AttestationGenerationForm(request.POST, session=session)
        if form.is_valid():
            return redirect("documents:print_batch_attestations", session_pk=session.pk)
    else:
        form = AttestationGenerationForm(session=session)

    return render(
        request, "documents/batch_attestations.html", {"form": form, "session": session}
    )


# ---------------------------------------------------------------------------
# Download (kept for history records)
# ---------------------------------------------------------------------------


@login_required
def download_document(request, pk):
    doc = get_object_or_404(GeneratedDocument, pk=pk)
    if not (
        request.user.profile.can_generate_documents()
        or request.user.profile.is_trainer_or_above()
    ):
        raise PermissionDenied()
    if not doc.file:
        messages.error(request, "Fichier non trouvé.")
        return redirect("documents:dashboard", session_pk=doc.session.pk)
    # fix: content type must match the actual stored file — the attestation
    # is stored as a QR-stamped .pdf while every other doc_type is a .docx.
    content_type = (
        "application/pdf"
        if doc.file.name.lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    try:
        with open(doc.file.path, "rb") as f:
            response = HttpResponse(f.read(), content_type=content_type)
            response["Content-Disposition"] = (
                f'attachment; filename="{doc.get_download_filename()}"'
            )
            return response
    except FileNotFoundError:
        messages.error(request, "Fichier introuvable sur le serveur.")
        return redirect("documents:dashboard", session_pk=doc.session.pk)


# ---------------------------------------------------------------------------
# Employee mission orders — global, session-independent (quick access bar)
# ---------------------------------------------------------------------------
@login_required
def employee_mission_order_list_view(request):
    """List + create page for standalone (non-formateur) employee mission
    orders. Reachable from the sidebar's Documents quick-access, not from
    any specific session's document dashboard — see
    EmployeeMissionOrder / core.sequencing.allocate_mission_order_number
    for why this is deliberately separate."""
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    if request.method == "POST":
        form = EmployeeMissionOrderForm(request.POST, user=request.user)
        if form.is_valid():
            order = form.save(commit=False)
            order.created_by = request.user
            order.full_clean()
            order.save()
            order.assign_archive_number()
            return redirect("documents:print_employee_mission_order", pk=order.pk)
    else:
        form = EmployeeMissionOrderForm(user=request.user)

    orders = EmployeeMissionOrder.objects.select_related("created_by").all()[:100]
    return render(
        request,
        "documents/employee_mission_order_list.html",
        {"form": form, "orders": orders},
    )


@login_required
def employee_mission_order_edit_view(request, pk):
    """Edit an existing standalone employee mission order — the only way
    to reach `archive_number` (admin-only field, see
    EmployeeMissionOrderForm), so an admin can hard-code/override its N°
    d'archivage the same way Session.pv_number / mission_order_number and
    Participant.certificate_number can be overridden from their own edit
    forms. Regular fields stay editable here too."""
    order = get_object_or_404(EmployeeMissionOrder, pk=pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    if request.method == "POST":
        form = EmployeeMissionOrderForm(request.POST, instance=order, user=request.user)
        if form.is_valid():
            order = form.save()
            messages.success(
                request, f"Ordre de mission « {order.employee_name} » modifié."
            )
            return redirect("documents:employee_mission_order_list")
    else:
        form = EmployeeMissionOrderForm(instance=order, user=request.user)

    return render(
        request,
        "documents/employee_mission_order_form.html",
        {"form": form, "order": order},
    )
