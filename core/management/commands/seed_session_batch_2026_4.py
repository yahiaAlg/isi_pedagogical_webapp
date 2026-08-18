# formations/management/commands/seed_session_batch_setif_2025_2026.py
"""
Batch seeder for Session + Participant records, transcribed from 17
جدول اسمي نهائي (nominal list) documents (uploaded batch, PV references
spanning 08/12/2025 → 30/06/2026):

    1787053666036_SARL_EL_WATANIA_TENUE_DE_MAGASIN_ET_BONNE_PRATIQUE_DE_RANGEMENT_NOMINAL_LIST.doc
    1787053666037_NEDJMEDINE_PLAST_FONDAMENTAUX_ET_ROLE_STRATEGIQUE_DES_ACHATS_NOMINAL_LIST.doc
    1787053666038_NEDJMEDINE_PLAST_MAINTENANCE_PRODUCTION_ET_PLANIFICATION_NOMINAL_LIST.doc
    1787053666039_NICE_PLUS_GESTION_DE_PERSONNEL_NOMINAL_LIST.doc
    1787053666040_NICE_PLUS_GESTION_DES_COMPETENCES_NOMINAL_LIST.doc
    1787053666040_POWER_TECHT_COMMISSION_PARITAIRE_D_HYGIENE_ET_SECURITE_NOMINAL_LIST.doc
    1787053666041_POWER_TECHT_PREMIERS_SECOURS_NOMINAL_LIST.doc
    1787053666041_SARL_ALGERIA_HAM_MOTORS_TENUE_ET_GESTION_MAGASIN_ET_ENTREPOT_NOMINAL_LIST.doc
    1787053666042_SARL_ATLAS_COMMISSION_PARITAIRE_D_HYGIENE_ET_SECURITE_NOMINAL_LIST.doc
    1787053666042_SARL_EIMI_TRANSFO_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    1787053666043_SARL_EL_WATANIA_CPHS_NOMINAL_LIST.doc
    1787053666043_SARL_EL_WATANIA_FONDAMENTAUX_ET_ROLE_STRATEGIQUE_DES_ACHATS_NOMINAL_LIST.doc
    1787053666044_SARL_EL_WATANIA_GESTION_DE_STOCK_NOMINAL_LIST.doc
    1787053666044_SARL_EL_WATANIA_ISO9001_NOMINAL_LIST.doc
    1787053666045_SARL_EL_WATANIA_MAINTENANCE_INDUSTRIELLE_NOMINAL_LIST.doc
    1787053666045_SARL_EL_WATANIA_NEGOCIATION_ACHATS_ET_LEVIERS_DE_REDUCTION_NOMINAL_LIST.doc
    1787053666046_SARL_EL_WATANIA_TECHNIQUES_D_ACHATS_NOMINAL_LIST.doc

Structural template
────────────────────
This command is a direct structural copy of
`seed_session_batch_examplary.py`: same fuzzy-match-or-create resolution
for Formation/Client/Trainer/Branch/Specialty (`resolve_formation`,
`resolve_client`, `resolve_trainer`, `get_or_create_fallback_specialty`),
same `SESSION_SEED_DATA` list-of-dicts shape, same hard-coded
`doc_reference` → `pv_number` + `session_number`, same `status="planned"`,
same participant AR/FR name + DOB/POB parsing (`resolve_participant_names`,
`split_arabic_name`, `split_latin_name`, `parse_ddmmyyyy`). The catalog
these lookups fuzzy-match against is whatever `clients_seed.py` /
`formations_seed.py` / `trainers_seed.py` (documented in
`master_initial_seed_scripts.md`) has already loaded — genuine non-matches
are created inline exactly as the exemplary script does, with the same
"⚠ created — please review" warnings.

One addition over the exemplary template: several of these nominal lists
carry an "علامة الامتحان" (exam mark) column (out of 20), sometimes marked
"ABSENT" instead of a score. `_create_participant()` below maps that
into `Participant.exam_score` (nullable Decimal) and flips `attended` to
False for an "ABSENT" mark — the exemplary script's 5 source lists never
had this column, so this is new but uses only existing model fields
(Participant.exam_score / Participant.attended — see master_models.md).

Source-document data-quality notes (kept here rather than scattered as
inline comments so they're easy to audit against the original .doc files)
────────────────────────────────────────────────────────────────────────
* Several filenames disagree with what the document body actually says
  (client and/or formation title were evidently copy-pasted from a
  previous nominal list and not fully updated). The BODY text is treated
  as the source of truth in every case below, per entry comments:
    - 036 (filename says "Tenue de Magasin…"): body specialty field
      reads "Agent HSE"; body client reads "SARL NEDJMEDINE PLAST", not
      "SARL EL WATANIA".
    - 037 (filed under NEDJMEDINE_PLAST): body client reads
      "SARL ELWATANIA".
    - 039 / 040 (filename says "Gestion de Personnel" /
      "Gestion des Compétences"): body specialty reads
      "GESTION DES CONFLITS"; body client reads "EURL MADJOUR", not
      "NICE PLUS". These two files are byte-for-byte identical nominal
      lists (same PV ref 008/12/2025) — both are transcribed below and
      will collapse into a single Session via get_or_create.
    - 042a (filename says "SARL ATLAS…"): body client reads
      "SPA EBACOM".
  037 and 043b (FONDAMENTAUX ET ROLE STRATEGIQUE DES ACHATS) are also a
  byte-for-byte duplicate pair (same PV ref 016/06/2026) — both kept
  below for the same reason.
* A handful of DOB/PV cells contain obvious transcription slips
  (extra/missing digit making the date unparseable, or a stray
  character). Where the intended value is unambiguous these are
  corrected with a comment; where a date is merely implausible but
  syntactically valid (e.g. birth years "1930"), it is transcribed
  literally, since "wrong but as-printed" is safer than silently
  guessing a correction for a validation-passing value.
* ISO 9001 list (044b), row 11: the source table's French-name cell was
  left empty and the DOB text was pasted into it by mistake (DOB then
  appears twice). Cross-referenced against the near-identical roster in
  036 (same institute, same intake pool), the person is unambiguously
  "SID ATMANE SARAH" (dob 07/09/1994, BOUIRA) — reconstructed below with
  a comment rather than silently dropped.

Run
───
    python manage.py seed_session_batch_setif_2025_2026
    python manage.py seed_session_batch_setif_2025_2026 --dry-run
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db import transaction

# ═══════════════════════════════════════════════════════════════════════
# Raw data — transcribed as-is from the 17 نهائي nominal list documents.
# ═══════════════════════════════════════════════════════════════════════

SESSION_SEED_DATA = [
    {
        # Source: 1787053666036_..._TENUE_DE_MAGASIN..._NOMINAL_LIST.doc
        # Body specialty/client override the filename — see module
        # docstring. End-date cell was corrupted ("3." — not a date), so
        # date_end is computed from date_start + duration_days_hint
        # instead of transcribed literally.
        "doc_reference": "009/12/2025",
        "formation_title": "Agent HSE",
        "client_name": "SARL NEDJMEDINE PLAST",
        "date_start": "08/12/2025",
        "date_end": "11/12/2025",  # computed: 08/12/2025 + 4j (source cell was "3.")
        "duration_days_hint": 4,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "عبد الله هلالي", "fr": "HELLALI ABDELLAH", "dob": "23/02/1985", "pob": "EL EULMA"},
            {"ar": "غانية موساوي", "fr": "MOUSSAOUI GHANIA", "dob": "30/04/1980", "pob": "BOUIRA"},
            {"ar": "جميلة حمداش", "fr": "HAMDACHE DJAMILA", "dob": "04/10/1991", "pob": "BOUIRA"},
            {"ar": "صباح حاج علي", "fr": "HADJ ALI SABAH", "dob": "11/04/1993", "pob": "BOUIRA"},
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "BOUIRA"},
            {"ar": "زكية يحياوي", "fr": "YAHAIAOUI ZAKIA", "dob": "30/07/1990", "pob": "BOUIRA"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "BOUIRA"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "BOUIRA"},
            {"ar": "سارة سيد عثمان", "fr": "SID ATMANE SARAH", "dob": "07/09/1994", "pob": "BOUIRA"},
            # dob source cell: "01/06/200 TIZIOUZOU" — missing digit, "200" -> 2000
            {"ar": "فروجة عبدربي", "fr": "ABDEREBBI FAROUDJA", "dob": "01/06/2000", "pob": "TIZIOUZOU"},
            {"ar": "محمد لعربي", "fr": "LARBI MOHAMMED", "dob": "05/11/1993", "pob": "BOUIRA"},
            # dob source cell: "19/*03/1993" — stray asterisk removed
            {"ar": "سيدعلي بنينال", "fr": "BENNIAL SID ALI", "dob": "19/03/1993", "pob": "BOUIRA"},
        ],
    },
    {
        # Source: 1787053666037_NEDJMEDINE_PLAST_FONDAMENTAUX..._NOMINAL_LIST.doc
        # Filed under NEDJMEDINE_PLAST but body client reads "SARL ELWATANIA".
        # Byte-for-byte duplicate of the 043b entry below (same PV ref).
        "doc_reference": "016/06/2026",
        "formation_title": "Fondamentaux Et Rôle Stratégique Des Achats",
        "client_name": "SARL ELWATANIA",
        "date_start": "31/05/2026",
        "date_end": "03/06/2026",
        "duration_days_hint": 4,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Rida", "Messaoud"),
        "participants": [
            {"ar": "فهيمة شكمام", "fr": "FAHIMA CHEKMAM", "dob": "25/05/1992", "pob": "M'Chedallah"},
        ],
    },
    {
        # Source: 1787053666038_NEDJMEDINE_PLAST_MAINTENANCE_PRODUCTION..._NOMINAL_LIST.doc
        "doc_reference": "001/07/2026",
        "formation_title": "Fondamentaux Opération Dans Une Entreprise Industrielle "
        "(Maintenance-Production et Planification)",
        "client_name": "SARL NEDJMEDINE PLAST",
        "date_start": "11/07/2026",
        "date_end": "13/07/2026",
        "duration_days_hint": 3,
        # Same trainer as above, name order reversed on this particular
        # document (kept literal — see resolve_trainer()'s AR/fuzzy
        # fallback, exactly like the exemplary script's own caveat).
        "trainer_ar": "مسعود رضا",
        "trainer_latin": ("Messaoud", "Rida"),
        "participants": [
            {"ar": "يحى تشير", "fr": "YAHIA TCHEIR", "dob": "10/02/2002", "pob": "Ain Arnat"},
            {"ar": "سفيان ثمراوي", "fr": "SOUFIANE TEMRAOUI", "dob": "03/10/1995", "pob": "Ain Arnat"},
            {"ar": "ميلود دانة", "fr": "MILOUD DANA", "dob": "06/03/1994", "pob": "Ain Arnat"},
            {"ar": "يونس بلهول", "fr": "YOUNES BELHOUL", "dob": "10/10/1994", "pob": "Ras El Ouad"},
        ],
    },
    {
        # Source: 1787053666039_NICE_PLUS_GESTION_DE_PERSONNEL_NOMINAL_LIST.doc
        # Body specialty/client override the filename — see module docstring.
        # Byte-for-byte duplicate of the 040a entry below (same PV ref).
        "doc_reference": "008/12/2025",
        "formation_title": "Gestion des Conflits",
        "client_name": "EURL MADJOUR",
        "date_start": "01/12/2025",
        "date_end": "02/12/2025",
        "duration_days_hint": 2,
        "trainer_ar": "أوطاهر صليحة",
        "trainer_latin": ("Aoutaher", "Saliha"),
        "participants": [
            {"ar": "أمينة طالب", "fr": "TALEB AMINA", "dob": "16/07/2001", "pob": "AIN AZEL"},
            {"ar": "قمر الدين بن النوي", "fr": "BENNOUI KAMER EDDINE", "dob": "19/07/1998", "pob": "AIN AZEL"},
            {"ar": "خليل مرزوقي", "fr": "MERZOUGUI KHALIL", "dob": "06/02/1993", "pob": ""},
            {"ar": "إسحاق روابح", "fr": "ROUABAH ISHAK", "dob": "30/07/1999", "pob": ""},
            {"ar": "ماجور عبد الغاني", "fr": "MADJOUR ABDELGHANI", "dob": "15/12/1994", "pob": ""},
            {"ar": "إسحاق لعماري", "fr": "LAMARI ISHAK", "dob": "08/08/2000", "pob": "AIN AZEL"},
            {"ar": "ماجور لزهر", "fr": "MADJOUR LAZHAR", "dob": "14/03/1978", "pob": "SETIF"},
        ],
    },
    {
        # Source: 1787053666040_NICE_PLUS_GESTION_DES_COMPETENCES_NOMINAL_LIST.doc
        # Identical roster/PV/dates to the 039 entry above — a second
        # paper copy of the same nominal list filed under a different
        # name. Transcribed as its own entry; get_or_create on
        # (formation, client, date_start) collapses it into the same
        # Session, and Participant get_or_create does the same per row.
        "doc_reference": "008/12/2025",
        "formation_title": "Gestion des Conflits",
        "client_name": "EURL MADJOUR",
        "date_start": "01/12/2025",
        "date_end": "02/12/2025",
        "duration_days_hint": 2,
        "trainer_ar": "أوطاهر صليحة",
        "trainer_latin": ("Aoutaher", "Saliha"),
        "participants": [
            {"ar": "أمينة طالب", "fr": "TALEB AMINA", "dob": "16/07/2001", "pob": "AIN AZEL"},
            {"ar": "قمر الدين بن النوي", "fr": "BENNOUI KAMER EDDINE", "dob": "19/07/1998", "pob": "AIN AZEL"},
            {"ar": "خليل مرزوقي", "fr": "MERZOUGUI KHALIL", "dob": "06/02/1993", "pob": ""},
            {"ar": "إسحاق روابح", "fr": "ROUABAH ISHAK", "dob": "30/07/1999", "pob": ""},
            {"ar": "ماجور عبد الغاني", "fr": "MADJOUR ABDELGHANI", "dob": "15/12/1994", "pob": ""},
            {"ar": "إسحاق لعماري", "fr": "LAMARI ISHAK", "dob": "08/08/2000", "pob": "AIN AZEL"},
            {"ar": "ماجور لزهر", "fr": "MADJOUR LAZHAR", "dob": "14/03/1978", "pob": "SETIF"},
        ],
    },
    {
        # Source: 1787053666040_POWER_TECHT_COMMISSION_PARITAIRE_D_HYGIENE_ET_SECURITE_NOMINAL_LIST.doc
        # Body client cell literally reads "POWER TRCHT" (vs. "POWER
        # TECHT" on the sibling 041a document) — transcribed literally;
        # resolve_client()'s fuzzy match will reconcile the two spellings
        # against whichever is already in the catalog.
        "doc_reference": "006/03/2026",
        "formation_title": "Commission Paritaire d'Hygiène et Sécurité",
        "client_name": "POWER TRCHT",
        "date_start": "14/03/2026",
        "date_end": "18/03/2026",
        "duration_days_hint": 5,
        "trainer_ar": "لعوارم عبد المومن",
        "trainer_latin": ("Laouarem", "Abdelmoumen"),
        "participants": [
            {"ar": "مصطفى بوحفص", "fr": "BOUHAFS MUSTAPHA", "dob": "20/06/1975", "pob": "N'gaous", "exam_score": "15.5"},
            {"ar": "عبد الحليم بونشادة", "fr": "BOUNECHADA ABDELHALIM", "dob": "31/08/1985", "pob": "Ain Azel", "exam_score": "17"},
            {"ar": "سيف الإسلام قاسمي", "fr": "GASMI SIF EL ISLAM", "dob": "27/05/1996", "pob": "Ain Oulmene", "exam_score": "19.5"},
            {"ar": "مهدي حمزاوي", "fr": "HAMZAOUI MAHDI", "dob": "30/10/1986", "pob": "Ain Azel", "exam_score": "16.5"},
            {"ar": "مراد رفيس", "fr": "REFIS MOURAD", "dob": "02/01/1983", "pob": "Ain Azel", "exam_score": "18"},
            {"ar": "خليل رقيعي", "fr": "ROGAI KHALIL", "dob": "07/12/1982", "pob": "Ain Oulmene", "exam_score": "19"},
            {"ar": "عبد الحق روابح", "fr": "ROUABAH ABDELHAK", "dob": "29/01/1999", "pob": "Ain Azel", "exam_score": "18.5"},
            # Same person as this session's trainer, enrolled as a
            # committee participant — plausible for a CPHS commission
            # session; transcribed as printed.
            {"ar": "عبد المومن لعوارم", "fr": "LAOUAREM ABDELMOUMEN", "dob": "18/05/1982", "pob": "Sétif", "exam_score": "18"},
        ],
    },
    {
        # Source: 1787053666041_POWER_TECHT_PREMIERS_SECOURS_NOMINAL_LIST.doc
        "doc_reference": "004/03/2026",
        "formation_title": "Premiers Secours",
        "client_name": "POWER TECHT",
        "date_start": "09/03/2026",
        "date_end": "11/03/2026",
        "duration_days_hint": 3,
        "trainer_ar": "حوماد مولود",
        "trainer_latin": ("Houmad", "Mouloud"),
        "participants": [
            {"ar": "سيف الإسلام قاسمي", "fr": "GASMI SIF ELISLAM", "dob": "27/05/1996", "pob": "AIN OULMENE"},
            {"ar": "سيف الدين لترش", "fr": "SEYF EDDINE LATRECHE", "dob": "27/04/1989", "pob": "AIN AZEL"},
            {"ar": "بن سراي بلال", "fr": "BENSERAI BILEL", "dob": "13/02/1988", "pob": "AIN AZEL"},
            {"ar": "مهدي حمودة", "fr": "MAHDI HAMOUDA", "dob": "26/02/1985", "pob": "AIN AZEL"},
            {"ar": "وليد حيشايشي", "fr": "HECHAICHI WALID", "dob": "09/07/1985", "pob": "AIN AZEL"},
            {"ar": "خليل مطاعي", "fr": "KHALIL METTAI", "dob": "10/03/1994", "pob": "AIN AZEL"},
            {"ar": "ليتيم حمزة", "fr": "HAMZA LITIM", "dob": "10/09/1991", "pob": "AIN AZEL"},
            {"ar": "خالد منصورية", "fr": "KHALED MANSOURIA", "dob": "08/08/1979", "pob": "SETIF"},
            {"ar": "مصطفى مسوس", "fr": "MUSTAPHA MESSOUS", "dob": "10/09/1975", "pob": "SETIF"},
            {"ar": "صوفيان عيطو", "fr": "SOUFIANE AITOU", "dob": "21/04/1994", "pob": "HAMMA"},
            {"ar": "سيف الدين عمران", "fr": "SEFEDDINE AMRANE", "dob": "05/08/2002", "pob": "AIN AZEL"},
            {"ar": "سحنون عبد النور", "fr": "SAHNOUN ABDENNOUR", "dob": "06/08/1996", "pob": "AIN AZEL"},
        ],
    },
    {
        # Source: 1787053666041_SARL_ALGERIA_HAM_MOTORS_TENUE_ET_GESTION_MAGASIN_ET_ENTREPOT_NOMINAL_LIST.doc
        "doc_reference": "015/02/2026",
        "formation_title": "Tenue et Gestion Magasin et Entrepôt",
        "client_name": "SARL ALGERIA HAM MOTORS",
        "date_start": "15/02/2026",
        "date_end": "17/02/2026",
        "duration_days_hint": 3,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Rida", "Messaoud"),
        "participants": [
            {"ar": "علي دامس", "fr": "DAMES ALI", "dob": "02/12/1991", "pob": "ain azel"},
            {"ar": "فوزي دهيمي", "fr": "DEHIMI FAWZI", "dob": "20/06/1992", "pob": "ain lahdjar"},
            {"ar": "محمد لمين زيتوني", "fr": "ZITOUNI MOHAMED LAMINE", "dob": "19/03/1994", "pob": "setif"},
            {"ar": "بلال قراش", "fr": "GUERRACHE BILEL", "dob": "14/12/1994", "pob": "ain azel"},
            {"ar": "سليم بوبلوطة", "fr": "BOUBELLOUTA SELIM", "dob": "21/04/1987", "pob": "ain azel"},
            {"ar": "خلود بوخشيمة", "fr": "Khouloud boukhchima", "dob": "23/08/2000", "pob": "skikda"},
            {"ar": "هديل بلقيدوم", "fr": "Belguidoum hadil", "dob": "23/07/2001", "pob": "ain lahdjar"},
            {"ar": "أحمد بلكبير", "fr": "Blhebir ahmed", "dob": "24/08/1989", "pob": "ain azel"},
        ],
    },
    {
        # Source: 1787053666042_SARL_ATLAS_COMMISSION_PARITAIRE_D_HYGIENE_ET_SECURITE_NOMINAL_LIST.doc
        # Body client overrides the filename — see module docstring.
        "doc_reference": "001/01/2026",
        "formation_title": "Commission Paritaire d'Hygiène et Sécurité",
        "client_name": "SPA EBACOM",
        "date_start": "25/01/2026",
        "date_end": "29/01/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "محمد درياس", "fr": "DRIAS MOHAMED", "dob": "02/10/1983", "pob": "BATNA", "exam_score": "15"},
            {"ar": "علي بكار", "fr": "BEKKAR ALI", "dob": "24/02/1984", "pob": "SETIF", "exam_score": "16"},
            {"ar": "عومار عثماني", "fr": "OTMANI OMAR", "dob": "27/09/1966", "pob": "SETIF", "exam_score": "15"},
            {"ar": "صابر عقيلي", "fr": "SABER AKILI", "dob": "14/10/1985", "pob": "", "exam_score": "16"},
            {"ar": "يوسف زواوي", "fr": "ZOUAOUI YOUCEF", "dob": "29/04/1994", "pob": "Sétif", "exam_score": "16"},
            {"ar": "جملة عبلة", "fr": "DJEMLA ABLA", "dob": "29/12/1974", "pob": "Sétif", "exam_score": "16"},
            # "ABSENT" on the exam-mark column — no score, and not
            # counted as having attended the exam (see _create_participant).
            {"ar": "فارح تواتي", "fr": "TOUATI FAREH", "dob": "08/08/1979", "pob": "Sétif", "exam_score": "ABSENT"},
            {"ar": "عبد الحق عقون", "fr": "AGGOUN ABDELHAK", "dob": "24/02/1978", "pob": "Sétif", "exam_score": "15"},
        ],
    },
    {
        # Source: 1787053666042_SARL_EIMI_TRANSFO_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
        "doc_reference": "010/05/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "SARL EIMI TRANSFO",
        "date_start": "11/05/2026",
        "date_end": "13/05/2026",
        "duration_days_hint": 5,
        "trainer_ar": "عبد الحق لحبيب",
        "trainer_latin": ("Abdelhak", "Lahbib"),
        "participants": [
            {"ar": "نصر الدين مرابط", "fr": "NASR EDDINE MERABET", "dob": "12/03/1987", "pob": ""},
            {"ar": "كمال والي", "fr": "KAMEL OUALI", "dob": "28/03/1983", "pob": "Bourdj Bou Arreridj"},
            {"ar": "بلال شلال", "fr": "BILLEL CHELLAL", "dob": "17/11/1989", "pob": "Sétif"},
            {"ar": "عيسى ماجة", "fr": "AISSA MEDJA", "dob": "03/10/1973", "pob": "Ain Oulmene"},
        ],
    },
    {
        # Source: 1787053666043_SARL_EL_WATANIA_CPHS_NOMINAL_LIST.doc
        "doc_reference": "027/12/2025",
        "formation_title": "Commission Paritaire Hygiène Et Sécurité",
        "client_name": "SARL EL WATANIA",
        "date_start": "25/11/2025",
        "date_end": "27/11/2025",
        "duration_days_hint": 3,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            # dob source cell: "23/04/19977" — extra digit, "19977" -> 1977
            {"ar": "كريم خداش", "fr": "KHEDACHE KARIM", "dob": "23/04/1977", "pob": "BOUIRA"},
            {"ar": "عبد الله هلالي", "fr": "HELLALI ABDELLAH", "dob": "23/02/1985", "pob": "EL EULMA"},
            {"ar": "بلقاسم حديوش", "fr": "HADIOUCHE BELKACEM", "dob": "23/10/1981", "pob": "BOUIRA"},
            # Source row prints the exact same DOB as the row above
            # (23/10/1981) — kept literal, flagged as a likely copy-paste
            # slip in the original document rather than silently changed.
            {"ar": "فروجة عبدربي", "fr": "ABDEREBBI FAROUDJA", "dob": "23/10/1981", "pob": "TIZI OUZOU"},
            {"ar": "محمد لعربي", "fr": "LARBI MOHAMMED", "dob": "05/11/1993", "pob": "BOUIRA"},
            {"ar": "أنيس مداوي", "fr": "MADAOUI ANIS", "dob": "01/01/1999", "pob": "BOUIRA"},
            {"ar": "لتمان شوية", "fr": "CHOUYA LLATAMENE", "dob": "05/02/1990", "pob": "BOUIRA"},
            {"ar": "زكية يحياوي", "fr": "YAHIAOUI ZAKIA", "dob": "30/07/1990", "pob": "BOUIRA"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "BOUIRA"},
        ],
    },
    {
        # Source: 1787053666043_SARL_EL_WATANIA_FONDAMENTAUX_ET_ROLE_STRATEGIQUE_DES_ACHATS_NOMINAL_LIST.doc
        # Identical roster/PV/dates to the 037 entry above — see that
        # entry's note; both are transcribed and will collapse into one
        # Session via get_or_create.
        "doc_reference": "016/06/2026",
        "formation_title": "Fondamentaux Et Rôle Stratégique Des Achats",
        "client_name": "SARL ELWATANIA",
        "date_start": "31/05/2026",
        "date_end": "03/06/2026",
        "duration_days_hint": 4,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Rida", "Messaoud"),
        "participants": [
            {"ar": "فهيمة شكمام", "fr": "FAHIMA CHEKMAM", "dob": "25/05/1992", "pob": "M'Chedallah"},
        ],
    },
    {
        # Source: 1787053666044_SARL_EL_WATANIA_GESTION_DE_STOCK_NOMINAL_LIST.doc
        # End-date source cell reads "2026/04/29" (ISO-like, out of step
        # with every other document's dd/mm/yyyy) — parsed as 29/04/2026.
        "doc_reference": "022/04/2026",
        "formation_title": "Gestion de Stocks",
        "client_name": "SARL EL WATANIA",
        "date_start": "26/04/2026",
        "date_end": "29/04/2026",
        "duration_days_hint": 4,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Rida", "Messaoud"),
        "participants": [
            {"ar": "نصيرة وشن", "fr": "NASSIRA OUCHENE", "dob": "10/05/1991", "pob": "Lakhdaria"},
            {"ar": "زكية يحياوي", "fr": "YAHAIAOUI ZAKIA", "dob": "30/07/1990", "pob": "Bechloul"},
            {"ar": "جميلة حمداش", "fr": "HAMDACHE DJAMILA", "dob": "04/10/1991", "pob": "Haizer"},
            {"ar": "سيدعلي بنينال", "fr": "BENNIAL SID ALI", "dob": "19/03/1993", "pob": "Ain Bessem"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "Haizer"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "Bouira"},
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "Mchedallah"},
            {"ar": "محمد لعربي", "fr": "LARBI MOHAMMED", "dob": "05/11/1993", "pob": "Mchedallah"},
            {"ar": "حاج علي صباح", "fr": "HADJ ALI SABAH", "dob": "11/04/1993", "pob": "Draa El Mizan"},
        ],
    },
    {
        # Source: 1787053666044_SARL_EL_WATANIA_ISO9001_NOMINAL_LIST.doc
        "doc_reference": "023/12/2025",
        "formation_title": "Systèmes de Management de La Qualité ISO 9001 V 2015",
        "client_name": "SARL EL WATANIA",
        "date_start": "09/09/2025",
        "date_end": "11/09/2025",
        "duration_days_hint": 3,
        "trainer_ar": "رضوان عزوز",
        "trainer_latin": ("Redouane", "Azzouz"),
        "participants": [
            {"ar": "كريم خداش", "fr": "KHEDACHE KARIM", "dob": "23/04/1977", "pob": "BOUIRA"},
            {"ar": "عبد الله هلالي", "fr": "HELLALI ABDELLA", "dob": "23/02/1985", "pob": "EL EULMA"},
            {"ar": "بلقاسم حديوش", "fr": "HADIOUCHE BELKACEM", "dob": "23/10/1981", "pob": "BOUIRA"},
            {"ar": "غانية موساوي", "fr": "MOUSSAOUI GHANIA", "dob": "30/04/1980", "pob": "BOUIRA"},
            {"ar": "جميلة حمداش", "fr": "HAMDACHE DJAMILA", "dob": "04/10/1991", "pob": "BOUIRA"},
            # dob source cell ran into the pob cell ("11/04/1993BOUIRA") — split.
            {"ar": "صباح حلج علي", "fr": "HADJ ALI SABAH", "dob": "11/04/1993", "pob": "BOUIRA"},
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "BOUIRA"},
            {"ar": "زكية يحياوي", "fr": "YAHAIAOUI ZAKIA", "dob": "30/07/1990", "pob": "BOUIRA"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "BOUIRA"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "BOUIRA"},
            # Row 11: the source table's FR-name cell was left empty and
            # the DOB text was pasted in twice by mistake — reconstructed
            # from the near-identical 036 roster (same person, same DOB).
            {"ar": "سارة سيدعثمان", "fr": "SID ATMANE SARAH", "dob": "07/09/1994", "pob": "BOUIRA"},
            {"ar": "فروجة عبدربي", "fr": "ABDEREBBI FAROUDJA", "dob": "01/06/2000", "pob": "TIZI OUZOU"},
            # dob "05/11/1930" as printed — implausible but a valid,
            # unambiguous date; transcribed literally (see module docstring).
            {"ar": "محمد لعربي", "fr": "LARBI MOHAMMED", "dob": "05/11/1930", "pob": "BOUIRA"},
            {"ar": "سيد علي بنينال", "fr": "BENNIAL SID ALI", "dob": "19/03/1930", "pob": "BOUIRA"},
            {"ar": "فارس نبيق مناع", "fr": "NEBIG MENAA FARES", "dob": "21/06/1992", "pob": "BOUIRA"},
        ],
    },
    {
        # Source: 1787053666045_SARL_EL_WATANIA_MAINTENANCE_INDUSTRIELLE_NOMINAL_LIST.doc
        "doc_reference": "024/12/2025",
        "formation_title": "Gestion de La Maintenance Industrielle",
        "client_name": "SARL EL WATANIA",
        "date_start": "22/09/2025",
        "date_end": "24/09/2025",
        "duration_days_hint": 3,
        "trainer_ar": "مسعود رضا",
        "trainer_latin": ("Messaoud", "Rida"),
        "participants": [
            {"ar": "عبد الله هلالي", "fr": "HELLALI ABDELLAH", "dob": "23/02/1985", "pob": "EL EULMA"},
            {"ar": "فارس نبيق مناع", "fr": "NEBIG FARES", "dob": "21/06/1992", "pob": "BOUIRA"},
            {"ar": "أمين عبدلاوي", "fr": "ABDELLAOUI AMINE", "dob": "19/02/1996", "pob": "BOUIRA"},
            {"ar": "يحي مادي", "fr": "MADI YAHIA", "dob": "02/11/1992", "pob": "BOUIRA"},
            {"ar": "سمير واكلي", "fr": "OUAKLI SAMIR", "dob": "12/03/1991", "pob": "BOUIRA"},
            {"ar": "محمد رحموني", "fr": "RAHMOUNI MOHAMED", "dob": "11/03/1997", "pob": "BOUIRA"},
            {"ar": "احسن جلاوي", "fr": "DJELLAOUI AHCENE", "dob": "09/09/1989", "pob": "BOUIRA"},
            {"ar": "عبدالحليم لعباسي", "fr": "LABBACI ABDELHALIM", "dob": "23/06/1993", "pob": "BOUIRA"},
            {"ar": "جمال الدين داود", "fr": "DAOUD DJAMEL EDDINE", "dob": "12/05/1987", "pob": "BOUIRA"},
            {"ar": "ايدير سيد عثمان", "fr": "SID ATMANE IDIR", "dob": "23/07/1992", "pob": "BOUIRA"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "BOUIRA"},
            {"ar": "عبد الغاني زايدي", "fr": "ZAIDI ABDELGHANI", "dob": "01/01/1995", "pob": "BOUIRA"},
            {"ar": "انيس مداوي", "fr": "MADAOUI ANIS", "dob": "01/01/1999", "pob": "BOUIRA"},
            {"ar": "لتمان شوية", "fr": "GHOUYA LATAMENE", "dob": "05/02/1990", "pob": "BOUIRA"},
        ],
    },
    {
        # Source: 1787053666045_SARL_EL_WATANIA_NEGOCIATION_ACHATS_ET_LEVIERS_DE_REDUCTION_NOMINAL_LIST.doc
        # doc_reference source cell: "002 /06/2026" — stray space removed.
        "doc_reference": "002/06/2026",
        "formation_title": "Négociation Achats et Leviers de Réduction des Couts",
        "client_name": "SARL EL WATANIA",
        "date_start": "28/06/2026",
        "date_end": "30/06/2026",
        "duration_days_hint": 3,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Rida", "Messaoud"),
        "participants": [
            {"ar": "كنزة إيكان", "fr": "KENZA IKENE", "dob": "29/08/1998", "pob": "Ahnif"},
        ],
    },
    {
        # Source: 1787053666046_SARL_EL_WATANIA_TECHNIQUES_D_ACHATS_NOMINAL_LIST.doc
        "doc_reference": "028/12/2025",
        "formation_title": "Techniques D'achats",
        "client_name": "SARL EL WATANIA",
        "date_start": "02/12/2025",
        "date_end": "04/12/2025",
        "duration_days_hint": 3,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "Bouira"},
            {"ar": "عبد الله هلالي", "fr": "HELLALI ABDELLAH", "dob": "23/02/1985", "pob": "El Eulma"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "Bouira"},
            {"ar": "فروجة عبدربي", "fr": "ABDEREBBI FAROUDJA", "dob": "01/06/2000", "pob": "Tizi-Ouzou"},
        ],
    },
]

# Fallback client used only when a nominal list carries no "الزبون:" line
# at all (spec requires Session.client — it has no null=True/blank=True).
# Not needed by this batch (every one of the 17 lists has a client line),
# kept for structural parity with the exemplary script / future reuse.
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


def parse_exam_score(text: str):
    """
    '15.5/20' -> Decimal('15.5'); '19/20' -> Decimal('19'); 'ABSENT' or
    blank -> None. Matches Participant.exam_score (nullable Decimal,
    max_digits=5, decimal_places=2 — see master_models.md).
    """
    text = (text or "").strip()
    if not text or text.upper() == "ABSENT":
        return None
    text = text.split("/")[0].strip()
    try:
        return Decimal(text)
    except InvalidOperation:
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
        "Seed Session + Participant batches from 17 نهائي nominal list "
        "documents (SARL EL WATANIA, NEDJMEDINE PLAST, EURL MADJOUR, "
        "POWER TECHT, SARL ALGERIA HAM MOTORS, SPA EBACOM, SARL EIMI "
        "TRANSFO), auto-creating Formation/Trainer/Client/Branch/"
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
                "status": "planned",
                "session_number": entry["doc_reference"],
                # Hard-code the REAL PV number transcribed from the paper
                # nominal list/PV document, instead of leaving pv_number
                # blank. Left blank, the first time anyone prints this
                # historical session's nominal list/deliberation report,
                # Session.assign_pv_number() would silently mint a BRAND
                # NEW number off today's active monthly counter — showing
                # a number that never matches the paper original. Setting
                # it here on creation is exactly the same hard-coding
                # path as the session edit form (Session.save() only
                # protects against pv_number being CLEARED, not set), so
                # assign_pv_number() will see it already has a value and
                # skip straight to reusing it, exactly like a normal
                # user-confirmed override.
                "pv_number": entry["doc_reference"],
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

        exam_raw = row.get("exam_score")
        exam_score = parse_exam_score(exam_raw) if exam_raw is not None else None
        # "ABSENT" on the exam-mark column means the participant did not
        # sit the exam — reflected on `attended`, distinct from a normal
        # attendee who simply has no exam_score recorded yet.
        attended = not (exam_raw and exam_raw.strip().upper() == "ABSENT")

        participant, created = self.Participant.objects.get_or_create(
            session=session,
            last_name=last_name,
            first_name=first_name,
            defaults={
                "first_name_ar": first_ar,
                "last_name_ar": last_ar,
                "date_of_birth": dob,
                "place_of_birth": row.get("pob", ""),
                "attended": attended,
                "exam_score": exam_score,
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
