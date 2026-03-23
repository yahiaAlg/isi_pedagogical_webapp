import re
from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Session, Participant


def generate_session_reference(session):
    """Generate unique session reference: CODE-NNN/MM/YYYY"""
    formation_code = session.formation.code
    year = session.date_start.year
    month = session.date_start.month

    existing_refs = (
        Session.objects.filter(
            formation=session.formation,
            date_start__year=year,
            date_start__month=month,
        )
        .exclude(pk=session.pk)
        .values_list("reference", flat=True)
    )

    pattern = rf"^{re.escape(formation_code)}-(\d+)/{month:02d}/{year}$"
    sequences = []
    for ref in existing_refs:
        match = re.match(pattern, ref)
        if match:
            sequences.append(int(match.group(1)))

    next_seq = max(sequences) + 1 if sequences else 1
    return f"{formation_code}-{next_seq:03d}/{month:02d}/{year}"


def assign_certificate_number(participant):
    """
    Assign a sequential certificate number within the session.
    Spec §11.3 — numbers assigned by roster order (pk) among all passed participants.
    """
    if participant.certificate_number or not participant.can_receive_certificate():
        return

    session = participant.session

    passed_participants = [
        p for p in session.participant_set.order_by("pk") if p.can_receive_certificate()
    ]

    sequence = next(
        (i + 1 for i, p in enumerate(passed_participants) if p.pk == participant.pk),
        None,
    )
    if sequence is None:
        return

    base_ref = session.reference.replace("/", "_")
    participant.certificate_number = f"{base_ref}-{sequence:02d}"
    participant.save(update_fields=["certificate_number"])


def validate_session_transition(session, new_status):
    """
    Validate a session status transition.
    Returns a list of human-readable error strings (empty = allowed).
    """
    errors = []

    if not session.can_transition_to(new_status):
        errors.append(
            f"Transition vers '{new_status}' non autorisée depuis '{session.status}'"
        )
        return errors

    if new_status == "completed":
        # For multi-day sessions, verify child sessions exist and have attendance recorded.
        # Attendance is tracked via the `attended` boolean on each session's participants
        # (child sessions represent each day). attendance_per_day is not used by the
        # main workflow so we do NOT check it here.
        if session.is_primary and session.formation.duration_days > 1:
            child_count = session.child_sessions.count()
            expected = session.formation.duration_days - 1
            if child_count < expected:
                errors.append(
                    f"Sessions suivantes manquantes : {child_count}/{expected} générées. "
                    f"Utilisez « Régénérer » depuis la fiche session."
                )

        eval_type = session.formation.evaluation_type
        present = session.participant_set.filter(attended=True)

        if eval_type in ["theory_only", "both"]:
            missing = present.filter(score_theory__isnull=True)
            if missing.exists():
                errors.append(
                    f"Notes théoriques manquantes pour {missing.count()} participant(s)"
                )

        if eval_type in ["practice_only", "both"]:
            missing = present.filter(score_practice__isnull=True)
            if missing.exists():
                errors.append(
                    f"Notes pratiques manquantes pour {missing.count()} participant(s)"
                )

        # For primary sessions, warn if exam scores are missing
        if session.is_primary:
            missing_exam = session.participant_set.filter(
                attended=True, exam_score__isnull=True
            )
            if missing_exam.exists():
                errors.append(
                    f"Notes d'examen manquantes pour {missing_exam.count()} participant(s) "
                    f"— saisissez-les via « Notes d'examen »"
                )

    return errors


def generate_child_sessions(primary_session):
    """
    Auto-generate child sessions (day 2 … N) from a primary session.

    Rules:
    - Number of children = formation.duration_days - 1
    - Each child is exactly 1 day: date_start = date_end = primary.date_start + offset
    - All primary participants are copied with attended=True
    - Daily scores (score_theory / score_practice) pre-filled at max_score / 2
    - Primary participants' exam_score pre-filled at max_score / 2 (if not already set)
    - Existing child sessions are deleted and regenerated (idempotent)

    Returns a list of the created Session objects.
    """
    formation = primary_session.formation
    total_days = formation.duration_days

    if total_days <= 1:
        return []

    # Idempotent: wipe existing children
    primary_session.child_sessions.all().delete()

    half_score = (formation.max_score / Decimal("2")).quantize(Decimal("0.01"))
    eval_type = formation.evaluation_type

    created = []
    for day_offset in range(1, total_days):
        session_date = primary_session.date_start + timedelta(days=day_offset)

        child = Session.objects.create(
            formation=formation,
            client=primary_session.client,
            trainer=primary_session.trainer,
            date_start=session_date,
            date_end=session_date,
            location_type=primary_session.location_type,
            room=primary_session.room,
            external_location=primary_session.external_location,
            capacity=primary_session.capacity,
            status="planned",
            specialty_code=primary_session.specialty_code,
            session_number=primary_session.session_number,
            committee_members=primary_session.committee_members,
            is_primary=False,
            parent_session=primary_session,
        )

        # Copy participants with pre-filled scores
        for p in primary_session.participant_set.order_by("pk"):
            Participant.objects.create(
                session=child,
                first_name=p.first_name,
                last_name=p.last_name,
                first_name_ar=p.first_name_ar,
                last_name_ar=p.last_name_ar,
                date_of_birth=p.date_of_birth,
                place_of_birth=p.place_of_birth,
                place_of_birth_ar=p.place_of_birth_ar,
                job_title=p.job_title,
                employer=p.employer,
                employer_client=p.employer_client,
                phone=p.phone,
                email=p.email,
                notes=p.notes,
                attended=True,
                score_theory=(
                    half_score if eval_type in ["theory_only", "both"] else None
                ),
                score_practice=(
                    half_score if eval_type in ["practice_only", "both"] else None
                ),
                source_participant=p,
            )

        created.append(child)

    # Pre-fill exam scores on primary participants (only those not already set)
    for p in primary_session.participant_set.filter(exam_score__isnull=True):
        p.exam_score = half_score
        p.save(update_fields=["exam_score"])

    return created


