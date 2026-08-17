# core/management/commands/institute_seed.py
"""
Seeds the institute's own identity data:
  - Superuser  (admin / admin1234!)
  - InstituteInfo  (legal + fiscal identity, sourced from the official
    accreditation decrees and the invoice header)

Source documents
─────────────────
  - Décision d'accréditation n°003 du 14/03/2022 (ministère de la Formation
    et de l'Enseignement Professionnels) — accreditation_number/date
  - Facture n°0152026 du 08/04/2026 (SARL Alger Chimie) — legal header:
    raison sociale, adresse, téléphone, RC, NIF, RIB, article d'imposition
  - Plaquette commerciale "EEMS" (Établissement d'Excellence de Management
    et de Sécurité) — trading name used publicly by the institute; the
    legal name registered with the ministry/RC remains "SARL MOUASSASSET
    TAMAYOUZ LILIDARA W ESSALAMA", so the trading name is kept in the
    French footer rather than overwriting the registered name.

Run
───
    python manage.py institute_seed
    python manage.py institute_seed --force   # overwrite existing records
"""

from __future__ import annotations

import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

# ─────────────────────────── raw data ──────────────────────────────────────

INSTITUTE = {
    # Legal name as registered on the RC / accreditation decree.
    "name_fr": "SARL MOUASSASSET TAMAYOUZ LILIDARA W ESSALAMA",
    "name_ar": "مؤسسة التميز للإدارة والسلامة",
    "address": "CITE LOTIS HACHEMI 1ère TRANCHE ETAGE 1 ET 2, SETIF",
    # From facture n°0152026 header: "Tél. 036527557"
    "phone": "036527557",
    "email": "",
    "nif": "002119009444326",
    "nis": "002119010021763",
    "rc": "21B 0094443-19/00",
    "article_imposition": "19011780071",
    "rib": "001-007110300001829-41",
    # Décision d'accréditation n°003 du 14/03/2022 — établissement de
    # formation privé agréé par le ministère de la Formation Professionnelle.
    "accreditation_number": "EFP 003",
    "accreditation_date": datetime.date(2022, 3, 14),
    "if_number": "19011780071",
    # Trading name "EEMS — Établissement d'Excellence de Management et de
    # Sécurité" surfaced on commercial documents/plaquette; kept here since
    # InstituteInfo has no dedicated "trading name" field.
    "footer_fr": (
        "Établissement d'Excellence de Management et de Sécurité (EEMS) — "
        "Agrément EFP 003 du 14/03/2022 · Bureau d'études agréé Environnement n°134 du 21/10/2021"
    ),
    "footer_ar": (
        "مؤسسة التميز للإدارة والسلامة — اعتماد EFP 003 بتاريخ 14/03/2022 "
        "· مكتب دراسات معتمد من وزارة البيئة رقم 134 بتاريخ 21/10/2021"
    ),
}


# ─────────────────────────── command ───────────────────────────────────────


class Command(BaseCommand):
    help = "Seed initial data: admin user and institute (EEMS/Tamayouz) info."

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

    # ── helpers ──────────────────────────────────────────────────────────
    def _ok(self, msg: str):
        self.stdout.write(self.style.SUCCESS(f"  ✓ {msg}"))

    def _skip(self, msg: str):
        self.stdout.write(f"  – {msg} (already exists, skipped)")

    def _info(self, msg: str):
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n► {msg}"))

    # ── admin user ───────────────────────────────────────────────────────
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

    # ── institute info ───────────────────────────────────────────────────
    def _seed_institute(self, force: bool):
        self._info("Institute info (EEMS / Tamayouz)")

        try:
            from core.models import InstituteInfo
        except ImportError:
            self.stderr.write(
                self.style.WARNING(
                    "  ⚠ Could not import InstituteInfo – skipping. "
                    "Check that the 'core' app label is correct."
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
