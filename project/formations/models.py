from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")
    color = models.CharField(max_length=7, blank=True, verbose_name="Couleur")

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Formation(models.Model):
    EVALUATION_CHOICES = [
        ("theory_only", "Théorique seulement"),
        ("practice_only", "Pratique seulement"),
        ("both", "Théorique et pratique"),
    ]

    title = models.CharField(max_length=200, verbose_name="Titre")
    title_ar = models.CharField(max_length=200, verbose_name="Titre (AR)")
    code = models.CharField(max_length=20, unique=True, verbose_name="Code")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    description = models.TextField(blank=True, verbose_name="Description")

    duration_days = models.IntegerField(verbose_name="Durée (jours)")
    duration_hours = models.IntegerField(verbose_name="Durée (heures)")
    min_participants = models.IntegerField(verbose_name="Minimum participants")
    max_participants = models.IntegerField(verbose_name="Maximum participants")
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix de base (DA)",
    )

    evaluation_type = models.CharField(
        max_length=20, choices=EVALUATION_CHOICES, verbose_name="Type d'évaluation"
    )
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        verbose_name="Note de passage",
    )
    # Spec §new — maximum score for exam (default 20, modifiable)
    max_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        verbose_name="Note maximale de l'examen",
    )
    # Spec §new — minimum attendance days required for certification
    min_attendance_days = models.IntegerField(
        default=1,
        verbose_name="Présence minimale (jours)",
        help_text="Nombre minimum de jours de présence requis pour obtenir l'attestation",
    )

    produces_certificate = models.BooleanField(
        default=True, verbose_name="Produit une attestation"
    )

    accreditation_body = models.CharField(
        max_length=100, blank=True, verbose_name="Organisme d'agrément"
    )
    legal_references = models.TextField(blank=True, verbose_name="Références légales")

    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Formation"
        verbose_name_plural = "Formations"
        ordering = ["title"]

    def __str__(self):
        return f"{self.code} - {self.title}"

    def clean(self):
        if self.min_participants and self.max_participants:
            if self.min_participants > self.max_participants:
                raise ValidationError(
                    "Le minimum ne peut pas être supérieur au maximum"
                )
        if self.duration_days is not None and self.duration_days <= 0:
            raise ValidationError("La durée en jours doit être positive")
        if self.duration_hours is not None and self.duration_hours <= 0:
            raise ValidationError("La durée en heures doit être positive")
        if self.passing_score is not None and self.max_score is not None:
            if self.passing_score < 0 or self.passing_score > self.max_score:
                raise ValidationError(
                    f"La note de passage doit être entre 0 et {self.max_score}"
                )
        if self.max_score is not None and self.max_score <= 0:
            raise ValidationError("La note maximale doit être positive")
        if self.min_attendance_days is not None:
            if self.min_attendance_days < 1:
                raise ValidationError("La présence minimale doit être au moins 1 jour")
            if self.duration_days and self.min_attendance_days > self.duration_days:
                raise ValidationError(
                    "La présence minimale ne peut pas dépasser la durée de la formation"
                )

        # Spec §15.1 — block deactivation when active/planned sessions exist
        if self.pk and not self.is_active:
            try:
                old = Formation.objects.get(pk=self.pk)
            except Formation.DoesNotExist:
                old = None
            if old and old.is_active:
                blocking_sessions = self.session_set.filter(
                    status__in=["planned", "in_progress"]
                )
                if blocking_sessions.exists():
                    raise ValidationError(
                        "Impossible de désactiver cette formation : des sessions actives "
                        "ou planifiées existent. Annulez-les d'abord."
                    )


