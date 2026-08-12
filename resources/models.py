from django.conf import settings
from django.db import models


class Room(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom de la salle")
    capacity = models.IntegerField(verbose_name="Capacité")
    # Spec §5.7 / §2.6a — renamed from `equipment`: free-text description of
    # fixed equipment permanently installed in the room (projector, whiteboard...)
    # Kept only for legacy/fixed built-in fittings (electrical outlets, AC...).
    # Movable/trackable equipment now lives in the `Equipment` model below and
    # is linked here via `Equipment.room` (spec §new — room ↔ equipment M2M).
    equipment_notes = models.TextField(
        blank=True, verbose_name="Équipements fixes (notes libres)"
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.capacity} places)"

    # ------------------------------------------------------------- equipment
    @property
    def available_equipment(self):
        """Spec §new — equipment permanently homed in this room (relational,
        multi-select, replaces free-text description)."""
        return self.equipment_set.filter(status="available")


class Local(models.Model):
    """Spec §5.7 / §2.6b — broader institute premises (workshops, storage,
    garages, offices...), tracked for record-keeping and equipment
    assignment but not itself selectable when scheduling a session."""

    LOCAL_TYPE_CHOICES = [
        ("atelier", "Atelier"),
        ("entrepot", "Entrepôt"),
        ("garage", "Garage"),
        ("bureau", "Bureau"),
        ("autre", "Autre"),
    ]

    name = models.CharField(max_length=100, verbose_name="Nom")
    local_type = models.CharField(
        max_length=20,
        choices=LOCAL_TYPE_CHOICES,
        default="autre",
        verbose_name="Type",
    )
    address = models.TextField(
        blank=True, verbose_name="Adresse (si distincte du siège)"
    )
    description = models.TextField(blank=True, verbose_name="Description")
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Local"
        verbose_name_plural = "Locaux"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_local_type_display()})"


class Equipment(models.Model):
    """Spec §5.7 / §2.6c — inventory of training machines, tools, and
    protective gear owned by the institute."""

    CATEGORY_CHOICES = [
        ("machine", "Machine"),
        ("tool", "Outil"),
        ("safety_gear", "Équipement de sécurité"),
        ("other", "Autre"),
    ]
    STATUS_CHOICES = [
        ("available", "Disponible"),
        ("under_maintenance", "En maintenance"),
        ("out_of_service", "Hors service"),
    ]

    name = models.CharField(max_length=150, verbose_name="Nom")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default="other",
        verbose_name="Catégorie",
    )
    inventory_code = models.CharField(
        max_length=50, blank=True, verbose_name="Référence d'inventaire"
    )
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantité")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="available",
        verbose_name="État",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_set",
        verbose_name="Salle assignée",
    )
    local = models.ForeignKey(
        Local,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_set",
        verbose_name="Local assigné",
    )
    acquisition_date = models.DateField(
        null=True, blank=True, verbose_name="Date d'acquisition"
    )
    notes = models.TextField(blank=True, verbose_name="Notes")

    class Meta:
        verbose_name = "Équipement"
        verbose_name_plural = "Équipements"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name}{f' ({self.inventory_code})' if self.inventory_code else ''}"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.room_id and self.local_id:
            raise ValidationError(
                "Un équipement ne peut être assigné qu'à une salle OU un local, pas les deux."
            )

    # ------------------------------------------------------- allocation guardrails
    def active_allocation(self):
        """Spec §new — the active *session-based* checkout currently
        holding this equipment, if any. Guardrail: an equipment item can't
        be put to use in another session while it still has one of these
        (unreleased), until it's released there. A plain home-room
        assignment (no session) doesn't lock the item — it's exactly what
        makes it available/idle for other rooms to borrow."""
        return self.allocations.filter(
            released_at__isnull=True, session__isnull=False
        ).first()

    def is_locked_elsewhere(self, room=None, session=None):
        """True if this equipment has an active session checkout other
        than the given session (or no session given at all)."""
        alloc = self.active_allocation()
        if not alloc:
            return False
        if session is not None and alloc.session_id == session.pk:
            return False
        return True


class EquipmentAllocation(models.Model):
    """Spec §new — history/audit log of equipment allocation to rooms and
    sessions, with release tracking. Guardrail: an equipment item cannot be
    put to use in another room/session while it still has an active
    (unreleased) allocation elsewhere — see `Equipment.is_locked_elsewhere`.
    """

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="allocations",
        verbose_name="Équipement",
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name="equipment_allocations",
        verbose_name="Salle",
    )
    session = models.ForeignKey(
        "formations.Session",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="equipment_allocations",
        verbose_name="Session",
        help_text="Vide = affectation permanente à la salle (hors session).",
    )
    allocated_at = models.DateTimeField(auto_now_add=True, verbose_name="Alloué le")
    allocated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Alloué par",
    )
    released_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Libéré le"
    )
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Libéré par",
    )

    class Meta:
        verbose_name = "Allocation d'équipement"
        verbose_name_plural = "Historique d'allocation des équipements"
        ordering = ["-allocated_at"]

    def __str__(self):
        state = "actif" if self.is_active else "libéré"
        return f"{self.equipment.name} → {self.room.name} ({state})"

    @property
    def is_active(self):
        return self.released_at is None

    def release(self, by=None):
        from django.utils import timezone

        if self.released_at:
            return
        self.released_at = timezone.now()
        self.released_by = by
        self.save(update_fields=["released_at", "released_by"])


class Trainer(models.Model):
    EMPLOYMENT_CHOICES = [
        ("internal", "Interne"),
        ("external", "Externe"),
    ]

    # ------------------------------------------------------------------ names
    first_name = models.CharField(max_length=50, verbose_name="Prénom")
    last_name = models.CharField(max_length=50, verbose_name="Nom")
    first_name_ar = models.CharField(
        max_length=50, blank=True, verbose_name="Prénom (AR)"
    )
    last_name_ar = models.CharField(max_length=50, blank=True, verbose_name="Nom (AR)")

    # --------------------------------------------------------- professional info
    specialty = models.CharField(max_length=200, verbose_name="Spécialité")
    professional_address = models.TextField(
        blank=True, verbose_name="Adresse professionnelle"
    )
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_CHOICES,
        default="external",
        verbose_name="Type d'emploi",
    )

    # --------------------------------------------------------- qualifications
    # spec §10.5 — M2M to Formation; lazy string ref avoids circular import
    qualifications = models.ManyToManyField(
        "formations.Formation",
        blank=True,
        related_name="qualified_trainers",
        verbose_name="Formations qualifiées",
    )

    # ----------------------------------------------------------------- status
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Formateur"
        verbose_name_plural = "Formateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name_ar(self):
        if self.first_name_ar and self.last_name_ar:
            return f"{self.first_name_ar} {self.last_name_ar}"
        return ""

    @property
    def session_count(self):
        return self.session_set.count()

    def can_generate_mission_order(self):
        """Spec §11.1 — mission order blocked if professional_address absent."""
        return bool(self.professional_address.strip())
