# formations/management/commands/branches_seed.py
"""
Seeds the `Branch` (شعبة) records the institute is officially authorised
to deliver, per the accreditation/extension decrees issued by the
Direction de la Formation et de l'Enseignement Professionnels de la
wilaya de Sétif.

Updated in this revision
─────────────────────────
  - Added INT (Informatique - Numérique - Télécom) to support the new
    2025 changelog IT specialties.
  - Added MEE (Métiers de l'Eau et de l'Environnement) to support the
    environment/HSE-related 2025 changelog specialties.

Run
───
    python manage.py branches_seed
    python manage.py branches_seed --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

BRANCHES = {
    # ── Original accredited branches ─────────────────────────────────────
    "CIP": dict(
        abbreviation="CIP",
        name="Chimie Industrielle et Plasturgie",
        name_ar="الكيمياء الصناعية والبلاستيك",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "MIC": dict(
        abbreviation="MIC",
        name="Mines et Carrières",
        name_ar="المناجم والمحاجر",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "ELE": dict(
        abbreviation="ELE",
        name="Electricité - Electronique - Energétique",
        name_ar="الكهرباء - الإلكترونيك - الطاقوية",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "MME": dict(
        abbreviation="MME",
        name="Mécanique - Moteurs - Engins",
        name_ar="الميكانيك - المحركات - الآليات",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    # ── NEW branches (candidates for accreditation extension) ───────────
    "BTP": dict(
        abbreviation="BTP",
        name="Bâtiment - Travaux Publics",
        name_ar="البناء والأشغال العمومية",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "TAG": dict(
        abbreviation="TAG",
        name="Techniques Administratives et de Gestion",
        name_ar="التقنيات الإدارية والتسيير",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "HRT": dict(
        abbreviation="HRT",
        name="Hôtellerie - Restauration - Tourisme",
        name_ar="الفندقة - المطاعم - السياحة",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "IAA": dict(
        abbreviation="IAA",
        name="Industries Agroalimentaires",
        name_ar="الصناعات الغذائية",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "CMS": dict(
        abbreviation="CMS",
        name="Construction Mécanique et Sidérurgique",
        name_ar="البناء الميكانيكي والصناعة الحديدية",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "INP": dict(
        abbreviation="INP",
        name="Industries Pétrolières",
        name_ar="الصناعات البترولية",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    # ── Added for 2025 Changelog Specialties ────────────────────────────
    "INT": dict(
        abbreviation="INT",
        name="Informatique - Numérique - Télécom",
        name_ar="إعلام آلي - الرقمنة - الاتصالات",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
    "MEE": dict(
        abbreviation="MEE",
        name="Métiers de l'Eau et de l'Environnement",
        name_ar="مهن المياه و البيئة",
        curriculum_type="qualifiante",
        curriculum_min_months=1,
        curriculum_max_months=6,
    ),
}


class Command(BaseCommand):
    help = "Seed the state-accredited Branches (شعب) authorised for this institute."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        force = options["force"]
        try:
            from formations.models import Branch
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("\n► Branches"))

        for key, data in BRANCHES.items():
            obj, created = Branch.objects.get_or_create(
                abbreviation=data["abbreviation"],
                defaults=data,
            )
            if not created and force:
                for field, value in data.items():
                    setattr(obj, field, value)
                obj.full_clean()
                obj.save()
                self.stdout.write(self.style.SUCCESS(f"  ✓ Branch [{key}] updated"))
            elif created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ Branch [{key}] created"))
            else:
                self.stdout.write(f"  – Branch [{key}] (already exists, skipped)")
