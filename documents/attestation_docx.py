"""
documents/attestation_docx.py

Generates the Document 08 attestation (Diplôme / Certificat) from the
institute's real Word template by direct placeholder substitution in
word/document.xml — no python-docx dependency for this document type.

This lives next to the existing stub generators in documents/utils.py;
documents/utils.py:generate_attestation() calls into this module instead
of writing placeholder bytes.

Pipeline:
    1. build_context(participant)        -> dict of the 21 template fields
    2. render_docx(context)               -> bytes of the merged .docx
    3. render_pdf(docx_bytes)             -> bytes of the .docx converted to PDF (LibreOffice)
    4. stamp_qr(pdf_bytes, qr_payload)    -> bytes of the PDF with a QR code
                                              overlaid beneath the signature block
    5. generate_attestation(participant)  -> convenience wrapper running 1-4,
                                              returns (docx_bytes, pdf_bytes)

Only step 4 requires the `qrcode`, `pypdf`, and `reportlab` packages.
Steps 1-3 have no third-party dependencies beyond the standard library
and LibreOffice.
"""

from __future__ import annotations

import io
import re
import subprocess
import zipfile
from datetime import date, timedelta
from pathlib import Path

TEMPLATE_PATH = Path(__file__).parent / "doc_templates" / "attestation_template.docx"

FIELDS = [
    "branch_abbr",
    "cip_num",
    "annee",
    "num_serie",
    "mois_serie",
    "nom_ar",
    "prenom_ar",
    "nom_fr",
    "prenom_fr",
    "date_naissance",
    "lieu_naissance_ar",
    "lieu_naissance_fr",
    "specialite_ar",
    "specialite_fr",
    "duree_heures",
    "duree_mois_ar",
    "duree_mois_fr",
    "date_debut",
    "date_fin",
    "date_emission",
    "agrement_num",
    "if_num",
]

# ---------------------------------------------------------------------------
# Arabic day-count wording, matching the institute's existing numeral-word
# convention used elsewhere on the certificate ("يوم واحد" for 1, "يومين"
# for 2, "N أيام" for 3-10, "N يوما" beyond that). Despite the historical
# "duree_mois_*" field names (kept as-is — they map to fixed placeholders
# baked into the .docx template), this field displays a DAY count, matching
# the template's own "(بالأيام)" / "(Jours)" labels.
# ---------------------------------------------------------------------------
_AR_DAYS = {
    1: "يوم واحد",
    2: "يومين",
    3: "ثلاثة أيام",
    4: "أربعة أيام",
    5: "خمسة أيام",
    6: "ستة أيام",
    7: "سبعة أيام",
    8: "ثمانية أيام",
    9: "تسعة أيام",
    10: "عشرة أيام",
}


def _ar_day_label(n: int) -> str:
    if n in _AR_DAYS:
        return _AR_DAYS[n]
    return f"{n} يوما"  # 11+ — plural form, numeral spelled digitally


def _fr_day_label(n: int) -> str:
    if n == 1:
        return "01 jour"
    return f"{n:02d} jours"


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


# ---------------------------------------------------------------------------
# Step 1 — context builder
# ---------------------------------------------------------------------------
def build_context(participant, *, issuance_date: date | None = None) -> dict:
    """Maps a Participant instance (and its session/formation/institute
    chain) onto the 21 template placeholders.

    Requires participant.certificate_number to already be assigned
    (see formations.utils.assign_certificate_number / can_receive_certificate).

    `issuance_date` defaults to the day after the session group's actual
    last day (its `group_end_date` — the last generated day, not just the
    primary/day-1 session's own date_end) — override if the attestation is
    being (re)generated for a date other than that default.
    """
    session = participant.session
    formation = session.formation
    specialty = getattr(formation, "specialty", None)
    branch = getattr(specialty, "branch", None) if specialty else None
    date_fin = session.group_end_date
    issuance_date = issuance_date or (date_fin + timedelta(days=1))

    annee, mois_serie, num_serie = _parse_certificate_number(
        participant.certificate_number
    )
    days = session.group_duration_days

    institute = get_institute_info()

    return {
        "branch_abbr": branch.abbreviation if branch else "",
        # session.specialty_code carries the branch+specialty root (e.g.
        # "CIP1202") on sessions created before the Branch/Specialty link
        # existed; specialty.code is the canonical source once set.
        "cip_num": f"{specialty.code if specialty else session.specialty_code}-"
        f"{num_serie}/{mois_serie}/{annee}",
        "annee": annee,
        "num_serie": num_serie,
        "mois_serie": mois_serie,
        "nom_ar": participant.last_name_ar,
        "prenom_ar": participant.first_name_ar,
        "nom_fr": participant.last_name,
        "prenom_fr": participant.first_name,
        "date_naissance": _fmt(participant.date_of_birth),
        "lieu_naissance_ar": participant.place_of_birth_ar,
        "lieu_naissance_fr": participant.place_of_birth,
        "specialite_ar": formation.title_ar,
        "specialite_fr": formation.title,
        "duree_heures": str(formation.duration_hours),
        "duree_mois_ar": _ar_day_label(days),
        "duree_mois_fr": _fr_day_label(days),
        "date_debut": _fmt(session.group_start_date),
        "date_fin": _fmt(date_fin),
        "date_emission": _fmt(issuance_date),
        "agrement_num": institute.accreditation_number,
        "if_num": institute.if_number,
    }


