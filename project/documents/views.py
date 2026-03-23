from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.db import transaction

from formations.models import Session, Participant
from .models import GeneratedDocument
from .forms import AttendanceSheetForm, AttestationGenerationForm, CommitteeForm
from .utils import check_document_requirements


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_available_document_types(session):
    pre = ["candidate_list", "attendance_sheet", "mission_order", "nominal_list"]
    post = ["evaluation_list", "deliberation_report", "evaluation_sheet", "attestation"]
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
    errors = check_document_requirements(session, "candidate_list")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)
    return redirect("documents:print_candidate_list", session_pk=session.pk)


@login_required
def generate_attendance_sheet_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    if request.method == "POST":
        form = AttendanceSheetForm(request.POST, session=session)
        if form.is_valid():
            day_number = form.cleaned_data["day_number"]
            errors = check_document_requirements(session, "attendance_sheet")
            if errors:
                messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
                return redirect("documents:dashboard", session_pk=session.pk)
            return redirect(
                f"{request.build_absolute_uri('/')[:-1]}/documents/sessions/{session_pk}/print/attendance-sheet/?day={day_number}"
            )
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
    return redirect("documents:print_deliberation_report", session_pk=session.pk)


@login_required
def set_committee_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)
    if not request.user.profile.can_manage_sessions():
        raise PermissionDenied()
    if request.method == "POST":
        form = CommitteeForm(request.POST, session=session)
        if form.is_valid():
            session.committee_members = form.cleaned_data["committee_members"]
            session.save(update_fields=["committee_members"])
            messages.success(request, "Membres du comité mis à jour.")
            return redirect("documents:dashboard", session_pk=session.pk)
    else:
        form = CommitteeForm(session=session)
    return render(
        request, "documents/committee_form.html", {"form": form, "session": session}
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
    # Reuse evaluation list for individual (or add a dedicated print view later)
    return redirect("documents:print_evaluation_list", session_pk=session.pk)


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
    try:
        with open(doc.file.path, "rb") as f:
            response = HttpResponse(
                f.read(),
                content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{doc.get_download_filename()}"'
            )
            return response
    except FileNotFoundError:
        messages.error(request, "Fichier introuvable sur le serveur.")
        return redirect("documents:dashboard", session_pk=doc.session.pk)
