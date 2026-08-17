from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.core.validators import FileExtensionValidator
from decimal import Decimal, ROUND_HALF_UP
import uuid


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


class Branch(models.Model):
    """Spec §2.0a — top-level catalog grouping (`الشعبة`). Determines curriculum
    type and attestation type for every specialty/formation beneath it."""

    CURRICULUM_CHOICES = [
        ("diplomante", "Diplômante"),
        ("qualifiante", "Qualifiante"),
    ]

    abbreviation = models.CharField(
        max_length=10, unique=True, verbose_name="Abréviation"
    )
    name = models.CharField(max_length=150, verbose_name="Nom")
    name_ar = models.CharField(max_length=150, blank=True, verbose_name="Nom (AR)")
    curriculum_type = models.CharField(
        max_length=20, choices=CURRICULUM_CHOICES, verbose_name="Type de cursus"
    )
    curriculum_min_months = models.IntegerField(verbose_name="Durée minimale (mois)")
    curriculum_max_months = models.IntegerField(verbose_name="Durée maximale (mois)")

    class Meta:
        verbose_name = "Branche"
        verbose_name_plural = "Branches"
        ordering = ["abbreviation"]

    def __str__(self):
        return f"{self.abbreviation} - {self.name}"

    def clean(self):
        self.abbreviation = (self.abbreviation or "").upper().strip()
        if self.curriculum_type == "diplomante":
            lo, hi = 6, 30
        elif self.curriculum_type == "qualifiante":
            lo, hi = 1, 6
        else:
            return

        if self.curriculum_min_months is not None and not (
            lo <= self.curriculum_min_months <= hi
        ):
            raise ValidationError(
                f"Pour un cursus {self.get_curriculum_type_display().lower()}, "
                f"la durée minimale doit être comprise entre {lo} et {hi} mois."
            )
        if self.curriculum_max_months is not None and not (
            lo <= self.curriculum_max_months <= hi
        ):
            raise ValidationError(
                f"Pour un cursus {self.get_curriculum_type_display().lower()}, "
                f"la durée maximale doit être comprise entre {lo} et {hi} mois."
            )
        if (
            self.curriculum_min_months is not None
            and self.curriculum_max_months is not None
            and self.curriculum_min_months > self.curriculum_max_months
        ):
            raise ValidationError(
                "La durée minimale ne peut pas dépasser la durée maximale."
            )

    @property
    def attestation_type(self):
        """Spec rule 17 — diplomante → diplome, qualifiante → certificat."""
        return "diplome" if self.curriculum_type == "diplomante" else "certificat"


class Specialty(models.Model):
    """Spec §2.0b — belongs to exactly one branch; supplies the numeric code
    used in every reference and certificate number issued under it (`التخصص`)."""

    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name="specialties",
        verbose_name="Branche",
    )
    code = models.CharField(max_length=20, verbose_name="Code")
    title = models.CharField(max_length=200, verbose_name="Titre")
    title_ar = models.CharField(max_length=200, blank=True, verbose_name="Titre (AR)")

    class Meta:
        verbose_name = "Spécialité"
        verbose_name_plural = "Spécialités"
        ordering = ["branch__abbreviation", "code"]
        unique_together = ["branch", "code"]

    def __str__(self):
        return f"{self.reference_root} - {self.title}"

    def clean(self):
        self.code = (self.code or "").strip()

    @property
    def reference_root(self):
        """Spec rule — branch.abbreviation + specialty.code, e.g. CIP + 1202 -> CIP1202."""
        if not self.branch_id:
            return self.code
        return f"{self.branch.abbreviation}{self.code}"


