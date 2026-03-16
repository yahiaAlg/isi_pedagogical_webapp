from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import PermissionDenied
from django.db import transaction

from formations.models import Session, Participant
from .models import GeneratedDocument
from .forms import AttendanceSheetForm, AttestationGenerationForm, CommitteeForm
from .utils import (
    generate_candidate_list,
    generate_attendance_sheet,
    generate_mission_order,
    generate_nominal_list,
    generate_evaluation_list,
    generate_deliberation_report,
    generate_evaluation_sheet,
    generate_attestation,
    check_document_requirements,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_available_document_types(session):
    """
    Spec §12.3:
      Pre-session docs  → status in {planned, in_progress} AND participant_count > 0
      Post-session docs → status = completed
    """
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
        request,
        "documents/history.html",
        {
            "session": session,
            "documents": documents,
        },
    )


# ---------------------------------------------------------------------------
# Pre-session documents
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

    try:
        with transaction.atomic():
            file_path = generate_candidate_list(session)
            doc = GeneratedDocument.objects.create(
                session=session,
                doc_type="candidate_list",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(request, "Liste des candidats générée.")
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


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
            try:
                with transaction.atomic():
                    file_path = generate_attendance_sheet(session, day_number)
                    doc = GeneratedDocument.objects.create(
                        session=session,
                        doc_type="attendance_sheet",
                        day_number=day_number,
                        file=file_path,
                        generated_by=request.user,
                    )
                    doc.invalidate_previous()
                    messages.success(
                        request, f"Feuille présence Jour {day_number} générée."
                    )
                    return redirect("documents:download", pk=doc.pk)
            except Exception as e:
                messages.error(request, f"Erreur: {str(e)}")
    else:
        form = AttendanceSheetForm(session=session)

    return render(
        request,
        "documents/attendance_sheet_form.html",
        {
            "form": form,
            "session": session,
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

    try:
        with transaction.atomic():
            file_path = generate_mission_order(session)
            doc = GeneratedDocument.objects.create(
                session=session,
                doc_type="mission_order",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(request, "Ordre de mission généré.")
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


@login_required
def generate_nominal_list_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)

    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    errors = check_document_requirements(session, "nominal_list")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    try:
        with transaction.atomic():
            file_path = generate_nominal_list(session)
            doc = GeneratedDocument.objects.create(
                session=session,
                doc_type="nominal_list",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(request, "Liste nominale générée.")
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


# ---------------------------------------------------------------------------
# Post-session documents
# ---------------------------------------------------------------------------


@login_required
def generate_evaluation_list_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)

    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    errors = check_document_requirements(session, "evaluation_list")
    if errors:
        messages.error(request, f"Impossible de générer: {'; '.join(errors)}")
        return redirect("documents:dashboard", session_pk=session.pk)

    try:
        with transaction.atomic():
            file_path = generate_evaluation_list(session)
            doc = GeneratedDocument.objects.create(
                session=session,
                doc_type="evaluation_list",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(request, "Liste des notes générée.")
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


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

    try:
        with transaction.atomic():
            file_path = generate_deliberation_report(session)
            doc = GeneratedDocument.objects.create(
                session=session,
                doc_type="deliberation_report",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(request, "محضر مداولات نهاية التكوين généré.")
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


@login_required
def set_committee_view(request, session_pk):
    """
    Committee members are session data — guard with can_manage_sessions(),
    not can_generate_documents() (spec §9.2).
    """
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
        request,
        "documents/committee_form.html",
        {
            "form": form,
            "session": session,
        },
    )


# ---------------------------------------------------------------------------
# Individual participant documents
# ---------------------------------------------------------------------------


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

    try:
        with transaction.atomic():
            file_path = generate_evaluation_sheet(participant)
            doc = GeneratedDocument.objects.create(
                session=session,
                participant=participant,
                doc_type="evaluation_sheet",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()
            messages.success(
                request, f"Fiche d'évaluation pour {participant.full_name} générée."
            )
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


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

    try:
        with transaction.atomic():
            if not participant.certificate_number:
                from formations.utils import assign_certificate_number

                assign_certificate_number(participant)
                participant.refresh_from_db()

            file_path = generate_attestation(participant)
            doc = GeneratedDocument.objects.create(
                session=session,
                participant=participant,
                doc_type="attestation",
                file=file_path,
                generated_by=request.user,
            )
            doc.invalidate_previous()

            participant.certificate_issued = True
            participant.save(update_fields=["certificate_issued"])

            messages.success(
                request, f"Attestation pour {participant.full_name} générée."
            )
            return redirect("documents:download", pk=doc.pk)
    except Exception as e:
        messages.error(request, f"Erreur: {str(e)}")
    return redirect("documents:dashboard", session_pk=session.pk)


# ---------------------------------------------------------------------------
# Batch attestations
# ---------------------------------------------------------------------------


@login_required
def generate_batch_attestations_view(request, session_pk):
    session = get_object_or_404(Session, pk=session_pk)

    if not request.user.profile.can_generate_documents():
        raise PermissionDenied()

    if request.method == "POST":
        form = AttestationGenerationForm(request.POST, session=session)
        if form.is_valid():
            selected = []
            for field_name, value in form.cleaned_data.items():
                if field_name.startswith("participant_") and value:
                    pk = field_name.replace("participant_", "")
                    try:
                        p = session.participant_set.get(pk=pk)
                        if p.result == "passed":
                            selected.append(p)
                    except Participant.DoesNotExist:
                        continue

            if not selected:
                messages.warning(request, "Aucun participant sélectionné.")
                return redirect("documents:dashboard", session_pk=session.pk)

            generated_count = 0
            for participant in selected:
                errors = check_document_requirements(
                    session, "attestation", participant
                )
                if errors:
                    messages.warning(
                        request, f"{participant.full_name}: {'; '.join(errors)}"
                    )
                    continue
                try:
                    with transaction.atomic():
                        if not participant.certificate_number:
                            from formations.utils import assign_certificate_number

                            assign_certificate_number(participant)
                            participant.refresh_from_db()

                        file_path = generate_attestation(participant)
                        doc = GeneratedDocument.objects.create(
                            session=session,
                            participant=participant,
                            doc_type="attestation",
                            file=file_path,
                            generated_by=request.user,
                        )
                        doc.invalidate_previous()

                        participant.certificate_issued = True
                        participant.save(update_fields=["certificate_issued"])
                        generated_count += 1
                except Exception as e:
                    messages.error(
                        request, f"Erreur ({participant.full_name}): {str(e)}"
                    )

            if generated_count:
                messages.success(
                    request, f"{generated_count} attestation(s) générée(s)."
                )
            return redirect("documents:dashboard", session_pk=session.pk)
    else:
        form = AttestationGenerationForm(session=session)

    return render(
        request,
        "documents/batch_attestations.html",
        {
            "form": form,
            "session": session,
        },
    )


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


@login_required
def download_document(request, pk):
    """
    Spec §9.2 — can download: Admin, Staff, Trainer (own sessions), Viewer.
    Trainer "own session" check requires Trainer→User FK which the current
    Trainer model does not have.  Until that FK is added, all trainer_or_above
    users may download (least-breaking safe default).
    """
    doc = get_object_or_404(GeneratedDocument, pk=pk)
    profile = request.user.profile

    # Admin / Staff → always allowed
    # Trainer / Viewer → allowed (session ownership narrowing needs Trainer.user FK)
    if not (profile.can_generate_documents() or profile.is_trainer_or_above()):
        raise PermissionDenied()

    if not doc.file:
        messages.error(request, "Fichier non trouvé.")
        return redirect("documents:dashboard", session_pk=doc.session.pk)

    try:
        with open(doc.file.path, "rb") as f:
            response = HttpResponse(
                f.read(),
                content_type=(
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                ),
            )
            response["Content-Disposition"] = (
                f'attachment; filename="{doc.get_download_filename()}"'
            )
            return response
    except FileNotFoundError:
        messages.error(request, "Fichier introuvable sur le serveur.")
        return redirect("documents:dashboard", session_pk=doc.session.pk)