class Session(models.Model):
    STATUS_CHOICES = [
        ("planned", "Planifiée"),
        ("in_progress", "En cours"),
        ("completed", "Terminée"),
        ("archived", "Archivée"),
        ("cancelled", "Annulée"),
    ]

    LOCATION_CHOICES = [
        ("institute", "Institut"),
        ("on_site", "Sur site"),
    ]

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE)
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE)
    trainer = models.ForeignKey("resources.Trainer", on_delete=models.CASCADE)

    reference = models.CharField(max_length=50, unique=True, verbose_name="Référence")
    date_start = models.DateField(verbose_name="Date début")
    date_end = models.DateField(verbose_name="Date fin")

    location_type = models.CharField(
        max_length=20, choices=LOCATION_CHOICES, verbose_name="Type de lieu"
    )
    room = models.ForeignKey(
        "resources.Room", on_delete=models.SET_NULL, null=True, blank=True
    )
    external_location = models.CharField(
        max_length=200, blank=True, verbose_name="Lieu externe"
    )

    capacity = models.IntegerField(verbose_name="Capacité")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="planned", verbose_name="Statut"
    )
    cancellation_reason = models.TextField(
        blank=True, verbose_name="Raison d'annulation"
    )

    committee_members = models.JSONField(
        default=list, blank=True, verbose_name="Membres du comité"
    )
    specialty_code = models.CharField(
        max_length=20, blank=True, verbose_name="Code spécialité"
    )
    session_number = models.CharField(
        max_length=20, blank=True, verbose_name="Numéro de session"
    )

    # Spec §new — session group support
    is_primary = models.BooleanField(
        default=True,
        verbose_name="Session principale",
        help_text="Session principale (jour 1). Les sessions suivantes sont auto-générées.",
    )
    parent_session = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="child_sessions",
        verbose_name="Session parente",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Session"
        verbose_name_plural = "Sessions"
        ordering = ["-date_start"]

    def __str__(self):
        return f"{self.reference} - {self.formation.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generate_reference()
        if not self.capacity:
            self.capacity = self.formation.max_participants
        super().save(*args, **kwargs)

    def _generate_reference(self):
        from .utils import generate_session_reference

        return generate_session_reference(self)

    def clean(self):
        if self.date_start and self.date_end and self.date_end < self.date_start:
            raise ValidationError("La date de fin doit être après la date de début")

        if self.location_type == "institute" and not self.room:
            raise ValidationError(
                "Une salle doit être sélectionnée pour une formation à l'institut"
            )
        if self.location_type == "on_site" and not self.external_location:
            raise ValidationError("Le lieu externe doit être spécifié")
        if self.status == "cancelled" and not self.cancellation_reason:
            raise ValidationError("Une raison d'annulation est requise")

        # Terminal state guard
        if self.pk:
            try:
                old_status = Session.objects.get(pk=self.pk).status
            except Session.DoesNotExist:
                old_status = None
            if old_status in ["archived", "cancelled"] and self.status != old_status:
                raise ValidationError(
                    f"Impossible de changer le statut depuis '{old_status}'"
                )

    # ---------------------------------------------------------------- computed
    @property
    def participant_count(self):
        return self.participant_set.count()

    @property
    def available_spots(self):
        return max(0, self.capacity - self.participant_count)

    @property
    def fill_rate(self):
        if self.capacity == 0:
            return 0
        return round((self.participant_count / self.capacity) * 100, 1)

    @property
    def total_present(self):
        return self.participant_set.filter(attended=True).count()

    @property
    def total_absent(self):
        return self.participant_set.filter(attended=False).count()

    @property
    def duration_days(self):
        return (self.date_end - self.date_start).days + 1

    @property
    def group_sessions_count(self):
        """Total sessions in this group (primary + children)."""
        if self.is_primary:
            return 1 + self.child_sessions.count()
        if self.parent_session:
            return 1 + self.parent_session.child_sessions.count()
        return 1

    @property
    def day_number(self):
        """1-based day number within the session group."""
        if self.is_primary:
            return 1
        if self.parent_session:
            siblings = list(
                self.parent_session.child_sessions.order_by("date_start").values_list(
                    "pk", flat=True
                )
            )
            try:
                return siblings.index(self.pk) + 2
            except ValueError:
                return None
        return 1

    @property
    def child_sessions_generated(self):
        """True if child sessions have already been generated."""
        return self.child_sessions.exists()

    # ---------------------------------------------------------------- helpers
    def can_add_participants(self):
        return self.status in ["planned", "in_progress"] and self.available_spots > 0

    def can_edit(self):
        return self.status not in ["archived", "cancelled"]

    def can_transition_to(self, new_status):
        if self.status in ["archived", "cancelled"]:
            return False
        valid_transitions = {
            "planned": ["in_progress", "cancelled"],
            "in_progress": ["completed", "cancelled"],
            "completed": ["archived"],
        }
        return new_status in valid_transitions.get(self.status, [])


