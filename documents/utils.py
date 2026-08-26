import os
from datetime import timedelta  # fix: timezone.timedelta does not exist
from django.conf import settings
from core.models import InstituteInfo


def check_document_requirements(session, doc_type, participant=None):
    """Return list of blocking error strings. Empty list = generation allowed."""
    errors = []

    if not session.formation_id:
        errors.append("Formation manquante")
    if not session.client_id:
        errors.append("Client manquant")
    if not session.trainer_id:
        errors.append("Formateur manquant")

    institute = InstituteInfo.get_instance()
    if not institute:
        errors.append("Informations institut non configurées")

    if doc_type == "mission_order":
        if not session.trainer.professional_address.strip():
            errors.append(
                "Adresse professionnelle du formateur manquante — "
                "veuillez mettre à jour le profil du formateur"
            )

    elif doc_type in ("candidate_list", "attendance_sheet"):
        if session.participant_count == 0:
            errors.append("Aucun participant inscrit")

    elif doc_type == "evaluation_list":
        if session.status != "completed":
            errors.append("Session non terminée")
        eval_type = session.formation.evaluation_type
        present = session.participant_set.filter(attended=True)
        if eval_type in ("theory_only", "both"):
            missing = present.filter(score_theory__isnull=True)
            if missing.exists():
                errors.append(
                    f"Notes théoriques manquantes ({missing.count()} participant(s))"
                )
        if eval_type in ("practice_only", "both"):
            missing = present.filter(score_practice__isnull=True)
            if missing.exists():
                errors.append(
                    f"Notes pratiques manquantes ({missing.count()} participant(s))"
                )

    elif doc_type == "nominal_list":
        # Spec v2.2 — post-session: carries each participant's exam result
        # and is the source document for the deliberation (§8.6).
        if session.status != "completed":
            errors.append("Session non terminée")
        if session.participant_count == 0:
            errors.append("Aucun participant inscrit")
        missing = session.participant_set.filter(
            attended=True, exam_score__isnull=True
        )
        if missing.exists():
            errors.append(
                f"Notes d'examen manquantes ({missing.count()} participant(s))"
            )

    elif doc_type == "deliberation_report":
        if session.status != "completed":
            errors.append("Session non terminée")
        if not session.committee_members or len(session.committee_members) < 2:
            errors.append("Comité incomplet (minimum 2 membres requis)")

    elif doc_type == "evaluation_sheet":
        if not participant:
            errors.append("Participant non spécifié")
        elif participant.result == "pending":
            errors.append("Évaluation non terminée pour ce participant")

    elif doc_type == "attestation":
        if not participant:
            errors.append("Participant non spécifié")
        else:
            if participant.result != "passed":
                errors.append("Le participant n'est pas reçu")
            if not participant.date_of_birth:
                errors.append("Date de naissance manquante")
            # Lieu de naissance (place_of_birth) is an optional field on
            # Participant (blank=True) and batch generation already prints
            # attestations without it (blank "A : ___" line) — the
            # individual generator used to hard-block on it here, which
            # was inconsistent with batch and with the field's own
            # optionality, so it's no longer a blocking requirement.

    return errors


def get_document_context(session, participant=None, day_number=None):
    """Build common template / generation context for all doc types."""
    institute = InstituteInfo.get_instance()

    context = {
        "session": session,
        "formation": session.formation,
        "client": session.client,
        "trainer": session.trainer,
        "institute": institute,
        "participants": session.participant_set.all().order_by(
            "last_name", "first_name"
        ),
    }

    if participant:
        context["participant"] = participant

    if day_number:
        context["day_number"] = day_number
        # fix: use datetime.timedelta, not timezone.timedelta (doesn't exist)
        context["day_date"] = session.date_start + timedelta(days=day_number - 1)

    return context


# ---------------------------------------------------------------------------
# Stub generation functions
# All file handles use binary mode ('wb') so real python-docx output won't
# be corrupted when the stubs are replaced with actual template rendering.
# ---------------------------------------------------------------------------


def _make_path(session, filename):
    """Build a media-relative path and ensure the directory exists."""
    file_path = os.path.join("documents", "sessions", str(session.pk), filename)
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return file_path, full_path


def generate_candidate_list(session):
    get_document_context(session)
    fname = f"candidate_list_{session.reference.replace('/', '_')}.docx"
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(b"Candidate List Document - Generated")
    return file_path


def generate_attendance_sheet(session, day_number):
    get_document_context(session, day_number=day_number)
    fname = (
        f"attendance_sheet_day{day_number}_{session.reference.replace('/', '_')}.docx"
    )
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(f"Attendance Sheet Day {day_number} - Generated".encode())
    return file_path


def generate_mission_order(session):
    get_document_context(session)
    fname = f"mission_order_{session.reference.replace('/', '_')}.docx"
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(b"Mission Order Document - Generated")
    return file_path


def generate_evaluation_list(session):
    get_document_context(session)
    fname = f"evaluation_list_{session.reference.replace('/', '_')}.docx"
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(b"Evaluation List Document - Generated")
    return file_path


def generate_nominal_list(session):
    """Spec v2.2 — post-session document (Doc 07); generated immediately
    before the deliberation report and used as its basis."""
    get_document_context(session)
    fname = f"nominal_list_{session.reference.replace('/', '_')}.docx"
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(b"Nominal List Document - Generated")
    return file_path


def generate_deliberation_report(session):
    get_document_context(session)
    fname = f"deliberation_report_{session.reference.replace('/', '_')}.docx"
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(b"Deliberation Report Document - Generated")
    return file_path


def generate_evaluation_sheet(participant):
    session = participant.session
    get_document_context(session, participant=participant)
    fname = (
        f"evaluation_sheet_{participant.last_name}_{participant.first_name}"
        f"_{session.reference.replace('/', '_')}.docx"
    )
    file_path, full_path = _make_path(session, fname)
    with open(full_path, "wb") as f:
        f.write(f"Evaluation Sheet - {participant.full_name}".encode())
    return file_path


# Note: unlike the stubs above, there's no generate_attestation() here.
# Attestations follow the same pattern as every other document type —
# documents/views.py:generate_attestation_view redirects straight to the
# HTML print view (documents/print/attestation.html, built from
# certificate_render.build_certificate_data + certificate_layout's boxes).
# No server-side PDF file is produced or stored; the browser's own
# Print / Save-as-PDF is the generator.

