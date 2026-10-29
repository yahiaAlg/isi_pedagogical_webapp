# core/management/commands/seed_session_batch_nominal_2026.py
"""
Batch seeder for Session + Participant records, sourced directly from 16
جدول اسمي نهائي (nominal list) documents:

    GPH_HABILITATION_ELECTRIQUE_5JOURS_NOMINAL_LIST.doc
    GPH_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    GROUP_RIADH_EL_FETH_GESTION_DES_CONFLITS_GROUP01_NOMINAL_LIST.doc
    GROUP_RIADH_EL_FETH_GESTION_DES_CONFLITS_GROUP02_NOMINAL_LIST.doc
    INSPECTA_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    IRIS_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_GROUP_01_NOMINAL_LIST.doc
    IRIS_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_GROUP_02_NOMINAL_LIST.doc
    LOUATI_CATERING_CPHS_L_NOMINAL_LIST.doc
    LOUATI_CATERING_DEVELOPPEMENT_SITE_WEB_NOMINAL_LIST.doc
    LOUATI_CATERING_FORMATION_COMUNICATION_INTERPERSONELLE_NOMINAL_LIST.doc
    LOUATI_CATERING_PREMIERS_SECOURS_NOMINAL_LIST.doc
    MEZLOUG_METAL_COMMUNICATION_INTERPERSONNELLE_EN_ENTREPRISE_1_NOMINAL_LIST.doc
    MEZLOUG_METAL_PLANIFICATION_COMMERCIAL_ET_PRODUCTION_NOMINAL_LIST.doc
    NEDJMEDINE_PLAST_FONDAMENTAUX_ET_ROLE_STRATEGIQUE_DES_ACHATS_NOMINAL_LIST.doc
    NEDJMEDINE_PLAST_MAINTENANCE_PRODUCTION_ET_PLANIFICATION_NOMINAL_LIST.doc
    NICE_PLUS_GESTION_DE_PERSONNEL_NOMINAL_LIST.doc

NOT transcribed
────────────────
    LOUATI_CATERING_FORMATION_INSPECTEUR_HSE_NOMINAL_LIST.doc — the header
    fields (client SNC KEBICH, dates, trainer "اسلام") are present but the
    participant table itself is completely empty (rows 01/02 have no name,
    DOB or place of birth at all). There is nothing to transcribe, so no
    Session/Participant is created for this document — printing it would
    just fabricate data the source doesn't contain.

Two entries below carry a title that does NOT literally appear on their
nominal list ("الاختصاص:" line was either blank or contradicted the
filename) — the ACTUAL text printed in the document's own info block was
used instead of the filename's suggestion:
    - MEZLOUG_METAL_COMMUNICATION_INTERPERSONNELLE_EN_ENTREPRISE_1: the
      document's "الاختصاص:" field literally reads "Gestion Des Ressources
      Humaines", not "Communication Interpersonnelle".
    - NICE_PLUS_GESTION_DE_PERSONNEL: the document's "الاختصاص:" field
      literally reads "GESTION DES CONFLITS", not "Gestion de Personnel".
LOUATI_CATERING_FORMATION_COMUNICATION_INTERPERSONELLE carries no
"الاختصاص:" line at all — "Communication Interpersonnelle" (per the
filename) is used as a best-effort title hint only.

Core idea — identical to seed_session_batch_examplary.py
──────────────────────────────────────────────────────────
A nominal list never guarantees its Formation / Trainer / Client already
exist in the catalog seeded by formations_seed.py / trainers_seed.py /
clients_seed.py, so every lookup below is FUZZY:

    1. Try to find a close-enough existing record (Formation title,
       Client name, Trainer name) using a normalized similarity ratio.
    2. If nothing crosses the confidence threshold, CREATE it on the
       spot with sane defaults, and print a "⚠ created — please review"
       warning instead of silently guessing critical business fields
       (specialty link, pricing, category...).

Run
───
    python manage.py seed_session_batch_nominal_2026
    python manage.py seed_session_batch_nominal_2026 --dry-run
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
# Raw data — transcribed as-is from the 16 نهائي nominal list documents.
# ═══════════════════════════════════════════════════════════════════════

SESSION_SEED_DATA = [
    # ── LOUAI CATERING — Commission Paritaire Hygiène Et Sécurité ──────
    {
        "doc_reference": "014/06/2026",
        "formation_title": "Commission Paritaire Hygiène Et Sécurité",
        "client_name": "LOUAI CATERING",
        "date_start": "01/06/2026",
        "date_end": "04/06/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حطاب محمود",
        # Same trainer already in the master catalog as first_name="MAHMOUD",
        # last_name="HATTAB" — kept in that (first, last) order here too so
        # the latin fuzzy match actually reuses the catalog record instead
        # of creating a duplicate under the reversed word order.
        "trainer_latin": ("Mahmoud", "Hattab"),
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
    # ── LOUAI CATERING — Développement Site Web ─────────────────────────
    {
        "doc_reference": "006/04/2026",
        "formation_title": "Développement Site Web",
        "client_name": "LOUAI CATERING",
        "date_start": "07/04/2026",
        "date_end": "15/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "يحى عبد الرؤوف لخفيف",
        "trainer_latin": ("Yahia Abderraouf", "Lakhfif"),
        "participants": [
            {"ar": "أحمد ليتيم", "fr": "Ahmed litim", "dob": "16/11/1997", "pob": "Skikda"},
        ],
    },
    # ── (no client on document) — Communication Interpersonnelle ───────
    {
        "doc_reference": "001/03/2023",
        # No "الاختصاص:" line at all on this particular nominal list —
        # title is a best-effort hint taken from the filename.
        "formation_title": "Communication Interpersonnelle",
        # No "الزبون:" (client) line at all on this particular nominal
        # list either — treated as an institute-run open session with no
        # sponsoring company, same fallback pattern as the examplary
        # script's "Déchets de Fientes" entry. See resolve_client() below.
        "client_name": "",
        # Source document prints these two dates as YYYY/MM/DD
        # ("2023/03/03" / "2023/03/09") instead of the DD/MM/YYYY used by
        # every other nominal list in this batch — normalized here to
        # DD/MM/YYYY so the same parse_ddmmyyyy() parser works for all
        # entries without a special case.
        "date_start": "03/03/2023",
        "date_end": "09/03/2023",
        "duration_days_hint": 7,
        "trainer_ar": "بلة خليفة",
        # Same trainer already in the master catalog as first_name="KHELIFA",
        # last_name="BELLA" — kept in that order for the same reason as the
        # LOUAI CATERING / CPHS trainer above.
        "trainer_latin": ("Khelifa", "Bella"),
        "participants": [
            # This nominal list's DOB column also carries the place of
            # birth in Arabic, e.g. "1984/11/23 – خراطة -"; both pieces
            # were pulled apart here (dob normalized to DD/MM/YYYY, pob
            # transliterated to Latin) instead of dumping the raw cell
            # into `dob`, consistent with every other entry in this file.
            {"ar": "سماحي منير", "fr": "SMAHI MOUNIR", "dob": "23/11/1984", "pob": "Kherrata"},
            {"ar": "عون عبد الرحيم", "fr": "AOUN ABDERRAHIM", "dob": "13/09/1988", "pob": "Sétif"},
            {"ar": "هدور أنفال", "fr": "HADDOUR ANFAL", "dob": "26/12/1995", "pob": "Sétif"},
            {"ar": "زوغبي كريمة", "fr": "ZOGHBI KARIMA", "dob": "12/04/1983", "pob": "Sétif"},
            {"ar": "لعوارم عماد الدين", "fr": "LAOUAREM IMED EDDINE", "dob": "10/06/1992", "pob": "Sétif"},
        ],
    },
    # ── LOUAI CATERING — Premiers Secours ───────────────────────────────
    {
        "doc_reference": "016/04/2026",
        "formation_title": "Premiers Secours",
        "client_name": "LOUAI CATERING",
        "date_start": "26/04/2026",
        "date_end": "27/04/2026",
        "duration_days_hint": 2,
        "trainer_ar": "مولود حوماد",
        # Same trainer already in the master catalog as first_name="MOULOUD",
        # last_name="HOUMAD".
        "trainer_latin": ("Mouloud", "Houmad"),
        "participants": [
            {"ar": "عريفة موات", "fr": "ARIFA MOUATS", "dob": "25/04/1981", "pob": "Skikda", "score": "17/20"},
            {"ar": "براءة شلي", "fr": "BARAA CHELLI", "dob": "18/02/1999", "pob": "Skikda", "score": "17/20"},
            {"ar": "مريم دعاس", "fr": "MERIEM DAAS", "dob": "04/10/1999", "pob": "Skikda", "score": "17/20"},
            {"ar": "امال بن عاشور", "fr": "AMEL BENACHOUR", "dob": "05/06/1988", "pob": "Skikda", "score": "17/20"},
            {"ar": "غنية يحياوي", "fr": "GHANIA YAHIAOUI", "dob": "21/08/1973", "pob": "Skikda", "score": "17/20"},
            {"ar": "أحمد ليتيم", "fr": "AHMED LITIM", "dob": "16/11/1997", "pob": "Skikda", "score": "17/20"},
            {"ar": "عادل سيسطة", "fr": "ADEL SISTA", "dob": "25/07/1982", "pob": "Skikda", "score": "17/20"},
            {"ar": "زهير دغمان", "fr": "ZOHIR DORMANE", "dob": "02/10/1969", "pob": "Ain Mlila", "score": "17/20"},
            {"ar": "محمد يزلي", "fr": "MOHAMED YEZLI", "dob": "31/03/1975", "pob": "Skikda", "score": "17/20"},
            {"ar": "خديجة أميرة سيد", "fr": "KHADIDJA SID", "dob": "21/12/1997", "pob": "Skikda", "score": "17/20"},
        ],
    },
    # ── MEZLOUG METAL — Gestion Des Ressources Humaines ─────────────────
    {
        "doc_reference": "004/06/2026",
        # See module docstring — the document's own "الاختصاص:" field says
        # "Gestion Des Ressources Humaines", not "Communication
        # Interpersonnelle" (the filename's title).
        "formation_title": "Gestion Des Ressources Humaines",
        "client_name": "MEZLOUG METAL",
        "date_start": "14/06/2026",
        "date_end": "16/06/2026",
        "duration_days_hint": 3,
        "trainer_ar": "صليحة أوطاهر",
        "trainer_latin": ("Saliha", "Aoutaher"),
        "participants": [
            {"ar": "الياس بن طراد", "fr": "BENTRAD LYES", "dob": "07/10/1980", "pob": "Constantine"},
            {"ar": "كريمة زغبي", "fr": "KARIMA ZOGHBI", "dob": "12/04/1983", "pob": "Sétif"},
        ],
    },
    # ── MEZLOUG METAL SARL — Planification (commercial et production) ──
    {
        "doc_reference": "002/03/2026",
        "formation_title": "Planification (commercial et production)",
        # Same real company as "MEZLOUG METAL" above, spelled with the
        # trailing "SARL" here — below the client fuzzy-match threshold
        # (0.6) against each other on the FIRST run, so if this entry is
        # ever processed before the "MEZLOUG METAL" one above, resolve_
        # client() will legitimately create it as a second, separate
        # Client record. Flagged here rather than silently merged, same
        # spirit as every other "⚠ review manually" case in this file.
        "client_name": "MEZLOUG METAL SARL",
        "date_start": "01/03/2026",
        "date_end": "05/03/2026",
        "duration_days_hint": 5,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Reda", "Messaoud"),
        "participants": [
            {"ar": "ياسمين عالم", "fr": "Yasmine alem", "dob": "19/04/1999", "pob": "Sétif"},
            {"ar": "إبتسام جدو", "fr": "Ibtissem djeddou", "dob": "12/05/1996", "pob": "Sétif"},
            {"ar": "محمد السعيد كتفي", "fr": "Mohamed said ketfi", "dob": "06/10/1967", "pob": "SETIF"},
            {"ar": "منير سماحي", "fr": "Mounir smahi", "dob": "26/11/1984", "pob": "bejaia"},
            {"ar": "يازيد خليفي", "fr": "Yazid khelifi", "dob": "07/11/1997", "pob": "Sétif"},
            {"ar": "علي شراقة", "fr": "Ali cheraga", "dob": "07/05/1983", "pob": "Sétif"},
            {"ar": "فطيمة الزهرة علام", "fr": "Fatima zohra alem", "dob": "14/07/1992", "pob": "Sétif"},
            {"ar": "هشام سعود", "fr": "Hichem saoud", "dob": "06/09/1990", "pob": "Ain Oulmene"},
        ],
    },
    # ── SARL ELWATANIA — Fondamentaux Et Rôle Stratégique Des Achats ───
    {
        "doc_reference": "016/06/2026",
        "formation_title": "Fondamentaux Et Rôle Stratégique Des Achats",
        "client_name": "SARL ELWATANIA",
        "date_start": "31/05/2026",
        "date_end": "03/06/2026",
        "duration_days_hint": 4,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Reda", "Messaoud"),
        "participants": [
            {"ar": "فهيمة شكمام", "fr": "FAHIMA CHEKMAM", "dob": "25/05/1992", "pob": "M'Chedallah"},
        ],
    },
    # ── SARL NEDJMEDINE PLAST — Fondamentaux Opération ... ──────────────
    {
        "doc_reference": "001/07/2026",
        "formation_title": (
            "Fondamentaux Opération Dans Une Entreprise Industrielle "
            "(Maintenance-Production et Planification)"
        ),
        "client_name": "SARL NEDJMEDINE PLAST",
        "date_start": "11/07/2026",
        "date_end": "13/07/2026",
        "duration_days_hint": 3,
        # Same trainer as the two "رضا مسعود" entries above — this
        # particular document prints the two words in the opposite order
        # ("مسعود رضا"), transcribed as-is (source fidelity). The AR-exact
        # lookup in resolve_trainer() will therefore NOT match those two,
        # but the shared `trainer_latin` tuple below makes the latin
        # fuzzy-match fallback reuse the same Trainer record regardless.
        "trainer_ar": "مسعود رضا",
        "trainer_latin": ("Reda", "Messaoud"),
        "participants": [
            {"ar": "يحى تشير", "fr": "YAHIA TCHEIR", "dob": "10/02/2002", "pob": "Ain Arnat"},
            {"ar": "سفيان ثمراوي", "fr": "SOUFIANE TEMRAOUI", "dob": "03/10/1995", "pob": "Ain Arnat"},
            {"ar": "ميلود دانة", "fr": "MILOUD DANA", "dob": "06/03/1994", "pob": "Ain Arnat"},
            {"ar": "يونس بلهول", "fr": "YOUNES BELHOUL", "dob": "10/10/1994", "pob": "Ras El Ouad"},
        ],
    },
    # ── EURL MADJOUR — Gestion Des Conflits ─────────────────────────────
    {
        "doc_reference": "008/12/2025",
        # See module docstring — the document's own "الاختصاص:" field says
        # "GESTION DES CONFLITS", not "Gestion De Personnel" (the
        # filename's title).
        "formation_title": "Gestion Des Conflits",
        "client_name": "EURL MADJOUR",
        "date_start": "01/12/2025",
        "date_end": "02/12/2025",
        "duration_days_hint": 2,
        # Same trainer as "MEZLOUG METAL"'s session above, printed here in
        # the opposite word order ("أوطاهر صليحة") — transcribed as-is,
        # deduplicated via the shared `trainer_latin` tuple exactly like
        # the "رضا مسعود" / "مسعود رضا" case above.
        "trainer_ar": "أوطاهر صليحة",
        "trainer_latin": ("Saliha", "Aoutaher"),
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
    # ── G.P.H — Habilitation Electrique (Charge De Consignation BC.HC) ─
    {
        "doc_reference": "013/03/2026",
        "formation_title": "Habilitation Electrique (Charge De Consignation BC.HC)",
        "client_name": "G.P.H",
        "date_start": "29/03/2026",
        "date_end": "02/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        # Same trainer already in the master catalog as first_name="BACHIR",
        # last_name="HAMMANI".
        "trainer_latin": ("Bachir", "Hammani"),
        "participants": [
            {"ar": "هشام بلعارم", "fr": "HICHEME BELAREM", "dob": "07/10/1976", "pob": "France", "score": "17/20"},
            {"ar": "عبد سلام بورقبة", "fr": "ABDESSLAM BOURAKBA", "dob": "03/07/1986", "pob": "Sétif", "score": "17/20"},
            {"ar": "مخلوف كشرود", "fr": "MAKHLOUF KECHROUD", "dob": "27/07/1972", "pob": "Sétif", "score": "17/20"},
            {"ar": "صلاح الدين برلة", "fr": "SALAH EDDINE BERLA", "dob": "11/08/1997", "pob": "Sétif", "score": "15/20"},
            {"ar": "محمد طاهر صابر", "fr": "MOHAMED TAHAR SABER", "dob": "28/09/1971", "pob": "Sétif", "score": "13/20"},
            {"ar": "رائد نوري", "fr": "RAID NOURI", "dob": "22/12/1997", "pob": "Sétif", "score": "17/20"},
            {"ar": "صلاح بركات", "fr": "SALAH BARKAT", "dob": "12/02/1990", "pob": "Ain abessa", "score": "15/20"},
            {"ar": "دهيل خالد", "fr": "DEHIL KHALED", "dob": "12/11/1973", "pob": "", "score": "18/20"},
            {"ar": "مسعودي اسامة", "fr": "OUSSAMA MESSAOUDI", "dob": "11/11/1990", "pob": "Sétif", "score": "18/20"},
            {"ar": "محمد امين شوادرة", "fr": "MOHAMED AMINE CHOUADRA", "dob": "26/09/1993", "pob": "Sétif", "score": "15/20"},
            {"ar": "أيوب سناطور", "fr": "AYOUB SENATOR", "dob": "05/07/1984", "pob": "", "score": "17/20"},
            {"ar": "زعبار يوسف", "fr": "ZAABAR YOUCEF", "dob": "28/09/1991", "pob": "Sétif", "score": "16/20"},
            {
                "ar": "بن عثمان عبد العزيز",
                "fr": "BENOTHMANE ABDELAZIZ",
                # Source cell literally reads "08/21/1997" — day/month
                # transposed (month 21 doesn't exist). Corrected to
                # 21/08/1997, which also matches this same participant's
                # DOB on the companion "BR" nominal list below.
                "dob": "21/08/1997",
                "pob": "Sétif",
                "score": "17/20",
            },
        ],
    },
    # ── G.P.H — Habilitation Electrique (Basse Tension BR) ──────────────
    {
        "doc_reference": "012/03/2026",
        "formation_title": "Habilitation Electrique (Basse Tension BR)",
        "client_name": "G.P.H",
        "date_start": "29/03/2026",
        "date_end": "31/03/2026",
        "duration_days_hint": 3,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hammani"),
        # No exam-score column at all on this particular nominal list
        # (blank on every row) — omitted from these rows, unlike the
        # "5 JOURS" list above which does carry scores.
        "participants": [
            {"ar": "أسامة مسعودي", "fr": "OUSSAMA MESSAOUDI", "dob": "11/11/1990", "pob": "Sétif"},
            {
                "ar": "هشام بلعارم",
                "fr": "HICHEM BELAREM",
                # Source cell literally reads "0710/1976" — missing slash.
                "dob": "07/10/1976",
                "pob": "France",
            },
            {"ar": "محمد امين شوادرة", "fr": "MOHAMED AMINE CHOUADRA", "dob": "26/09/1993", "pob": "Sétif"},
            {"ar": "عبد السلام بورقبة", "fr": "ABDESSLAM BOURAKBA", "dob": "27/07/1972", "pob": "Sétif"},
            # NOTE: this document's own DOBs for KECHROUD (below) and
            # BOURAKBA (above) don't match the same two names' DOBs on the
            # companion "5 JOURS" nominal list — an inconsistency in the
            # SOURCE paperwork itself, not a transcription error here.
            # Each nominal list is transcribed exactly as printed rather
            # than "corrected" against the other document.
            {"ar": "مخلوف كشرود", "fr": "MAKHLOUF KECHROUD", "dob": "05/07/1984", "pob": ""},
            {"ar": "أيوب سناطور", "fr": "AYOUB SENATOR", "dob": "05/07/1984", "pob": ""},
            {"ar": "صلاح الدين برلة", "fr": "SALAHEDDINE BERLA", "dob": "11/08/1997", "pob": "Sétif"},
            {"ar": "محمد الطاهر صابر", "fr": "MOHAMED TAHAR SABER", "dob": "28/09/1971", "pob": "Sétif"},
            {"ar": "يوسف زعبار", "fr": "YOUCEF ZAABAR", "dob": "28/09/1991", "pob": "Sétif"},
            {"ar": "رائد نوري", "fr": "RAID NOURI", "dob": "22/12/1997", "pob": "Sétif"},
            {"ar": "صالح بركات", "fr": "SALAH BERKAT", "dob": "12/02/1990", "pob": "Ain Abessa"},
            {"ar": "عبد العزيز بن عثمان", "fr": "ABDELAZIZ BENOTHMANE", "dob": "21/08/1997", "pob": "Sétif"},
            {"ar": "خالد دهيل", "fr": "KHALED DEHIL", "dob": "12/11/1973", "pob": ""},
        ],
    },
    # ── GROUP RIADH EL FETH — Gestion Des Conflits (Groupe 01) ──────────
    {
        "doc_reference": "005/05/2026",
        "formation_title": "Gestion Des Conflits",
        "client_name": "GROUP RIADH EL FETH",
        "date_start": "09/05/2026",
        "date_end": "10/05/2026",
        "duration_days_hint": 2,
        "trainer_ar": "عادل عسول",
        "trainer_latin": ("Adel", "Assoul"),
        "participants": [
            {"ar": "أشرف بوعكاز", "fr": "ACHREF BOUAKAZ", "dob": "08/07/1998", "pob": "Ain Azel"},
            {"ar": "محمد نبيل ربيعي", "fr": "MOHAMED NABIL REBIAI", "dob": "09/12/1999", "pob": "Ain Azel"},
            {"ar": "محمد بن لوصيف", "fr": "MOHAMED BENLOUCIF", "dob": "24/04/1995", "pob": "Ain Azel"},
            {"ar": "حمزة بن خلاف", "fr": "HAMZA BENKHELLEF", "dob": "02/05/1984", "pob": "Ain Azel"},
            {"ar": "رؤوف عمراوي", "fr": "RAOUF AMRAOUI", "dob": "03/03/1985", "pob": "El Eulma"},
            {"ar": "زكرياء راشي", "fr": "ZAKARIA RACHI", "dob": "02/01/1996", "pob": "El Eulma"},
            {"ar": "يوسف جيلاني", "fr": "YOUCEF DJILANI", "dob": "07/09/1980", "pob": "Ain Azel"},
            {"ar": "كمال قاسمي", "fr": "KAMEL GASMI", "dob": "08/08/1971", "pob": ""},
            {"ar": "أنس حداد", "fr": "ANES HADDAD", "dob": "27/05/1989", "pob": "Ain Azel"},
            {"ar": "حسام الدين سعيدي", "fr": "HOUSSAM EDDINE SAIDI", "dob": "08/05/1992", "pob": "El Eulma"},
            {"ar": "أنور بن خلاف", "fr": "ANWAR BENKHELLAF", "dob": "29/08/1989", "pob": "Batna"},
            {"ar": "عمر لعماري", "fr": "AMOR LAMMARI", "dob": "10/04/1975", "pob": "Sétif"},
        ],
    },
    # ── GROUP RIADH EL FETH — Gestion Des Conflits (Groupe 02) ──────────
    {
        "doc_reference": "006/05/2026",
        "formation_title": "Gestion Des Conflits",
        "client_name": "GROUP RIADH EL FETH",
        "date_start": "11/05/2026",
        "date_end": "12/05/2026",
        "duration_days_hint": 2,
        "trainer_ar": "عادل عسول",
        "trainer_latin": ("Adel", "Assoul"),
        "participants": [
            {"ar": "عبد الله طلحي", "fr": "ABD ALLAH TALHI", "dob": "11/08/1999", "pob": "El Eulma"},
            {"ar": "ياسر كاسح", "fr": "YASSER KASSAH", "dob": "04/04/2001", "pob": "Sétif"},
            {"ar": "محمد المهدي بشير", "fr": "MOHAMED EL MAHDI BACHIR", "dob": "04/02/1999", "pob": "El Eulma"},
            {"ar": "أنور حمودة", "fr": "ANOUAR HAMOUDA", "dob": "08/06/1996", "pob": "Ain Azel"},
            {"ar": "حسين حايف", "fr": "HOCINE HAIF", "dob": "10/04/1995", "pob": "Beidha Bordj"},
            {"ar": "خالد قنيفي", "fr": "KHALED GUENIFI", "dob": "27/02/1972", "pob": ""},
            # Source cell literally reads "1984/00/00" — month/day both
            # zero (unusable). Left as-is; parse_ddmmyyyy() below already
            # returns None for any date string it can't parse, so this
            # participant is simply created with date_of_birth=None.
            {"ar": "وليد العيدي", "fr": "WALID LAIDI", "dob": "1984/00/00", "pob": ""},
            {"ar": "أمين عيطو", "fr": "AMINE AITOU", "dob": "21/01/2000", "pob": "Ain Azel"},
            {"ar": "مراد خنصال", "fr": "MOURAD KHANSAL", "dob": "29/10/1997", "pob": "Ain Azel"},
            {"ar": "محمد الأمين بن العوكلي", "fr": "MOHAMED EL AMINE BENLAOUKLI", "dob": "17/02/1992", "pob": "El Eulma"},
            {"ar": "سمير بوعمامة", "fr": "SAMIR BOUAMAMA", "dob": "27/05/1988", "pob": "El Eulma"},
            {"ar": "سيف الإسلام بودغة", "fr": "SEIF EL ISLAM BOUDEGHA", "dob": "14/12/1992", "pob": "El Eulma"},
            {"ar": "يوسف شرف الدين بركات", "fr": "YOUCEF CHARAF EDDINE BARKAT", "dob": "23/05/1994", "pob": "El Eulma"},
        ],
    },
    # ── INSPECTA — Habilitation Electrique ──────────────────────────────
    {
        "doc_reference": "001/06/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "INSPECTA",
        "date_start": "01/06/2026",
        "date_end": "03/06/2026",
        "duration_days_hint": 3,
        "trainer_ar": "عبد الحق لحبيب",
        "trainer_latin": ("Abdelhak", "Lahbib"),
        "participants": [
            {"ar": "محمد نوفل", "fr": "MOHAMED NOUFEL", "dob": "02/10/1981", "pob": "Sétif"},
            {"ar": "محمد سقاي", "fr": "MOHAMED SEKAI", "dob": "25/04/1996", "pob": "Blida"},
            {"ar": "مهدي سليماتني", "fr": "MEHDI SLIMATNI", "dob": "29/08/1998", "pob": "Alger"},
        ],
    },
    # ── IRIS — Habilitation D'utilisation des Produits Chimiques (G01) ──
    {
        "doc_reference": "004/07/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "IRIS",
        "date_start": "19/07/2026",
        "date_end": "23/07/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hammani"),
        "participants": [
            {"ar": "اسماعيل مسكين", "fr": "SMAIL MESKINE", "dob": "28/06/1965", "pob": ""},
            {"ar": "الهادي ازباطن", "fr": "EL HADI IZEBATEN", "dob": "24/12/1988", "pob": ""},
            {"ar": "نصير سماح", "fr": "NACER SAMAH", "dob": "09/02/1987", "pob": ""},
            {"ar": "حمزة قدير", "fr": "HAMZA KEDIR", "dob": "01/11/1993", "pob": ""},
            {"ar": "جمال الدين بكيري", "fr": "DJAMEL EDDINE BAKIRI", "dob": "10/12/1980", "pob": ""},
            {"ar": "باديس كرجاني", "fr": "BADIS KORDJANI", "dob": "18/10/1994", "pob": ""},
            {"ar": "خالد بوعمامة", "fr": "KHALED BOUAMAMA", "dob": "02/07/1997", "pob": ""},
            {"ar": "يوسف بازة", "fr": "YOUCEF BAZA", "dob": "01/10/1988", "pob": ""},
            {"ar": "ساعد خرباشي", "fr": "SAAD KHERBACHI", "dob": "21/01/1985", "pob": ""},
            {"ar": "مراد قوات", "fr": "MOURAD GAOUET", "dob": "03/01/1983", "pob": ""},
            {
                "ar": "عبد الكريم عاشور",
                "fr": "ABD ELKRIM ACHOUR",
                # Source cell literally reads "01/01//1977" (double slash).
                "dob": "01/01/1977",
                "pob": "",
            },
            {"ar": "خالد بلهادي", "fr": "KHALED BELHADI", "dob": "11/10/2001", "pob": ""},
            {"ar": "نصر الدين هنوس", "fr": "NACER EDDINE HENNOUS", "dob": "02/03/1988", "pob": ""},
            {"ar": "عماد دراجي", "fr": "IMAD DERRADJI", "dob": "09/09/1998", "pob": ""},
            {"ar": "عبد الحق زغيدة", "fr": "ABDELHAK ZEGHIDA", "dob": "09/12/1995", "pob": ""},
            {"ar": "نعيم برباقي", "fr": "NAIM BERBAGUI", "dob": "12/06/1992", "pob": ""},
            {"ar": "محمد أنيس ملولي", "fr": "MOHAMED ANIS MELLOULI", "dob": "16/11/1999", "pob": ""},
            {"ar": "مصطفى شارف", "fr": "MUSTAFA CHAREF", "dob": "27/05/1991", "pob": ""},
            # Source cell literally reads "00/00/1971" — day/month both
            # zero (unusable); left as-is, resolves to date_of_birth=None.
            {"ar": "سمير ناصري", "fr": "SAMIR NASRI", "dob": "00/00/1971", "pob": ""},
        ],
    },
    # ── IRIS — Habilitation D'utilisation des Produits Chimiques (G02) ──
    {
        "doc_reference": "002/08/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "IRIS",
        "date_start": "02/08/2026",
        "date_end": "06/08/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hammani"),
        "participants": [
            {"ar": "أحمد رجالين", "fr": "AHMED RIDJALINE", "dob": "24/08/2001", "pob": "Amoucha"},
            {"ar": "شوقي عمران", "fr": "CHAWKI AMRANE", "dob": "25/11/1994", "pob": "Sétif"},
            {"ar": "فوزي العاصمي", "fr": "FAOUZI LASMI", "dob": "27/04/1996", "pob": "Kherrata"},
            {"ar": "إدير صابري", "fr": "IDIR SABRI", "dob": "03/04/1998", "pob": "Bouandas"},
            {"ar": "عبد الغني مكاري", "fr": "ABDALGHANI MEKKARI", "dob": "29/12/1978", "pob": "Tixter"},
            {"ar": "شعبان بوشناق", "fr": "CHAABANE BOUCHENAK", "dob": "11/01/1966", "pob": "Bougaa"},
            {"ar": "نور الإسلام تشير", "fr": "NOUR EL ISLEM TCHIER", "dob": "06/01/1998", "pob": "Sétif"},
            {"ar": "محمد بازة", "fr": "MOHAMED BAZA", "dob": "24/02/1995", "pob": ""},
            {"ar": "عبد الحليم مجاني", "fr": "ABDELHALIM MEDJANI", "dob": "05/04/1988", "pob": ""},
            {"ar": "زين العابدين شعوي", "fr": "ZINEELABIDINE CHAOUI", "dob": "05/12/1991", "pob": ""},
            {"ar": "عبد القادر شوقي", "fr": "ABDELKADER CHOUGUI", "dob": "18/05/1980", "pob": ""},
            {"ar": "لياميني لعجيسي", "fr": "LIAMINI LAADJISSI", "dob": "15/04/1993", "pob": ""},
            {"ar": "يوسف حمادو", "fr": "YOUCEF HAMADOU", "dob": "09/11/1985", "pob": ""},
            {"ar": "نصر الدين بحار", "fr": "NACER EDDINE BAHAR", "dob": "30/06/1990", "pob": ""},
            {"ar": "أيمن مهدي", "fr": "AYMENE MAHDI", "dob": "06/03/2001", "pob": ""},
            {"ar": "محسن مرابط", "fr": "MOHCENE MERABET", "dob": "21/10/1997", "pob": ""},
            {"ar": "هشام بن عياش", "fr": "HICHEM BENAYACHE", "dob": "24/07/1990", "pob": ""},
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
# used so "عبد المومن" / "عبد الرؤوف" aren't split into two separate units.
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
    """Parses a "17/20"-style cell into a Decimal("17.00") out of
    Formation.max_score (always 20 in this dataset). Returns None for
    missing/unparseable values instead of raising, same fail-soft
    convention as parse_ddmmyyyy above."""
    text = (text or "").strip()
    if not text or "/" not in text:
        return None
    numerator = text.split("/")[0].strip()
    try:
        return Decimal(numerator)
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
        "Seed Session + Participant batches from 16 نهائي nominal list "
        "documents, auto-creating Formation/Trainer/Client/Branch/"
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
        exam_score = parse_exam_score(row.get("score", ""))

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
