# formations/management/commands/specialities_seed.py
"""
Seeds the `Specialty` (تخصص) records officially authorised for this
institute, each attached to its `Branch` (see branches_seed.py).

Updated for Nomenclature 2025 (Version Finale)
──────────────────────────────────────────────
  - Added ALL new specialties from the 2025 changelog for:
    • HSE & Related branches (ELE, MEE, CIP, CMS, MME, INP)
    • Informatique branch (INT)

Run
───
    python manage.py specialities_seed
    python manage.py specialities_seed --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

SPECIALTIES = {
    # ── Original accredited specialties ─────────────────────────────────
    "CIP1202": dict(
        branch_abbr="CIP",
        code="1202",
        title="Chimie Industrielle et Plasturgie",
        title_ar="الكيمياء الصناعية والبلاستيك",
    ),
    "MIC1901": dict(
        branch_abbr="MIC",
        code="1901",
        title="Mines et Carrières",
        title_ar="المناجم والمحاجر",
    ),
    "ELE01Q": dict(
        branch_abbr="ELE",
        code="01Q",
        title="Assistant Électricien Bâtiment",
        title_ar="مساعد الكهرباء المعمارية",
    ),
    "ELE02Q": dict(
        branch_abbr="ELE",
        code="02Q",
        title="Installation de Câblage Électrique",
        title_ar="تركيب الأسلاك الكهربائية",
    ),
    "MME1202": dict(
        branch_abbr="MME",
        code="1202",
        title="Cariste",
        title_ar="سائق الرافعات الشوكية",
    ),
    # ── Estimated Specialties from Nomenclature 2019/2025 ───────────────
    "BTP0724": dict(
        branch_abbr="BTP",
        code="0724",
        title="Dessinateur projeteur en architecture",
        title_ar="راسم مسقط في الهندسة المعمارية",
    ),
    "BTP0716": dict(
        branch_abbr="BTP",
        code="0716",
        title="Suivi de réalisation en bâtiment",
        title_ar="متابعة الإنجاز في البناء",
    ),
    "BTP0720": dict(
        branch_abbr="BTP",
        code="0720",
        title="Conducteur de travaux bâtiment",
        title_ar="مسير أشغال البناء",
    ),
    "TAG0714": dict(
        branch_abbr="TAG",
        code="0714",
        title="Comptabilité et gestion",
        title_ar="المحاسبة والتسيير",
    ),
    "TAG1801": dict(
        branch_abbr="TAG",
        code="1801",
        title="Gestion des stocks et logistique",
        title_ar="تسيير المخزون واللوجستيك",
    ),
    "TAG1205": dict(
        branch_abbr="TAG",
        code="1205",
        title="Achat et approvisionnement",
        title_ar="الشراء والتموين",
    ),
    "TAG0717": dict(
        branch_abbr="TAG",
        code="0717",
        title="Gestion des ressources humaines",
        title_ar="تسيير الموارد البشرية",
    ),
    "TAG0712": dict(
        branch_abbr="TAG", code="0712", title="Marketing", title_ar="التسويق"
    ),
    "TAG0710": dict(
        branch_abbr="TAG",
        code="0710",
        title="Documentation et archives",
        title_ar="التوثيق والأرشيف",
    ),
    "TAG0711": dict(
        branch_abbr="TAG",
        code="0711",
        title="Commerce international",
        title_ar="التجارة الدولية",
    ),
    "HRT1803": dict(
        branch_abbr="HRT",
        code="1803",
        title="Restauration / Option : Cuisine",
        title_ar="الإطعام / خيار : الطبخ",
    ),
    "IAA0713": dict(
        branch_abbr="IAA",
        code="0713",
        title="Contrôle de qualité dans les industries agroalimentaires",
        title_ar="مراقبة الجودة في الصناعات الغذائية",
    ),
    "CMS0709": dict(
        branch_abbr="CMS",
        code="0709",
        title="Maintenance industrielle en construction mécanique et sidérurgique",
        title_ar="الصيانة الصناعية في البناء الميكانيكي والصناعة الحديدية",
    ),
    "CMS0707": dict(
        branch_abbr="CMS",
        code="0707",
        title="Métrologie et contrôle de qualité",
        title_ar="الميترولوجيا ومراقبة الجودة",
    ),
    "INP1204": dict(
        branch_abbr="INP",
        code="1204",
        title="Industries pétrolières/ Option : Hygiène et Sécurité Industrielles",
        title_ar="الصناعات البترولية/ خيار: الصحة والسلامة الصناعية",
    ),
    "MME1204": dict(
        branch_abbr="MME", code="1204", title="Grutier", title_ar="سائق الرافعة"
    ),
    "MME1802": dict(
        branch_abbr="MME",
        code="1802",
        title="Conducteur d'engins de travaux de chaussées",
        title_ar="سائق آلات أشغال الطرقات",
    ),
    "ELE0702": dict(
        branch_abbr="ELE",
        code="0702",
        title="Electricité industrielle",
        title_ar="الكهرباء الصناعية",
    ),
    "CIP0703": dict(
        branch_abbr="CIP",
        code="0703",
        title="Technicien Chimiste",
        title_ar="تقني في الكيمياء",
    ),
    # ────────────────────────────────────────────────────────────────────
    # ── NEW 2025 CHANGELOG: HSE & RELATED BRANCHES ──────────────────────
    # ────────────────────────────────────────────────────────────────────
    # ELE Branch (Électricité - Électronique - Énergétique)
    "ELE2501": dict(
        branch_abbr="ELE",
        code="2501",
        title="Électrotechnique / Option : Machines Électriques",
        title_ar="الكهروتقني خيار: آلات كهربائية",
    ),
    "ELE2502": dict(
        branch_abbr="ELE",
        code="2502",
        title="Électrotechnique / Option : Réseaux Électriques",
        title_ar="الكهروتقني خيار : الشبكات الكهربائية",
    ),
    "ELE2503": dict(
        branch_abbr="ELE",
        code="2503",
        title="Installation et Maintenance des Systèmes Solaires Photovoltaïques et Thermiques",
        title_ar="تركيب و صيانة الانظمة الشمسية، الضوئية و الحرارية",
    ),
    "ELE2504": dict(
        branch_abbr="ELE",
        code="2504",
        title="Électronique Embarquée et Systèmes Intelligents",
        title_ar="إليكترونيك المدمجة والأنظمة الذكية",
    ),
    "ELE2505": dict(
        branch_abbr="ELE",
        code="2505",
        title="Maintenance des Équipements Bureautiques",
        title_ar="صيانة الأجهزة المكتبية",
    ),
    "ELE2506": dict(
        branch_abbr="ELE",
        code="2506",
        title="Réparation des Téléphones Fixes et Mobiles",
        title_ar="تصليح الهواتف الثابتة والنقالة",
    ),
    "ELE2509": dict(
        branch_abbr="ELE",
        code="2509",
        title="Installation et Maintenance des Systèmes CVC (HVAC)",
        title_ar="تركيب وصيانة أنظمة HVAC",
    ),
    "ELE2510": dict(
        branch_abbr="ELE",
        code="2510",
        title="Réparation du Faisceau Électrique Automobile",
        title_ar="تصليح حزمة الخيوط الكهربائية للسيارات",
    ),
    "ELE2511": dict(
        branch_abbr="ELE",
        code="2511",
        title="Production Industrie 4.0",
        title_ar="إنتاج الصناعة 4.0",
    ),
    # INP Branch (Industries Pétrolières)
    "INP2501": dict(
        branch_abbr="INP",
        code="2501",
        title="Opérateur d'Essais de Puits (Well Testing)",
        title_ar="مشغل اختبار الأبار WELLTESTING",
    ),
    # MEE Branch (Métiers de l'Eau et de l'Environnement)
    "MEE2501": dict(
        branch_abbr="MEE",
        code="2501",
        title="Installation de Fosses Septiques",
        title_ar="تركيب خزان الصرف الصحي",
    ),
    "MEE2502": dict(
        branch_abbr="MEE",
        code="2502",
        title="Maintenance des Ouvrages d'Assainissement",
        title_ar="صيانة مساحات مياه الصرف الصحي",
    ),
    "MEE2503": dict(
        branch_abbr="MEE",
        code="2503",
        title="Maintenance des Barrages",
        title_ar="صيانة منشآت السدود",
    ),
    "MEE2504": dict(
        branch_abbr="MEE",
        code="2504",
        title="Maintenance des Usines de Dessalement d'Eau de Mer",
        title_ar="صيانة مصانع تحلية مياه البحر",
    ),
    "MEE2505": dict(
        branch_abbr="MEE",
        code="2505",
        title="Surveillance des Réseaux d'Eau Potable",
        title_ar="مراقبة شبكات المياه الصالحة للشرب",
    ),
    "MEE2506": dict(
        branch_abbr="MEE",
        code="2506",
        title="Maintenance des Cours d'Eau",
        title_ar="صيانة المجاري المائية",
    ),
    "MEE2507": dict(
        branch_abbr="MEE",
        code="2507",
        title="Réalisation de Forages",
        title_ar="إنجاز الآبار",
    ),
    "MEE2508": dict(
        branch_abbr="MEE",
        code="2508",
        title="Valorisation des Déchets",
        title_ar="تثمين النفايات",
    ),
    "MEE2301": dict(
        branch_abbr="MEE",
        code="2301",
        title="Exploitation des Usines de Dessalement d'Eau de Mer",
        title_ar="إستغلال محطات تحلية مياه البحر",
    ),
    "MEE2509": dict(
        branch_abbr="MEE",
        code="2509",
        title="Dessinateur Projeteur en Irrigation",
        title_ar="رسام مصمم في الري",
    ),
    "MEE2510": dict(
        branch_abbr="MEE", code="2510", title="Hydrogéologie", title_ar="هيدروجيولوجيا"
    ),
    "MEE2511": dict(
        branch_abbr="MEE",
        code="2511",
        title="Gestion des Écosystèmes",
        title_ar="تسيير النظام البيئي",
    ),
    "MEE2512": dict(
        branch_abbr="MEE",
        code="2512",
        title="Propreté, Sécurité et Environnement",
        title_ar="نظافة امن و البيئة",
    ),
    "MEE2601": dict(
        branch_abbr="MEE",
        code="2601",
        title="Repiquage des Réseaux Urbains",
        title_ar="ترصيص الشبكات الحضرية",
    ),
    # CIP Branch (Chimie Industrielle et Plasturgie)
    "CIP2501": dict(
        branch_abbr="CIP",
        code="2501",
        title="Traitement des Matériaux",
        title_ar="معالجة المواد",
    ),
    "CIP2502": dict(
        branch_abbr="CIP",
        code="2502",
        title="Contrôle Qualité des Produits Pharmaceutiques",
        title_ar="مراقبة النوعية في المنتوجات الصيدلانية",
    ),
    "CIP2201": dict(
        branch_abbr="CIP",
        code="2201",
        title="Production Pharmaceutique",
        title_ar="الإنتاج الصيدلاني",
    ),
    # CMS Branch (Construction Mécanique et Sidérurgique)
    "CMS2501": dict(
        branch_abbr="CMS",
        code="2501",
        title="Fraisage à Commande Numérique",
        title_ar="إستصناع بالتفريز ذات التحكم الرقمي",
    ),
    # MME Branch (Mécanique - Moteurs - Engins)
    "MME2501": dict(
        branch_abbr="MME",
        code="2501",
        title="Assistant Mécanicien Aéronefs / Option : Avion",
        title_ar="مساعد ميكانيكي الطائرات:خيار/الطائرة",
    ),
    "MME2502": dict(
        branch_abbr="MME",
        code="2502",
        title="Assistant Mécanicien Aéronefs / Option : Cellule d'Aéronef",
        title_ar="مساعد ميكانيكي الطائرات:خيار/جسم الطائرة",
    ),
    "MME2503": dict(
        branch_abbr="MME",
        code="2503",
        title="Assistant Mécanicien Aéronefs / Option : Électronique Aéronef",
        title_ar="مساعد ميكانيكي الطائرات:خيار / إليكترونيات الطائرة",
    ),
    # ────────────────────────────────────────────────────────────────────
    # ── NEW 2025 CHANGELOG: INFORMATIQUE BRANCH (INT) ───────────────────
    # ────────────────────────────────────────────────────────────────────
    "INT2501": dict(
        branch_abbr="INT", code="2501", title="Développeur Web", title_ar="مبرمج واب"
    ),
    "INT2502": dict(
        branch_abbr="INT",
        code="2502",
        title="Développeur d'Applications Mobiles",
        title_ar="مبرمج تطبيقات الهاتف النقال",
    ),
    "INT2503": dict(
        branch_abbr="INT",
        code="2503",
        title="Systèmes et Réseaux Informatiques / Option : Administration Réseau",
        title_ar="أنظمة وشبكة المعلوماتية/ خيار: إدارة الشبكة",
    ),
    "INT2401": dict(
        branch_abbr="INT",
        code="2401",
        title="Systèmes et Réseaux Informatiques / Option : Cybersécurité",
        title_ar="أنظمة وشبكة المعلوماتية خيار الأمن السيبراني",
    ),
    "INT2504": dict(
        branch_abbr="INT",
        code="2504",
        title="Systèmes et Réseaux Informatiques / Option : Systèmes et Infrastructure IT",
        title_ar="أنظمة وشبكة معلوماتية خيار : أنظمة وبنية تحتية للمعلوماتية",
    ),
    "INT2505": dict(
        branch_abbr="INT",
        code="2505",
        title="Analyste de Données (Data Analyst)",
        title_ar="محلل بيانات",
    ),
    "INT2506": dict(
        branch_abbr="INT",
        code="2506",
        title="Développeur de Réalité Étendue (XR) et Métavers",
        title_ar="تطوير تقنيات الواقع الممتد «XR »و الميتافارس",
    ),
    "INT2507": dict(
        branch_abbr="INT",
        code="2507",
        title="Informatique / Option : Support Technique et Maintenance Informatique",
        title_ar="الإعلام الآلي – خيار الدعم التقني والصيانة المعلوماتية",
    ),
    "INT2601": dict(
        branch_abbr="INT",
        code="2601",
        title="Développeur Web Full Stack",
        title_ar="مطور الواب Full stack",
    ),
    "INT2201": dict(
        branch_abbr="INT",
        code="2201",
        title="Informatique / Option : Développeur Web et Mobile",
        title_ar="إعلام آلي /خيار: مطور الواب والمحمول",
    ),
}


class Command(BaseCommand):
    help = "Seed the state-accredited Specialties (تخصصات) for this institute."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true")

    def handle(self, *args, **options):
        force = options["force"]
        try:
            from formations.models import Branch, Specialty
        except ImportError as exc:
            self.stderr.write(self.style.ERROR(f"  Import error: {exc}"))
            return

        self.stdout.write(self.style.MIGRATE_HEADING("\n► Specialties"))

        for key, data in SPECIALTIES.items():
            try:
                branch = Branch.objects.get(abbreviation=data["branch_abbr"])
            except Branch.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f"  ✗ Branch '{data['branch_abbr']}' not found — "
                        f"run `python manage.py branches_seed` first. "
                        f"Skipping specialty [{key}]."
                    )
                )
                continue

            defaults = {
                "code": data["code"],
                "title": data["title"],
                "title_ar": data["title_ar"],
            }

            obj, created = Specialty.objects.get_or_create(
                branch=branch,
                code=data["code"],
                defaults=defaults,
            )
            if not created and force:
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.full_clean()
                obj.save()
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Specialty [{obj.reference_root}] updated")
                )
            elif created:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Specialty [{obj.reference_root}] created")
                )
            else:
                self.stdout.write(
                    f"  – Specialty [{branch.abbreviation}{data['code']}] (already exists, skipped)"
                )