def import_participants_from_file(session, file):
    """
    Import participants from CSV/Excel file.

    Spec §13.3 behaviour:
      - Stop immediately when capacity is reached; report remaining rows as rejected
      - Skip duplicates (same first_name + last_name already in session)
      - Return dict: {'imported': N, 'duplicates': N, 'rejected': N, 'errors': [...]}
    """
    import csv
    import openpyxl
    from io import StringIO, TextIOWrapper
    from datetime import datetime

    result = {
        "imported": 0,
        "duplicates": 0,
        "rejected": 0,
        "errors": [],
    }

    filename = file.name.lower()
    rows = []

    try:
        if filename.endswith(".csv"):
            content = TextIOWrapper(file, encoding="utf-8").read()
            reader = csv.DictReader(StringIO(content))
            rows = list(reader)
        elif filename.endswith((".xlsx", ".xls")):
            workbook = openpyxl.load_workbook(file)
            worksheet = workbook.active
            headers = [cell.value for cell in worksheet[1]]
            for row in worksheet.iter_rows(min_row=2, values_only=True):
                row_dict = {}
                for i, value in enumerate(row):
                    if i < len(headers) and headers[i]:
                        row_dict[headers[i]] = value
                rows.append(row_dict)
    except Exception as e:
        raise Exception(f"Erreur lors de la lecture du fichier: {str(e)}")

    header_mapping = {
        "prénom": "first_name",
        "prenom": "first_name",
        "nom": "last_name",
        "prénom ar": "first_name_ar",
        "prenom ar": "first_name_ar",
        "nom ar": "last_name_ar",
        "date naissance": "date_of_birth",
        "date de naissance": "date_of_birth",
        "lieu naissance": "place_of_birth",
        "lieu de naissance": "place_of_birth",
        "lieu naissance ar": "place_of_birth_ar",
        "fonction": "job_title",
        "employeur": "employer",
        "email": "email",
        "téléphone": "phone",
        "telephone": "phone",
    }

    for row_num, row_data in enumerate(rows, start=2):
        if session.available_spots <= 0:
            result["rejected"] += len(rows) - (row_num - 2)
            break

        try:
            normalized = {}
            for key, value in row_data.items():
                if key and value is not None:
                    clean_key = key.lower().strip()
                    mapped = header_mapping.get(clean_key, clean_key)
                    normalized[mapped] = str(value).strip() if value else ""

            first_name = normalized.get("first_name", "").strip()
            last_name = normalized.get("last_name", "").strip()

            if not first_name or not last_name:
                result["errors"].append(
                    {"row": row_num, "message": "Prénom et nom requis"}
                )
                continue

            if Participant.objects.filter(
                session=session,
                first_name=first_name,
                last_name=last_name,
            ).exists():
                result["duplicates"] += 1
                continue

            date_of_birth = None
            dob_str = normalized.get("date_of_birth", "").strip()
            if dob_str:
                for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                    try:
                        date_of_birth = datetime.strptime(dob_str, fmt).date()
                        break
                    except ValueError:
                        continue
                if date_of_birth is None:
                    result["errors"].append(
                        {
                            "row": row_num,
                            "message": f"Format de date invalide: {dob_str}",
                        }
                    )

            Participant.objects.create(
                session=session,
                first_name=first_name,
                last_name=last_name,
                first_name_ar=normalized.get("first_name_ar", ""),
                last_name_ar=normalized.get("last_name_ar", ""),
                date_of_birth=date_of_birth,
                place_of_birth=normalized.get("place_of_birth", ""),
                place_of_birth_ar=normalized.get("place_of_birth_ar", ""),
                job_title=normalized.get("job_title", ""),
                employer=normalized.get("employer", ""),
                phone=normalized.get("phone", ""),
                email=normalized.get("email", ""),
                attended=True,  # default present
            )
            result["imported"] += 1

        except Exception as e:
            result["errors"].append({"row": row_num, "message": f"Erreur: {str(e)}"})

    return result
