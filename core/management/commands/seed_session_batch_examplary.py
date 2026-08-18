# formations/management/commands/seed_session_batch_examplary.py
"""
EXEMPLARY batch seeder for Session + Participant records, sourced directly
from 5 جدول اسمي نهائي (nominal list) documents isolated by
`find_nominal_files.py`:

    ALGER_CHIMIE_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_NOMINAL_LIST.docx
    BIOREAL_PHARM_COMMUNICATION_INTERPERSONNELLE_EN_ENTREPRISE_1_NOMINAL_LIST.docx
    BIOREAL_PHARM_LA_SURETE_INTERNE_NOMINAL_LIST.docx
    EEMS_CPHS_NOMINAL_LIST.docx
    EEMS_DECHETS_DE_FIENTES_NOMINAL_LIST.docx

Core idea
─────────
A nominal list never guarantees its Formation / Trainer / Client already
exist in the catalog seeded by formations_seed.py / trainers_seed.py /
clients_seed.py — titles are transcribed slightly differently between
"official paperwork" and "commercial catalogue" (e.g. "Habilitation
D'utilisation des Produits Chimiques" vs. catalog's "Habilitation à
l'Utilisation des Produits Chimiques"). So instead of a strict
`get_or_create(title=...)`, every lookup below is FUZZY:

    1. Try to find a close-enough existing record (Formation title,
       Client name, Trainer name) using a normalized similarity ratio.
    2. If nothing crosses the confidence threshold, CREATE it on the
       spot with sane defaults, and print a "⚠ created — please review"
       warning instead of silently guessing critical business fields
       (specialty link, pricing, category...).

This mirrors exactly what was flagged as missing in the original
DB-seeding analysis: Session.capacity, Formation catalog existence,
Trainer specialty, and now also Branch/Specialty when a brand-new
formation has no obvious catalog specialty to attach to.

Run
───
    python manage.py seed_session_batch_examplary
    python manage.py seed_session_batch_examplary --dry-run
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

# ═══════════════════════════════════════════════════════════════════════
# Raw data — transcribed as-is from the 5 نهائي nominal list documents.
# ═══════════════════════════════════════════════════════════════════════

SESSION_SEED_DATA = [
    {
        "doc_reference": "002/04/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "Alger Chimie",
        "date_start": "30/03/2026",
        "date_end": "03/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "رابح ابازيز",
        # Manual transliteration of the Arabic-only trainer name (source
        # carries no Latin spelling) — kept alongside the AR text so the
        # trainer can be matched by either script going forward.
        "trainer_latin": ("Rabah", "Abaziz"),
        "participants": [
            {"ar": "فرحي سامي", "fr": "FARHI SAMY", "dob": "21/07/1999", "pob": "Alger"},
            {"ar": "تخابيت بشير", "fr": "TKHABIT BACHIR", "dob": "12/01/1971", "pob": "Alger"},
            {"ar": "طهرور محند", "fr": "TAHROR MOHAND", "dob": "14/09/1994", "pob": "Bejaia"},
        ],
    },
    {
        "doc_reference": "003/08/2026",
        "formation_title": "Communication Interpersonnelle En Entreprise",
        "client_name": "BIOREAL PHARM",
        "date_start": "04/08/2026",
        "date_end": "06/08/2026",
        "duration_days_hint": 3,
        "trainer_ar": "صليحة أوطاهر",
        "trainer_latin": ("Saliha", "Aoutaher"),
        "participants": [
            {"ar": "فارس عميور", "fr": "FARES AMIOUR", "dob": "15/02/1996", "pob": "El Eulma"},
            {"ar": "يوسف سديرة", "fr": "YOUCEF SEDIRA", "dob": "14/08/1991", "pob": "Annaba"},
            {"ar": "عبد الله شبل", "fr": "ABDALLAH CHEBEL", "dob": "17/11/1991", "pob": "Ain Lahdjar"},
            {"ar": "أسامة بورفرف", "fr": "OUSSAMA BOUREFREF", "dob": "08/01/1995", "pob": "El Eulma"},
            {"ar": "منير برحايل", "fr": "MOUNIR BERREHAIL", "dob": "08/07/1992", "pob": "El Eulma"},
            {"ar": "أمين بوقطاية", "fr": "AMINE BOUGAETAIA", "dob": "03/02/1995", "pob": "Ain El Kebira"},
            {"ar": "عقبة تركي", "fr": "OKBA TERKI", "dob": "25/01/1993", "pob": "Djemila"},
        ],
    },
    {
        "doc_reference": "009/07/2026",
        "formation_title": "La Sûreté Interne",
        "client_name": "BIOREAL PHARM",
        "date_start": "26/07/2026",
        "date_end": "29/07/2026",
        "duration_days_hint": 4,
        "trainer_ar": "كمال بوليفة",
        "trainer_latin": ("Kamel", "Boulifa"),
        "participants": [
            # No French transliteration was provided on this particular
            # nominal list — "fr": "" triggers the AR-mirrored-into-Latin
            # fallback in `resolve_participant_names()` below, needed to
            # keep Participant's (session, last_name, first_name)
            # uniqueness constraint satisfied.
            {"ar": "الخير بن زاوي", "fr": "", "dob": "13/11/1980", "pob": ""},
            {"ar": "أسامة بلخيري", "fr": "", "dob": "16/03/1988", "pob": ""},
            {"ar": "عزيز جدتلي", "fr": "", "dob": "29/04/1986", "pob": ""},
            {"ar": "عبد السلام بومديري", "fr": "", "dob": "09/06/1982", "pob": ""},
            {"ar": "بلال كامل", "fr": "", "dob": "02/06/1995", "pob": ""},
            {"ar": "توفيق بومراثي", "fr": "", "dob": "26/12/1976", "pob": ""},
            {"ar": "محمد امين خليل", "fr": "", "dob": "20/06/1981", "pob": ""},
            {"ar": "حسين بودربالة", "fr": "", "dob": "08/05/1982", "pob": ""},
        ],
    },
    {
        "doc_reference": "014/06/2026",
        "formation_title": "Commission Paritaire Hygiène Et Sécurité",
        "client_name": "LOUAI CATERING",
        "date_start": "01/06/2026",
        "date_end": "04/06/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        "participants": [
            {"ar": "امال بن عاشور", "fr": "AMEL BENACHOUR", "dob": "05/06/1988", "pob": "Skikda"},
            {"ar": "زهير دغمان", "fr": "ZOHEIR DORMANE", "dob": "02/10/1969", "pob": "Ain Mlila"},
            {"ar": "أحمد ليتيم", "fr": "AHMED LITIM", "dob": "16/11/1997", "pob": "Skikda"},
            {"ar": "غنية يحياوي", "fr": "GHANIA YAHIAOUI", "dob": "21/08/1973", "pob": "Skikda"},
            {"ar": "محمد يزلي", "fr": "MOHAMED YEZLI", "dob": "31/03/1975", "pob": "Skikda"},
            {"ar": "أميرة سيد", "fr": "AMIRA SID", "dob": "21/12/1997", "pob": "Skikda"},
            {"ar": "جمال شبري", "fr": "DJAMEL CHEBIRI", "dob": "21/08/1983", "pob": "Tizi Ouzou"},
            {"ar": "مخلوف أيث غربي", "fr": "MAKHLOUF AIT GHARBI", "dob": "30/04/1988", "pob": "Tizi Ouzou"},
            {"ar": "جمال سيد ادريس", "fr": "DJAMEL SID IDRIS", "dob": "10/06/1993", "pob": ""},
            {"ar": "جعفر اعراب", "fr": "DJAFFAR ARAB", "dob": "05/01/1985", "pob": "Tizi Ouzou"},
            {"ar": "محمد أشرف بلعباس", "fr": "MOHAMED ACHRAF BELABBES", "dob": "04/05/2000", "pob": "Oran"},
            {"ar": "محمد بلعضام", "fr": "MOHAMED BELADAM", "dob": "01/01/1978", "pob": "Oran"},
            {"ar": "طيب مخلوفي", "fr": "TAIB MAKHLOUFI", "dob": "11/02/1989", "pob": ""},
        ],
    },
    {
        "doc_reference": "001/05/2026",
        "formation_title": "Collecte des Déchets Spéciaux « Déchets de Fientes »",
        # No "الزبون:" (client) line at all on this particular nominal list —
        # treated as an institute-run open session with no sponsoring
        # company. See `resolve_client()` fallback below.
        "client_name": "",
        "date_start": "02/05/2026",
        "date_end": "04/05/2026",
        "duration_days_hint": 3,
        "trainer_ar": "لعوارم عبد المومن",
        "trainer_latin": ("Laouar", "Abdelmoumen"),
        "participants": [
            {"ar": "سمير خرباشي", "fr": "SAMIR KHARBACHI", "dob": "02/09/1983", "pob": "Bougaa"},
            {"ar": "رضا خرباشي", "fr": "RIDA KHARBACHI", "dob": "27/11/1984", "pob": "Bouandas"},
            {"ar": "أحمد بونعجة", "fr": "AHMED BOUNADJA", "dob": "12/06/1991", "pob": "Kherrata"},
        ],
    },
]

# Fallback client used only when a nominal list carries no "الزبون:" line
# at all (spec requires Session.client — it has no null=True/blank=True).
NO_CLIENT_SENTINEL_NAME = "Session Ouverte — Sans Client Spécifié"

# New formations created on the fly are parked under this Branch/Specialty
# when nothing in the catalog is a plausible match — a clearly-named
# holding bucket rather than a silent guess, flagged for manual review.
FALLBACK_BRANCH_ABBR = "MEE"  # Métiers de l'Eau et de l'Environnement (already seeded)
FALLBACK_SPECIALTY_CODE = "9999"
FALLBACK_SPECIALTY_TITLE = "Non classifié — à réviser"


# ═══════════════════════════════════════════════════════════════════════
# Normalization / fuzzy-matching helpers
# ═══════════════════════════════════════════════════════════════════════


def normalize(text: str) -> str:
    """Lowercase, strip accents/diacritics, collapse punctuation to
    spaces, drop leading French articles — used for ALL fuzzy matching
    below (formation titles, client names)."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[’'`]", " ", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"^(la |le |les |l )", "", text)
    return text