class Formation(models.Model):
    EVALUATION_CHOICES = [
        ("theory_only", "Théorique seulement"),
        ("practice_only", "Pratique seulement"),
        ("both", "Théorique et pratique"),
    ]

    ATTESTATION_TYPE_CHOICES = [
        ("diplome", "Diplôme"),
        ("certificat", "Certificat"),
    ]

    title = models.CharField(max_length=200, verbose_name="Titre")
    title_ar = models.CharField(max_length=200, verbose_name="Titre (AR)")
    code = models.CharField(
        max_length=20, blank=True, db_index=True, verbose_name="Code"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True
    )
    # Spec §2.0b/§2.1 — replaces the standalone Category grouping; when set, it
    # drives an auto-derived `code` and `attestation_type` (see save()).
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="formations",
        verbose_name="Spécialité",
    )
    # Spec rule 17 — derived from specialty.branch.curriculum_type; not
    # independently editable once a specialty is set (see save()).
    attestation_type = models.CharField(
        max_length=20,
        choices=ATTESTATION_TYPE_CHOICES,
        blank=True,
        verbose_name="Type d'attestation",
    )
    description = models.TextField(blank=True, verbose_name="Description")

    duration_days = models.IntegerField(verbose_name="Durée (jours)")
    duration_hours = models.IntegerField(verbose_name="Durée (heures)")
    min_participants = models.IntegerField(
        default=6, verbose_name="Minimum participants"
    )
    max_participants = models.IntegerField(
        default=12, verbose_name="Maximum participants"
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

    def _apply_specialty_derivation(self):
        """Spec §2.1 rule — when a specialty is set, `code` and
        `attestation_type` are auto-derived and cannot drift from it."""
        if self.specialty_id:
            self.code = self.specialty.reference_root
            self.attestation_type = self.specialty.branch.attestation_type

    def save(self, *args, **kwargs):
        self._apply_specialty_derivation()
        super().save(*args, **kwargs)

    @property
    def average_price(self):
        """
        Spec §new — a formation no longer carries its own fixed price: each
        session cycle (its primary session) sets its own `base_price` /
        `price_mode`, since the market price fluctuates per cycle depending
        on demand. This is a weighted average of those cycle prices,
        weighted by each cycle's participant count (a fuller session
        influences the average more than a near-empty one), so the
        formation still exposes a single representative price for catalog
        display/sorting. Cycles without a base_price are ignored. Returns
        None if no cycle has been priced yet.
        """
        primaries = self.session_set.filter(
            is_primary=True, base_price__isnull=False
        ).only("base_price", "capacity", "pk")
        total_weight = Decimal("0")
        weighted_sum = Decimal("0")
        for s in primaries:
            weight = Decimal(s.participant_count or 1)
            weighted_sum += s.base_price * weight
            total_weight += weight
        if total_weight == 0:
            return None
        return (weighted_sum / total_weight).quantize(Decimal("0.01"))

    def clean(self):
        # Derive before validation runs, otherwise clean_fields() would flag
        # a blank code on specialty-linked formations that haven't been
        # saved yet (e.g. admin / direct full_clean() calls).
        self._apply_specialty_derivation()

        if not self.specialty_id and not self.code:
            raise ValidationError("Le code est requis en l'absence de spécialité.")

        # Formations without a specialty keep a freely-entered code, which must
        # stay unique among other specialty-less formations. Specialty-linked
        # formations intentionally share their specialty's root code (they are
        # à-la-carte modules of the same curriculum), so no uniqueness check
        # applies to them.
        if self.code and not self.specialty_id:
            if Formation.objects.filter(code=self.code).exclude(pk=self.pk).exists():
                raise ValidationError("Ce code existe déjà.")

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

    # Spec §new — pricing now belongs to the session CYCLE (its primary
    # session), not the formation: the market price fluctuates each time
    # depending on demand, rather than being a fixed formation attribute.
    # See Formation.average_price for the catalog-level rollup.
    PRICE_MODE_CHOICES = [
        ("by_day", "Par jour (prix de base × nombre de jours)"),
        ("by_person", "Par participant (prix de base × participants)"),
        (
            "by_day_person",
            "Par jour et par participant (prix de base × jours × participants)",
        ),
    ]

    formation = models.ForeignKey(Formation, on_delete=models.CASCADE)
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE)
    trainer = models.ForeignKey("resources.Trainer", on_delete=models.CASCADE)

    reference = models.CharField(max_length=50, unique=True, verbose_name="Référence")

    # pv_number: the محضر مداولات (PV) reference — a SEPARATE monthly-reset
    # sequence from `reference` (see core/sequencing.py:allocate_pv_number).
    # Auto-assigned once, on first use (nominal list or PV print — whichever
    # happens first), then reused by both documents. Never user-editable and
    # never reassigned once set, same protection pattern as
    # Participant.certificate_number below.
    pv_number = models.CharField(
        max_length=20, blank=True, verbose_name="Numéro PV"
    )

    # mission_order_number: the "ordre de mission" archival number — drawn
    # from the SAME yearly counter as documents.EmployeeMissionOrder (see
    # core/sequencing.py:allocate_mission_order_number), so formateur and
    # employee mission orders share one continuous per-year sequence.
    # Auto-assigned once, the first time the session's mission order is
    # printed — see Session.assign_mission_order_number(). Same
    # never-reassigned protection as pv_number above.
    mission_order_number = models.CharField(
        max_length=20, blank=True, verbose_name="Numéro d'ordre de mission"
    )

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
    equipment = models.ManyToManyField(
        "resources.Equipment",
        blank=True,
        related_name="session_set",
        verbose_name="Équipements réservés",
        help_text="Utilisé pour détecter les doubles réservations entre sessions qui se chevauchent.",
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
        max_length=100, blank=True, verbose_name="Numéro de session"
    )

    # Spec §new — this cycle's market price. Set on the primary session;
    # read from there for the whole group (see total_price below).
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix de base (DA)",
        help_text="Prix de ce cycle de session — peut varier d'un cycle à "
        "l'autre selon la demande.",
    )
    price_mode = models.CharField(
        max_length=20,
        choices=PRICE_MODE_CHOICES,
        default="by_person",
        verbose_name="Mode de tarification",
    )
    # Spec §new — the invoice/billing sequence this session cycle is
    # associated with (searchable from the session listing).
    invoice_reference = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name="Numéro de facture",
        help_text="Référence/séquence de facture associée à ce cycle de session.",
    )

    # Spec §new — the formateur's share of this cycle, defaulted from the
    # trainer's own default (Trainer.default_cost_mode/…) when the cycle is
    # created, but fully editable per cycle. Set on the primary session and
    # read from there for the whole group, same pattern as base_price above.
    TRAINER_COST_MODE_CHOICES = [
        ("percentage", "Pourcentage du prix total"),
        ("direct", "Montant direct"),
    ]
    trainer_cost_mode = models.CharField(
        max_length=20,
        choices=TRAINER_COST_MODE_CHOICES,
        default="percentage",
        verbose_name="Mode de rémunération du formateur",
    )
    trainer_cost_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Pourcentage formateur (%)",
        help_text="Part (%) du prix total de ce cycle revenant au formateur.",
    )
    trainer_cost_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Montant direct formateur (DA)",
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
        if self.pk:
            # Protect pv_number from being changed/cleared once assigned —
            # same rule as Participant.certificate_number.
            old_pv_number = (
                Session.objects.filter(pk=self.pk)
                .values_list("pv_number", flat=True)
                .first()
            )
            if old_pv_number and self.pv_number != old_pv_number:
                self.pv_number = old_pv_number
            old_mission_order_number = (
                Session.objects.filter(pk=self.pk)
                .values_list("mission_order_number", flat=True)
                .first()
            )
            if (
                old_mission_order_number
                and self.mission_order_number != old_mission_order_number
            ):
                self.mission_order_number = old_mission_order_number
        super().save(*args, **kwargs)

    def _generate_reference(self):
        from .utils import generate_session_reference

        return generate_session_reference(self)

    def assign_pv_number(self):
        """
        Assign this session's PV (محضر مداولات) number if it doesn't have
        one yet. Idempotent and safe to call from both the nominal-list
        print view and the deliberation-report print view — whichever is
        rendered first allocates the number, the other one just reuses it,
        so both documents always show the same reference.
        """
        if self.pv_number:
            return
        from core.sequencing import allocate_pv_number

        self.pv_number = allocate_pv_number()
        self.save(update_fields=["pv_number"])

    def assign_mission_order_number(self):
        """
        Assign this session's ordre de mission archival number if it
        doesn't have one yet — idempotent, safe to call every time the
        mission order is printed. Drawn from the same yearly counter as
        standalone employee mission orders (core.sequencing.
        allocate_mission_order_number), so the two never collide.
        """
        if self.mission_order_number:
            return
        from core.sequencing import allocate_mission_order_number

        self.mission_order_number = allocate_mission_order_number()
        self.save(update_fields=["mission_order_number"])

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
    def female_count(self):
        """عدد المتربصات — used as « منهم بنات » on the محضر مداولات."""
        return self.participant_set.filter(gender="F").count()

    @property
    def passed_count(self):
        return sum(1 for p in self.participant_set.all() if p.result == "passed")

    @property
    def duration_days(self):
        return (self.date_end - self.date_start).days + 1

    @property
    def total_price(self):
        """
        Spec §new — total price for the whole session group, computed from
        the *cycle's own* `price_mode` and `base_price` (set on the primary
        session — the market price fluctuates per cycle depending on
        demand, it isn't a fixed formation attribute). Meant to be read
        once the session is terminated (status completed/archived), when
        the participant count is final.
          - by_day:         base_price × total days in the group
          - by_person:      base_price × participants
          - by_day_person:  base_price × total days × participants
        Always computed from the *primary* session of the group so the
        total is not duplicated across child (day 2-N) sessions.
        """
        primary = self if self.is_primary else (self.parent_session or self)
        price = primary.base_price
        if price is None:
            return None
        days = primary.group_sessions_count
        persons = primary.participant_count
        mode = primary.price_mode
        if mode == "by_day":
            return price * days
        if mode == "by_day_person":
            return price * days * persons
        return price * persons  # by_person (default)

    @property
    def trainer_cost(self):
        """Spec §new — the formateur's share of this cycle's `total_price`,
        per the cycle's own `trainer_cost_mode` (set on the primary session,
        same read pattern as `total_price`/`base_price` above):
          - direct:     a flat `trainer_cost_amount`, regardless of total_price
          - percentage: `trainer_cost_percentage`% of `total_price`
        Returns None while the inputs it needs aren't available yet (e.g.
        total_price isn't final until the cycle is completed/archived).
        """
        primary = self if self.is_primary else (self.parent_session or self)
        mode = primary.trainer_cost_mode
        if mode == "direct":
            return primary.trainer_cost_amount
        total = self.total_price
        pct = primary.trainer_cost_percentage
        if total is None or pct is None:
            return None
        return (Decimal(total) * pct / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    @property
    def net_revenue(self):
        """Spec §new — this cycle's `total_price` minus the formateur's
        `trainer_cost`: what the institute actually nets from the formation
        once the trainer's part is deducted. None until both are known."""
        total = self.total_price
        cost = self.trainer_cost
        if total is None or cost is None:
            return None
        return total - cost

    @property
    def trainer_payments(self):
        """Spec §new — full installment history for this cycle's formateur
        settlement (most recent first), tied to the *primary* session same
        as `trainer_cost`."""
        primary = self if self.is_primary else (self.parent_session or self)
        return TrainerPayment.objects.filter(session_id=primary.pk).order_by(
            "-paid_at"
        )

    @property
    def trainer_paid_total(self):
        """Spec §new — sum of confirmed installments only (pending/cancelled
        installments don't count towards what's actually been settled)."""
        total = self.trainer_payments.filter(status="confirmed").aggregate(
            s=Sum("amount")
        )["s"]
        return total or Decimal("0.00")

    @property
    def trainer_payment_balance(self):
        """Spec §new — remaining amount still owed to the formateur for
        this cycle. None while `trainer_cost` itself isn't known yet."""
        cost = self.trainer_cost
        if cost is None:
            return None
        return max(cost - self.trainer_paid_total, Decimal("0.00"))

    @property
    def trainer_payment_status(self):
        """Spec §new — 'unpaid' / 'partial' / 'paid' for this cycle's
        formateur settlement, based on confirmed installments vs the cost."""
        cost = self.trainer_cost
        if cost is None:
            return "unknown"
        paid = self.trainer_paid_total
        if paid <= 0:
            return "unpaid"
        if paid < cost:
            return "partial"
        return "paid"

    @property
    def trainer_payment_confirmed(self):
        """True once the formateur's part for this cycle is fully settled
        (kept for back-compat with existing templates/checks)."""
        return self.trainer_payment_status == "paid"

    @property
    def trainer_payment(self):
        """Back-compat single-result accessor (most recent installment)."""
        return self.trainer_payments.first()

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


def trainer_payment_proof_path(instance, filename):
    """MEDIA_ROOT/trainer_payments/{uuid}_{filename} — uuid avoids relying
    on a pk that doesn't exist yet on first save, and prevents collisions."""
    return f"trainer_payments/{uuid.uuid4().hex}_{filename}"


class TrainerPayment(models.Model):
    """Spec §new — one *installment* towards a session cycle's formateur
    share (`Session.trainer_cost`), once the cycle is terminated. A cycle
    can have several installments (règlement en plusieurs tranches) — the
    running total of `confirmed` installments is compared against
    `Session.trainer_cost` to know whether the cycle is unpaid / partially
    paid / fully paid (see `Session.trainer_payment_status`). Each
    installment carries its own settlement mode, transaction reference,
    status, and an optional scanned proof of payment, and can be edited
    later by an administrator (see `resources.trainer_detail` history)."""

    MODE_CHOICES = [
        ("espece", "Espèce"),
        ("cheque", "Chèque"),
        ("virement_bancaire", "Virement bancaire"),
        ("ccp", "Virement CCP"),
    ]

    # Spec §new — installment status: a règlement can be recorded ahead of
    # actual settlement (`pending`), settled (`confirmed`, the default —
    # counts towards `Session.trainer_paid_total`), or voided after the
    # fact (`cancelled`) without losing the audit trail.
    STATUS_CHOICES = [
        ("confirmed", "Confirmé"),
        ("pending", "En attente"),
        ("cancelled", "Annulé"),
    ]

    session = models.ForeignKey(
        Session,
        on_delete=models.CASCADE,
        related_name="trainer_payments_set",
        verbose_name="Cycle de session",
    )
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name="Montant réglé (DA)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="confirmed",
        verbose_name="Statut",
    )
    payment_mode = models.CharField(
        max_length=20, choices=MODE_CHOICES, verbose_name="Mode de règlement"
    )
    reference = models.CharField(
        max_length=100,
        verbose_name="Référence de transaction",
        help_text="Auto-générée (ESP-{formateur}-{date}-{heure}) pour un règlement en espèce.",
    )
    proof_document = models.FileField(
        upload_to=trainer_payment_proof_path,
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["pdf", "jpg", "jpeg", "png", "webp"])
        ],
        verbose_name="Justificatif (scan)",
        help_text="Image ou PDF, optionnel.",
    )
    notes = models.CharField(
        max_length=255, blank=True, verbose_name="Note interne"
    )
    paid_at = models.DateTimeField(default=timezone.now, verbose_name="Réglé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Modifié le")
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Confirmé par",
    )

    class Meta:
        verbose_name = "Paiement formateur"
        verbose_name_plural = "Paiements formateurs"
        ordering = ["-paid_at"]

    def __str__(self):
        return f"{self.session.reference} — {self.amount} DA ({self.get_payment_mode_display()})"

    @staticmethod
    def generate_espece_reference(trainer):
        """ESP-{FORMATEUR}-{YYYYMMDD}-{HHMMSS}, the default transaction
        reference used when the settlement mode is espèce and no reference
        was supplied."""
        now = timezone.localtime()
        slug = slugify(trainer.last_name).upper() if trainer and trainer.last_name else "FORMATEUR"
        return f"ESP-{slug}-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}"

    @property
    def proof_is_pdf(self):
        return bool(self.proof_document) and self.proof_document.name.lower().endswith(".pdf")


