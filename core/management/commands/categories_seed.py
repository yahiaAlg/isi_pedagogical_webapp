# formations/management/commands/categories_seed.py
"""
Seeds the commercial catalogue Categories used to group the institute's
training offer.

Refined in this revision
─────────────────────────
  - Split QMS (Management de la Qualité) into its own category. ISO, Audit,
    Non-Conformités, Contrôle Qualité, MSA, and IATF 16949 are now properly
    separated from RH.
  - Moved purely commercial formations (Vente, Négociation) to COM.
  - Sharpened the descriptions of existing categories to better reflect
    the actual invoiced training portfolio.

Run
───
    python manage.py categories_seed
    python manage.py categories_seed --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

CATEGORIES = {
    "RH": (
        "Management des Ressources Humaines",
        "Gestion RH, droit du travail, rémunération, indicateurs de performance et développement des compétences",
        "#1ABC9C",
    ),
    "COM": (
        "Communication, Leadership & Soft Skills",
        "Leadership managérial, gestion d'équipes, gestion du temps, communication interpersonnelle et techniques de vente",
        "#7ED321",
    ),
    "QMS": (
        "Management de la Qualité & Conformité",
        "Systèmes de management (ISO 9001, ISO 22000, IATF 16949), audit SMQ, traitement des non-conformités, MSA et contrôle qualité",
        "#3498DB",
    ),
    "PMD": (
        "Maintenance & Productique Industrielle",
        "Maintenance industrielle, GMAO, TPM, RCM, fondamentaux de la production et planification",
        "#F5A623",
    ),
    "HSE": (
        "Hygiène, Sécurité & Environnement",
        "Habilitations (électriques, ATEX, chariots), sécurité des procédés, HACCP, environnement et secourisme",
        "#D0021B",
    ),
    "INF": (
        "Informatique, Bureautique & Data Analyse",
        "Bureautique avancée, outils décisionnels (Power BI), analyse de données et réseaux",
        "#9B59B6",
    ),
    "BAT": (
        "Bâtiment & Travaux Publics",
        "Architecture, suivi de chantier, conduite de travaux et gestion de projet immobilier",
        "#5D8AA0",
    ),
    "GES": (
        "Gestion Administrative, Financière & Logistique",
        "Comptabilité, trésorerie, gestion des stocks, approvisionnements, achats et logistique",
        "#2ECC71",
    ),
    "PHA": (
        "Industrie Pharmaceutique & Santé",
        "BPF, affaires réglementaires, gestion documentaire (SMF), contrôle qualité pharmaceutique et gestion des flux",
        "#E67E22",
    ),
}


class Command(BaseCommand):
    help = "Seed the commercial catalogue categories (RH, COM, QMS, PMD, HSE, INF, BAT, GES, PHA)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        force = options["force"]
        try:
            from formations.models import Category
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("\n► Categories"))

        for key, (name, description, color) in CATEGORIES.items():
            obj, created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description, "color": color},
            )
            if not created and force:
                obj.description = description
                obj.color = color
                obj.save(update_fields=["description", "color"])
                self.stdout.write(self.style.SUCCESS(f"  ✓ [{key}] '{name}' updated"))
            elif created:
                self.stdout.write(self.style.SUCCESS(f"  ✓ [{key}] '{name}' created"))
            else:
                self.stdout.write(f"  – [{key}] '{name}' (already exists, skipped)")
