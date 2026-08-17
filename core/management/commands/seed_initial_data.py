# formations/management/commands/seed_initial_data.py
"""
Seeds all initial data for the Training Management System:
  - Superuser  (admin / admin1234!)
  - InstituteInfo  (vendor block from invoices)
  - 5 Categories  (RH · COM · PMD · HSE · INF)
  - All Formations  (catalog from facture_formations.txt, prices from initial_db.json)
  - 12 Clients  (from initial_db.json)

Run
───
    python manage.py seed_initial_data
    python manage.py seed_initial_data --force   # overwrite existing records
"""

from __future__ import annotations

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

# ─────────────────────────── raw data ────────────────────────────────────────

INSTITUTE = {
    "name_fr": "SARL MOUASSASSET TAMAYOUZ LILIDARA W ESSALAMA",
    "name_ar": "مؤسسة التميز للإدارة والسلامة",
    "address": "CITE LOTIS HACHEMI 1ère TRANCHE ETAGE 1 ET 2, SETIF",
    "phone": "",
    "email": "",
    "nif": "002119009444326",
    "nis": "002119010021763",
    "rc": "21B 0094443-19/00",
    "article_imposition": "19011780071",
    "rib": "001-007110300001829-41",
    "accreditation_number": "EFP 003",
    "accreditation_date": datetime.date(2022, 3, 14),
    "if_number": "19011780071",
    "footer_fr": "Agrément EFP 003 – 14/03/2022",
    "footer_ar": "اعتماد EFP 003 – 14/03/2022",
}

# ── Categories ────────────────────────────────────────────────────────────────
# key → (display_name, description, hex_color)
CATEGORIES = {
    "RH": (
        "Management des Ressources Humaines",
        "Formations en gestion RH, droit du travail, rémunération et indicateurs de performance",
        "#4A90D9",
    ),
    "COM": (
        "Communication et Leadership",
        "Formations en communication, leadership, gestion du temps et animation d'équipe",
        "#7ED321",
    ),
    "PMD": (
        "Gestion de la Maintenance (PMD)",
        "Formations en maintenance industrielle : GMAO, TPM, fiabilité et méthodes",
        "#F5A623",
    ),
    "HSE": (
        "Formation HSE",
        "Formations Hygiène, Sécurité et Environnement : habilitations, certifications et sensibilisations",
        "#D0021B",
    ),
    "INF": (
        "Informatique",
        "Formations bureautiques et outils décisionnels : Excel, Word, Power BI",
        "#9B59B6",
    ),
}

# ── Formations ────────────────────────────────────────────────────────────────
# Each entry:
#   (code, title, category_key, duration_days, duration_hours,
#    min_p, max_p, base_price_DA, evaluation_type, produces_certificate,
#    passing_score, max_score, min_attendance_days, accreditation_body)
#
# Prices sourced from initial_db.json unit_price_ht values.
# Formations not present in invoices default to base_price=0.

