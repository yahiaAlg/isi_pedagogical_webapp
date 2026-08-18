from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import os


def session_document_path(instance, filename):
    """
    Spec §10.6 — store under MEDIA_ROOT/documents/sessions/{session_pk}/
    instance.session_id is available even before the instance is fully saved.
    """
    return f"documents/sessions/{instance.session_id}/{filename}"


class GeneratedDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ("candidate_list", "Liste des informations candidats"),
        ("attendance_sheet", "Feuille de présence"),
        ("mission_order", "Ordre de mission"),
        ("evaluation_list", "Liste des notes d'évaluation"),
        # Spec v2.2 — post-session document, generated immediately before the
        # deliberation report (carries each participant's exam result)
        ("nominal_list", "Liste nominale"),
        ("deliberation_report", "محضر مداولات نهاية التكوين"),
        ("evaluation_sheet", "Fiche d'évaluation individuelle"),
        ("attestation", "شهادة تكوين تأهيلي"),
    ]

    session = models.ForeignKey("formations.Session", on_delete=models.CASCADE)
    participant = models.ForeignKey(
        "formations.Participant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Null pour les documents au niveau session",
    )

    doc_type = models.CharField(max_length=50, choices=DOC_TYPE_CHOICES)
    # Spec §10.6 — MEDIA_ROOT/documents/sessions/{pk}/
    file = models.FileField(upload_to=session_document_path)

    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_latest = models.BooleanField(default=True)

    day_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Pour les feuilles de présence (jour 1, 2, etc.)",
    )

    class Meta:
        verbose_name = "Document généré"
        verbose_name_plural = "Documents générés"
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["session", "doc_type", "is_latest"]),
            models.Index(fields=["participant", "doc_type", "is_latest"]),
        ]

    def __str__(self):
        doc_name = self.get_doc_type_display()
        if self.participant:
            return f"{doc_name} - {self.participant.full_name}"
        if self.day_number:
            return f"{doc_name} - Jour {self.day_number}"
        return f"{doc_name} - {self.session.reference}"

    def _generate_filename(self):
        doc_type = self.doc_type
        session_ref = self.session.reference.replace("/", "_")
        base_name = f"{session_ref}_{doc_type}"
        if self.participant:
            name = (
                f"{self.participant.first_name}_{self.participant.last_name}".replace(
                    " ", "_"
                )
            )
            base_name += f"_{name}"
        if self.day_number:
            base_name += f"_jour{self.day_number}"
        return f"{base_name}.docx"

    def get_download_filename(self):
        doc_name = self.get_doc_type_display().replace(" ", "_")
        session_ref = self.session.reference.replace("/", "-")
        base_name = f"{session_ref}_{doc_name}"
        if self.participant:
            base_name += f"_{self.participant.full_name.replace(' ', '_')}"
        if self.day_number:
            base_name += f"_Jour{self.day_number}"
        # fix: preserve the real extension of the stored file (e.g. the
        # attestation is stored/served as .pdf, not .docx like every other
        # doc_type) instead of hardcoding .docx for all document types.
        ext = os.path.splitext(self.file.name)[1] or ".docx"
        return f"{base_name}{ext}"

    def invalidate_previous(self):
        """Mark previous documents of same type/participant/day as is_latest=False."""
        filters = {
            "session": self.session,
            "doc_type": self.doc_type,
            "is_latest": True,
        }
        if self.participant:
            filters["participant"] = self.participant
        else:
            filters["participant__isnull"] = True

        if self.day_number:
            filters["day_number"] = self.day_number
        else:
            filters["day_number__isnull"] = True

        qs = GeneratedDocument.objects.filter(**filters)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        qs.update(is_latest=False)

    @classmethod
    def get_latest_for_session(
        cls, session, doc_type, participant=None, day_number=None
    ):
        filters = {"session": session, "doc_type": doc_type, "is_latest": True}
        if participant:
            filters["participant"] = participant
        else:
            filters["participant__isnull"] = True
        if day_number:
            filters["day_number"] = day_number
        else:
            filters["day_number__isnull"] = True
        try:
            return cls.objects.get(**filters)
        except cls.DoesNotExist:
            return None

    def clean(self):
        participant_required = ["evaluation_sheet", "attestation"]
        session_only = [
            "candidate_list",
            "mission_order",
            "nominal_list",
            "evaluation_list",
            "deliberation_report",
        ]
        day_based = ["attendance_sheet"]

        if self.doc_type in participant_required and not self.participant:
            raise ValidationError(
                f"Un participant est requis pour '{self.get_doc_type_display()}'"
            )
        if self.doc_type in session_only and self.participant:
            raise ValidationError(
                f"Aucun participant ne doit être spécifié pour '{self.get_doc_type_display()}'"
            )
        if self.doc_type in day_based and not self.day_number:
            raise ValidationError(
                f"Un numéro de jour est requis pour '{self.get_doc_type_display()}'"
            )