def best_fuzzy_match(query: str, candidates, key=lambda x: x, threshold=0.6):
    """Returns (best_candidate, ratio) or (None, 0.0) if nothing clears
    `threshold`. `candidates` is any iterable of objects; `key` extracts
    the comparable string from each."""
    nq = normalize(query)
    best_obj, best_ratio = None, 0.0
    for obj in candidates:
        ratio = difflib.SequenceMatcher(None, nq, normalize(key(obj))).ratio()
        if ratio > best_ratio:
            best_obj, best_ratio = obj, ratio
    if best_ratio >= threshold:
        return best_obj, best_ratio
    return None, 0.0


# Particles that form ONE naming unit with the token right after them —
# used so "عبد المومن" / "عبد الله" aren't split into two separate units.
_AR_PARTICLES = {"عبد", "بن", "بو", "أبو", "ابو"}


def split_arabic_name(full_name: str):
    """
    Best-effort split of a single "ism + laqab" Arabic cell into
    (first_name, last_name), consistent with the convention already used
    by trainers_seed.py for the Latin roster (family name treated as the
    LAST resolved unit). Compound units starting with a connective
    particle (عبد / بن / بو...) are kept together first.

    This is a heuristic, not a linguistic authority — Algerian admin
    documents don't apply name order consistently. Same caveat as
    trainers_seed.py's own docstring: review ambiguous rows manually.
    """
    tokens = full_name.split()
    if not tokens:
        return "", ""

    units = []
    i = 0
    while i < len(tokens):
        if tokens[i] in _AR_PARTICLES and i + 1 < len(tokens):
            units.append(f"{tokens[i]} {tokens[i + 1]}")
            i += 2
        else:
            units.append(tokens[i])
            i += 1

    if len(units) == 1:
        return units[0], units[0]

    last_name = units[-1]
    first_name = " ".join(units[:-1])
    return first_name, last_name