FORMATIONS = [
    # ── MANAGEMENT DES RESSOURCES HUMAINES ───────────────────────────────────
    (
        "RH-001",
        "Enjeux de la Fonction RH et le Management des Ressources Humaines",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "RH-002",
        "Gestion des Emplois et des Compétences (GPEC)",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "RH-003",
        "Techniques de Résolution des Conflits",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "RH-004",
        "Emprise du Droit de Travail National sur les Pratiques GRH",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "RH-005",
        "Législation et Sécurité Sociale",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "RH-006",
        "Analyse et Évolution des Systèmes de Rémunération",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "RH-007",
        "Système d'Information RH et Tableau de Bord",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "RH-008",
        "Les Indicateurs de Performance KPI",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "RH-009",
        "Politique de Rémunération",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        # Invoiced: ISO 9001 → 63 000 DA/jour · 3 jours (invoice 010)
        "RH-010",
        "Formation ISO 9001, ISO 14001, ISO 45001",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("63000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "ISO",
    ),
    (
        "RH-011",
        "Élaboration des Budgets pour RH",
        "RH",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        # Invoiced: audit SMQ → 68 000 DA/jour · 3 jours (invoice 008)
        "RH-012",
        "Formation Audit SMQ",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("68000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        # Invoiced: Gestion Des Risque → 63 000 DA/jour · 3 jours (invoice 010)
        "RH-013",
        "Formation Gestion des Risques",
        "RH",
        3,
        21,
        5,
        20,
        Decimal("63000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    # ── COMMUNICATION ET LEADERSHIP ──────────────────────────────────────────
    (
        "COM-001",
        "Gestion de Conflits",
        "COM",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        # Invoiced: Maitrise du temps et gestion des priorités → 80 000 DA/jour · 4 jours (invoice 012)
        "COM-002",
        "Maîtrise du Temps et Gestion des Priorités",
        "COM",
        4,
        28,
        5,
        20,
        Decimal("80000.00"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        4,
        "",
    ),
    (
        # Invoiced: Formation communication → 65 000 DA/jour · 3 jours (invoice 007)
        "COM-003",
        "Communication Interpersonnelle et ses Techniques",
        "COM",
        3,
        21,
        5,
        20,
        Decimal("65000.00"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "COM-004",
        "Gestion d'Équipe",
        "COM",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "COM-005",
        "Agent Commercial",
        "COM",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "COM-006",
        "Les Écrits Professionnels et Administratifs",
        "COM",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "COM-007",
        "Animation de Réunions et Prise de Parole en Public",
        "COM",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    # ── GESTION DE LA MAINTENANCE (PMD) ──────────────────────────────────────
    (
        "PMD-001",
        "Gestion de la Maintenance Assistée par Ordinateur (GMAO) – Initiation et Viabilité",
        "PMD",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "PMD-002",
        "Maintenance Basée sur la Fiabilité (RCM)",
        "PMD",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "PMD-003",
        "Extraire les Bonnes Informations des Tableaux de Bord et Analyse",
        "PMD",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "PMD-004",
        "Maîtrise de la Totale Productive Maintenance (TPM)",
        "PMD",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "PMD-005",
        "Formation Méthodes de Maintenance",
        "PMD",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    # ── FORMATION HSE ─────────────────────────────────────────────────────────
    (
        # Invoiced: IOSH MS → 65 000 DA/personne (invoice 009)
        "HSE-001",
        "IOSH Managing Safely",
        "HSE",
        4,
        28,
        1,
        20,
        Decimal("65000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        4,
        "IOSH",
    ),
    (
        # Invoiced: Superviseur HSE → 50 000 DA/personne (invoice 001), 48 000 (invoice 005) → use 50 000
        "HSE-002",
        "Superviseur HSE",
        "HSE",
        3,
        21,
        1,
        20,
        Decimal("50000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "HSE-003",
        "Protections Électriques (Réseaux & Centrales)",
        "HSE",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "HSE-004",
        "Leadership et Culture HSE",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-005",
        "La Veille Réglementaire HSE (Lois, Règles, Normes)",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-006",
        "Sécurité Basée sur le Comportement (BBS)",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-007",
        "Les Techniques d'Investigation des Accidents et Incidents",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-008",
        "Commission Paritaire d'Hygiène et de Sécurité (CPHS)",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        # Invoiced: habilitation conduite chariots élévateurs → 22 000 DA/personne (invoices 006, 014)
        "HSE-009",
        "Habilitation à la Conduite des Chariots Élévateurs",
        "HSE",
        2,
        14,
        1,
        20,
        Decimal("22000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-010",
        "Hazard Analysis Critical Control Point (HACCP)",
        "HSE",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "HSE-011",
        "Habilitation Électrique",
        "HSE",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        # Invoiced: habilitation produit chimique → 55 000 DA/jour (invoice 004), 50 000 DA/jour (invoice 011)
        # Most recent price: 50 000 DA/jour
        "HSE-012",
        "Habilitation à l'Utilisation des Produits Chimiques",
        "HSE",
        4,
        28,
        5,
        20,
        Decimal("50000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        4,
        "",
    ),
    (
        "HSE-013",
        "Premier Secours",
        "HSE",
        1,
        7,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        1,
        "",
    ),
    (
        "HSE-014",
        "Lutte Contre l'Incendie",
        "HSE",
        1,
        7,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        1,
        "",
    ),
    (
        "HSE-015",
        "Habilitation Travail en Hauteur",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-016",
        "La Conduite en Sécurité des Engins",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-017",
        "Risque Hydrogène Sulfuré H2S",
        "HSE",
        1,
        7,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        1,
        "",
    ),
    (
        "HSE-018",
        "Atmosphère Explosive – Niveau 01 (ISM-ATEX 1)",
        "HSE",
        3,
        21,
        1,
        10,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "ISM",
    ),
    (
        # Invoiced: ISM-ATEX 2EM → 192 660.56 DA/p (invoice 002), 180 000 DA/p (invoices 003, 013) → use 180 000
        "HSE-019",
        "Atmosphère Explosive – Niveau 02 E (ISM-ATEX 2EM)",
        "HSE",
        5,
        35,
        1,
        10,
        Decimal("180000.00"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        5,
        "ISM",
    ),
    (
        "HSE-020",
        "La Conduite Sécuritaire des Ponts Roulants",
        "HSE",
        2,
        14,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    (
        "HSE-021",
        "Délégué Environnement",
        "HSE",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        True,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        # Invoiced: sensibilisation risque carrières → 45 000 DA/jour · 2 jours (invoice 005)
        "HSE-022",
        "Formation Sensibilisation aux Risques liés à l'Activité de Carrières",
        "HSE",
        2,
        14,
        5,
        30,
        Decimal("45000.00"),
        "theory_only",
        False,
        Decimal("10"),
        Decimal("20"),
        2,
        "",
    ),
    # ── INFORMATIQUE ─────────────────────────────────────────────────────────
    (
        "INF-001",
        "Excel & Word Avancés",
        "INF",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
    (
        "INF-002",
        "Power BI",
        "INF",
        3,
        21,
        5,
        20,
        Decimal("0"),
        "both",
        False,
        Decimal("10"),
        Decimal("20"),
        3,
        "",
    ),
]

# ── Clients ───────────────────────────────────────────────────────────────────
# (name, address, city, nif, nis, rc)
CLIENTS = [
    {
        "name": "SARL Metal Steel Company LTD",
        "address": "Cité Houari Boumediene Rue Ounis Hamlaoui",
        "city": "Sétif",
        "nif": "001519009174778",
        "nis": "001519200026459",
        "rc": "15 B 0091747 - 00/19",
    },
    {
        "name": "EURL G S AUTOMATION",
        "address": "43 Rue El Joundi Boukhaloua Cheikh, Local N°04 Es Seddikia",
        "city": "Oran",
        "nif": "001631011645745",
        "nis": "001631030034561",
        "rc": "16 B 0116457-00/31",
    },
    {
        "name": "SPA ACG SIM",
        "address": "EL HAMOUL CLASSE 13 GP 69 ET 67 EL KARMA",
        "city": "Oran",
        "nif": "001609080924405",
        "nis": "001609010028853",
        "rc": "16 B 0809244-00/31",
    },
    {
        "name": "SARL SMOFE",
        "address": "Cité Telidjene",
        "city": "Sétif",
        "nif": "000319008503407",
        "nis": "000319010143268",
        "rc": "03B0085034-19/00",
    },
    {
        "name": "SNC KEBICHE ABDELHALIM ET CIE",
        "address": "ELKEF LAHMAR",
        "city": "Sétif",
        "nif": "000419008571081",
        "nis": "000419340810946",
        "rc": "04 b 0085710-00/19",
    },
    {
        "name": "SARL GROUPE RIADH EL-FETH",
        "address": "BD Beggag Bouzid Cité Financière",
        "city": "Sétif",
        "nif": "09971900820164600000",
        "nis": "099719010778514",
        "rc": "97 B 0082016-00/19",
    },
    {
        "name": "EURL TAHWEEL DZ",
        "address": "Zone Act Art 5ème Tranche Ilot 18 Sec 309",
        "city": "Sétif",
        "nif": "002219009505042",
        "nis": "002219010072849",
        "rc": "22 B 0095050 -00/19",
    },
    {
        "name": "WEG ALGERIA MOTOROS SPA",
        "address": "Zone Industrielle LEHLATMA 01/03, Commune de Guidjel",
        "city": "Sétif",
        "nif": "002219009506760",
        "nis": "",
        "rc": "22 B 0095067 00-19",
    },
    {
        "name": "SARL RONIX",
        "address": "FID SMARA SEC 06 GRP N12 N01 BAZER SAKRA",
        "city": "Sétif",
        "nif": "001819200047451",
        "nis": "001819200047451",
        "rc": "18 B 0093479-00/19",
    },
    {
        "name": "SARL A2M ELECTRONICS",
        "address": "Z.I N°23 Lot N°32 bis",
        "city": "Sétif",
        "nif": "001019008854771",
        "nis": "001019010000771",
        "rc": "10 B 0088547-00/19",
    },
    {
        "name": "EURL BAIT EL OUTOUR EL ALAMIA",
        "address": "Cité Kaaboub Coop Belle Vue Section 07 Groupe 911 RDC",
        "city": "Sétif",
        "nif": "002219009511634",
        "nis": "002219010134018",
        "rc": "22 B 0095116 - 00/19",
    },
    {
        "name": "EURL AFNES-PROJECT",
        "address": "CITE RYM SIDI ACHOUR COOP IMMOB IHCENE BT°01",
        "city": "Annaba",
        "nif": "000623036433719",
        "nis": "000623010300376",
        "rc": "06 B 0364337-00/23",
    },
]


# ─────────────────────────── command ─────────────────────────────────────────


class Command(BaseCommand):
    help = (
        "Seed initial data: admin user, institute info, "
        "5 training categories, all formations, and 12 clients."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing records (identified by unique key).",
        )

    def handle(self, *args, **options):
        force = options["force"]

        self._seed_admin(force)
        self._seed_institute(force)
        self._seed_categories(force)
        self._seed_formations(force)
        self._seed_clients(force)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _ok(self, msg: str):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def _skip(self, msg: str):
        self.stdout.write(f"  – {msg} (already exists, skipped)")

    def _info(self, msg: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n► {msg}"))

    # ── admin user ────────────────────────────────────────────────────────────

    def _seed_admin(self, force: bool):
        self._info("Admin user")
        if User.objects.filter(username="admin").exists():
            if force:
                user = User.objects.get(username="admin")
                user.set_password("admin1234!")
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self._ok("admin user — password reset")
            else:
                self._skip("admin user")
            return

        User.objects.create_superuser(
            username="admin",
            email="admin@tamayouz.local",
            password="admin1234!",
            first_name="Administrateur",
            last_name="Système",
        )
        self._ok("admin superuser created  (username: admin / password: admin1234!)")

    # ── institute info ────────────────────────────────────────────────────────

    def _seed_institute(self, force: bool):
        self._info("Institute info")

        try:
            from core.models import InstituteInfo  # adjust app label if needed
        except ImportError:
            self.stderr.write(
                self.style.WARNING(
                    "  ⚠ Could not import InstituteInfo – skipping. "
                    "Check that the 'institute' app label is correct."
                )
            )
            return

        existing = InstituteInfo.get_instance()
        if existing:
            if force:
                for field, value in INSTITUTE.items():
                    setattr(existing, field, value)
                existing.save()
                self._ok("InstituteInfo updated")
            else:
                self._skip("InstituteInfo")
            return

        InstituteInfo.objects.create(**INSTITUTE)
        self._ok("InstituteInfo created")

    # ── categories ────────────────────────────────────────────────────────────

    def _seed_categories(self, force: bool):
        self._info("Categories")

        try:
            from formations.models import Category
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        self._cat_cache: dict[str, object] = {}

        for key, (name, description, color) in CATEGORIES.items():
            obj, created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description, "color": color},
            )
            if not created and force:
                obj.description = description
                obj.color = color
                obj.save(update_fields=["description", "color"])
                self._ok(f"Category [{key}] '{name}' updated")
            elif created:
                self._ok(f"Category [{key}] '{name}' created")
            else:
                self._skip(f"Category [{key}] '{name}'")

            self._cat_cache[key] = obj

    # ── formations ───────────────────────────────────────────────────────────

    def _seed_formations(self, force: bool):
        self._info("Formations")

        try:
            from formations.models import Formation, Category
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        # Ensure category cache exists (in case _seed_categories was already run
        # in a previous call and the cache wasn't populated for this run).
        if not hasattr(self, "_cat_cache"):
            self._cat_cache = {
                key: Category.objects.get(name=name)
                for key, (name, _desc, _color) in CATEGORIES.items()
            }

        created_count = updated_count = skipped_count = 0

        for row in FORMATIONS:
            (
                code,
                title,
                cat_key,
                duration_days,
                duration_hours,
                min_p,
                max_p,
                base_price,
                eval_type,
                produces_cert,
                passing_score,
                max_score,
                min_attendance_days,
                accreditation_body,
            ) = row

            category = self._cat_cache.get(cat_key)
            defaults = {
                "title": title,
                "title_ar": "",  # to be filled in later via admin
                "category": category,
                "duration_days": duration_days,
                "duration_hours": duration_hours,
                "min_participants": min_p,
                "max_participants": max_p,
                # Spec §new — Formation no longer carries a fixed price;
                # price now lives per session cycle (Session.base_price).
                # This importer only seeds the formation catalog (it does
                # not create sessions), so `base_price` from the invoice
                # data has nothing to attach to here and is intentionally
                # not applied.
                "evaluation_type": eval_type,
                "produces_certificate": produces_cert,
                "passing_score": passing_score,
                "max_score": max_score,
                "min_attendance_days": min_attendance_days,
                "accreditation_body": accreditation_body,
                "is_active": True,
            }

            obj, was_created = Formation.objects.get_or_create(
                code=code,
                defaults=defaults,
            )

            if was_created:
                created_count += 1
                self._ok(f"[{code}] {title}")
            elif force:
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.save()
                updated_count += 1
                self._ok(f"[{code}] {title} — updated")
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Formations — {created_count} created, "
                f"{updated_count} updated, {skipped_count} skipped "
                f"(total {len(FORMATIONS)})."
            )
        )

    # ── clients ───────────────────────────────────────────────────────────────

    def _seed_clients(self, force: bool):
        self._info("Clients")

        try:
            from clients.models import Client
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        created_count = updated_count = skipped_count = 0

        for data in CLIENTS:
            name = data["name"]
            defaults = {k: v for k, v in data.items() if k != "name"}
            defaults["is_active"] = True

            obj, was_created = Client.objects.get_or_create(
                name=name,
                defaults=defaults,
            )

            if was_created:
                created_count += 1
                self._ok(f"Client '{name}'")
            elif force:
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.save()
                updated_count += 1
                self._ok(f"Client '{name}' — updated")
            else:
                skipped_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Clients — {created_count} created, "
                f"{updated_count} updated, {skipped_count} skipped "
                f"(total {len(CLIENTS)})."
            )
        )