def get_institute_info():
    from core.models import InstituteInfo  # local import: Django app registry

    return InstituteInfo.get_instance()


# ---------------------------------------------------------------------------
# Step 2 — docx merge (raw XML placeholder substitution, no python-docx)
# ---------------------------------------------------------------------------
def render_docx(context: dict, template_path: Path = TEMPLATE_PATH) -> bytes:
    missing = [f for f in FIELDS if f not in context]
    if missing:
        raise ValueError(f"Missing template fields: {missing}")

    with zipfile.ZipFile(template_path, "r") as zin:
        xml = zin.read("word/document.xml").decode("utf-8")
        for field in FIELDS:
            xml = xml.replace("{{" + field.upper() + "}}", str(context[field]))

        leftover = re.findall(r"\{\{[A-Z_]+\}\}", xml)
        if leftover:
            raise ValueError(f"Unfilled placeholders remain: {sorted(set(leftover))}")

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                payload = (
                    xml.encode("utf-8")
                    if item.filename == "word/document.xml"
                    else zin.read(item.filename)
                )
                zout.writestr(item, payload)
        return buffer.getvalue()


# ---------------------------------------------------------------------------
# Step 3 — docx -> pdf (LibreOffice headless)
# ---------------------------------------------------------------------------
def render_pdf(docx_bytes: bytes) -> bytes:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        docx_path = tmp / "attestation.docx"
        docx_path.write_bytes(docx_bytes)

        # Isolated LibreOffice profile per call: without -env:UserInstallation
        # soffice shares a single profile dir across invocations, and two
        # concurrent conversions (e.g. "Tout générer" for several
        # participants) collide on its lock file and fail.
        profile_dir = tmp / "lo_profile"
        try:
            result = subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation={profile_dir.as_uri()}",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp),
                    str(docx_path),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "LibreOffice ('soffice') is not installed or not on PATH. "
                "Install it on the server, e.g. `sudo apt install libreoffice`."
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "LibreOffice failed to convert the attestation to PDF: "
                f"{exc.stderr.decode(errors='replace')}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError("LibreOffice conversion timed out after 120s") from exc

        pdf_path = tmp / "attestation.pdf"
        if not pdf_path.exists():
            raise RuntimeError(
                "LibreOffice reported success but produced no PDF file. "
                f"stderr: {result.stderr.decode(errors='replace')}"
            )
        return pdf_path.read_bytes()


# ---------------------------------------------------------------------------
# Step 4 — stamp the QR code onto the rendered PDF
# ---------------------------------------------------------------------------
# Page is A4 landscape (841.89 x 595.30 pt). The template's footer line
# ("Agrément n°.../ IF n°...") currently overflows onto a second page in
# LibreOffice's rendering, leaving that second page almost entirely blank —
# a natural, collision-free spot for the QR stamp. If a future template
# revision fits everything back onto one page, re-target QR_PAGE_INDEX at
# page 0 and move QR_Y_PT down into the blank strip below "Le Directeur".
QR_SIZE_PT = 90
QR_X_PT = 375  # from left edge — roughly centered
QR_Y_PT = 320  # from bottom edge — below the Agrément/IF footer line
QR_PAGE_INDEX = -1  # last page; see note above


def stamp_qr(pdf_bytes: bytes, qr_payload: str) -> bytes:
    import qrcode
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    qr_img = qrcode.make(qr_payload)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    reader = PdfReader(io.BytesIO(pdf_bytes))
    target_index = (
        QR_PAGE_INDEX if QR_PAGE_INDEX >= 0 else len(reader.pages) + QR_PAGE_INDEX
    )
    page_width = float(reader.pages[target_index].mediabox.width)
    page_height = float(reader.pages[target_index].mediabox.height)

    overlay_buffer = io.BytesIO()
    c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
    c.drawImage(
        ImageReader(qr_buffer),
        QR_X_PT,
        QR_Y_PT,
        width=QR_SIZE_PT,
        height=QR_SIZE_PT,
        mask="auto",
    )
    c.save()
    overlay_buffer.seek(0)
    overlay_page = PdfReader(overlay_buffer).pages[0]

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i == target_index:
            page.merge_page(overlay_page)
        writer.add_page(page)

    out_buffer = io.BytesIO()
    writer.write(out_buffer)
    return out_buffer.getvalue()


# ---------------------------------------------------------------------------
# Step 5 — orchestrator
# ---------------------------------------------------------------------------
def generate_attestation_files(
    participant, *, issuance_date: date | None = None
) -> tuple[bytes, bytes]:
    """Returns (docx_bytes, pdf_bytes). The PDF carries the QR code; the
    docx does not (embedding an image directly into the OOXML would require
    modifying the template's relationships — the PDF overlay is simpler and
    is the copy actually handed out / archived as the official document).

    Named generate_attestation_files (not generate_attestation) to avoid
    colliding with documents/utils.py:generate_attestation(), which wraps
    this and handles the GeneratedDocument file-path bookkeeping shared by
    every other document type.
    """
    context = build_context(participant, issuance_date=issuance_date)
    docx_bytes = render_docx(context)
    pdf_bytes = render_pdf(docx_bytes)

    qr_payload = getattr(participant, "qr_code_content", None)
    if not qr_payload:
        from django.conf import settings  # local import

        qr_payload = f"{settings.SITE_URL}/verify/{participant.id}/"

    pdf_bytes = stamp_qr(pdf_bytes, qr_payload)
    return docx_bytes, pdf_bytes