class EmployeeMissionOrder(models.Model):
    """
    A standalone "ordre de mission" for a non-formateur employee — global,
    not tied to any Session/formation, filled directly with its own data
    and generated from a dedicated quick-access page (rather than from a
    specific session's document list, which only covers the formateur's
    own mission order for that session).

    Shares the SAME yearly archival sequence as Session.mission_order_number
    (see core/sequencing.py:allocate_mission_order_number), so the combined
    registry of mission orders — whether for a formateur or an employee —
    is one continuous, gapless per-year count.
    """

    TRANSPORT_CHOICES = [
        ("vehicule_service", "Véhicule de service"),
        ("vehicule_personnel", "Véhicule personnel"),
        ("transport_commun", "Transport en commun"),
        ("autre", "Autre"),
    ]

    archive_number = models.CharField(
        max_length=20,
        blank=True,
        unique=True,
        verbose_name="N° d'archivage",
    )

    employee_name = models.CharField(max_length=150, verbose_name="Nom et prénom")
    job_title = models.CharField(
        max_length=150, blank=True, verbose_name="Fonction occupée"
    )
    professional_address = models.CharField(
        max_length=255, blank=True, verbose_name="Adresse professionnelle"
    )

    destination = models.CharField(max_length=200, verbose_name="Destination")
    motif = models.CharField(max_length=255, verbose_name="Motif de la mission")

    date_start = models.DateField(verbose_name="Date de départ")
    time_start = models.TimeField(
        null=True, blank=True, verbose_name="Heure de départ"
    )
    date_end = models.DateField(verbose_name="Date de retour")

    transport_means = models.CharField(
        max_length=30,
        choices=TRANSPORT_CHOICES,
        default="vehicule_service",
        verbose_name="Moyen de transport",
    )

    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Ordre de mission (employé)"
        verbose_name_plural = "Ordres de mission (employés)"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.archive_number or '—'} — {self.employee_name}"

    def save(self, *args, **kwargs):
        if self.pk:
            # Protect archive_number from being silently CLEARED by an
            # unrelated save once assigned — same relaxed rule as
            # Session.pv_number / Participant.certificate_number: only
            # blanking is blocked, an admin explicitly typing a NEW value
            # (hard-coding it via the edit form) is always honoured.
            old_archive_number = (
                EmployeeMissionOrder.objects.filter(pk=self.pk)
                .values_list("archive_number", flat=True)
                .first()
            )
            if old_archive_number and not self.archive_number:
                self.archive_number = old_archive_number
        super().save(*args, **kwargs)

    def clean(self):
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError(
                "La date de retour doit être après la date de départ"
            )

    def assign_archive_number(self):
        """Idempotent — same never-reassigned pattern as
        Session.assign_mission_order_number / assign_pv_number."""
        if self.archive_number:
            return
        from core.sequencing import allocate_mission_order_number

        self.archive_number = allocate_mission_order_number()
        self.save(update_fields=["archive_number"])


