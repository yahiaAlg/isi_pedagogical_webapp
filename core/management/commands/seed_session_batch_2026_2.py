# core/management/commands/seed_session_batch_batch2.py
"""
Batch #2 seeder for Session + Participant records, sourced directly from
the 12 جدول اسمي نهائي (nominal list) documents that were NOT already
covered by `seed_session_batch_examplary.py` (that first batch handled
ALGER_CHIMIE_HABILITATION..., BIOREAL_PHARM_COMMUNICATION...,
BIOREAL_PHARM_LA_SURETE..., EEMS_CPHS..., and EEMS_DECHETS_DE_FIENTES...
only). This batch transcribes the remaining 12:

    EEMS_ENJEUX_DE_LA_FONCTION_RH_ET_MANAGEMENT_RH_NOMINAL_LIST.docx
    EEMS_FORMATION_TRAVAIL_EN_HAUTEUR_NOMINAL_LIST.docx
    ETPB_BAZIZI_HAMIDA_KH_TRANSFO_HABILITATION_ELECTRIQUE_NOMINAL_LIST.docx
    EURL_SOCIETE_ZOUAOUI_ISO_9001_JUIN_2026_NOMINAL_LIST.docx
    EURL_SOCIETE_ZOUAOUI_LES_ÉCRITS_PROFESSIONNELS_NOMINAL_LIST.docx
    EURL_SOCIETE_ZOUAOUI_MONTAGE_ET_INSPECTION_DES_ECHAFAUDAGES_NOMINAL_LIST.docx
    EURL_ZOUAOUI_TC_UNITE_PANNEAUX_SANDWICH_HABILITATION_ELECTRIQUE_NOMINAL_LIST.docx
    GOLDEN_BODY_COMMISSION_PARITAIRE_D_HYGIÈNE_ET_SÉCURITÉ_NOMINAL_LIST.docx
    GPH_COMPTABILITE_GENERALE_NOMINAL_LIST.docx
    GPH_FORMATION_SENSIBILISATION_ATEX_NOMINAL_LIST.docx
    GPH_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_2_JOURS_NOMINAL_LIST.docx
    GPH_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_NOMINAL_LIST.docx

The two "legacy" .doc originals for these files were converted to .docx
before transcription (LibreOffice headless conversion — no textual
content was altered, only the container format).

Core idea — identical to the exemplary batch
──────────────────────────────────────────────
A nominal list never guarantees its Formation / Client / Trainer already
exist in the catalog seeded by formations_seed.py / trainers_seed.py /
clients_seed.py, and titles are transcribed slightly differently between
"official paperwork" and "commercial catalogue" (e.g. this batch's
"Enjeux de La Fonction RH et Management RH" vs. catalog's "Enjeux de la
Fonction RH et le Management des Ressources Humaines"). So instead of a
strict `get_or_create(title=...)`, every lookup below is FUZZY:

    1. Try to find a close-enough existing record (Formation title,
       Client name, Trainer name) using a normalized similarity ratio.
    2. If nothing crosses the confidence threshold, CREATE it on the
       spot with sane defaults, and print a "⚠ created — please review"
       warning instead of silently guessing critical business fields
       (specialty link, pricing, category...).

Two nominal lists in this batch carry rows with no usable participant
data at all (blank "02"/"03" table rows with every cell empty) or a
birthdate cell that isn't a valid dd/mm/yyyy date (a bare year, or an
obvious transcription typo like month "14"). Those are handled the same
way the exemplary batch handled its own blank-cell rows: skipped
entirely if there is no name to transcribe, and passed through
`parse_ddmmyyyy()` — which safely returns None on anything it can't
parse — if there is a name but a malformed date.

Run
───
    python manage.py seed_session_batch_batch2
    python manage.py seed_session_batch_batch2 --dry-run
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
# Raw data — transcribed as-is from the 12 نهائي nominal list documents.
# ═══════════════════════════════════════════════════════════════════════

SESSION_SEED_DATA = [
    {
        "doc_reference": "005/07/2026",
        "formation_title": "Enjeux de La Fonction RH et Management RH",
        # Not a single legal entity — the source document's own "الزبون:"
        # line lists an INTRA-ENTREPRISE cohort spanning several sponsor
        # companies. Transcribed verbatim rather than arbitrarily picking
        # one company; resolve_client() will not find a confident catalog
        # match for this composite string and will create it flagged for
        # manual review, exactly as designed for any non-matching name.
        "client_name": "INTRA – ENTREPRISE (sarl golden body- eurl zouaoui. "
        "spa boirealpharm. Sarl mezlogue metal. Sarl mcsc)",
        "date_start": "19/07/2026",
        "date_end": "23/07/2026",
        "duration_days_hint": 5,
        "trainer_ar": "صليحة أوطاهر",
        "trainer_latin": ("Saliha", "Aoutaher"),
        "participants": [
            {"ar": "محمد مدني", "fr": "MOHAMED MADANI", "dob": "13/08/1989", "pob": "Sétif"},
            {"ar": "دحمان شوادرة", "fr": "DAHMANE CHOUADRA", "dob": "24/04/1998", "pob": "Sétif"},
            {"ar": "محمد أمير بدار", "fr": "MOHAMED AMIR BEDDAR", "dob": "17/07/1996", "pob": "Sétif"},
            {"ar": "الأرقم بلمهدي", "fr": "ELARKEM BELMAHDI", "dob": "24/02/1996", "pob": "Ain Arnat"},
            {"ar": "أسامة بن معماش", "fr": "OUSSAMA BEN MAMECHE", "dob": "06/09/1989", "pob": "Ain Oulmene"},
            {"ar": "فارس عميور", "fr": "FARES AMIOUR", "dob": "15/02/1996", "pob": "El Eulma"},
        ],
    },
    {
        "doc_reference": "001/04/2025",
        "formation_title": "Travail en Hauteur",
        "client_name": "Entreprise Construction Métallique",
        "date_start": "06/04/2025",
        "date_end": "12/04/2025",
        "duration_days_hint": 7,
        "trainer_ar": "لعوارم عبد المومن",
        "trainer_latin": ("Laouar", "Abdelmoumen"),
        # Rows "02" and "03" on this particular nominal list are entirely
        # blank (no AR name, no FR name, no dob) — nothing to transcribe,
        # so they are simply omitted rather than fabricated.
        "participants": [
            {"ar": "فوزي اوتيلي", "fr": "FAOUZI OUTILI", "dob": "05/04/1984", "pob": "Skikda"},
        ],
    },
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
    {
        "doc_reference": "004/08/2025",
        "formation_title": "Systèmes de Management de La Qualité ISO 9001 V 2015",
        # Transcribed exactly as printed on the source document, including
        # its own "ERUL" (rather than "EURL") typo — normalize() lowercases
        # and strips punctuation but does not fix transposed letters, so
        # resolve_client()'s fuzzy match still comfortably clears the 0.6
        # threshold against the catalog's "EURL SOCIETE ZOUAOUI".
        "client_name": "ERUL SOCIETE ZOUAOUI",
        "date_start": "26/08/2025",
        "date_end": "28/08/2025",
        "duration_days_hint": 3,
        "trainer_ar": "رضوان عزوز",
        "trainer_latin": ("Redouane", "Azzouz"),
        "participants": [
            {"ar": "خويرة نور الهدى هيشور", "fr": "HICHOUR KHOUIRA NOUR EL HOUDA", "dob": "17/07/1993", "pob": "Mascara"},
            {"ar": "خولة سيدهم", "fr": "SIDHOUM KHAOULA", "dob": "23/02/1994", "pob": "Setif"},
            {"ar": "نور الهدى عيشور", "fr": "AICHOUR NOUR EL HOUDA", "dob": "03/09/1999", "pob": "Setif"},
            {"ar": "شيماء بوالصوف", "fr": "BOUSOUF CHAIMA", "dob": "29/06/1999", "pob": "Setif"},
            {"ar": "كريم سليماني", "fr": "SLIMANI KARIM", "dob": "15/07/1984", "pob": "Setif"},
            {"ar": "أسامة بلحداد", "fr": "BELHADDAD OUSSAMA", "dob": "26/05/2000", "pob": "Setif"},
            {"ar": "تقي الدين بو الفخار", "fr": "BOULFEKHAR TAKI EDDINE", "dob": "31/03/1993", "pob": "Setif"},
            {"ar": "كريم دويدي", "fr": "DOUIDI KARIM", "dob": "04/12/1999", "pob": "Bougaa"},
            {"ar": "أحمد توفيق بوفياية", "fr": "BOUFAYAYA AHMED TOUFIK", "dob": "17/04/2001", "pob": "Setif"},
            {"ar": "زين العابدين محنان", "fr": "MAHNANE ZINE EL ABIDINE", "dob": "07/05/1995", "pob": "Setif"},
            {"ar": "عبد الكريم لعليوي", "fr": "LALIOUI ABDELKRIM", "dob": "24/07/1980", "pob": "Setif"},
            {"ar": "هباش مريم", "fr": "HABACHE MERIEM", "dob": "06/10/1987", "pob": "Setif"},
        ],
    },
    {
        "doc_reference": "013/02/2025",
        "formation_title": "Les Ecrits Professionnels",
        "client_name": "EURL SOCIETE ZOUAOUI",
        "date_start": "19/02/2025",
        "date_end": "25/02/2025",
        "duration_days_hint": 7,
        "trainer_ar": "محيوت مصطفى",
        "trainer_latin": ("Mustapha", "Mahiout"),
        "participants": [
            {"ar": "نور الهدى عيشور", "fr": "Aichour Nourelhouda", "dob": "03/09/1999", "pob": "Sétif"},
            {"ar": "زايدي الجودي", "fr": "Zaidi Eldjoudi", "dob": "05/02/1999", "pob": "Amizour"},
            {"ar": "زين العابدين محنان", "fr": "Mahnane Zine El Abidine", "dob": "07/05/1995", "pob": "Sétif"},
            {"ar": "وليد جطوي", "fr": "Djetoui Walid", "dob": "04/10/1985", "pob": "Sétif"},
            # AR cell on the source document reads only "زين الدين" (given
            # name), shorter than its own FR transliteration "Makhlouche
            # Zineddine" (which does carry a family name) — both
            # transcribed exactly as printed rather than invented.
            {"ar": "زين الدين", "fr": "Makhlouche Zineddine", "dob": "01/09/2000", "pob": "Sétif"},
            {"ar": "كريم سليماني", "fr": "Karim Slimani", "dob": "15/07/1984", "pob": "Maoklane"},
            {"ar": "شافية سلمان", "fr": "Selmane Chafia", "dob": "05/12/1992", "pob": ""},
            {"ar": "ياسمينة بن سايلة", "fr": "Bensaila Yasmina", "dob": "09/11/1988", "pob": "Sétif"},
            {"ar": "بوالصوف شيماء", "fr": "Boussouf Chaima", "dob": "29/06/1999", "pob": "Sétif"},
            {"ar": "مندوش أسامة", "fr": "Mzndouche Oussama", "dob": "06/06/1996", "pob": "Sétif"},
            {"ar": "سيدهم خولة", "fr": "Sidhoum Khaoula", "dob": "23/02/1994", "pob": "Sétif"},
            {"ar": "بوالفخار تقي الدين", "fr": "Boulfekhar Taki Eddine", "dob": "31/07/1993", "pob": "Sétif"},
            {"ar": "معيزة حمزة", "fr": "Maiza Hamza", "dob": "24/02/1998", "pob": "Sétif"},
            {"ar": "دودو عامر", "fr": "Doudou Ameur", "dob": "24/04/1981", "pob": "Bougaa"},
        ],
    },
    {
        "doc_reference": "002/12/2025",
        "formation_title": "Montage et Inspection des Echafaudages",
        "client_name": "EURL SOCIETE ZOUAOUI",
        "date_start": "29/11/2025",
        "date_end": "30/11/2025",
        "duration_days_hint": 2,
        "trainer_ar": "لبعيلي أنيس",
        "trainer_latin": ("Anis", "Labaili"),
        "participants": [
            {"ar": "بن عرفة يونس", "fr": "BENARFA YOUNES", "dob": "16/08/1993", "pob": "Setif"},
            {"ar": "فؤاد ركيز", "fr": "REKIZ FOUAD", "dob": "01/02/1973", "pob": "Beni Fouda"},
            {"ar": "بشير هميسي", "fr": "HEMICI BACHIR", "dob": "18/01/1983", "pob": "Bougaa"},
            {"ar": "محمد حداد", "fr": "HADDAD MOHAMED", "dob": "12/03/1983", "pob": "Bougaa"},
            # Source dob cell for this row is only a bare year ("1972"), not
            # a full dd/mm/yyyy date — parse_ddmmyyyy() safely returns None
            # for it (date_of_birth is nullable), so the year is preserved
            # here for the record but doesn't crash the import.
            {"ar": "عبد الوهاب سمارة", "fr": "SMARA ABDELOUAHAB", "dob": "1972", "pob": "Ain El Kebira"},
            {"ar": "عبد المجيد زادي", "fr": "ZADI ABDELMADJID", "dob": "06/06/1980", "pob": "Beni Fouda"},
            {"ar": "فيصل غباش", "fr": "GHEBACH FAICAL", "dob": "01/01/1991", "pob": "Ain El Kbira"},
            {"ar": "عبد الباسط وازع", "fr": "OUAZAA ABDELBASSET", "dob": "30/01/1996", "pob": "Bougaa"},
            {"ar": "هارون زواوي", "fr": "ZOUAOUI HAROUN", "dob": "25/01/1986", "pob": "Ras El Oued"},
            {"ar": "فيصل بوطارة", "fr": "BOUTARA FAYCAL", "dob": "07/02/1976", "pob": "Setif"},
            {"ar": "ياسين صابر", "fr": "SABEUR YASSINE", "dob": "13/09/1980", "pob": "Amoucha"},
            {"ar": "بوجمعة قاسمي", "fr": "GUASSEMI BOUDJEMAA", "dob": "10/11/1980", "pob": "Amoucha"},
            {"ar": "هشام لقديم", "fr": "LEKDIM HICHEM", "dob": "09/04/1988", "pob": "Ain El Kbira"},
            {"ar": "سيف الدين سياري", "fr": "SIARI SEYF EDDINE", "dob": "19/09/1985", "pob": "Ain El Kbira"},
            {"ar": "سمير لطرشي", "fr": "LATERCHI SAMIR", "dob": "16/10/1980", "pob": "M'Silla"},
            {"ar": "كمال أوكيل", "fr": "OUKI KAMEL", "dob": "20/01/1984", "pob": "Mouklane"},
            # Source dob cell reads "06/14/1998" — month 14 is not a valid
            # calendar month, clearly a transcription slip on the original
            # paper document (day/month likely transposed). Kept verbatim
            # rather than silently "corrected"; parse_ddmmyyyy() returns
            # None for it rather than raising.
            {"ar": "هاني ريغي", "fr": "HANI RIGHI", "dob": "06/14/1998", "pob": "Setif"},
        ],
    },
    {
        "doc_reference": "014/03/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "ZOUAOUI",
        "date_start": "29/03/2026",
        "date_end": "02/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hamani"),
        "participants": [
            {"ar": "جمال الدين خلفون", "fr": "DJAMEL EDDINE KHELFOUNE", "dob": "18/03/2001", "pob": "Ain Azel"},
            {"ar": "برهان الدين بن عبيد", "fr": "BORHAN EDDINE BENABID", "dob": "11/04/1999", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "004/04/2026",
        "formation_title": "Commission Paritaire d'Hygiène et Sécurité",
        "client_name": "GOLDEN BODY",
        "date_start": "06/04/2026",
        "date_end": "09/04/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Bachir", "Hamani"),
        "participants": [
            {"ar": "ريان خلفي", "fr": "RAYENE KHALFI", "dob": "21/05/1997", "pob": "Sétif"},
            {"ar": "صافيناز لطرش", "fr": "SAFINEZ LATRECHE", "dob": "25/07/2000", "pob": "Sétif"},
            {"ar": "خديجة زغبي", "fr": "KHADIDJA ZOGHBI", "dob": "05/05/1997", "pob": "Sétif"},
            {"ar": "محمد شطيبي", "fr": "MOHAMED CHETIBI", "dob": "08/08/2001", "pob": "Sétif"},
            {"ar": "شهيناز شيبان", "fr": "CHAHINAZ CHIBANE", "dob": "17/03/1999", "pob": "Ahnif"},
            {"ar": "الأرقم بلمهدي", "fr": "EL-ARKEM BELMAHDI", "dob": "24/02/1996", "pob": "Ain Arnat"},
            {"ar": "عبد البديع مشتة", "fr": "ABDELBADIE MECHTA", "dob": "01/12/2002", "pob": "Sétif"},
            {"ar": "أسامة عبيد", "fr": "OUSSAMA ABID", "dob": "19/01/1994", "pob": "Sétif"},
            {"ar": "شريف بريمي", "fr": "CHERIF BERIMI", "dob": "16/11/1992", "pob": "Sétif"},
            {"ar": "عبد المومن ثوامر", "fr": "ABDELMOMENE TOUAMEUR", "dob": "18/07/1997", "pob": ""},
        ],
    },
    {
        "doc_reference": "001/02/2025",
        "formation_title": "Comptabilité et Fiscalité",
        "client_name": "Bio Real Pharm. El Eulma",
        "date_start": "25/01/2025",
        "date_end": "06/02/2025",
        "duration_days_hint": 4,
        "trainer_ar": "عبد الحليم برارمة",
        "trainer_latin": ("Abdelhalim", "Berarma"),
        "participants": [
            {"ar": "فارس عميور", "fr": "Amiour Fares", "dob": "15/02/1996", "pob": "El-Eulma"},
            {"ar": "أسامة بورفرف", "fr": "Bourefref Oussama", "dob": "08/01/1995", "pob": "El-Eulma"},
            {"ar": "أكرم صدقة", "fr": "Sedka Akram", "dob": "29/01/1991", "pob": "Ain El Kebira"},
            {"ar": "أكرم مرابطي", "fr": "Merabti Akram", "dob": "25/06/1999", "pob": "Collo"},
        ],
    },
    {
        "doc_reference": "2026/03/009",
        "formation_title": "Atmosphère Explosive Niveau 02 E",
        # No "الزبون:" line at all on this nominal list, same as the
        # exemplary batch's DECHETS_DE_FIENTES entry — treated as an
        # institute-run open session with no sponsoring company. See
        # `resolve_client()` fallback below.
        "client_name": "",
        "date_start": "25/03/2026",
        "date_end": "28/03/2026",
        "duration_days_hint": 4,
        "trainer_ar": "مشهود أحمد",
        "trainer_latin": ("Ahmed", "Mechhoud"),
        "participants": [
            {"ar": "عبد النور عمراوي", "fr": "ABDENOUR AMRAOUI", "dob": "04/10/1995", "pob": "Annaba"},
            {"ar": "عبد الرحمان بومعزة", "fr": "ABDERRAHMANE BOUMAZA", "dob": "01/03/1996", "pob": "Annaba"},
            {"ar": "جلال مخاليف", "fr": "DJALLEL MEKHALFI", "dob": "26/09/1978", "pob": "Sétif"},
            {"ar": "طارق خويلدي", "fr": "TAREK KHOUILDI", "dob": "03/05/1991", "pob": "Touggourt"},
            {"ar": "عبد الصمد غطاس", "fr": "ABDESSAMED GHETTAS", "dob": "13/01/1986", "pob": "Touggourt"},
        ],
    },
    {
        "doc_reference": "009/06/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "G.P.H",
        "date_start": "16/06/2026",
        "date_end": "17/06/2026",
        "duration_days_hint": 2,
        "trainer_ar": "حسين فتيتة",
        "trainer_latin": ("Houcine", "Fetita"),
        "participants": [
            {"ar": "العمري ذهبي", "fr": "DEHBI LAMRI", "dob": "23/08/1992", "pob": "Sétif"},
            {"ar": "سيناطور أيوي", "fr": "SENATOR AYOUB", "dob": "05/07/1984", "pob": "Sétif"},
            {"ar": "فريد سوالم", "fr": "FARID SOUALEM", "dob": "13/04/1985", "pob": "Sétif"},
            {"ar": "عبد السلام بورقة", "fr": "ABDESSLEM BOURAKBA", "dob": "03/07/1986", "pob": "Sétif"},
            {"ar": "هشام بلعارم", "fr": "BELAREM HICHEME", "dob": "01/10/1976", "pob": "France"},
            {"ar": "شوادرة محمد أمين", "fr": "CHOUADRA MOHAMED AMINE", "dob": "26/09/1993", "pob": "Sétif"},
            {"ar": "صلاح الدين برلة", "fr": "BERLA SALAH EDDINE", "dob": "11/08/1997", "pob": "El Eulma"},
            {"ar": "سيق الإسلام بن شبل", "fr": "BENCHEBEL SEIF ELISLEM", "dob": "14/11/1996", "pob": "Sétif"},
            {"ar": "عبد الرحمان بن بهوش", "fr": "BENBAHOUCHE ABDERRHMANE", "dob": "14/08/2002", "pob": "Sétif"},
            {"ar": "بن عثمان عبد العزيز", "fr": "BENOTHMANE ABDELAZIZ", "dob": "21/08/1997", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "005/03/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "G.P.H",
        "date_start": "09/03/2026",
        "date_end": "11/03/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        # A different (4-day) session cycle of the same G.P.H formation as
        # above, run on different dates with a different trainer — repeat
        # trainees are expected and unproblematic: Participant's
        # uniqueness constraint is scoped to (session, last_name,
        # first_name), not global, so the same person can legitimately
        # appear once per session they actually attended.
        "participants": [
            {"ar": "العمري ذهبي", "fr": "DEHBI LAMRI", "dob": "23/08/1992", "pob": "Setif"},
            {"ar": "سيناطور أيوي", "fr": "SENATOR AYOUB", "dob": "05/07/1984", "pob": "Setif"},
            {"ar": "فريد سوالم", "fr": "FARID SOUALEM", "dob": "13/04/1985", "pob": "Setif"},
            {"ar": "عبد السلام بورقة", "fr": "ABDESSLEM BOURAKBA", "dob": "03/07/1986", "pob": "Setif"},
            {"ar": "هشام بلعارم", "fr": "BELAREM HICHEME", "dob": "01/10/1976", "pob": "France"},
            {"ar": "شوادرة محمد أمين", "fr": "CHOUADRA MOHAMED AMINE", "dob": "26/09/1993", "pob": "Setif"},
            {"ar": "صلاح الدين برلة", "fr": "BERLA SALAH EDDINE", "dob": "11/08/1997", "pob": "El Eulma"},
            {"ar": "سيق الإسلام بن شبل", "fr": "BENCHEBEL SEIF ELISLEM", "dob": "14/11/1996", "pob": "Setif"},
            {"ar": "عبد الرحمن بن بهوش", "fr": "BENBAHOUCHE ABDERRHMANE", "dob": "14/08/2002", "pob": "Setif"},
            {"ar": "بن عثمان عبد العزيز", "fr": "BENOTHMANE ABDELAZIZ", "dob": "21/08/1997", "pob": "Setif"},
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
        "Batch #2: seed Session + Participant batches from the 12 remaining "
        "نهائي nominal list documents, auto-creating Formation/Trainer/"
        "Client/Branch/Specialty on the fly when no confident catalog "
        "match exists."
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

        self._info(f"Session batch #2 ({len(SESSION_SEED_DATA)} nominal lists)")

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
