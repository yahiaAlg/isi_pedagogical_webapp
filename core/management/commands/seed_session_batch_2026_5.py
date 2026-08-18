# core/management/commands/seed_session_batch_setif_clients.py
"""
Batch seeder for Session + Participant records, sourced directly from 17
جدول اسمي نهائي (nominal list) .doc documents (converted to .docx for
transcription — Arabic text is unreadable through the legacy binary .doc
encoding):

    SARL_SETIF_CITERNE_LA_VIEILLE_REGLEMENTAIRE_NOMINAL_LIST.doc
    SARL_SETIF_CITERNE_PONT_ROULANT_15_NOMINAL_LIST.doc
    SARL_SMOFE_HABILITATION_D_UTILISATION_DES_PRODUITS_CHIMIQUES_NOMINAL_LIST.doc
    SETIF_MEDIC_HABILITATION_CHIMIQUES_14_18_06_2026_NOMINAL_LIST.doc
    SETIF_MEDIC_HABILITATION_CHIMIQUES_NOMINAL_LIST.doc          (client is actually "SARL H-BAG")
    SETIF_MEDIC_HABILITATION_ELECTRIQUE_NOMINAL_LIST.doc
    SNC_KEBICHE_ABDELHALIM_ET_CIE_COMMISSION_PARITAIRE_D_HYGIÈNE_ET_SÉCURITÉ_NOMINAL_LIST.doc
    SNC_KEBICHE_ABDELHALIM_ET_CIE_CONDUITE_SECURITAIRE_DES_ENGINS_NOMINAL_LIST.doc
    SNC_KEBICHE_ABDELHALIM_ET_CIE_SENSIBILISATION_DES_RISQUE_NOMINAL_LIST.doc
    SNC_KEBICHE_ABDELHALIM_ET_CIE_SUPERVISEUR_HSE_NOMINAL_LIST.doc  (blank roster on paper — no participants)
    SOCIETÉ_D_ETUDES_TECHNIQUES_DE_SETIF_SETS_PREMIERS_SCOURS_NOMINAL_LIST.doc
    SPA_EBACOM_COMMISSION_PARITAIRE_D_HYGIÈNE_ET_SÉCURITÉ_NOMINAL_LIST.doc
    SPA_EBACOM_CONDUITE_SECURITAIRE_DES_ENGINS_NOMINAL_LIST.doc
    SPA_EBACOM_SENSIBILISATION_DES_RISQUE_NOMINAL_LIST.doc
    SPA_EBACOM_SUPERVISEUR_HSE_NOMINAL_LIST.doc                   (no "الزبون:" line on this one)
    SYM_SUPERVISEUR_HSE_IOSH_MS_NOMINAL_LIST.doc                  (client is actually "SARL RONIX")
    TAHOUEEL_DZ_COMMUNICATION_NOMINAL_LIST.doc

Core idea
─────────
A nominal list never guarantees its Formation / Trainer / Client already
exist in the catalog seeded by clients_seed.py / formations_seed.py /
trainers_seed.py — titles are transcribed slightly differently between
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

This mirrors exactly the pattern used by seed_session_batch_examplary.py:
Session.capacity, Formation catalog existence, Trainer specialty, and
Branch/Specialty when a brand-new formation has no obvious catalog
specialty to attach to.

Transcription notes (paper → data, kept faithful to source)
─────────────────────────────────────────────────────────
- SARL SETIF CITERNE nominal list #1 spells the client "Sétif Citrene"
  (paper typo for "Sétif Citernes") — transcribed as written; the fuzzy
  client match will still land on "SARL SETIF CITERNES" from the catalog.
- SNC KEBICHE's "Conduite Sécuritaire des Engins" list spells the client
  "...EL CIE" instead of "...ET CIE" — transcribed as written.
- SNC KEBICHE's "Superviseur HSE" list abbreviates the client to just
  "SNC KEBICH", and its roster rows are blank on paper (no names were
  ever filled in) — the Session is still created (doc_reference/dates are
  real), but with zero participants.
- SPA EBACOM's "Superviseur HSE" list has no "الزبون:" line at all —
  `client_name` is left empty, same "no sponsoring company" fallback as
  seed_session_batch_examplary.py's Déchets de Fientes entry.
- Two nominal lists carry a trainer name with no Latin spelling anywhere
  on the page (KEBICHE Superviseur HSE: "اسلام" only). `trainer_latin` is
  a best-effort manual transliteration, same convention as the exemplary
  script's own "رابح ابازيز" → ("Rabah", "Abaziz").
- KEBICHE "Sensibilisation aux Risques" row 12 has an obvious paper typo
  in the DOB ("114/11/1994") — corrected to "14/11/1994".
- TAHOUEEL "Communication" list mis-numbers two rows "05" in a row (the
  paper itself skips "04") — row numbering is cosmetic only and isn't
  stored on Participant, so this doesn't affect the data.

Run
───
    python manage.py seed_session_batch_setif_clients
    python manage.py seed_session_batch_setif_clients --dry-run
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
    {
        "doc_reference": "006/07/2026",
        "formation_title": "La Vieille Règlementaire",
        "client_name": "SARL Sétif Citrene",
        "date_start": "20/07/2026",
        "date_end": "23/07/2026",
        "duration_days_hint": 3,
        "trainer_ar": "عادل صالحي",
        "trainer_latin": ("Adel", "Salhi"),
        "participants": [
            {"ar": "سعاد زيتوني", "fr": "SOUAD ZITOUNI", "dob": "12/10/1979", "pob": ""},
        ],
    },
    {
        "doc_reference": "004/05/2026",
        "formation_title": "La Conduite Sécuritaire des Pont Roulants",
        "client_name": "SARL SETIF CITERNES",
        "date_start": "05/05/2026",
        "date_end": "06/05/2026",
        "duration_days_hint": 2,
        "trainer_ar": "رابح ابعزيز",
        "trainer_latin": ("Rabah", "Abaziz"),
        "participants": [
            {"ar": "يوسف بخوش", "fr": "YOUCEF BAKHOUCHE", "dob": "19/10/1990", "pob": ""},
            {"ar": "جابر خادري", "fr": "DJABER KHADRI", "dob": "07/09/1992", "pob": ""},
            {"ar": "سيف الدين قلالتة", "fr": "SIEF EDDINE GUELALTA", "dob": "25/07/2004", "pob": ""},
            {"ar": "رشيد بورامة", "fr": "RACHID BOURAMA", "dob": "14/03/1974", "pob": ""},
        ],
    },
    {
        "doc_reference": "5/02/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "SARL SMOFE",
        "date_start": "01/02/2026",
        "date_end": "04/02/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        "participants": [
            {"ar": "مراد مولاي", "fr": "MOULAI MOURAD", "dob": "07/10/1994", "pob": "Sétif"},
            {"ar": "فاتح العارفي", "fr": "LARFI FATEH", "dob": "06/12/1988", "pob": "Ain Bessam"},
            {"ar": "عبد القادر بالحاج", "fr": "BELHADJ ABDEKADER", "dob": "28/10/1988", "pob": "Alger"},
            {"ar": "عادل عيش", "fr": "AICHE ADEL", "dob": "12/01/1984", "pob": "Ain Bessam"},
            {"ar": "محفوظ السبتي", "fr": "SEBTI MAHFOUD", "dob": "24/07/1988", "pob": "Bouira"},
            {"ar": "ضياء الدين لعور", "fr": "LAOUAR DIA EDDINE", "dob": "16/08/1993", "pob": "Constantine"},
            {"ar": "عصام لبيوض", "fr": "LABIAD ISSAM", "dob": "05/05/1987", "pob": "El Eulma"},
            {"ar": "عبد المالك مولاي", "fr": "MOULAI ABDELMALEK", "dob": "08/06/1982", "pob": "Bejaia"},
            {"ar": "زكرياء للوش", "fr": "LALLOUCHE ZAKARIA", "dob": "07/08/1979", "pob": "Bir El Arch"},
            {"ar": "ماضوي مراد", "fr": "MADOUI MORAD", "dob": "20/12/1985", "pob": "Bouira"},
            {"ar": "قفيفة ياسين", "fr": "GUEFIFA YACINE", "dob": "30/11/1988", "pob": "Ain Bessam"},
            {"ar": "جرالفية طارق", "fr": "DJERALFIA TAREK", "dob": "09/06/1989", "pob": "Ain Bessam"},
            {"ar": "سعيد العارفي", "fr": "LARFI SAID", "dob": "18/03/1974", "pob": "Bouira"},
            {"ar": "محمد زين العابدين روام", "fr": "ROUAM ZINE AL ABIDINE", "dob": "04/01/1988", "pob": "Bouira"},
            {"ar": "عصام مولاي", "fr": "MOULAI ISSAM", "dob": "19/11/2000", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "008/06/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "SETIF MEDIC",
        "date_start": "14/06/2026",
        "date_end": "18/06/2026",
        "duration_days_hint": 5,
        "trainer_ar": "جلال حياة",
        "trainer_latin": ("Djelal", "Hayet"),
        "participants": [
            {"ar": "زين الدين هيشور", "fr": "ZINE EDDINE HICHOUR", "dob": "02/01/1997", "pob": "Constantine"},
            {"ar": "عباس مدني", "fr": "ABBES MEDANI", "dob": "10/03/1996", "pob": "Sétif"},
            {"ar": "شعيب رحماني", "fr": "CHOUAIB RAHMANI", "dob": "25/05/1992", "pob": "Sétif"},
            {"ar": "احسين عقيل", "fr": "H’SSEIN AKIL", "dob": "12/02/1991", "pob": "Sétif"},
            {"ar": "حسناء شتاحي", "fr": "HASNA CHETAHI", "dob": "27/02/1992", "pob": "Sétif"},
            {"ar": "رحيمة بلهوشات", "fr": "RAHIMA BELHOUCHE", "dob": "21/11/1997", "pob": "Batna"},
            {"ar": "أماني عابد", "fr": "AMANI ABED", "dob": "26/01/1995", "pob": "Sétif"},
            {"ar": "أسامة شعبان", "fr": "OUSSAMA CHABNE", "dob": "06/03/2002", "pob": "Bejaia"},
            {"ar": "الحاج الطيب غضاب", "fr": "EL HADJ TAYB GHADHAB", "dob": "20/10/1994", "pob": "Constantine"},
            {"ar": "حسام فرشة", "fr": "HOUSSEM FERCHA", "dob": "10/10/1989", "pob": "Batna"},
            {"ar": "عزوز رقيق فراح", "fr": "AZOUZ REGUIG FARAH", "dob": "07/08/1999", "pob": "El Eulma"},
        ],
    },
    {
        "doc_reference": "010/04/2026",
        "formation_title": "Habilitation D'utilisation des Produits Chimiques",
        "client_name": "SARL H-BAG",
        "date_start": "19/04/2026",
        "date_end": "23/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
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
    {
        "doc_reference": "016/06/2026",
        "formation_title": "Habilitation Electrique",
        "client_name": "SETIF MEDIC",
        "date_start": "28/06/2026",
        "date_end": "01/07/2026",
        "duration_days_hint": 4,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "شعيب رحماني", "fr": "CHOUAIB RAHMANI", "dob": "25/05/1992", "pob": "Sétif"},
            {"ar": "حسام بن معيزة", "fr": "HOUSSEM BENMAIZA", "dob": "29/07/1990", "pob": "Sétif"},
            {"ar": "أسامة شعبان", "fr": "OUSSAMA CHABANE", "dob": "06/03/2002", "pob": "Bejaia"},
            {"ar": "عصام بوحبيلة", "fr": "ISSAM BOUHABILA", "dob": "10/10/1996", "pob": "Constantine"},
            {"ar": "مراد هميسي", "fr": "MOURAD H’MISSI", "dob": "07/05/1976", "pob": "Sétif"},
            {"ar": "طيب بلال", "fr": "TAYEB BLAL", "dob": "01/07/1987", "pob": "Sougueur"},
            {"ar": "الحاج الطيب غضاب", "fr": "EL-HADJ TAYEB GHADHAB", "dob": "20/10/1994", "pob": "Constantine"},
            {"ar": "عقيل احسين", "fr": "AKIL H’SSEIN", "dob": "12/02/1991", "pob": "Sétif"},
            {"ar": "حسام فرشة", "fr": "HOUSSAM FERCHA", "dob": "10/10/1989", "pob": "Batna"},
        ],
    },
    {
        "doc_reference": "015/03/2026",
        "formation_title": "Commission Paritaire d'Hygiène et Sécurité",
        "client_name": "SNC KEBICHE ABDELHALIM ET CIE",
        "date_start": "29/03/2026",
        "date_end": "02/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حطاب محمود",
        "trainer_latin": ("Hattab", "Mahmoud"),
        "participants": [
            {"ar": "مختار بن شانة", "fr": "MOKHTAR BENCHANAA", "dob": "19/01/1984", "pob": "Sétif"},
            {"ar": "قابيل مداسي", "fr": "KABIL MADACI", "dob": "25/11/1989", "pob": "Sétif"},
            {"ar": "حمزة زواقري", "fr": "HAMZA ZOUAGRI", "dob": "27/10/1984", "pob": "Batna"},
            {"ar": "زين الدين سالم", "fr": "ZINE DDINE SALEM", "dob": "26/09/1988", "pob": "Sétif"},
            {"ar": "أبو سفيان ساكر", "fr": "ABOU SOUFIANE SAKER", "dob": "14/03/1982", "pob": "Sétif"},
            {"ar": "الزيتوني بن عبيرز", "fr": "ZITOUNI BEN ABIREZ", "dob": "22/10/1975", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "012/02/2026",
        "formation_title": "Conduite Securitaire des Engins",
        "client_name": "SNC KEBICHE ABDELHALIM EL CIE",
        "date_start": "15/02/2026",
        "date_end": "17/02/2026",
        "duration_days_hint": 3,
        "trainer_ar": "سفراني محمد",
        "trainer_latin": ("Sefrani", "Mohamed"),
        "participants": [
            {"ar": "مداسي قابيل", "fr": "MADACI KABIL", "dob": "25/11/1989", "pob": "SETIF"},
            {"ar": "بوعرق أحمد", "fr": "BOUAREG AHMED", "dob": "26/01/1970", "pob": "SETIF"},
            {"ar": "بن عبيرز كريم", "fr": "BENABIREZ KARIM", "dob": "21/03/1978", "pob": "SETIF"},
            {"ar": "بعداش حواس", "fr": "BAADACHE HAOUES", "dob": "26/05/1976", "pob": "AIN EL HADJER"},
        ],
    },
    {
        "doc_reference": "006/02/2026",
        "formation_title": "Sensibilisation au Risques des Carrières",
        "client_name": "SNC KEBICHE ABDELHALIM ET CIE",
        "date_start": "10/02/2026",
        "date_end": "11/02/2026",
        "duration_days_hint": 2,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "ساكر أبو صوفيان", "fr": "SAKER ABOUSOFINE", "dob": "14/03/1982", "pob": "AIN LAHDJAR"},
            {"ar": "ذويبي عبد الباقي", "fr": "DOUIBI ABDELBAKI", "dob": "05/04/1987", "pob": "BIR HADDADA"},
            {"ar": "مخناش محمد العيد", "fr": "MOKHNACHE MOHAMMED ELAID", "dob": "30/12/1977", "pob": "BIR HADDADA"},
            {"ar": "بعداش حواس", "fr": "BAADACHE HAOUASSE", "dob": "26/05/1966", "pob": "AIN LAHDJAR"},
            {"ar": "سايح يسين", "fr": "SAYAH YASSINE", "dob": "01/03/1980", "pob": "AIN LAHDJAR"},
            {"ar": "بعداش اليمين", "fr": "BAADACHE EL YAMINE", "dob": "19/10/1979", "pob": "AIN LAHDJAR"},
            {"ar": "غبيرز الحاج", "fr": "ABIREZ EL HADJ", "dob": "07/12/1982", "pob": "EL-EULMA"},
            {"ar": "بعداش لحسن", "fr": "BAADACHE LAHCENE", "dob": "1968", "pob": "AIN LAHDJAR"},
            {"ar": "بعداش عبد الكريم", "fr": "BAADACHE ABDDELKRIM", "dob": "04/01/1966", "pob": "AIN LAHDJAR"},
            {"ar": "بن عبيرز كريم", "fr": "BENABIREZ KARIM", "dob": "21/03/1978", "pob": "AIN LAHDJAR"},
            {"ar": "كحللش بشير", "fr": "KAHLELECHE BACHIR", "dob": "17/07/1983", "pob": "AIN LAHDJAR"},
            {"ar": "لحلو حسان", "fr": "LAHLOU HACENE", "dob": "14/11/1994", "pob": "AIN LAHDJAR"},
            {"ar": "بن عبيرز زيتوني", "fr": "BENABIREZ ZITOUNI", "dob": "22/10/1975", "pob": "AIN LAHDJAR"},
            {"ar": "ساكر سليم", "fr": "SAKER SALIM", "dob": "27/03/1973", "pob": "AIN LAHDJAR"},
            {"ar": "مخناش قيس", "fr": "MOKHNACHE KAIS", "dob": "25/07/1987", "pob": "AIN OULMENE"},
            {"ar": "بوعرق أحمد", "fr": "BOUAARGUE AHMED", "dob": "26/01/1970", "pob": "BOUGAA"},
            {"ar": "نقاب عدنان", "fr": "NEKAB ADNAN", "dob": "28/11/1979", "pob": "AIN LAHDJAR"},
        ],
    },
    {
        "doc_reference": "002/02/2026",
        "formation_title": "Superviseur HSE",
        "client_name": "SNC KEBICH",
        "date_start": "19/04/2026",
        "date_end": "23/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "اسلام",
        "trainer_latin": ("Islam", "Islam"),
        "participants": [
            # Blank roster on the paper original — no names were ever filled in.
        ],
    },
    {
        "doc_reference": "011/06/2026",
        "formation_title": "Premiers Secours",
        "client_name": "Société d'études techniques de Sétif SETS",
        "date_start": "22/06/2026",
        "date_end": "23/06/2026",
        "duration_days_hint": 2,
        "trainer_ar": "مولود حوماد",
        "trainer_latin": ("Maloud", "Houmad"),
        "participants": [
            {"ar": "رشيدة صحراوي", "fr": "RACHIDA SAHRAOUI", "dob": "20/02/1993", "pob": "Sétif"},
            {"ar": "مريم حرابة", "fr": "MERIEM HARABA", "dob": "17/09/1984", "pob": "Sétif"},
            {"ar": "غنية مسالتي", "fr": "GHANIA MESSALTI", "dob": "14/07/1971", "pob": "Sétif"},
            {"ar": "عبد اللطيف زكراوي", "fr": "ABDELATIF ZEKRAOUI", "dob": "26/08/1999", "pob": "Béchar"},
            {"ar": "يونس زكراوي", "fr": "YOUNES ZAKRAOUI", "dob": "20/05/1999", "pob": "Béni Abbès"},
            {"ar": "زوبير بومالك", "fr": "ZOUBIR BOUMALAK", "dob": "03/04/1969", "pob": "Sétif"},
            {"ar": "العيد لولو", "fr": "LAID LOULOU", "dob": "06/10/1975", "pob": "Sétif"},
            {"ar": "خالد دواير", "fr": "KHALED DOUAIRE", "dob": "18/08/1983", "pob": "Sétif"},
            {"ar": "حسان بن خليفة", "fr": "HACENE BENKHELIFA", "dob": "13/04/1986", "pob": "Sétif"},
            {"ar": "هيثم ضياء الدين ثابت", "fr": "HAITHEM DHIA EDDINE THABET", "dob": "16/11/1997", "pob": "Sétif"},
            {"ar": "سيف الدين سماش", "fr": "SEIF EDDINE SEMMACHE", "dob": "03/04/1985", "pob": "Sétif"},
            {"ar": "رفيق بن الشيخ", "fr": "RAFIK BENCHEIKH", "dob": "18/09/1976", "pob": "Sétif"},
            {"ar": "فارس لواتي", "fr": "FARES LOUATI", "dob": "18/08/1985", "pob": "Sétif"},
            {"ar": "ناصر لعقون", "fr": "LAGGOUN NACER", "dob": "14/12/1982", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "001/01/2026",
        "formation_title": "Commission Paritaire d'Hygiène et Sécurité",
        "client_name": "SPA EBACOM",
        "date_start": "25/01/2026",
        "date_end": "29/01/2026",
        "duration_days_hint": 5,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "محمد درياس", "fr": "DRIAS MOHAMED", "dob": "02/10/1983", "pob": "BATNA"},
            {"ar": "علي بكار", "fr": "BEKKAR ALI", "dob": "24/02/1984", "pob": "SETIF"},
            {"ar": "عومار عثماني", "fr": "OTMANI OMAR", "dob": "27/09/1966", "pob": "SETIF"},
            {"ar": "صابر عقيلي", "fr": "SABER AKILI", "dob": "14/10/1985", "pob": ""},
            {"ar": "يوسف زواوي", "fr": "ZOUAOUI YOUCEF", "dob": "29/04/1994", "pob": "Sétif"},
            {"ar": "جملة عبلة", "fr": "DJEMLA ABLA", "dob": "29/12/1974", "pob": "Sétif"},
            {"ar": "فارح تواتي", "fr": "TOUATI FAREH", "dob": "08/08/1979", "pob": "Sétif"},
            {"ar": "عبد الحق عقون", "fr": "AGGOUN ABDELHAK", "dob": "24/02/1978", "pob": "Sétif"},
        ],
    },
    {
        "doc_reference": "004/02/2026",
        "formation_title": "Conduite Securitaire des Engins",
        "client_name": "SPA EBACOM",
        "date_start": "03/02/2026",
        "date_end": "05/02/2026",
        "duration_days_hint": 3,
        "trainer_ar": "سفراني محمد",
        "trainer_latin": ("Sefrani", "Mohamed"),
        "participants": [
            {"ar": "توفيق عيساني", "fr": "AISSANI TOUFIK", "dob": "20/12/1984", "pob": "AIN EL KEBIRA"},
            {"ar": "الطيب ختالة", "fr": "KHATTALA TAYEB", "dob": "08/11/1972", "pob": "GUIDJAL"},
            {"ar": "عشاشة الهاشمي", "fr": "ACHACHE HACHEMI", "dob": "19/03/1968", "pob": "GUIDJAL"},
            {"ar": "عشاشة السعيد", "fr": "ACHACHA SAID", "dob": "29/06/1984", "pob": "SETIF"},
            {"ar": "فرج اله عبد الغاني", "fr": "FARDJALLA ABDELGHANI", "dob": "25/07/1963", "pob": "AIN OUALMENE"},
            {"ar": "قاسم فارس", "fr": "KACEM FARES", "dob": "26/02/1982", "pob": "SETIF"},
            {"ar": "بازة عبد الرزاق", "fr": "BAZA ABDELREZZAK", "dob": "09/08/1988", "pob": "AIN EL KEBIRA"},
            {"ar": "صغير أسماعيل", "fr": "SEGHUR SAMIL", "dob": "14/01/1979", "pob": "SETIF"},
            {"ar": "عبد الله غيو", "fr": "GHAYOU ABDELLAH", "dob": "03/09/1998", "pob": "GUELLAL"},
            {"ar": "بوزبد بن زيد", "fr": "BENZID BOUZID", "dob": "21/01/1971", "pob": "SETIF"},
            {"ar": "نصير قومي", "fr": "TOUMI NACIR", "dob": "10/07/1975", "pob": "SETIF"},
            {"ar": "بوعجاجة وليد", "fr": "BOUADJADJA WALID", "dob": "21/11/1987", "pob": "AIN ABBASSA"},
        ],
    },
    {
        "doc_reference": "001/02/2026",
        "formation_title": "Sensibilisation ou Risques des Carrières",
        "client_name": "SPA EBACOM",
        "date_start": "01/02/2026",
        "date_end": "02/02/2026",
        "duration_days_hint": 2,
        "trainer_ar": "حماني بشير",
        "trainer_latin": ("Hamani", "Bachir"),
        "participants": [
            {"ar": "عشاشة السعيد", "fr": "ACHACHA SAID", "dob": "29/06/1984", "pob": "SETIF"},
            {"ar": "عشاشة الهاشمي", "fr": "ACHACHE HACHEMI", "dob": "19/03/1968", "pob": "GUIDJAL"},
            {"ar": "فرج اله عبد الغاني", "fr": "FARDJALLA ABDELGHANI", "dob": "25/07/1963", "pob": "AIN OUALMENE"},
            {"ar": "توفيق عيساني", "fr": "AISSANI TOUFIK", "dob": "20/12/1984", "pob": "AIN EL KEBIRA"},
            {"ar": "قاسم فارس", "fr": "KACEM FARES", "dob": "26/02/1982", "pob": "SETIF"},
            {"ar": "عبد الله غيو", "fr": "GHAYOU ABDELLAH", "dob": "03/09/1998", "pob": "GUELLAL"},
            {"ar": "نصير تومي", "fr": "TOUMI NACIR", "dob": "10/07/1975", "pob": "SETIF"},
            {"ar": "بازة عبد الرزاق", "fr": "BAZA ABDELREZZAK", "dob": "09/08/1988", "pob": "AIN EL KEBIRA"},
            {"ar": "الطيب ختالة", "fr": "KHATTALA TAYEB", "dob": "08/11/1972", "pob": "GUIDJAL"},
            {"ar": "صغير أسماعيل", "fr": "SEGHUR SAMIL", "dob": "14/01/1979", "pob": "SETIF"},
            {"ar": "بوزبد بن زيد", "fr": "BENZID BOUZID", "dob": "21/01/1971", "pob": "SETIF"},
        ],
    },
    {
        "doc_reference": "011/04/2026",
        "formation_title": "Superviseur HSE",
        "client_name": "",
        "date_start": "19/04/2026",
        "date_end": "23/04/2026",
        "duration_days_hint": 5,
        "trainer_ar": "أحمد إسلام بن غالم",
        "trainer_latin": ("Ahmed Islam", "Ben Ghalem"),
        "participants": [
            {"ar": "رياض بورقبة", "fr": "Riad Bourakba", "dob": "10/03/1984", "pob": "Sétif"},
            {"ar": "رياض حداد", "fr": "Riad Haddad", "dob": "03/06/1981", "pob": "Sétif"},
            {"ar": "هيثم عبد الرؤوف مسعودي شريف", "fr": "Haithem Abderraouf Messaoudi Cherif", "dob": "09/11/1997", "pob": "Sétif"},
            {"ar": "وائل صلاح الدين حوش", "fr": "Wail Salah Eddine Haouche", "dob": "21/05/2003", "pob": "Sétif"},
            {"ar": "إسلام بليل", "fr": "Islam Bellil", "dob": "01/12/2002", "pob": "Tadjenanet"},
        ],
    },
    {
        "doc_reference": "003/02/2026",
        "formation_title": "Superviseur HSE",
        "client_name": "SARL RONIX",
        "date_start": "01/02/2026",
        "date_end": "05/02/2026",
        "duration_days_hint": 5,
        "trainer_ar": "فاتح سهام",
        "trainer_latin": ("Fatah", "Siham"),
        "participants": [
            {"ar": "قريب فاتح", "fr": "GRIB FATEH", "dob": "18/07/1990", "pob": "Sétif"},
            {"ar": "معلم عبد الرحمان", "fr": "MALLEM ABDERRAHMANE", "dob": "25/09/2000", "pob": "Skikda"},
        ],
    },
    {
        "doc_reference": "017/02/2026",
        "formation_title": "Communication Interpersonnelle",
        "client_name": "EURL TAHOUEEL DZ",
        "date_start": "22/02/2026",
        "date_end": "24/02/2026",
        "duration_days_hint": 3,
        "trainer_ar": "أوطاهر صليحة",
        "trainer_latin": ("Aoutaher", "Saliha"),
        "participants": [
            {"ar": "آسية مومن", "fr": "MOUMEN AISSA", "dob": "31/03/1986", "pob": "Setif"},
            {"ar": "كمال نكاع", "fr": "NEKKAA  KAMEL", "dob": "16/07/1990", "pob": "Setif"},
            {"ar": "كابة عبد القادر", "fr": "KABA ABDELKADER", "dob": "25/08/1994", "pob": "Sétif"},
            {"ar": "عبد الحليم زرارقي", "fr": "ZERARGUI ABDELHALIM", "dob": "05/08/1976", "pob": "Sétif"},
            {"ar": "محمد سعيد عكال", "fr": "AKKAL MOHAMEDSAID", "dob": "06/06/1982", "pob": "Beni Chabana"},
            {"ar": "بدر الين مرزكة", "fr": "MERAZKA BADREDINE", "dob": "01/01/1995", "pob": "Beni Aziz"},
            {"ar": "عبد النوري صلاح", "fr": "ABDENNOURI SALAH", "dob": "21/01/1966", "pob": "SETIF"},
            {"ar": "بدر الدين عقون", "fr": "AGGOUNE BADR EDDINE", "dob": "06/09/1993", "pob": "AIN AZEL"},
            {"ar": "محمد غدير", "fr": "GHEDIR MOHAMED", "dob": "04/06/1986", "pob": "SETIF"},
            {"ar": "العلمي شكيب بن غذفة", "fr": "BENGHEDFA EL AILMI CHAKIB", "dob": "26/10/1997", "pob": "SETIF"},
            {"ar": "عياش زديوي", "fr": "ZEDIOUI AYACHE", "dob": "27/03/1982", "pob": "SETIF"},
            {"ar": "جلول رزوالي", "fr": "REZOUALI DJELLOUL", "dob": "15/12/1985", "pob": "SETIF"},
            {"ar": "سارة قرنيش", "fr": "GUERNICHE SARA", "dob": "12/03/2000", "pob": "SETIF"},
            {"ar": "يونس بجاوي", "fr": "BEDJAOUI YOUNES", "dob": "14/04/1992", "pob": "SETIF"},
        ],
    },
]

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
        "Seed Session + Participant batches from 17 نهائي nominal "
        "list documents (Sétif-area clients), auto-creating Formation/"
        "Trainer/Client/Branch/Specialty on the fly when no confident "
        "catalog match exists."
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