class Participant(models.Model):
    GENDER_CHOICES = [
        ("M", "Homme"),
        ("F", "Femme"),
    ]

    session = models.ForeignKey(Session, on_delete=models.CASCADE)

    first_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Prénom",
        help_text="Nom complet en français/latin OPTIONNEL — au moins un nom complet "
        "(français OU arabe) est requis au total.",
    )
    last_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Nom",
        help_text="Nom complet en français/latin OPTIONNEL — au moins un nom complet "
        "(français OU arabe) est requis au total.",
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        verbose_name="Genre",
        help_text="Utilisé pour le décompte « منهم بنات » du محضر مداولات",
    )
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

    # Spec §11.6 (planned, now implemented) — QR code on every attestation.
    # Defaults to a verification link built from the certificate number;
    # an operator may override it with any manually-entered text/URL.
    qr_payload = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Contenu du QR code (optionnel)",
        help_text=(
            "Texte ou URL personnalisé encodé dans le QR code de l'attestation. "
            "Laisser vide pour utiliser le lien de vérification généré automatiquement."
        ),
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
        # Spec — first/last name (FR) and first/last name (AR) are each
        # individually optional, but at least one complete pair (FR or AR)
        # must be provided — never demand one language over the other.
        if not self.has_fr_name and not self.has_ar_name:
            raise ValidationError(
                "Veuillez renseigner au moins un nom complet : soit Prénom + Nom "
                "(français/latin), soit الاسم و اللقب (arabe)."
            )

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
    def has_fr_name(self):
        """Spec — a name pair counts as provided only when BOTH prénom and
        nom are filled (an isolated prénom or nom is not a usable name)."""
        return bool(self.first_name and self.last_name)

    @property
    def has_ar_name(self):
        return bool(self.first_name_ar and self.last_name_ar)

    @property
    def full_name(self):
        if self.has_fr_name:
            return f"{self.first_name} {self.last_name}"
        if self.has_ar_name:
            return self.full_name_ar
        return (f"{self.first_name} {self.last_name}").strip() or "—"

    @property
    def full_name_ar(self):
        if self.has_ar_name:
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

    # ---------------------------------------------------------------- QR code
    @property
    def qr_code_content(self):
        """
        Spec §11.6 — payload encoded on the attestation QR code.
        Uses the manual override if set, otherwise falls back to an
        auto-generated verification link keyed on the certificate number.
        """
        if self.qr_payload:
            return self.qr_payload
        from django.conf import settings

        base = getattr(settings, "SITE_URL", "").rstrip("/")
        # Use the participant's pk rather than the certificate number itself:
        # certificate numbers contain "/" and spaces (e.g. "2026/04 ت.ح.ط /001")
        # which don't survive as a clean URL path segment.
        path = f"/verify/{self.pk}/"
        return f"{base}{path}" if base else path

    @property
    def qr_code_data_uri(self):
        """Render `qr_code_content` as a base64 PNG data URI, generated
        on demand at document-generation time (not persisted)."""
        import base64
        from io import BytesIO

        try:
            import qrcode
        except ImportError:
            return ""

        img = qrcode.make(self.qr_code_content)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    def get_attendance_for_day(self, day_key):
        return self.attendance_per_day.get(day_key, True)

    def set_attendance_for_day(self, day_key, present):
        if not self.attendance_per_day:
            self.attendance_per_day = {}
        self.attendance_per_day[day_key] = present
        self.attended = any(self.attendance_per_day.values())
        self.save()