class HotEvaluation(models.Model):
    """
    « Fiche d'évaluation à chaud » — post-training satisfaction survey
    filled out by the candidate on paper right after the session, then
    transcribed into the app. One per participant (doc_type
    "evaluation_sheet" / "Fiche d'évaluation individuelle" in
    GeneratedDocument — see check_document_requirements(), which already
    requires the participant's result to be settled before this can be
    generated).

    The 8 criteria and their A/B/C/D grading scale are fixed by the
    institute's own paper form (never configured per-formation), so they
    live as a plain class-level constant here instead of a separate
    lookup model.

    Two print modes share this same data (see documents/views_print.py):
    - blank  (?mode=blank) — nothing pre-filled, meant to be printed and
      handed to the candidate to tick by hand.
    - filled — renders the checkmarks/ticks from whatever has been
      transcribed here via the HotEvaluationForm.
    """

    GRADE_CHOICES = [
        ("A", "A — Satisfait"),
        ("B", "B — Bon"),
        ("C", "C — Moyen"),
        ("D", "D — Non satisfait"),
    ]
    # Max points each grade is worth — mirrors the paper form's own
    # "A /10  B /8  C /6  D /4" column headers. Used to render the
    # "NOTE/10" cell and to compute the overall score out of 80.
    GRADE_POINTS = {"A": 10, "B": 8, "C": 6, "D": 4}

    SATISFACTION_CHOICES = [
        ("very_satisfied", "Très satisfait"),
        ("satisfied", "Satisfait"),
        ("average", "Moyen"),
        ("dissatisfied", "Insatisfait"),
    ]

    # (field_suffix, French label, Arabic label) — order matches the
    # paper form (N° 1 to 8) and is fixed on purpose.
    CRITERIA = [
        (
            "content",
            "Contenu de la formation (objectifs, thème)",
            "محتوى التدريب (الأهداف, الموضوع)",
        ),
        (
            "duration",
            "Durée de la formation",
            "مدة التدريب",
        ),
        (
            "materials",
            "Supports pédagogiques (documents, présentation, autres…)",
            "الدعم التعليمي (الوثائق, العرض التقديمي للتدريب)",
        ),
        (
            "trainer_delivery",
            "Comment avez-vous ressenti l'animation du formateur ?",
            "ما هو شعورك تجاه شرح الأستاذ ؟",
        ),
        (
            "atmosphere",
            "Ambiance générale de la formation (degré de participation)",
            "الجو العام للتدريب (درجة المشاركة)",
        ),
        (
            "new_knowledge",
            "Nouvelles connaissances acquises",
            "المعرفة المكتسبة الجديدة",
        ),
        (
            "expectations",
            "Connaissances répondant à vos attentes et à vos besoins",
            "المعرفة التي تلبي توقعاتك و احتياجاتك",
        ),
        (
            "applicability",
            "Connaissances applicables sur le poste de travail",
            "المعرفة التي تنطبق على منصب عملك",
        ),
    ]

    participant = models.OneToOneField(
        "formations.Participant",
        on_delete=models.CASCADE,
        related_name="hot_evaluation",
        verbose_name="Participant",
    )

    grade_1 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="1. Contenu de la formation",
    )
    grade_2 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="2. Durée de la formation",
    )
    grade_3 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="3. Supports pédagogiques",
    )
    grade_4 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="4. Animation du formateur",
    )
    grade_5 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="5. Ambiance générale",
    )
    grade_6 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="6. Nouvelles connaissances acquises",
    )
    grade_7 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="7. Réponse aux attentes/besoins",
    )
    grade_8 = models.CharField(
        max_length=1, choices=GRADE_CHOICES, blank=True,
        verbose_name="8. Applicabilité sur le poste de travail",
    )

    overall_satisfaction = models.CharField(
        max_length=20,
        choices=SATISFACTION_CHOICES,
        blank=True,
        verbose_name="Appréciation générale",
        help_text="بشكل عام، كيف تقيم هذا التدريب ؟",
    )
    comments = models.TextField(blank=True, verbose_name="Commentaires")

    filled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Saisi par",
    )
    filled_at = models.DateTimeField(auto_now=True, verbose_name="Dernière saisie")

    class Meta:
        verbose_name = "Fiche d'évaluation à chaud"
        verbose_name_plural = "Fiches d'évaluation à chaud"

    def __str__(self):
        return f"Éval. à chaud — {self.participant.full_name}"

    def graded_criteria(self):
        """(criterion, grade, points) triples in display order — used by
        both the form and the print template so the 8 rows never drift
        out of sync with each other."""
        rows = []
        for i, (key, label_fr, label_ar) in enumerate(self.CRITERIA, start=1):
            grade = getattr(self, f"grade_{i}")
            rows.append(
                {
                    "number": i,
                    "field_name": f"grade_{i}",
                    "key": key,
                    "label_fr": label_fr,
                    "label_ar": label_ar,
                    "grade": grade,
                    "points": self.GRADE_POINTS.get(grade),
                }
            )
        return rows

    @property
    def is_complete(self):
        return bool(self.overall_satisfaction) and all(
            getattr(self, f"grade_{i}") for i in range(1, 9)
        )

    @property
    def total_score(self):
        """Sum of points across the 8 criteria (max 80), or None while
        any criterion is still ungraded."""
        points = [self.GRADE_POINTS.get(getattr(self, f"grade_{i}")) for i in range(1, 9)]
        if any(p is None for p in points):
            return None
        return sum(points)