def split_latin_name(full_name: str):
    """word1..N-1 = first_name, last word = last_name (mirrors
    `split_arabic_name`'s convention for consistency)."""
    tokens = full_name.split()
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], tokens[0]
    return " ".join(tokens[:-1]), tokens[-1]


def parse_ddmmyyyy(text: str):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        return None


def resolve_participant_names(row: dict):
    """
    Returns (first_name, last_name, first_name_ar, last_name_ar).

    Always splits the AR cell (source of truth). If no FR transliteration
    was provided on the nominal list, the AR-split values are ALSO
    mirrored into the Latin first_name/last_name fields — Participant's
    `unique_together = ["session", "last_name", "first_name"]` would
    otherwise collide for every FR-less row in the same session (they'd
    all share the same blank ("", "") pair).
    """
    first_ar, last_ar = split_arabic_name(row["ar"])
    if row.get("fr"):
        first_fr, last_fr = split_latin_name(row["fr"])
        return first_fr, last_fr, first_ar, last_ar
    return first_ar, last_ar, first_ar, last_ar


# ═══════════════════════════════════════════════════════════════════════
# Command
# ═══════════════════════════════════════════════════════════════════════


class Command(BaseCommand):
    help = (
        "EXEMPLARY: seed Session + Participant batches from 5 نهائي nominal "
        "list documents, auto-creating Formation/Trainer/Client/Branch/"
        "Specialty on the fly when no confident catalog match exists."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Resolve/print everything without writing to the database.",
        )

    def handle(self, *args, **options):
        self.dry_run = options["dry_run"]

        from clients.models import Client
        from formations.models import Branch, Formation, Participant, Session, Specialty
        from resources.models import Trainer

        self.Client = Client
        self.Branch = Branch
        self.Formation = Formation
        self.Participant = Participant
        self.Session = Session
        self.Specialty = Specialty
        self.Trainer = Trainer

        self._info(f"Session batch ({len(SESSION_SEED_DATA)} nominal lists)")

        try:
            with transaction.atomic():
                for entry in SESSION_SEED_DATA:
                    self._process_entry(entry)
                if self.dry_run:
                    raise _RollbackDryRun()
        except _RollbackDryRun:
            self.stdout.write(
                self.style.WARNING("\n  --dry-run: rolled back, nothing was written.")
            )

    # ── one nominal list → one Session + its Participants ──────────────
    def _process_entry(self, entry: dict):
        self.stdout.write(
            self.style.MIGRATE_HEADING(f"\n► {entry['formation_title']} [{entry['doc_reference']}]")
        )

        formation = self.resolve_formation(entry["formation_title"], entry["duration_days_hint"])
        client = self.resolve_client(entry["client_name"])
        trainer = self.resolve_trainer(entry["trainer_ar"], entry["trainer_latin"])

        date_start = parse_ddmmyyyy(entry["date_start"])
        date_end = parse_ddmmyyyy(entry["date_end"])

        session, created = self.Session.objects.get_or_create(
            formation=formation,
            client=client,
            date_start=date_start,
            defaults={
                "trainer": trainer,
                "date_end": date_end,
                "location_type": "on_site",
                "external_location": client.name,
                "capacity": formation.max_participants,
                "status": "completed",
                "session_number": entry["doc_reference"],
                "is_primary": True,
            },
        )
        if created:
            self._ok(f"Session {session.reference} created ({date_start} → {date_end})")
        else:
            self._skip(f"Session {session.reference} (already exists)")

        for row in entry["participants"]:
            self._create_participant(session, row)

    def _create_participant(self, session, row: dict):
        first_name, last_name, first_ar, last_ar = resolve_participant_names(row)
        dob = parse_ddmmyyyy(row["dob"])

        participant, created = self.Participant.objects.get_or_create(
            session=session,
            last_name=last_name,
            first_name=first_name,
            defaults={
                "first_name_ar": first_ar,
                "last_name_ar": last_ar,
                "date_of_birth": dob,
                "place_of_birth": row.get("pob", ""),
                "attended": True,
            },
        )
        if created:
            self._ok(f"  Participant {participant.full_name}")
        else:
            self._skip(f"  Participant {participant.full_name}")

    # ── Formation resolution (fuzzy match → else create) ────────────────
    def resolve_formation(self, title_hint: str, duration_days_hint: int):
        match, ratio = best_fuzzy_match(
            title_hint, self.Formation.objects.all(), key=lambda f: f.title, threshold=0.85
        )
        if match:
            self._ok(f"Formation matched: '{match.title}' (similarity {ratio:.2f})")
            return match

        self.stdout.write(
            self.style.WARNING(
                f"  ⚠ No catalog formation matched '{title_hint}' (best <0.85) — creating it."
            )
        )
        specialty = self.get_or_create_fallback_specialty()
        formation = self.Formation.objects.create(
            title=title_hint,
            title_ar="",
            specialty=specialty,
            duration_days=duration_days_hint,
            duration_hours=duration_days_hint * 7,
            min_participants=3,
            max_participants=20,
            evaluation_type="both",
            produces_certificate=True,
            passing_score=Decimal("10.00"),
            max_score=Decimal("20.00"),
            min_attendance_days=duration_days_hint,
            is_active=True,
        )
        self._ok(
            f"Formation created: '{formation.title}' [{formation.code}] "
            f"— ⚠ review category/specialty link manually"
        )
        return formation

    def get_or_create_fallback_specialty(self):
        branch, branch_created = self.Branch.objects.get_or_create(
            abbreviation=FALLBACK_BRANCH_ABBR,
            defaults=dict(
                abbreviation=FALLBACK_BRANCH_ABBR,
                name="Métiers de l'Eau et de l'Environnement",
                name_ar="مهن المياه و البيئة",
                curriculum_type="qualifiante",
                curriculum_min_months=1,
                curriculum_max_months=6,
            ),
        )
        if branch_created:
            self._ok(f"Branch created: [{branch.abbreviation}] {branch.name}")

        specialty, specialty_created = self.Specialty.objects.get_or_create(
            branch=branch,
            code=FALLBACK_SPECIALTY_CODE,
            defaults=dict(title=FALLBACK_SPECIALTY_TITLE, title_ar=""),
        )
        if specialty_created:
            self._ok(f"Specialty created: [{specialty.reference_root}] {specialty.title}")
        return specialty

    # ── Client resolution (fuzzy match → else create) ───────────────────
    def resolve_client(self, name_hint: str):
        if not name_hint:
            match, _ = best_fuzzy_match(
                NO_CLIENT_SENTINEL_NAME, self.Client.objects.all(), key=lambda c: c.name, threshold=0.9
            )
            if match:
                return match
            client = self.Client.objects.create(
                name=NO_CLIENT_SENTINEL_NAME, address="", city="", is_active=True
            )
            self._ok(f"Client created (sentinel): '{client.name}'")
            return client

        match, ratio = best_fuzzy_match(
            name_hint, self.Client.objects.all(), key=lambda c: c.name, threshold=0.6
        )
        if match:
            self._ok(f"Client matched: '{match.name}' (similarity {ratio:.2f})")
            return match

        self.stdout.write(
            self.style.WARNING(f"  ⚠ No client matched '{name_hint}' (best <0.6) — creating it.")
        )
        client = self.Client.objects.create(name=name_hint, address="", city="", is_active=True)
        self._ok(f"Client created: '{client.name}' — ⚠ review address/legal fields manually")
        return client

    # ── Trainer resolution (fuzzy match → else create) ──────────────────
    def resolve_trainer(self, ar_full_name: str, latin_names: tuple):
        first_ar, last_ar = split_arabic_name(ar_full_name)
        first_latin, last_latin = latin_names

        by_ar = self.Trainer.objects.filter(
            first_name_ar=first_ar, last_name_ar=last_ar
        ).first()
        if by_ar:
            self._ok(f"Trainer matched by Arabic name: {by_ar.full_name}")
            return by_ar

        match, ratio = best_fuzzy_match(
            f"{first_latin} {last_latin}",
            self.Trainer.objects.all(),
            key=lambda t: t.full_name,
            threshold=0.85,
        )
        if match:
            self._ok(f"Trainer matched: {match.full_name} (similarity {ratio:.2f})")
            return match

        self.stdout.write(
            self.style.WARNING(
                f"  ⚠ No trainer matched '{first_latin} {last_latin}' / '{ar_full_name}' — creating it."
            )
        )
        trainer = self.Trainer.objects.create(
            first_name=first_latin,
            last_name=last_latin,
            first_name_ar=first_ar,
            last_name_ar=last_ar,
            specialty="",
            employment_type="external",
            is_active=True,
        )
        self._ok(f"Trainer created: {trainer.full_name} — ⚠ review specialty/contact manually")
        return trainer

    # ── console helpers ──────────────────────────────────────────────────
    def _ok(self, msg: str):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def _skip(self, msg: str):
        self.stdout.write(f"  – {msg} (already exists, skipped)")

    def _info(self, msg: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n► {msg}"))


class _RollbackDryRun(Exception):
    """Raised only under --dry-run to unwind the (non-existent) atomic
    block cleanly; harmless no-op outside a transaction.atomic()."""
