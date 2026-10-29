# core/management/commands/trainers_seed.py
"""
Seeds the trainer roster from LA_LISTE_DE_FORMATEUR.xlsx.

Source
──────
  - LA_LISTE_DE_FORMATEUR.xlsx, sheet "Feuil1" (57 records) — name,
    professional address, contact, wilaya and RIB/CCP for each formateur.

Notes / assumptions
────────────────────
  - The source sheet has a single "NOM ET PRENOM" column with no split
    between family and given name. Algerian admin exports of this kind
    conventionally list the family name first, so the first word of each
    entry is taken as `last_name` and the remainder as `first_name`. A
    few rows (e.g. "HICHAM EL KOUF") don't clearly follow this pattern —
    review those manually after seeding.
  - `Trainer` has no dedicated wilaya/RIB field, so — following the same
    approach as `institute_seed.py`'s trading-name footer — the wilaya
    and RIB/CCP from the sheet are folded into `professional_address` as
    extra lines rather than being dropped.
  - `specialty` is a required field on `Trainer` but isn't present in the
    source sheet at all; it is seeded empty and should be filled in
    manually per trainer.
  - All rows are seeded with `employment_type="external"`, since every
    entry carries payment/RIB details (i.e. external formateurs paid per
    session) and the sheet has no field distinguishing internal staff.
  - One row ("HAMDAD BADRIDDINE") carries a sheet note reading roughly
    "CCP — do not authorize"; this is preserved as a "Note :" line in
    `professional_address` rather than interpreted, so it isn't missed.

Run
───
    python manage.py trainers_seed
    python manage.py trainers_seed --force   # overwrite existing records
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

# ─────────────────────────── raw data ──────────────────────────────────────

TRAINERS = [
    {
        "first_name": "HAYAT",
        "last_name": "ABOUBOU",
        "specialty": "",
        "professional_address": "Wilaya : OURGLA HASSI MESSAOUD\nRIB/CCP : 00799999 00 05817076 54",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "FERIEL NAWEL",
        "last_name": "ACHOURI",
        "specialty": "",
        "professional_address": "Wilaya : ALGER\nRIB/CCP : 00799999 00 07953283 29",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "KHELIFA",
        "last_name": "BELLA",
        "specialty": "",
        "professional_address": "RIB/CCP : AGB BANK 032 00100 2742321208 46",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "CHIHABEDDINE",
        "last_name": "BENGUESSOUM",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 14787160 27\nNote : $",
        "phone": "06 61 37 30 04",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "TAHA",
        "last_name": "BENIKHLEF",
        "specialty": "",
        "professional_address": "Wilaya : ALGER\nRIB/CCP : 00799999 00 02372488 20",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "SOFIANE",
        "last_name": "BENTAHAR",
        "specialty": "",
        "professional_address": "EL MEGHAIR ELOUAD El Meghaier 39200, Algeria\nWilaya : ELOUAD\nRIB/CCP : 00799999 00 09724247 21",
        "phone": "0668 015 432",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "IMEN",
        "last_name": "BENZAYED",
        "specialty": "",
        "professional_address": "RIB/CCP : PAR CHEQUE AU NOM FORMATEUR",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "SOUFIANE",
        "last_name": "BOUSSOULEM",
        "specialty": "",
        "professional_address": "Wilaya : ALGER\nRIB/CCP : CPA BANK 004 00174 4100004822 45",
        "phone": "06 61 33 71 08",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MAKHLOUF",
        "last_name": "CHAALAL",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 09388325 54",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "IMAN",
        "last_name": "CHAOUCHE",
        "specialty": "",
        "professional_address": "SETIF\nWilaya : SETIF\nRIB/CCP : 00799999 00 28078265 17",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "DERADACHE",
        "last_name": "CHARAFEDDINE",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 09724247 21",
        "phone": "0699 17 61 11",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AMOR",
        "last_name": "DERDOUR",
        "specialty": "",
        "professional_address": "Wilaya : RAS EL WAD\nRIB/CCP : 00799999 00 04428567 13",
        "phone": "0561 71 19 45",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "HAYAT",
        "last_name": "DIELAL",
        "specialty": "",
        "professional_address": "Wilaya : CONSTANTINE\nRIB/CCP : 00799999 00 05866563 03",
        "phone": "06 96 33 82 50",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MHMOUD",
        "last_name": "DJANI",
        "specialty": "",
        "professional_address": "CITE EL FOURSSAN M'rara W EL-OUED\nWilaya : EL-OUED\nRIB/CCP : 00799999 00 02170927 77",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ABDENOUR",
        "last_name": "DJEDID",
        "specialty": "",
        "professional_address": "Wilaya : ALGER\nRIB/CCP : 00799999 00 23754395 11",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "SIHAM",
        "last_name": "FATAH",
        "specialty": "",
        "professional_address": "hASSI MESSAOUD\nWilaya : OUARGLA\nRIB/CCP : 00799999 00 20396492 76",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "LAMINE",
        "last_name": "FENDRECHE",
        "specialty": "",
        "professional_address": "Wilaya : SETIF\nRIB/CCP : 00799999 00 10055188 90",
        "phone": "05 60 92 52 47",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "NOUR EL HOUDA",
        "last_name": "GUEZZI",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 17652907 90",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "-EDDINE LOUNES",
        "last_name": "HABIB",
        "specialty": "",
        "professional_address": "A03 AVENUE BARAHIM GHARAFA BEO ALGER\nWilaya : ALGER\nRIB/CCP : BANK BNP PARIBAS 027 00708 0111504001 68\nTéléphone secondaire : 0770 94 95 85",
        "phone": "05 5038 97 26",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "BADRIDDINE",
        "last_name": "HAMDAD",
        "specialty": "",
        "professional_address": 'GROUPE 11 BT "C" PLACE DU 1ER MAI ALGER\nWilaya : ALGER\nRIB/CCP : AGB BANK 032 00012 2239911208 43\nNote : CCP NE PAS OUTARISI',
        "phone": "07 93 16 43 15",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AMINA",
        "last_name": "HAMRAT",
        "specialty": "",
        "professional_address": "Wilaya : TIZ OUZOU\nRIB/CCP : 00799999 00 23709884 72",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MAHMOUD",
        "last_name": "HATTAB",
        "specialty": "",
        "professional_address": "CITE 50 LOGEMENT BOUZGUENE\nWilaya : TIZ OUZOU\nRIB/CCP : 00799999 00 01426002 94\nTéléphone secondaire : 0672 920 241",
        "phone": "0550 774 540",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "EL KOUF",
        "last_name": "HICHAM",
        "specialty": "",
        "professional_address": "Wilaya : OUARGLA\nRIB/CCP : 00799999 00 04705236 35",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MANSOUR",
        "last_name": "HOUSSEM",
        "specialty": "",
        "professional_address": "RUE MIRZA SALAH BATIMENT A NUMERO DE PORT 01 SETF\nWilaya : SETIF",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "YAAKOUB",
        "last_name": "KABILA",
        "specialty": "",
        "professional_address": "Wilaya : SETIF\nRIB/CCP : 00799999 00 17609768 12",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "YACINE",
        "last_name": "KACED",
        "specialty": "",
        "professional_address": "BIR MOURAD RAIS ALGER\nRIB/CCP : AGB BANK 032000072360341208 82",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "NABIL",
        "last_name": "KADRI",
        "specialty": "",
        "professional_address": "CITE 1600 LOGTS BAT 131 N 01 EL KHROUB CONSTANTINE\nWilaya : CONSTANTINE\nRIB/CCP : 00799999 00 06049474 96",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOULOUD",
        "last_name": "KAOUANE",
        "specialty": "",
        "professional_address": "CITE TLIDJANE SETIF\nWilaya : SETIF\nRIB/CCP : BANK CNEP 011 00371 1400018351 13",
        "phone": "06 57 94 81 31",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ZAHIA",
        "last_name": "KEBBOUCHE",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 04244799 66",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "HOCINE",
        "last_name": "LAKRACHE",
        "specialty": "",
        "professional_address": "Wilaya : SETIF\nRIB/CCP : 00 799999 00 01868659 53",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ABDLELMOUMENE",
        "last_name": "LAOUABEM",
        "specialty": "",
        "professional_address": "12 LOTS YAHIAOUI N° 03 BELLATOUAMI\nWilaya : SETIF",
        "phone": "06 73 35 08 42",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "EMBAREK",
        "last_name": "MAHGOUN",
        "specialty": "",
        "professional_address": "CITE ALI AMRANE 03 BT 05 APPT N° 9BEK/ALGRE\nWilaya : ALGER\nRIB/CCP : 00799999 00 01823595 27",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "messaoud",
        "last_name": "makhloufi",
        "specialty": "",
        "professional_address": "RIB/CCP : 007 99999 00 0796599 66",
        "phone": "gtm falch disk",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AHMED",
        "last_name": "MECHEHOUD",
        "specialty": "",
        "professional_address": "Wilaya : MOSTAGANEM\nRIB/CCP : B E A 002 00066 0661005029 46",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ABDELKRIM",
        "last_name": "MEHLOUFI",
        "specialty": "",
        "professional_address": "Wilaya : OUARGLA\nRIB/CCP : 00799999 00 02993086 44",
        "phone": "06 63 02 24 34",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOHAND",
        "last_name": "MELLAL",
        "specialty": "",
        "professional_address": "EL ACHOUR ALGER\nWilaya : ALGER\nRIB/CCP : 00799999 00 04991569 68",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ABDENACER",
        "last_name": "MOUFFOK",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 06007851 29",
        "phone": "06 71 08 00 19",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ILIES",
        "last_name": "REZAZGA",
        "specialty": "",
        "professional_address": "Hassi Messaoud, Algeria. / P.C: 30500\nWilaya : ELOUAD\nRIB/CCP : 00799999 00 05986873 10",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOKHTARIA",
        "last_name": "SAHNOUN",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 00 12482766 19",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "REDOUNE",
        "last_name": "SAIDI",
        "specialty": "",
        "professional_address": "HASSI MESSAOUD\nWilaya : OUARGLA\nRIB/CCP : BEA BANK 002 00033 0331002921 24",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "HADDA",
        "last_name": "SAOUD",
        "specialty": "",
        "professional_address": "Wilaya : ALGER\nRIB/CCP : 00799999 00 07643882 39",
        "phone": "07 91 34 52 00",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOHAMMED",
        "last_name": "SOFRANI",
        "specialty": "",
        "professional_address": "Z' MALET EMIR ABDLKADER\nWilaya : TIARET\nRIB/CCP : 00799999 00 05088856 80",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "DJAHID",
        "last_name": "TAFTICHT",
        "specialty": "",
        "professional_address": "CITE 687 LOG BAT 03 N° 09 BORDJ EL KIFFAN\nWilaya : ALGER\nRIB/CCP : SGA BANK 021 00019 1150313 09",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOHAMED",
        "last_name": "YACOUBI",
        "specialty": "",
        "professional_address": "VILLA N°14 CITEGHOUALEM BOUDOUAOU\nWilaya : BOUMERDES\nRIB/CCP : 00799999 00 16753416 23",
        "phone": "05 55 57 70 83",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOULOUD",
        "last_name": "HOUMAD",
        "specialty": "",
        "professional_address": "CITE BEN BOOULAID CONSTANTINE 20 AOUT\nWilaya : CONSTANTINE\nRIB/CCP : 00799999 00 10787447 72",
        "phone": "056 16 34 05",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AMIR",
        "last_name": "BENMAMER",
        "specialty": "",
        "professional_address": "CONSTANTINE\nWilaya : CONSTANTINE\nRIB/CCP : BEA 002 00110 110100 1175 55",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MOHAMMED",
        "last_name": "BOUMEDINNE",
        "specialty": "",
        "professional_address": "AIN MERANE\nWilaya : CHELF\nRIB/CCP : 00799999 000 1090708 86",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "BACHIR",
        "last_name": "HAMMANI",
        "specialty": "",
        "professional_address": "RIB/CCP : 00799999 0007406522 42",
        "phone": "",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "BENAISSA",
        "last_name": "TAIBI",
        "specialty": "",
        "professional_address": "CITE REKIA MUSTAPHA\nWilaya : MEDEA\nRIB/CCP : CCP 007 99999 0019229051 20",
        "phone": "0541475476",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "MUSTAPHA",
        "last_name": "MAHIOUT",
        "specialty": "",
        "professional_address": "CITE BOUGARA 02 BT 08 N°14 SIDI MOUSSA\nWilaya : ALGER\nRIB/CCP : CCP 007 99999 0001044128 49",
        "phone": "0775941508",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "RADOUANE",
        "last_name": "AZZOUZ",
        "specialty": "",
        "professional_address": "BOUSSADA\nWilaya : BOUSSADA\nRIB/CCP : BNA 001 00920 0300001583 29",
        "phone": "0550577856",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "REDA",
        "last_name": "SOUICI",
        "specialty": "",
        "professional_address": "CITE 400 BT 01 BISKRA\nWilaya : BISKRA\nRIB/CCP : BNP 027 00772 0100938001 21",
        "phone": "0671546484",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AYMEN SID ALI",
        "last_name": "BOUZIANE",
        "specialty": "",
        "professional_address": "BIRTOUTA CITE CHAIBIA BAT 133 N° 12 ALGER\nWilaya : alger\nRIB/CCP : CCP 007 99999 0020549762 46",
        "phone": "0554695518",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "AHMED REDA",
        "last_name": "SEBAINI",
        "specialty": "",
        "professional_address": "LAKHROUB\nWilaya : CONSTANTINE\nRIB/CCP : CCP 007 99999 0012225871 39",
        "phone": "0561827261",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "HICHAM",
        "last_name": "ARAB",
        "specialty": "",
        "professional_address": "MEROUANA\nWilaya : BATNA\nRIB/CCP : CCP 007 99999 0013550393 78",
        "phone": "0673993620",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ANIS",
        "last_name": "LEBAILI",
        "specialty": "",
        "professional_address": "ELMILIA\nWilaya : JIJEL\nRIB/CCP : CCP 007 99999 0013231541 20",
        "phone": "0777989757",
        "employment_type": "external",
        "is_active": True,
    },
    {
        "first_name": "ZEROUK",
        "last_name": "AYAT",
        "specialty": "",
        "professional_address": "AIN KEBIRA\nWilaya : ORAN\nRIB/CCP : BNP 027 007440116132001 12",
        "phone": "0561349124",
        "employment_type": "external",
        "is_active": True,
    },
]

# ─────────────────────────── command ───────────────────────────────────────


class Command(BaseCommand):
    help = "Seed trainer roster from LA_LISTE_DE_FORMATEUR.xlsx."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing records (matched by first_name + last_name, case-insensitive).",
        )

    def handle(self, *args, **options):
        force = options["force"]
        self._seed_trainers(force)

    # ── helpers ──────────────────────────────────────────────────────────
    def _ok(self, msg: str):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def _skip(self, msg: str):
        self.stdout.write(f"  – {msg} (already exists, skipped)")

    def _info(self, msg: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n► {msg}"))

    # ── trainers ─────────────────────────────────────────────────────────
    def _seed_trainers(self, force: bool):
        self._info(f"Trainers ({len(TRAINERS)} records)")

        try:
            from resources.models import Trainer
        except ImportError:
            self.stderr.write(
                self.style.WARNING(
                    "  ⚠ Could not import Trainer – skipping. "
                    "Check that the 'resources' app label/model path is correct."
                )
            )
            return

        created, updated, skipped = 0, 0, 0

        for data in TRAINERS:
            data = dict(data)

            existing = Trainer.objects.filter(
                first_name__iexact=data["first_name"],
                last_name__iexact=data["last_name"],
            ).first()

            if existing:
                if force:
                    for field, value in data.items():
                        setattr(existing, field, value)
                    existing.save()
                    updated += 1
                else:
                    skipped += 1
                continue

            Trainer.objects.create(**data)
            created += 1

        self._ok(f"{created} created, {updated} updated, {skipped} skipped")
