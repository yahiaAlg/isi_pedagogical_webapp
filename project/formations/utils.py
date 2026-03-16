import re
from datetime import date
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

    Spec §11.3 — numbers assigned by roster order (pk) among all
    passed participants. If regenerating, the SAME number is reused
    (the participant already has one by the time this is called from
    generate_attestation_view which checks `if not participant.certificate_number`).
    """
    if participant.certificate_number or not participant.can_receive_certificate():
        return

    session = participant.session

    # All passed participants in stable roster order (insertion order = pk)
    passed_participants = [
        p for p in session.participant_set.order_by("pk") if p.can_receive_certificate()
    ]

    sequence = next(
        (i + 1 for i, p in enumerate(passed_participants) if p.pk == participant.pk),
        None,
    )
    if sequence is None:
        return  # participant not in the passed list — should not happen

    base_ref = session.reference.replace("/", "_")
    participant.certificate_number = f"{base_ref}-{sequence:02d}"
    # Use update_fields to avoid triggering the full save() protection path
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
        # Attendance must have been recorded per-day for every participant
        # (attendance_per_day == {} means staff never opened the attendance form)
        unrecorded = session.participant_set.filter(attendance_per_day={})
        if unrecorded.exists():
            errors.append(
                f"{unrecorded.count()} participant(s) sans présence journalière enregistrée"
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

    return errors


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
        # Spec §13.3 — stop at capacity; remaining rows are all rejected
        if session.available_spots <= 0:
            result["rejected"] += len(rows) - (row_num - 2)
            break

        try:
            # Normalise keys
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

            # Spec §13.3 — skip duplicates
            if Participant.objects.filter(
                session=session,
                first_name=first_name,
                last_name=last_name,
            ).exists():
                result["duplicates"] += 1
                continue

            # Parse date of birth
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
            )
            result["imported"] += 1

        except Exception as e:
            result["errors"].append({"row": row_num, "message": f"Erreur: {str(e)}"})

    return result
