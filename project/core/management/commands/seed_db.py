"""
python manage.py seed_db

Populates the database with realistic Algerian sample data covering
every model in the project. Safe to run multiple times — skips records
that already exist by natural key.

Options
-------
--flush     Wipe all app data before seeding (keeps auth superusers).
--no-color  Disable coloured output.
"""

import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from documents.models import GeneratedDocument
from formations.models import Participant, Session, Formation, Category
from resources.models import Trainer, Room
from clients.models import Client
from core.models import InstituteInfo


class Command(BaseCommand):
    help = "Seed the database with sample data for ISI Pedagogical System"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all existing app data before seeding.",
        )

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        with transaction.atomic():
            self._seed_institute()
            users = self._seed_users()
            clients = self._seed_clients()
            rooms = self._seed_rooms()
            trainers = self._seed_trainers()
            cats = self._seed_categories()
            formations = self._seed_formations(cats)
            self._seed_trainer_qualifications(trainers, formations)
            sessions = self._seed_sessions(formations, clients, trainers, rooms)
            self._seed_participants(sessions)

        self.stdout.write(self.style.SUCCESS("\n✓ Database seeded successfully."))

    # ------------------------------------------------------------------
    # Flush
    # ------------------------------------------------------------------
    def _flush(self):
        self.stdout.write(self.style.WARNING("Flushing existing data…"))

        GeneratedDocument.objects.all().delete()
        Participant.objects.all().delete()
        Session.objects.all().delete()
        Formation.objects.all().delete()
        Category.objects.all().delete()
        Trainer.objects.all().delete()
        Room.objects.all().delete()
        Client.objects.all().delete()
        InstituteInfo.objects.all().delete()
        # Remove non-superuser users
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("  done.\n")

    # ------------------------------------------------------------------
    # InstituteInfo singleton
    # ------------------------------------------------------------------
    def _seed_institute(self):
        from core.models import InstituteInfo

        if InstituteInfo.objects.exists():
            self.stdout.write("  InstituteInfo already exists — skipping.")
            return
        InstituteInfo.objects.create(
            name_fr="Institut de Sécurité Industrielle",
            name_ar="معهد الأمن الصناعي",
            address="Cité des Orangers, Bt 08 N°01, Sétif 19000",
            phone="036 84 XX XX",
            email="contact@isi-setif.dz",
            nif="000000000000000",
            nis="000000000000000",
            rc="19/00-0000000B19",
            article_imposition="19000000000",
            rib="00000000000000000000",
            accreditation_number="DEFP 003",
            accreditation_date=datetime.date(2022, 3, 14),
            if_number="000000000",
            footer_fr="Institut de Sécurité Industrielle — Accrédité DEFP 003",
            footer_ar="معهد الأمن الصناعي — معتمد لدى DEFP 003",
        )
        self._ok("InstituteInfo")

    # ------------------------------------------------------------------
    # Users  (admin + staff + 2 trainers + viewer)
    # ------------------------------------------------------------------
    def _seed_users(self):
        from accounts.models import UserProfile

        created = {}
        specs = [
            # username, password, first, last, role, is_staff
            ("admin", "Admin@1234", "Karim", "Bensalem", "admin", True),
            ("staff1", "Staff@1234", "Nadia", "Hamidi", "staff", False),
            ("formateur1", "Form@1234", "Youcef", "Meziane", "trainer", False),
            ("formateur2", "Form@1234", "Amira", "Khelifi", "trainer", False),
            ("viewer1", "View@1234", "Salim", "Ouadah", "viewer", False),
        ]
        for username, pwd, first, last, role, is_staff in specs:
            user, new = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@isi-setif.dz",
                    "is_staff": is_staff,
                },
            )
            if new:
                user.set_password(pwd)
                user.save()
                UserProfile.objects.filter(user=user).update(role=role)
                self._ok(f"User {username}")
            created[username] = user
        return created

    # ------------------------------------------------------------------
    # Clients
    # ------------------------------------------------------------------
    def _seed_clients(self):
        from clients.models import Client

        data = [
            dict(
                name="SARL GRAVEM",
                name_ar="ش.ذ.م.م جرافيم",
                address="Zone Industrielle, Sétif",
                city="Sétif",
                phone="036 00 00 01",
                email="contact@gravem.dz",
                contact_person="M. Boudjemaa",
                nif="190019000000001",
                nis="190019000000001",
                rc="19/00-0000001B19",
            ),
            dict(
                name="NAFTAL SPA",
                name_ar="نفطال",
                address="Route Nationale N°5, Bordj Bou Arréridj",
                city="Bordj Bou Arréridj",
                phone="035 00 00 02",
                email="securite@naftal.dz",
                contact_person="Mme Larbi",
                nif="090009000000002",
                nis="090009000000002",
                rc="09/00-0000002B09",
            ),
            dict(
                name="SONELGAZ",
                name_ar="سونلغاز",
                address="Boulevard Krim Belkacem, Alger",
                city="Alger",
                phone="021 00 00 03",
                email="formation@sonelgaz.dz",
                contact_person="M. Chérif",
                nif="160016000000003",
                nis="160016000000003",
                rc="16/00-0000003B16",
            ),
            dict(
                name="CEVITAL SPA",
                name_ar="سيفيتال",
                address="Port de Béjaïa",
                city="Béjaïa",
                phone="034 00 00 04",
                email="rh@cevital.dz",
                contact_person="Mme Aït Youcef",
                nif="060006000000004",
                nis="060006000000004",
                rc="06/00-0000004B06",
            ),
            dict(
                name="ALGERIAN CEMENT COMPANY",
                name_ar="الشركة الجزائرية للإسمنت",
                address="Zone d'Activités, Aïn El Kebira, Sétif",
                city="Sétif",
                phone="036 00 00 05",
                email="hse@acc.dz",
                contact_person="M. Ouameur",
                nif="190019000000005",
                nis="190019000000005",
                rc="19/00-0000005B19",
            ),
        ]
        objs = {}
        for d in data:
            obj, new = Client.objects.get_or_create(name=d["name"], defaults=d)
            if new:
                self._ok(f"Client {obj.name}")
            objs[obj.name] = obj
        return objs

    # ------------------------------------------------------------------
    # Rooms
    # ------------------------------------------------------------------
    def _seed_rooms(self):
        from resources.models import Room

        data = [
            dict(
                name="Salle A",
                capacity=15,
                equipment="Vidéoprojecteur, tableau blanc, climatisation",
            ),
            dict(
                name="Salle B", capacity=12, equipment="Vidéoprojecteur, tableau blanc"
            ),
            dict(
                name="Salle C",
                capacity=20,
                equipment="Vidéoprojecteur, tableau blanc, climatisation, sono",
            ),
            dict(
                name="Atelier 1",
                capacity=10,
                equipment="Équipements HSE, matériel pratique",
            ),
        ]
        objs = {}
        for d in data:
            obj, new = Room.objects.get_or_create(name=d["name"], defaults=d)
            if new:
                self._ok(f"Room {obj.name}")
            objs[obj.name] = obj
        return objs

    # ------------------------------------------------------------------
    # Trainers
    # ------------------------------------------------------------------
    def _seed_trainers(self):
        from resources.models import Trainer

        data = [
            dict(
                first_name="Youcef",
                last_name="Meziane",
                first_name_ar="يوسف",
                last_name_ar="مزيان",
                specialty="Hygiène, Sécurité et Environnement",
                professional_address="12 Rue des Frères Bouadou, Sétif 19000",
                phone="0661 00 00 10",
                email="y.meziane@isi-setif.dz",
                employment_type="internal",
            ),
            dict(
                first_name="Amira",
                last_name="Khelifi",
                first_name_ar="أميرة",
                last_name_ar="خليفي",
                specialty="Sécurité Incendie et Premiers Secours",
                professional_address="Cité 1er Novembre, Bt 3, Sétif 19000",
                phone="0771 00 00 11",
                email="a.khelifi@isi-setif.dz",
                employment_type="internal",
            ),
            dict(
                first_name="Rachid",
                last_name="Boukhalfa",
                first_name_ar="رشيد",
                last_name_ar="بوخلفة",
                specialty="Conduite en Sécurité des Engins de Chantier",
                professional_address="Zone d'Activités Ain Arnet, Sétif",
                phone="0551 00 00 12",
                email="r.boukhalfa@extern.dz",
                employment_type="external",
            ),
            dict(
                first_name="Samira",
                last_name="Hadj Ahmed",
                first_name_ar="سميرة",
                last_name_ar="حاج أحمد",
                specialty="Commission Paritaire d'Hygiène et Sécurité",
                professional_address="Rue Didouche Mourad, Constantine 25000",
                phone="0660 00 00 13",
                email="s.hadjahmed@extern.dz",
                employment_type="external",
            ),
        ]
        objs = {}
        for d in data:
            key = f"{d['first_name']} {d['last_name']}"
            obj, new = Trainer.objects.get_or_create(
                first_name=d["first_name"], last_name=d["last_name"], defaults=d
            )
            if new:
                self._ok(f"Trainer {key}")
            objs[key] = obj
        return objs

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------
    def _seed_categories(self):
        from formations.models import Category

        data = [
            dict(
                name="Sécurité au Travail",
                color="#dc3545",
                description="Formations HSE de base",
            ),
            dict(
                name="Incendie & Secours",
                color="#fd7e14",
                description="Prévention et lutte contre l'incendie",
            ),
            dict(
                name="Engins & Conduite",
                color="#0d6efd",
                description="Conduite sécurisée d'engins",
            ),
            dict(
                name="Réglementaire",
                color="#198754",
                description="Formations à caractère légal et réglementaire",
            ),
        ]
        objs = {}
        for d in data:
            obj, new = Category.objects.get_or_create(name=d["name"], defaults=d)
            if new:
                self._ok(f"Category {obj.name}")
            objs[obj.name] = obj
        return objs

    # ------------------------------------------------------------------
    # Formations
    # ------------------------------------------------------------------
    def _seed_formations(self, cats):
        from formations.models import Formation

        data = [
            dict(
                title="Commission Paritaire d'Hygiène et Sécurité",
                title_ar="اللجنة المتساوية للنظافة والسلامة",
                code="CPHS",
                category=cats["Réglementaire"],
                description="Formation réglementaire pour les membres des commissions paritaires HSE.",
                duration_days=3,
                duration_hours=21,
                min_participants=5,
                max_participants=15,
                base_price=Decimal("45000.00"),
                evaluation_type="both",
                passing_score=Decimal("10.00"),
                produces_certificate=True,
                accreditation_body="DEFP 003",
                legal_references="Décret exécutif 05-09 du 8 janvier 2005",
            ),
            dict(
                title="Sécurité, Hygiène et Environnement — Niveau 1",
                title_ar="السلامة والنظافة والبيئة — المستوى 1",
                code="SHE1",
                category=cats["Sécurité au Travail"],
                description="Sensibilisation aux risques professionnels et aux gestes de prévention.",
                duration_days=2,
                duration_hours=14,
                min_participants=5,
                max_participants=15,
                base_price=Decimal("30000.00"),
                evaluation_type="theory_only",
                passing_score=Decimal("10.00"),
                produces_certificate=True,
                accreditation_body="DEFP 003",
                legal_references="Loi 88-07 du 26 janvier 1988",
            ),
            dict(
                title="Prévention et Lutte Contre l'Incendie",
                title_ar="الوقاية من الحرائق ومكافحتها",
                code="PLCI",
                category=cats["Incendie & Secours"],
                description="Théorie du feu, classes d'incendie, équipements de protection et évacuation.",
                duration_days=3,
                duration_hours=21,
                min_participants=5,
                max_participants=12,
                base_price=Decimal("50000.00"),
                evaluation_type="both",
                passing_score=Decimal("10.00"),
                produces_certificate=True,
                accreditation_body="DEFP 003",
                legal_references="Décret exécutif 76-48",
            ),
            dict(
                title="Conduite en Sécurité des Engins de Chantier",
                title_ar="القيادة الآمنة لآليات ورشات البناء",
                code="CSEC",
                category=cats["Engins & Conduite"],
                description="Règles de sécurité pour la conduite des chariots élévateurs et engins de chantier.",
                duration_days=5,
                duration_hours=35,
                min_participants=4,
                max_participants=10,
                base_price=Decimal("70000.00"),
                evaluation_type="both",
                passing_score=Decimal("10.00"),
                produces_certificate=True,
                accreditation_body="DEFP 003",
                legal_references="Arrêté du 22 mars 2004",
            ),
            dict(
                title="Premiers Secours en Entreprise",
                title_ar="الإسعافات الأولية في المؤسسة",
                code="PSE",
                category=cats["Incendie & Secours"],
                description="Gestes de premiers secours, RCP, utilisation du DAE.",
                duration_days=2,
                duration_hours=14,
                min_participants=5,
                max_participants=15,
                base_price=Decimal("35000.00"),
                evaluation_type="practice_only",
                passing_score=Decimal("10.00"),
                produces_certificate=True,
                accreditation_body="DEFP 003",
                legal_references="Décret exécutif 05-09",
            ),
        ]
        objs = {}
        for d in data:
            obj, new = Formation.objects.get_or_create(code=d["code"], defaults=d)
            if new:
                self._ok(f"Formation {obj.code}")
            objs[obj.code] = obj
        return objs

    # ------------------------------------------------------------------
    # Trainer ↔ Formation qualifications
    # ------------------------------------------------------------------
    def _seed_trainer_qualifications(self, trainers, formations):
        mapping = {
            "Youcef Meziane": ["CPHS", "SHE1", "PLCI"],
            "Amira Khelifi": ["PLCI", "PSE"],
            "Rachid Boukhalfa": ["CSEC"],
            "Samira Hadj Ahmed": ["CPHS", "SHE1"],
        }
        for trainer_name, codes in mapping.items():
            trainer = trainers.get(trainer_name)
            if not trainer:
                continue
            for code in codes:
                f = formations.get(code)
                if f:
                    trainer.qualifications.add(f)
        self._ok("Trainer qualifications")

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def _seed_sessions(self, formations, clients, trainers, rooms):
        from formations.models import Session

        today = datetime.date.today()

        # Helper
        def dt(offset_days):
            return today + datetime.timedelta(days=offset_days)

        data = [
            # --- planned (future)
            dict(
                formation=formations["CPHS"],
                client=clients["SARL GRAVEM"],
                trainer=trainers["Youcef Meziane"],
                date_start=dt(14),
                date_end=dt(16),
                location_type="institute",
                room=rooms["Salle A"],
                capacity=12,
                status="planned",
                specialty_code="CPHS",
                session_number="001/2025",
                committee_members=[],
            ),
            dict(
                formation=formations["SHE1"],
                client=clients["NAFTAL SPA"],
                trainer=trainers["Samira Hadj Ahmed"],
                date_start=dt(21),
                date_end=dt(22),
                location_type="on_site",
                external_location="NAFTAL BBA — Salle de formation",
                capacity=15,
                status="planned",
                specialty_code="SHE1",
                session_number="002/2025",
                committee_members=[],
            ),
            # --- in progress
            dict(
                formation=formations["PLCI"],
                client=clients["SONELGAZ"],
                trainer=trainers["Amira Khelifi"],
                date_start=dt(-1),
                date_end=dt(1),
                location_type="institute",
                room=rooms["Atelier 1"],
                capacity=10,
                status="in_progress",
                specialty_code="PLCI",
                session_number="003/2025",
                committee_members=[],
            ),
            # --- completed (with committee, ready for docs)
            dict(
                formation=formations["CPHS"],
                client=clients["CEVITAL SPA"],
                trainer=trainers["Youcef Meziane"],
                date_start=dt(-30),
                date_end=dt(-28),
                location_type="institute",
                room=rooms["Salle B"],
                capacity=12,
                status="completed",
                specialty_code="CPHS",
                session_number="004/2025",
                committee_members=[
                    "M. Karim Bensalem — Directeur ISI",
                    "Mme Nadia Hamidi — Responsable pédagogique",
                    "M. Youcef Meziane — Formateur",
                ],
            ),
            # --- archived
            dict(
                formation=formations["CSEC"],
                client=clients["ALGERIAN CEMENT COMPANY"],
                trainer=trainers["Rachid Boukhalfa"],
                date_start=dt(-90),
                date_end=dt(-86),
                location_type="on_site",
                external_location="ACC Aïn El Kebira — Zone industrielle",
                capacity=8,
                status="archived",
                specialty_code="CSEC",
                session_number="005/2024",
                committee_members=[
                    "M. Karim Bensalem — Directeur ISI",
                    "M. Rachid Boukhalfa — Formateur",
                ],
            ),
            # --- cancelled
            dict(
                formation=formations["PSE"],
                client=clients["NAFTAL SPA"],
                trainer=trainers["Amira Khelifi"],
                date_start=dt(-60),
                date_end=dt(-59),
                location_type="institute",
                room=rooms["Salle C"],
                capacity=15,
                status="cancelled",
                cancellation_reason="Client a reporté la session à une date ultérieure.",
                specialty_code="PSE",
                session_number="006/2024",
                committee_members=[],
            ),
        ]

        objs = []
        for d in data:
            # Use specialty_code + date_start as natural key
            existing = Session.objects.filter(
                specialty_code=d["specialty_code"],
                date_start=d["date_start"],
                client=d["client"],
            ).first()
            if existing:
                objs.append(existing)
                continue
            session = Session(**d)
            session.save()
            self._ok(f"Session {session.reference}")
            objs.append(session)
        return objs

    # ------------------------------------------------------------------
    # Participants
    # ------------------------------------------------------------------
    def _seed_participants(self, sessions):
        from formations.models import Participant, Session

        # Raw participant pool — bilingual Algerian names
        pool = [
            dict(
                first_name="Mohamed",
                last_name="Boulahia",
                first_name_ar="محمد",
                last_name_ar="بولحية",
                date_of_birth=datetime.date(1985, 4, 12),
                place_of_birth="Sétif",
                place_of_birth_ar="سطيف",
                job_title="Agent HSE",
                employer="SARL GRAVEM",
            ),
            dict(
                first_name="Fatima",
                last_name="Ouali",
                first_name_ar="فاطمة",
                last_name_ar="والي",
                date_of_birth=datetime.date(1990, 7, 22),
                place_of_birth="Sétif",
                place_of_birth_ar="سطيف",
                job_title="Responsable sécurité",
                employer="NAFTAL SPA",
            ),
            dict(
                first_name="Abdelkader",
                last_name="Ferhat",
                first_name_ar="عبد القادر",
                last_name_ar="فرحات",
                date_of_birth=datetime.date(1978, 1, 5),
                place_of_birth="Constantine",
                place_of_birth_ar="قسنطينة",
                job_title="Technicien",
                employer="SONELGAZ",
            ),
            dict(
                first_name="Lynda",
                last_name="Aït Saad",
                first_name_ar="ليندة",
                last_name_ar="آيت سعد",
                date_of_birth=datetime.date(1993, 11, 30),
                place_of_birth="Béjaïa",
                place_of_birth_ar="بجاية",
                job_title="Chargée HSE",
                employer="CEVITAL SPA",
            ),
            dict(
                first_name="Hicham",
                last_name="Ziani",
                first_name_ar="هشام",
                last_name_ar="زياني",
                date_of_birth=datetime.date(1988, 3, 17),
                place_of_birth="Batna",
                place_of_birth_ar="باتنة",
                job_title="Chef d'équipe",
                employer="SARL GRAVEM",
            ),
            dict(
                first_name="Soumia",
                last_name="Benali",
                first_name_ar="سومية",
                last_name_ar="بن علي",
                date_of_birth=datetime.date(1995, 6, 8),
                place_of_birth="Sétif",
                place_of_birth_ar="سطيف",
                job_title="Infirmière HSE",
                employer="ACC",
            ),
            dict(
                first_name="Kamel",
                last_name="Messaoud",
                first_name_ar="كمال",
                last_name_ar="مسعود",
                date_of_birth=datetime.date(1982, 9, 25),
                place_of_birth="Annaba",
                place_of_birth_ar="عنابة",
                job_title="Conducteur d'engins",
                employer="ACC",
            ),
            dict(
                first_name="Meriem",
                last_name="Hadjadj",
                first_name_ar="مريم",
                last_name_ar="حداد",
                date_of_birth=datetime.date(1991, 2, 14),
                place_of_birth="Alger",
                place_of_birth_ar="الجزائر",
                job_title="Assistante sécurité",
                employer="SONELGAZ",
            ),
        ]

        # Map session index → participant slice + scores/attendance config
        # (session order matches the list returned by _seed_sessions)
        session_configs = [
            # 0: planned — just register, no scores yet
            dict(indices=[0, 1, 2, 3, 4], score_config=None),
            # 1: planned — fewer participants
            dict(indices=[5, 6, 7], score_config=None),
            # 2: in_progress — attendance recorded, no scores yet
            dict(indices=[0, 2, 4, 6], score_config="attendance_only"),
            # 3: completed — full scores, mixed results
            dict(
                indices=[1, 3, 5, 7, 0, 2],
                score_config="full",
                scores=[
                    (14.0, 13.0),  # passed
                    (12.5, 11.0),  # passed
                    (8.0, 9.0),  # failed
                    (15.0, 16.0),  # passed
                    (11.0, 10.5),  # passed
                    (7.0, None),  # absent
                ],
            ),
            # 4: archived — full scores, all passed
            dict(
                indices=[0, 2, 4, 6],
                score_config="full",
                scores=[
                    (13.0, 12.0),
                    (15.5, 14.0),
                    (11.0, 10.0),
                    (16.0, 15.0),
                ],
            ),
            # 5: cancelled — participants registered but no action
            dict(indices=[1, 3], score_config=None),
        ]

        for s_idx, (session, cfg) in enumerate(zip(sessions, session_configs)):
            eval_type = session.formation.evaluation_type

            for p_idx, pool_idx in enumerate(cfg["indices"]):
                pdata = pool[pool_idx % len(pool)]

                # Skip if already exists
                if Participant.objects.filter(
                    session=session,
                    first_name=pdata["first_name"],
                    last_name=pdata["last_name"],
                ).exists():
                    continue

                p = Participant(session=session, **pdata)

                # Scores / attendance
                score_cfg = cfg.get("score_config")

                if score_cfg == "attendance_only":
                    p.attended = True
                    p.attendance_per_day = {"J1": True, "J2": True}

                elif score_cfg == "full":
                    scores = cfg.get("scores", [])
                    if p_idx < len(scores):
                        th, pr = scores[p_idx]
                        if th is None:
                            # Mark absent
                            p.attended = False
                            p.attendance_per_day = {
                                "J1": False,
                                "J2": False,
                                "J3": False,
                            }
                        else:
                            p.attended = True
                            p.attendance_per_day = {
                                f"J{d+1}": True
                                for d in range(session.formation.duration_days)
                            }
                            if eval_type in ["theory_only", "both"] and th is not None:
                                p.score_theory = Decimal(str(th))
                            if (
                                eval_type in ["practice_only", "both"]
                                and pr is not None
                            ):
                                p.score_practice = Decimal(str(pr))

                # For archived sessions also mark certificate_issued on passed participants
                p.save()

                if session.status == "archived" and p.result == "passed":
                    from formations.utils import assign_certificate_number

                    assign_certificate_number(p)
                    p.refresh_from_db()
                    p.certificate_issued = True
                    p.save(update_fields=["certificate_issued"])

            self._ok(f"Participants for session {session.reference}")

    # ------------------------------------------------------------------
    def _ok(self, label):
        self.stdout.write(f'  {self.style.SUCCESS("✓")} {label}')
