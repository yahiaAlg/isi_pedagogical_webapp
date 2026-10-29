# core/management/commands/seed_session_batch_setif_watania_hbag_comet_lmf.py
"""
Batch seeder for Session + Participant records, sourced directly from the
17 جدول اسمي نهائي (nominal list) documents in this drop (upload IDs
1787053805402 → 1787053805408):

    SARL_SETIF_CITERNE_LA_SURETE_INTERNE_NOMINAL_LIST.doc
    SARL_EL_WATANIA_TRAITEMENT_ET_GESTION_DE_NON_CONFORMITES_NOMINAL_LIST.doc
    SARL_EL_WATANIA_TRAVAUX_D_INTERVENTIONMETHODES_ET_DISCIPLINE_NOMINAL_LIST.doc
    SARL_H_B_A_G_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_NOMINAL_LIST.doc
    SARL_H_B_A_G_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_CND_CONTROLE_NON_DESTRUCTIF_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_PONT_ROULANT_15_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_PREMIERS_SECOURS_NOMINAL_LIST.doc
    SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_QUALIFICATION_DES_SOUDEURS_NOMINAL_LIST.doc
    SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_18_06_2026_NOMINAL_LIST.doc
    SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_20_22_04_2026_NOMINAL_LIST.doc
    SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_20_22_07_2026_NOMINAL_LIST.doc
    SARL_SETIF_CITERNE_CHARIOT_ELÉVATEUR_NOMINAL_LIST.doc
    SARL_SETIF_CITERNE_FORMATION_CPHS_NOMINAL_LIST.doc
    SARL_SETIF_CITERNE_HABILITATION_CHIMIQUE_NOMINAL_LIST.doc

Structural template
────────────────────
Mirrors `seed_session_batch_examplary.py` exactly: every Formation /
Client / Trainer lookup is FUZZY (normalized similarity ratio against the
live catalog seeded by clients_seed.py / formations_seed.py /
trainers_seed.py — see docs/master_backend/master_initial_seed_scripts.md),
falling back to an on-the-spot CREATE (with a "⚠ created — please review"
warning) only when nothing crosses the confidence threshold. `doc_reference`
(the رقم مرجع on the paper PV) is hard-coded into both `session_number` and
`pv_number` on creation, exactly like the exemplary script, so a reprint of
this historical session's nominal list/PV always shows the real paper
number instead of a freshly minted one. All sessions are created with
status="planned", matching the template.

⚠ TWO SOURCE/FILENAME MISMATCHES — please verify against the paper originals
──────────────────────────────────────────────────────────────────────────
  1. The file named
     "SARL_EL_WATANIA_TRAITEMENT_ET_GESTION_DE_NON_CONFORMITES_NOMINAL_LIST.doc"
     does NOT contain an EL WATANIA / Non-Conformités nominal list — its
     actual body is doc_reference "009/12/2025", spécialité "Agent HSE",
     client "SARL NEDJMEDINE PLAST". Transcribed below EXACTLY as the
     document body reads (not as the filename claims) — entry tagged
     "entry_02_MISMATCH_FILENAME" below. Please confirm this is the
     correct paperwork before trusting this session.
  2. The file named
     "SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_20_22_04_2026_NOMINAL_LIST.doc"
     has a body naming the client "ETP KH TRANSFO" (close to the existing
     catalog client "ETB BAZIZI HAMIDA (KH TRANSFO)"), not "SARL MAISON DES
     FILTRES". Transcribed as printed — entry tagged
     "entry_13_MISMATCH_FILENAME" below. Please confirm before trusting.

Other known source-legibility gaps (also flagged inline near each row):
  - Several dates-of-birth on the paper originals are visibly garbled/
    transposed (e.g. "04/25/2004", "2003/01/17", "/05/200129"). Where the
    intended date was unambiguous from context, it was corrected with a
    comment; where it wasn't (e.g. a birth year missing its last digit, or
    a bare year with no day/month), the field was left blank rather than
    guessed, so `parse_ddmmyyyy()` will store it as NULL — review those
    Participant rows manually.
  - A few sessions have exam results (numeric score, or a hand-written
    "غير ناجح" / "غياب" mention) — carried into `exam_score` and
    `attended` where informative; see the participant dicts.

Run
───
    python manage.py seed_session_batch_setif_watania_hbag_comet_lmf
    python manage.py seed_session_batch_setif_watania_hbag_comet_lmf --dry-run
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
# Raw data — transcribed as-is from the 17 نهائي nominal list documents.
# ═══════════════════════════════════════════════════════════════════════

SESSION_SEED_DATA = [
    # ── entry_01 — SARL_SETIF_CITERNE_LA_SURETE_INTERNE ────────────────
    {
        "doc_reference": "017/04/2026",
        "formation_title": "La Sûreté Interne",
        "client_name": "SARL SETIF CITERNE",
        "date_start": "27/04/2026",
        "date_end": "29/04/2026",
        "duration_days_hint": 3,
        "trainer_ar": "كمال بوليفة",
        "trainer_latin": ("Kamel", "Boulifa"),
        "participants": [
            {"ar": "فؤاد سعداوي", "fr": "FOUAD SAADAOUI", "dob": "11/02/1964", "pob": "Sétif"},
            {"ar": "بلال رفاوي", "fr": "BILLEL RAFFAOUI", "dob": "11/10/1989", "pob": ""},
            {"ar": "حسام سبيحي", "fr": "HOUSSEM SEBIHI", "dob": "02/01/1984", "pob": ""},
            {"ar": "عثمان لماي", "fr": "ATHMANE LEMAI", "dob": "30/05/1983", "pob": ""},
            {"ar": "محمد توابي", "fr": "MOHAMAD TOUBI", "dob": "02/01/1979", "pob": ""},
            {"ar": "عمار ذيب", "fr": "AMAR DIB", "dob": "10/06/1977", "pob": ""},
            {"ar": "وليد دعميش", "fr": "WALID DAMICHE", "dob": "25/01/1983", "pob": ""},
            {"ar": "بوعلام قطاف", "fr": "BOUELAM GUETTAF", "dob": "14/06/1978", "pob": ""},
            {"ar": "كمال جودي", "fr": "KAMEL DJOUDI", "dob": "26/11/1994", "pob": ""},
            {"ar": "مصطفى كرمة", "fr": "MOSTAFA KARMA", "dob": "07/01/1983", "pob": ""},
        ],
    },
    # ── entry_02_MISMATCH_FILENAME — filename says EL WATANIA / Non-
    # Conformités; the document BODY is "Agent HSE" for NEDJMEDINE PLAST.
    # Transcribed as the body actually reads — see warning at top of file.
    {
        "doc_reference": "009/12/2025",
        "formation_title": "Agent HSE",
        "client_name": "SARL NEDJMEDINE PLAST",
        "date_start": "08/12/2025",
        "date_end": "11/12/2025",
        "duration_days_hint": 4,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hemani"),
        "participants": [
            {"ar": "كريم خداش", "fr": "KHEDACHE KARIM", "dob": "23/04/1977", "pob": "Bouira"},
            {"ar": "عبدالله هلالي", "fr": "HELLALI ABDELLAH", "dob": "23/02/1985", "pob": "El Eulma"},
            {"ar": "بلقاسم حديوش", "fr": "HADIOUCHE BELKACEM", "dob": "23/10/1981", "pob": "Bouira"},
            {"ar": "غانية موساوي", "fr": "MOUSSAOUI GHANIA", "dob": "30/04/1981", "pob": "Bouira"},
            {"ar": "جميلة حمداش", "fr": "HAMDACHE DJAMILA", "dob": "04/10/1991", "pob": "Bouira"},
            {"ar": "صباح حاج علي", "fr": "HADJ ALI SABAH", "dob": "11/04/1993", "pob": "Bouira"},
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "Bouira"},
            {"ar": "زكية يحياوي", "fr": "YAHAIAOUI ZAKIA", "dob": "30/07/1990", "pob": "Bouira"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "Bouira"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "Bouira"},
            {"ar": "سارة سيد عثمان", "fr": "SID ATMANE SARAH", "dob": "07/09/1994", "pob": "Bouira"},
            {"ar": "فروجة عبدربي", "fr": "ABDEREBBI FAROUDJA", "dob": "01/06/2000", "pob": "Tizi Ouzou"},
            {"ar": "محمد لعربي", "fr": "LARBI MOHMMED", "dob": "05/11/1993", "pob": "Bouira"},
            {"ar": "سيدعلي بنينال", "fr": "BENNAIL SID ALI", "dob": "19/03/1993", "pob": "Bouira"},
            {"ar": "فارس نبيق مناع", "fr": "NEBIG MENAA FARES", "dob": "21/06/1992", "pob": "Bouira"},
        ],
    },
    # ── entry_03 — SARL_EL_WATANIA_TRAVAUX_D_INTERVENTIONMETHODES_ET_DISCIPLINE
    {
        "doc_reference": "013/04/2026",
        "formation_title": "Travaux d'Intervention Méthodes et Discipline",
        "client_name": "SARL ELWATANIA",
        "date_start": "19/04/2026",
        "date_end": "20/04/2026",
        "duration_days_hint": 2,
        "trainer_ar": "رضا مسعود",
        "trainer_latin": ("Reda", "Messaoud"),
        "participants": [
            {"ar": "سيدعلي بنينال", "fr": "BENNIAL SID ALI", "dob": "19/03/1993", "pob": "Ain Bessam"},
            {"ar": "مراد بوتمر", "fr": "BOUTEMEUR MOURAD", "dob": "10/10/1980", "pob": "Tizi Ouzou"},
            {"ar": "زكية يحياوي", "fr": "YAHAIAOUI ZAKIA", "dob": "30/07/1990", "pob": "Bechloul"},
            {"ar": "ثللي ادر", "fr": "IDER THILLELI", "dob": "08/12/1998", "pob": "Haizer"},
            {"ar": "محمد لعربي", "fr": "LARBI MOHAMMED", "dob": "05/11/1993", "pob": "Bouira"},
            {"ar": "نصيرة زكنون", "fr": "ZAKNOUN NACERA", "dob": "04/10/1984", "pob": "Bouira"},
            {"ar": "فهيمة شكمام", "fr": "CHEKMAM FAHIMA", "dob": "25/05/1992", "pob": "Bouira"},
            {"ar": "جميلة حمداش", "fr": "HAMDACHE DJAMILA", "dob": "04/10/1991", "pob": "Haizer"},
            {"ar": "نصيرة وشن", "fr": "OUCHENE NASSIRA", "dob": "10/05/1991", "pob": "Lakhdaria"},
            {"ar": "حاج علي صباح", "fr": "SABAH HADJ-ALI", "dob": "11/04/1993", "pob": "Draa El Mizan"},
        ],
    },
    # ── entry_04 — SARL_H_B_A_G_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES
    {
        "doc_reference": "010/04/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "SARL H-BAG",
        "date_start": "19/04/2026",
        "date_end": "23/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hemani"),
        "participants": [
            {"ar": "نور الدين بن شنوف", "fr": "NOUREDDINE BENCHENOUF", "dob": "21/06/1974", "pob": "Constantine"},
            {"ar": "عبد النور بلعايب", "fr": "ABDNOUR BELAIB", "dob": "02/02/1998", "pob": "Ain Azel"},
            {"ar": "صبيحة نزار", "fr": "SEBIHA NEZAR", "dob": "21/05/2006", "pob": "Ain Azel"},
            {"ar": "هشام زياني", "fr": "HICHEM ZIANI", "dob": "09/07/1985", "pob": "Ain Oulmane"},
            {"ar": "أحمد ذويبي", "fr": "AHMED DHOUIBI", "dob": "10/06/1998", "pob": "Ain Oulmane"},
            {"ar": "علاوة رقايقي", "fr": "ALLAOUA REGUAIGUI", "dob": "16/04/1985", "pob": "Ain Lahdjar"},
            {"ar": "خير الدين خلفون", "fr": "KHEIREDDINE KHALFOUN", "dob": "09/02/1996", "pob": "Ain Lahdjar"},
            {"ar": "خير الدين غول", "fr": "KHEIREDDINE GHOUL", "dob": "05/12/1996", "pob": "Ain Oulmane"},
            {"ar": "حمزة هيشور", "fr": "HAMZA HAICHOUR", "dob": "12/01/2003", "pob": "Sétif"},
            {"ar": "بدر الدين هادي", "fr": "BADREDDINE HADDI", "dob": "16/07/2004", "pob": "Sétif"},
            {"ar": "زينو ربيح", "fr": "ZINOU REBIH", "dob": "26/11/2005", "pob": "Sétif"},
            {"ar": "عيسى كرماش", "fr": "AISSA KERMACHE", "dob": "16/07/2006", "pob": "Sétif"},
            {"ar": "نسيم شوار", "fr": "NASSIM CHOUAR", "dob": "06/08/2003", "pob": "Ain Oulmane"},
        ],
    },
    # ── entry_05 — SARL_H_B_A_G_HABILITATION_ELECTRIQUE ────────────────
    # Source gives per-participant exam results (numeric /20, or a
    # hand-written "غير ناجح" = "did not pass" with no number) — carried
    # into exam_score / notes below.
    {
        "doc_reference": "008/05/2026",
        "formation_title": "Habilitation Electrique (Basse Tension BR)",
        "client_name": "SARL H.B.A.G",
        "date_start": "10/05/2026",
        "date_end": "14/05/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hemani"),
        "participants": [
            {"ar": "نور الدين بن شنوف", "fr": "NOUR EDDINE BENCHENOUF", "dob": "21/06/1974", "pob": "", "exam_score": "14.00"},
            {"ar": "رابح ساتة", "fr": "RABAH SETTA", "dob": "01/03/1976", "pob": "", "exam_score": "13.00"},
            {"ar": "عقبة دلة", "fr": "OKBA DELLA", "dob": "13/09/1984", "pob": "", "exam_score": "14.00"},
            {"ar": "أيوب هيشور", "fr": "AYOUB HAICHOUR", "dob": "11/06/2002", "pob": "", "notes": "غير ناجح (échec — mention manuscrite, pas de note chiffrée)"},
            {"ar": "عبد الرحيم نواصرية", "fr": "ABD EL-RAHIM NOUASSRIA", "dob": "24/06/2000", "pob": "", "notes": "غير ناجح (échec — mention manuscrite, pas de note chiffrée)"},
            # Source date is transposed: "/05/200129" — read as 29/05/2001.
            {"ar": "بلال عباس", "fr": "BILLEL ABBAS", "dob": "29/05/2001", "pob": "", "notes": "غير ناجح (échec — mention manuscrite, pas de note chiffrée); DOB transposée sur l'original : « /05/200129 » lue 29/05/2001"},
        ],
    },
    # ── entry_06 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_CND_CONTROLE_NON_DESTRUCTIF
    {
        "doc_reference": "005/04/2026",
        "formation_title": "CND Contrôle Non Destructif",
        "client_name": "COMET",
        "date_start": "05/04/2026",
        "date_end": "08/04/2026",
        "duration_days_hint": 4,
        "trainer_ar": "عبد النور ليمام",
        "trainer_latin": ("Abdenour", "Limam"),
        "participants": [
            {"ar": "لياس زنين", "fr": "LYES ZENINA", "dob": "04/08/1993", "pob": "Sétif"},
            {"ar": "يوسف لفي", "fr": "YOUCEF LAFI", "dob": "01/04/1996", "pob": "Sétif"},
            {"ar": "عبد المالك كرواني", "fr": "ABDELMALEK KEROUANI", "dob": "23/05/1999", "pob": "Sétif"},
            {"ar": "مروان سيد علي زنين", "fr": "MAROUANE SIDALI ZENINA", "dob": "26/04/2001", "pob": "Sétif"},
        ],
    },
    # ── entry_07 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES
    {
        "doc_reference": "021/04/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "COMET",
        "date_start": "26/04/2026",
        "date_end": "30/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hemani"),
        "participants": [
            {"ar": "أسامة بحروني", "fr": "OUSSAMA BAHROUNI", "dob": "06/03/1986", "pob": "Tunis"},
            {"ar": "لجسن راشدي", "fr": "LAHCENE RACHEDI", "dob": "03/08/1969", "pob": "Sétif"},
            # Source date is out-of-range for dd/mm ("04/25/2004"); read as 25/04/2004.
            {"ar": "سيف الإسلام عبسي", "fr": "SEIF EL ISLAM ABSI", "dob": "25/04/2004", "pob": "Tébessa"},
            {"ar": "عمار كرميش", "fr": "AMAR KERMICHE", "dob": "03/01/1998", "pob": "Ain Roua"},
            {"ar": "نبيل العيدودي", "fr": "NABIL LAIDOUDI", "dob": "26/03/1996", "pob": "Bougaa"},
        ],
    },
    # ── entry_08 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_HABILITATION_ELECTRIQUE
    {
        "doc_reference": "003/03/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "SARL MAGHREB TRAILER INDUSTRIE",
        "date_start": "01/03/2026",
        "date_end": "05/03/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hemani"),
        "participants": [
            {"ar": "أحمد مقصود", "fr": "AHMED MAKSOUD", "dob": "16/02/1993", "pob": ""},
            {"ar": "يحي خضار", "fr": "YAHIA KHEDDAR", "dob": "24/09/1999", "pob": ""},
            # Source date is ISO-ordered ("2003/01/17"); read as 17/01/2003.
            {"ar": "مهدي دخوش", "fr": "MAHDI DEKHOUCHE", "dob": "17/01/2003", "pob": ""},
            {"ar": "هيثم ضياء الدين بن دريهم", "fr": "HAITHEM DHIAADINNE BENDRIHEM", "dob": "21/05/2007", "pob": ""},
            {"ar": "إسحاق بوطهرة", "fr": "ISHAK BOUTAHRA", "dob": "27/09/1998", "pob": ""},
        ],
    },
    # ── entry_09 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_PONT_ROULANT_15 ─
    {
        "doc_reference": "003/05/2026",
        "formation_title": "La Conduite Sécuritaire des Pont Roulants",
        "client_name": "COMET",
        "date_start": "03/05/2026",
        "date_end": "04/05/2026",
        "duration_days_hint": 2,
        "trainer_ar": "رابح ابعزيز",
        # Spelling variant of the same trainer as "رابح ابازيز" elsewhere
        # in the catalog/seed data — same manual Latin transliteration
        # kept for consistent matching.
        "trainer_latin": ("Rabah", "Abaziz"),
        "participants": [
            {"ar": "عبد الرزاق قمجي", "fr": "ABDRAZEK KAMEDJI", "dob": "08/04/2006", "pob": ""},
            {"ar": "ياسين شوقي", "fr": "YASSINE CHOUGUI", "dob": "30/05/2002", "pob": ""},
            {"ar": "عبد الله قايدي", "fr": "ABDELLAH GAIDI", "dob": "06/01/2001", "pob": ""},
            {"ar": "إسحاق بوطهرة", "fr": "ISHAK BOUTAHRA", "dob": "27/09/1998", "pob": ""},
            {"ar": "ولحة وليم", "fr": "OULHA OULIM", "dob": "17/10/1980", "pob": ""},
            {"ar": "محمد ياسين بن بهوش", "fr": "MOHAMED YACINE BENBAHOUCHE", "dob": "30/03/1997", "pob": ""},
            {"ar": "يحى بصحراوي", "fr": "YAHIA BESSAHRAOUI", "dob": "16/05/2001", "pob": ""},
            {"ar": "إلياس جليلي", "fr": "ILYES DJELLILI", "dob": "11/09/2007", "pob": ""},
        ],
    },
    # ── entry_10 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_PREMIERS_SECOURS
    {
        "doc_reference": "001/04/2026",
        "formation_title": "Premiers Secours",
        "client_name": "SARL MAGHREB TRAILER INDUSTRIE",
        "date_start": "02/04/2026",
        "date_end": "04/04/2026",
        "duration_days_hint": 2,
        "trainer_ar": "مسعادي محمد",
        "trainer_latin": ("Messaadi", "Mohamed"),
        "participants": [
            {"ar": "عمار كرميش", "fr": "AMAR KERMICHE", "dob": "03/01/1998", "pob": "Ain Roua"},
            {"ar": "إسحاق بوطهرة", "fr": "ISHAK BOUTAHRA", "dob": "27/09/1998", "pob": "Sétif"},
            {"ar": "خليل غجاتي", "fr": "KHALIL GHEDJATI", "dob": "19/11/1996", "pob": "Sétif"},
            {"ar": "خليل ذهبي", "fr": "KHALIL DAHBI", "dob": "06/10/1981", "pob": "Sétif"},
            {"ar": "يعقوب بلالي", "fr": "YAAKOUB BELLALI", "dob": "01/09/2000", "pob": "Ain El Kebira"},
            {"ar": "ارزقي عزيب", "fr": "AREZKI AZIB", "dob": "23/04/1995", "pob": "Amizour"},
        ],
    },
    # ── entry_11 — SARL_MAGHREB_TRAILER_INDUSTRIE_COMET_QUALIFICATION_DES_SOUDEURS
    {
        "doc_reference": "003/07/2026",
        "formation_title": "Qualification des Soudeurs",
        "client_name": "COMET",
        "date_start": "12/07/2026",
        "date_end": "16/07/2026",
        "duration_days_hint": 5,
        "trainer_ar": "عبد النور ليمام",
        "trainer_latin": ("Abdenour", "Limam"),
        "participants": [
            {"ar": "مصطفى شرف الدين عيسى", "fr": "MUSTAPHA CHAREF EDDINE AISSA", "dob": "16/01/1999", "pob": "Sétif"},
            {"ar": "سيد علي بوقرار", "fr": "SIDALI BOUGRARA", "dob": "23/03/1992", "pob": "Batna"},
            {"ar": "بلال واضح", "fr": "BILEL OUADAH", "dob": "01/08/1991", "pob": "El Hamma"},
            {"ar": "عمر بن شعبان", "fr": "OMAR BENCHABEN", "dob": "03/07/1997", "pob": "Tunis"},
            {"ar": "عبد النور نواري", "fr": "ABDENOUR NOUARI", "dob": "11/11/1996", "pob": "Sétif"},
            {"ar": "الوليد بوصفصاف", "fr": "ELOUALID BOUSAFSAF", "dob": "23/07/1994", "pob": "El Eulma"},
            {"ar": "رضا بن عيسى", "fr": "REDHA BENAISSA", "dob": "24/12/2004", "pob": "Bordj Bou Arreridj"},
            {"ar": "عبد الناصر بورويس", "fr": "ABDENASSER BOUROUIS", "dob": "13/12/1999", "pob": "Tunis"},
            {"ar": "أيوب زقادي", "fr": "AYOUB ZEGADI", "dob": "10/03/2000", "pob": "Bir Kasdali"},
        ],
    },
    # ── entry_12 — SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_18_06_2026
    {
        "doc_reference": "015/06/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "SARL MAISON DES FILTRES",
        "date_start": "18/06/2026",
        "date_end": "18/06/2026",
        "duration_days_hint": 1,
        "trainer_ar": "عبد الحق لحبيب",
        "trainer_latin": ("Abdelhak", "Lahbib"),
        "participants": [
            {"ar": "مراد قروامسة", "fr": "MOURAD GUEROUAMSSA", "dob": "12/08/1992", "pob": "Médéa", "exam_score": "15.50"},
            {"ar": "عثمان مقلاتي", "fr": "OTHMANE MEGUELLATI", "dob": "05/06/1987", "pob": "Médéa", "exam_score": "16.50"},
        ],
    },
    # ── entry_13_MISMATCH_FILENAME — filename says "MAISON DES FILTRES";
    # the document BODY names the client "ETP KH TRANSFO" (near-match to
    # the catalog's "ETB BAZIZI HAMIDA (KH TRANSFO)"). Transcribed as the
    # body actually reads — see warning at top of file.
    {
        "doc_reference": "012/04/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "ETP KH TRANSFO",
        "date_start": "20/04/2026",
        "date_end": "22/04/2026",
        "duration_days_hint": 3,
        "trainer_ar": "عبد الحق لحبيب",
        "trainer_latin": ("Abdelhak", "Lahbib"),
        "participants": [
            {"ar": "لمين كرنو", "fr": "LAMINE KERNOU", "dob": "11/06/1990", "pob": ""},
            {"ar": "سفيان معوش", "fr": "SOFIANE MAOUCHE", "dob": "16/07/1980", "pob": ""},
            {"ar": "خالد أوغليس", "fr": "KHALED OUGHLIS", "dob": "15/07/1980", "pob": ""},
        ],
    },
    # ── entry_14 — SARL_MAISON_DES_FILTRE_LMF_HABILITATION_ELECTRIQUE_20_22_07_2026
    {
        "doc_reference": "007/07/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "SARL MAISON DES FILTRES",
        "date_start": "20/07/2026",
        "date_end": "22/07/2026",
        "duration_days_hint": 3,
        "trainer_ar": "عبد الحق لحبيب",
        "trainer_latin": ("Abdelhak", "Lahbib"),
        "participants": [
            {"ar": "عبد القادر ضحاك", "fr": "ABDELKADER DAHAK", "dob": "30/01/1973", "pob": ""},
            {"ar": "عبد الكريم قوادري", "fr": "ABDELKRIM KOUADRI", "dob": "13/06/1996", "pob": ""},
            {"ar": "عبد الحق متيجي", "fr": "ABDELHAK METIDJI", "dob": "05/04/1999", "pob": ""},
        ],
    },
    # ── entry_15 — SARL_SETIF_CITERNE_CHARIOT_ELÉVATEUR ────────────────
    {
        "doc_reference": "002/12/2024",
        "formation_title": "L'habilitation Conduite des Chariots Élévateurs",
        "client_name": "SARL SETIF CITERNE",
        "date_start": "30/11/2024",
        "date_end": "04/12/2024",
        "duration_days_hint": 5,
        "trainer_ar": "محمد بومدين",
        "trainer_latin": ("Mohamed", "Boumediene"),
        "participants": [
            {"ar": "جابر خالدي", "fr": "KHADRI DHABER", "dob": "07/09/1992", "pob": "Sétif"},
            {"ar": "إبراهيم رفاوي", "fr": "RAFFAOUI BRAHIM", "dob": "27/12/1981", "pob": "Sétif"},
            {"ar": "عبد الله ترشاق", "fr": "TERCHAK ABDALLAH", "dob": "03/03/1985", "pob": "Sétif"},
            {"ar": "مصطفى كرمة", "fr": "KARMA MOSTAFA", "dob": "07/01/1983", "pob": "Sétif"},
            {"ar": "عبد الحميد رتمة", "fr": "RATMA ABDELHAMID", "dob": "14/10/1987", "pob": "Sétif"},
            {"ar": "السعيد مدبر", "fr": "MOUDABAR SAID", "dob": "03/05/1995", "pob": "Sétif"},
            {"ar": "أسامة كمال الدين جودي", "fr": "DJOUDI OUSSAMA KAMEL EDDINE", "dob": "26/11/1994", "pob": "Sétif"},
            {"ar": "فؤاد أرقاز", "fr": "AREGAZ FOUAD", "dob": "03/01/1984", "pob": "Sétif"},
            {"ar": "يوسف بخوش", "fr": "BAKHOUCHE YOUCEF", "dob": "19/10/1990", "pob": "Sétif"},
            # Source gives only a bare year ("1978") — no day/month on the
            # paper original; DOB left blank rather than guessed.
            {"ar": "سليم نقاش", "fr": "NAKACHE SALIM", "dob": "", "pob": "Msila", "notes": "Date de naissance illisible sur l'original — seule l'année « 1978 » est indiquée."},
            {"ar": "سعيد دويبي", "fr": "DOUIBI SAID", "dob": "02/08/1985", "pob": "Sétif"},
            {"ar": "موادنة يوسف", "fr": "MOUADNA YOUCEF", "dob": "05/11/1992", "pob": "Sétif"},
            {"ar": "اوشان اشرف", "fr": "OUCHANE ACHREF", "dob": "17/09/1993", "pob": "Sétif"},
        ],
    },
    # ── entry_16 — SARL_SETIF_CITERNE_FORMATION_CPHS ───────────────────
    {
        "doc_reference": "004/06/2024",
        "formation_title": "Commission Paritaire HSE",
        "client_name": "SARL Sétif Citerne",
        # Source prints these two dates ISO-ordered (YYYY/MM/DD) instead
        # of the document's usual DD/MM/YYYY — reordered here to DD/MM/YYYY
        # so parse_ddmmyyyy() below reads them correctly.
        "date_start": "23/06/2024",
        "date_end": "27/06/2024",
        "duration_days_hint": 5,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        "participants": [
            # Source DOB is truncated ("01/10/197" — missing the final
            # year digit); left blank rather than guessed.
            {"ar": "برهان الدين يحي الشريف", "fr": "YAHIA CHERIF BORHANE EDDINE", "dob": "", "pob": "Constantine", "notes": "Date de naissance tronquée sur l'original : « 01/10/197 » (chiffre manquant)."},
            {"ar": "عزالدين عمورة", "fr": "AMOURA AZZEDDINE", "dob": "28/03/1990", "pob": "Sétif"},
            {"ar": "فؤاد رقاز", "fr": "REGAZ FOUAD", "dob": "03/01/1984", "pob": "Sétif"},
            {"ar": "عبد الله ترشاق", "fr": "TERCHAG ABDELLAH", "dob": "19/03/1985", "pob": "Sétif"},
            {"ar": "زيتوني سعاد", "fr": "ZITOUNI SOUAD", "dob": "12/10/1986", "pob": "Sétif"},
        ],
    },
    # ── entry_17 — SARL_SETIF_CITERNE_HABILITATION_CHIMIQUE ────────────
    # Source marks three rows "غياب" (absent) — carried into attended=False.
    {
        "doc_reference": "009/04/2025",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "SARL SETIF CITERNE",
        "date_start": "10/04/2025",
        "date_end": "17/04/2025",
        "duration_days_hint": 7,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        "participants": [
            {"ar": "عبد الرحمان خلاف", "fr": "KHALEF ABDERRAHMANE", "dob": "25/06/1995", "pob": "", "attended": False},
            {"ar": "نوفل بلجنان", "fr": "BELDJENANE NOUFEL", "dob": "14/12/2005", "pob": "", "attended": False},
            {"ar": "فيصل خروبي", "fr": "KHAROULI FAYCAL", "dob": "19/04/1989", "pob": "Ain Arnat"},
            {"ar": "وليد صالحي", "fr": "SALHI WALID", "dob": "17/07/1984", "pob": "", "attended": False},
            {"ar": "بولنوار منير", "fr": "BOUHLNOUAR MOUNIR", "dob": "03/03/1979", "pob": "Sétif"},
            {"ar": "مراد درباج", "fr": "DERBADJ MOURAD", "dob": "03/02/1972", "pob": "Sétif"},
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
        "Seed Session + Participant batches from the 17 نهائي nominal list "
        "documents for SETIF CITERNE / EL WATANIA / H.B.A.G / MAGHREB "
        "TRAILER INDUSTRIE (COMET) / MAISON DES FILTRES (LMF), "
        "auto-creating Formation/Trainer/Client/Branch/Specialty on the fly "
        "when no confident catalog match exists."
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

        exam_score = row.get("exam_score")
        if exam_score is not None:
            exam_score = Decimal(exam_score)

        participant, created = self.Participant.objects.get_or_create(
            session=session,
            last_name=last_name,
            first_name=first_name,
            defaults={
                "first_name_ar": first_ar,
                "last_name_ar": last_ar,
                "date_of_birth": dob,
                "place_of_birth": row.get("pob", ""),
                "attended": row.get("attended", True),
                "exam_score": exam_score,
                "notes": row.get("notes", ""),
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
