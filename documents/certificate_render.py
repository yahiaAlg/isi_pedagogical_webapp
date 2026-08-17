"""
documents/certificate_render.py

Attestation ("شهادة تكوين تأهيلي") data builder.

Maps a Participant (and its session/formation/institute chain) onto the
certificate's fields. Used by documents/views_print.py to feed the
on-screen/print HTML templates (documents/print/attestation.html and
documents/print/batch_attestations.html), which — together with
certificate_layout.py's pixel-exact BOXES — are the certificate's only
renderer. There's no server-side PDF/image generation: the browser's own
Print / Save-as-PDF produces the document, same as every other document
type in this app.
"""

from __future__ import annotations

import re
from datetime import date

# ---------------------------------------------------------------------------
# Arabic month-count wording, matching the institute's existing convention
# ("شهر واحد" for 1, "شهرين" for 2, "N أشهر" beyond that). Diplômante
# branches can run up to 30 months (Branch.curriculum_max_months),
# qualifiante up to 6 — this table comfortably covers both.
# ---------------------------------------------------------------------------
_AR_MONTHS = {
    1: "شهر واحد",
    2: "شهرين",
    3: "ثلاثة أشهر",
    4: "أربعة أشهر",
    5: "خمسة أشهر",
    6: "ستة أشهر",
    7: "سبعة أشهر",
    8: "ثمانية أشهر",
    9: "تسعة أشهر",
    10: "عشرة أشهر",
}


def _ar_month_label(n: int) -> str:
    if n in _AR_MONTHS:
        return _AR_MONTHS[n]
    return f"{n} أشهر"  # 11+ — plural form, numeral spelled digitally


def _fr_month_label(n: int) -> str:
    return f"{n:02d} mois"


def _months_between(date_start: date, date_end: date) -> int:
    """Whole-month span used for the 'Durée (Jours)' field, which — per the
    institute's own template — actually displays a month count rather than
    a day count for qualifying trainings. Rounds up to the nearest month,
    minimum 1."""
    months = (date_end.year - date_start.year) * 12 + (
        date_end.month - date_start.month
    )
    if date_end.day >= date_start.day:
        months += 1
    return max(1, months)


def _parse_certificate_number(certificate_number: str) -> tuple[str, str, str]:
    """Splits 'YYYY/MM ت.ح.ط /NNN' into (annee, mois_serie, num_serie).

    Mirrors Participant.certificate_number's fixed format (see
    formations/utils.py — assign_certificate_number). Raises ValueError
    with a clear message if the participant has no certificate number
    yet — the caller should assign one before generating the attestation,
    exactly as for every other post-session document.
    """
    match = re.match(
        r"^(\d{4})/(\d{2})\s*ت\.ح\.ط\s*/(\d+)$", certificate_number.strip()
    )
    if not match:
        raise ValueError(
            f"certificate_number {certificate_number!r} does not match the "
            "expected 'YYYY/MM ت.ح.ط /NNN' format — assign a certificate "
            "number before generating the attestation."
        )
    annee, mois_serie, num_serie = match.groups()
    return annee, mois_serie, num_serie


def _fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def get_institute_info():
    from core.models import InstituteInfo  # local import: Django app registry

    return InstituteInfo.get_instance()


# ---------------------------------------------------------------------------
# Data builder, consumed by the print/download HTML templates.
# ---------------------------------------------------------------------------
def build_certificate_data(participant, *, issuance_date: date | None = None) -> dict:
    """Maps a Participant instance (and its session/formation/institute
    chain) onto the certificate's fields. Keys match certificate_layout's
    BOXES/STATIC conventions (uppercase, ported from certificate_project).

    Requires participant.certificate_number to already be assigned
    (see formations.utils.assign_certificate_number / can_receive_certificate).

    `issuance_date` defaults to today — override if the attestation is
    being (re)generated for a date other than the moment of the call.
    """
    session = participant.session
    formation = session.formation

    annee, mois_serie, num_serie = _parse_certificate_number(
        participant.certificate_number
    )
    months = _months_between(session.date_start, session.date_end)

    # CIP_NUM prints the "وبناءا على محضر نهاية التكوين" line, i.e. the
    # session's own PV (محضر مداولات) reference — a separate, monthly-reset
    # sequence from the participant's certificate/attestation number used
    # for ANNEE/NUM_SERIE/MOIS_SERIE above (see core/sequencing.py). It must
    # come from session.pv_number (Session.assign_pv_number), never be
    # derived from the certificate number's own serial — the two counters
    # are independent and normally hold different values.
    session.assign_pv_number()

    institute = get_institute_info()

    return {
        "ANNEE": annee,
        "NUM_SERIE": num_serie,
        "MOIS_SERIE": mois_serie,
        # session.pv_number is already fully formatted, including its own
        # "{BRANCH}{SPECIALITE}-" prefix (see core.sequencing.allocate_pv_number) —
        # not reassembled here from the certificate number's serial/month/year.
        "CIP_NUM": session.pv_number,
        # Spec — dual-mode identity block: FR/latin and AR name pairs are
        # each independently optional (Participant.clean() already
        # enforces that at least one full pair exists). The print
        # template shows only the block(s) whose flag is True.
        "HAS_FR": participant.has_fr_name,
        "HAS_AR": participant.has_ar_name,
        "PRENOM_FR": participant.first_name.upper(),
        "NOM_FR": participant.last_name.upper(),
        "PRENOM_AR": participant.first_name_ar,
        "NOM_AR": participant.last_name_ar,
        "DATE_NAISSANCE": _fmt(participant.date_of_birth),
        "LIEU_NAISSANCE_FR": participant.place_of_birth,
        "LIEU_NAISSANCE_AR": participant.place_of_birth_ar,
        "SPECIALITE_FR": formation.title,
        "SPECIALITE_AR": formation.title_ar,
        "DUREE_HEURES": str(formation.duration_hours),
        "DUREE_MOIS_FR": _fr_month_label(months),
        "DUREE_MOIS_AR": _ar_month_label(months),
        "DATE_DEBUT": _fmt(session.date_start),
        "DATE_FIN": _fmt(session.date_end),
        "DATE_EMISSION": _fmt(issuance_date or date.today()),
        "AGREMENT_NUM": institute.accreditation_number if institute else "",
        "IF_NUM": institute.if_number if institute else "",
        "QR_PAYLOAD": participant.qr_code_content,
    }