class Participant(models.Model):
    session = models.ForeignKey(Session, on_delete=models.CASCADE)

    first_name = models.CharField(max_length=50, verbose_name="Prénom")
    last_name = models.CharField(max_length=50, verbose_name="Nom")
    first_name_ar = models.CharField(
        max_length=50, blank=True, verbose_name="Prénom (AR)"
    )
    last_name_ar = models.CharField(max_length=50, blank=True, verbose_name="Nom (AR)")

    date_of_birth = models.DateField(
        null=True, blank=True, verbose_name="Date de naissance"
    )
    place_of_birth = models.CharField(
        max_length=100, blank=True, verbose_name="Lieu de naissance"
    )
    place_of_birth_ar = models.CharField(
        max_length=100, blank=True, verbose_name="Lieu de naissance (AR)"
    )

    job_title = models.CharField(max_length=100, blank=True, verbose_name="Fonction")
    employer = models.CharField(max_length=200, blank=True, verbose_name="Employeur")
    employer_client = models.ForeignKey(
        "clients.Client", on_delete=models.SET_NULL, null=True, blank=True
    )

    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")

    attended = models.BooleanField(default=True, verbose_name="Présent")
    attendance_per_day = models.JSONField(
        default=dict, blank=True, verbose_name="Présence par jour"
    )

    score_theory = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note théorique (journée)",
    )
    score_practice = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note pratique (journée)",
    )

    # Spec §new — final exam score; only meaningful for primary-session participants
    exam_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Note d'examen final",
        help_text="Note de l'examen final — détermine la réussite et l'attribution de l'attestation",
    )

    # Spec §new — link back to primary-session participant (null for primary participants)
    source_participant = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="copies",
        verbose_name="Participant source",
    )

    # certificate_number: auto-assigned at generation time only — never user-editable
    certificate_number = models.CharField(
        max_length=50, blank=True, verbose_name="Numéro de certificat"
    )
    certificate_issued = models.BooleanField(
        default=False, verbose_name="Certificat émis"
    )

    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Participant"
        verbose_name_plural = "Participants"
        ordering = ["last_name", "first_name"]
        unique_together = ["session", "last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        if self.pk:
            # Protect certificate_number from being changed once assigned
            old = Participant.objects.get(pk=self.pk)
            if (
                old.certificate_number
                and self.certificate_number != old.certificate_number
            ):
                self.certificate_number = old.certificate_number
        else:
            # Spec §15.2 — certificate number never assignable through a form
            self.certificate_number = ""
        super().save(*args, **kwargs)

    def clean(self):
        max_s = self.session.formation.max_score if self.pk else Decimal("20.00")
        try:
            max_s = self.session.formation.max_score
        except Exception:
            max_s = Decimal("20.00")

        if self.score_theory is not None and (
            self.score_theory < 0 or self.score_theory > max_s
        ):
            raise ValidationError(f"La note théorique doit être entre 0 et {max_s}")
        if self.score_practice is not None and (
            self.score_practice < 0 or self.score_practice > max_s
        ):
            raise ValidationError(f"La note pratique doit être entre 0 et {max_s}")
        if self.exam_score is not None and (
            self.exam_score < 0 or self.exam_score > max_s
        ):
            raise ValidationError(f"La note d'examen doit être entre 0 et {max_s}")

    # ---------------------------------------------------------------- computed
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name_ar(self):
        if self.first_name_ar and self.last_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar}"
        return ""

    @property
    def days_attended(self):
        """
        For primary participants: total days attended across the whole session group.
        For child participants: 1 if attended, 0 otherwise.
        """
        if not self.session.is_primary:
            return 1 if self.attended else 0
        # Own attendance + copies in child sessions
        own = 1 if self.attended else 0
        copies_present = self.copies.filter(attended=True).count()
        return own + copies_present

    @property
    def total_group_sessions(self):
        """Total session days in this group."""
        return self.session.group_sessions_count

    @property
    def result(self):
        """
        Spec §new — result logic updated:
        - Non-primary participants: simple attendance indicator only.
        - Primary participants: based on exam_score + days_attended.
        """
        if not self.session.is_primary:
            # Child session: attendance only
            return "present" if self.attended else "absent"

        formation = self.session.formation
        min_days = formation.min_attendance_days

        # Check attendance threshold
        if self.days_attended < min_days:
            return "absent"

        # Check exam score
        if self.exam_score is None:
            return "pending"

        if self.exam_score >= formation.passing_score:
            return "passed"
        return "failed"

    def can_receive_certificate(self):
        return (
            self.result == "passed"
            and self.session.formation.produces_certificate
            and self.session.is_primary
        )

    def assign_certificate_number(self):
        if self.certificate_number or not self.can_receive_certificate():
            return
        from .utils import assign_certificate_number

        assign_certificate_number(self)

    def get_attendance_for_day(self, day_key):
        return self.attendance_per_day.get(day_key, True)

    def set_attendance_for_day(self, day_key, present):
        if not self.attendance_per_day:
            self.attendance_per_day = {}
        self.attendance_per_day[day_key] = present
        self.attended = any(self.attendance_per_day.values())
        self.save()
