import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import FileExtensionValidator
from django.db import models


def autocalc_price_pair(unit_price, total_price, qty):
    """Spec §new — bidirectional price autocalc shared by Equipment and
    PedagogicalAsset (and their allocation/movement snapshots): given a
    quantity, if only one of unit/total price is provided the other is
    inferred; if both are provided, unit_price wins and total is
    recomputed from it (keeps the pair consistent). Returns (unit, total).
    """
    qty = qty or 0
    if unit_price in (None, "") and total_price in (None, ""):
        return None, None
    if unit_price not in (None, "") and total_price in (None, ""):
        unit_price = Decimal(unit_price)
        total_price = (unit_price * qty).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return unit_price, total_price
    if total_price not in (None, "") and unit_price in (None, ""):
        total_price = Decimal(total_price)
        unit_price = (
            (total_price / qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if qty
            else Decimal("0.00")
        )
        return unit_price, total_price
    # Both given — trust unit_price as the source of truth, recompute total.
    unit_price = Decimal(unit_price)
    total_price = (unit_price * qty).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return unit_price, total_price


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
    # Spec §new — bidirectional price autocalc: give either the unit price
    # or the total price for the whole `quantity` owned, the other is
    # inferred automatically on save (see `autocalc_price_pair`).
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix unitaire",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix total (pour la quantité)",
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

    def save(self, *args, **kwargs):
        unit, total = autocalc_price_pair(
            self.unit_price, self.total_price, self.quantity
        )
        self.unit_price, self.total_price = unit, total
        super().save(*args, **kwargs)

    # ------------------------------------------------------- allocation guardrails
    def active_allocations(self):
        """Spec §new — all active (unreleased / not fully-returned)
        *session-based* checkouts currently holding units of this
        equipment. A plain home-room assignment (no session) doesn't
        lock the item — it's exactly what makes it available/idle for
        other rooms to borrow."""
        return self.allocations.filter(
            released_at__isnull=True, session__isnull=False
        )

    def active_allocation(self):
        """Back-compat single-result accessor (first active allocation)."""
        return self.active_allocations().first()

    @property
    def quantity_reserved(self):
        """Spec §new — units currently held by active session checkouts
        (accounting for partial returns)."""
        return sum(
            max(alloc.quantity - alloc.returned_quantity, 0)
            for alloc in self.active_allocations()
        )

    @property
    def quantity_available(self):
        """Spec §new — units still free to reserve for a new session."""
        return max(self.quantity - self.quantity_reserved, 0)

    def is_locked_elsewhere(self, room=None, session=None, quantity=1):
        """True if reserving `quantity` unit(s) of this equipment for
        `session` is blocked because not enough units are free — other
        active session checkouts (excluding `session` itself) already
        hold the rest."""
        reserved_elsewhere = 0
        for alloc in self.active_allocations():
            if session is not None and alloc.session_id == session.pk:
                continue
            reserved_elsewhere += max(alloc.quantity - alloc.returned_quantity, 0)
        return (self.quantity - reserved_elsewhere) < (quantity or 1)


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
    # Spec §new — how many units of `equipment` this allocation reserves.
    # Together with the unit-price snapshot below, this makes the
    # reservation/return cost auditable even if the equipment's own price
    # changes later.
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantité réservée")
    returned_quantity = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantité retournée",
        help_text="Retours partiels (ex : surplus rendu avant la fin de session).",
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix unitaire (au moment de l'allocation)",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix total réservé",
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

    def save(self, *args, **kwargs):
        # Snapshot the equipment's current unit price at reservation time
        # (only while still active/unpriced) so later price changes on
        # the equipment don't rewrite history.
        if self.unit_price is None and self.equipment_id:
            self.unit_price = self.equipment.unit_price
        unit, total = autocalc_price_pair(self.unit_price, None, self.quantity)
        if unit is not None:
            self.unit_price, self.total_price = unit, total
        super().save(*args, **kwargs)

    def return_partial(self, quantity, by=None):
        """Spec §new — return part of the reserved quantity (e.g. a
        surplus no longer needed) without releasing the whole allocation.
        Auto-releases once everything reserved has been returned."""
        if quantity is None or quantity <= 0:
            raise ValueError("La quantité retournée doit être positive.")
        if self.returned_quantity + quantity > self.quantity:
            raise ValueError(
                "La quantité retournée dépasse la quantité réservée."
            )
        self.returned_quantity += quantity
        if self.returned_quantity >= self.quantity:
            self.release(by=by)
        else:
            self.save(update_fields=["returned_quantity"])

    def release(self, by=None):
        from django.utils import timezone

        if self.released_at:
            return
        self.returned_quantity = self.quantity
        self.released_at = timezone.now()
        self.released_by = by
        self.save(
            update_fields=["returned_quantity", "released_at", "released_by"]
        )

    @property
    def outstanding_quantity(self):
        """Units still held (not yet returned)."""
        return max(self.quantity - self.returned_quantity, 0)


class AssetCategory(models.Model):
    """Spec §new — categorisation for pedagogical assets (IT, Bureautique,
    Autre...). Kept as data (not a hardcoded choices list) so the
    classification can be extended without a migration; seeded once via
    the dedicated `_seed_asset_categories` step in `seed_db`.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name="Nom")
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Catégorie d'actif pédagogique"
        verbose_name_plural = "Catégories d'actifs pédagogiques"
        ordering = ["name"]

    def __str__(self):
        return self.name


class PedagogicalAsset(models.Model):
    """Spec §new — consumable/refillable pedagogical supplies (IT, office,
    and other categories) that are delivered to sessions/trainings and
    consumed there, as opposed to `Equipment` which is reusable and
    checked in/out. Stock is refilled (`restock`) and depleted
    (`deliver`) through `AssetMovement`, which keeps a full audit trail.
    """

    UNIT_CHOICES = [
        ("piece", "Pièce"),
        ("pack", "Lot / Pack"),
        ("box", "Boîte"),
        ("ream", "Rame"),
        ("liter", "Litre"),
        ("kg", "Kilogramme"),
        ("other", "Autre"),
    ]

    name = models.CharField(max_length=150, verbose_name="Nom")
    category = models.ForeignKey(
        AssetCategory,
        on_delete=models.PROTECT,
        related_name="assets",
        verbose_name="Catégorie",
    )
    reference = models.CharField(
        max_length=50, blank=True, verbose_name="Référence"
    )
    unit = models.CharField(
        max_length=20, choices=UNIT_CHOICES, default="piece", verbose_name="Unité"
    )
    quantity_in_stock = models.PositiveIntegerField(
        default=0, verbose_name="Quantité en stock"
    )
    minimum_stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Seuil d'alerte",
        help_text="En dessous de ce seuil, l'actif est signalé comme stock bas.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")
    # Spec §new — bidirectional price autocalc: give either the unit price
    # or the total value of the current stock, the other is inferred
    # automatically on save (see `autocalc_price_pair`).
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix unitaire",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Valeur totale du stock",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Actif pédagogique"
        verbose_name_plural = "Actifs pédagogiques"
        ordering = ["category__name", "name"]

    def __str__(self):
        return f"{self.name} ({self.quantity_in_stock} {self.get_unit_display()})"

    def save(self, *args, **kwargs):
        unit, total = autocalc_price_pair(
            self.unit_price, self.total_price, self.quantity_in_stock
        )
        self.unit_price, self.total_price = unit, total
        super().save(*args, **kwargs)

    # --------------------------------------------------------------- stock
    @property
    def is_exhausted(self):
        return self.quantity_in_stock <= 0

    @property
    def is_low_stock(self):
        return 0 < self.quantity_in_stock <= self.minimum_stock

    def _movement_price(self, quantity, unit_price=None):
        """Spec §new — resolve the (unit, total) price to snapshot on a
        movement: an explicit `unit_price` wins, otherwise the asset's
        current unit price is used."""
        price = unit_price if unit_price is not None else self.unit_price
        return autocalc_price_pair(price, None, quantity)

    def restock(self, quantity, by=None, note="", unit_price=None):
        """Refill stock (spec §new). Returns the created `AssetMovement`.
        `unit_price` optionally overrides the asset's current price for
        this specific delivery/movement (e.g. a supplier price change);
        total is inferred from quantity."""
        if quantity is None or quantity <= 0:
            raise ValueError("La quantité doit être positive.")
        u_price, t_price = self._movement_price(quantity, unit_price)
        if u_price is not None:
            self.unit_price = u_price
        self.quantity_in_stock += quantity
        self.save(update_fields=["quantity_in_stock", "unit_price", "total_price", "updated_at"])
        return self.movements.create(
            movement_type="restock",
            quantity=quantity,
            unit_price=u_price,
            total_price=t_price,
            performed_by=by,
            note=note,
        )

    def deliver(self, quantity, session=None, by=None, note="", unit_price=None):
        """Deliver/consume stock, optionally against a session (spec §new).
        Hard guardrail (unlike the equipment soft warnings): a delivery
        can never exceed what's physically in stock.
        """
        if quantity is None or quantity <= 0:
            raise ValueError("La quantité doit être positive.")
        if quantity > self.quantity_in_stock:
            raise ValueError(
                f"Stock insuffisant : {self.quantity_in_stock} "
                f"{self.get_unit_display()} disponible(s)."
            )
        u_price, t_price = self._movement_price(quantity, unit_price)
        if u_price is not None:
            self.unit_price = u_price
        self.quantity_in_stock -= quantity
        self.save(update_fields=["quantity_in_stock", "unit_price", "total_price", "updated_at"])
        return self.movements.create(
            movement_type="delivery",
            quantity=quantity,
            session=session,
            unit_price=u_price,
            total_price=t_price,
            performed_by=by,
            note=note,
        )

    def return_stock(self, quantity, session=None, by=None, note="", unit_price=None):
        """Spec §new — return previously delivered stock (surplus not
        used, wrong item, etc.). Increases stock back like `restock` but
        is logged as its own movement type and can be tied to the
        session it came back from."""
        if quantity is None or quantity <= 0:
            raise ValueError("La quantité doit être positive.")
        u_price, t_price = self._movement_price(quantity, unit_price)
        if u_price is not None:
            self.unit_price = u_price
        self.quantity_in_stock += quantity
        self.save(update_fields=["quantity_in_stock", "unit_price", "total_price", "updated_at"])
        return self.movements.create(
            movement_type="return",
            quantity=quantity,
            session=session,
            unit_price=u_price,
            total_price=t_price,
            performed_by=by,
            note=note,
        )


class AssetMovement(models.Model):
    """Spec §new — audit log of stock movements for a `PedagogicalAsset`:
    `restock` (refill, no session) or `delivery` (consumed, usually tied
    to the session it was delivered to). Mirrors `EquipmentAllocation`'s
    role for the (reusable) `Equipment` model, but for consumables.
    """

    MOVEMENT_TYPE_CHOICES = [
        ("restock", "Réapprovisionnement"),
        ("delivery", "Livraison / Consommation"),
        ("return", "Retour (surplus / autre)"),
    ]

    asset = models.ForeignKey(
        PedagogicalAsset,
        on_delete=models.CASCADE,
        related_name="movements",
        verbose_name="Actif",
    )
    session = models.ForeignKey(
        "formations.Session",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_movements",
        verbose_name="Session",
        help_text="Renseigné uniquement pour une livraison consommée dans une session.",
    )
    movement_type = models.CharField(
        max_length=20, choices=MOVEMENT_TYPE_CHOICES, verbose_name="Type"
    )
    quantity = models.PositiveIntegerField(verbose_name="Quantité")
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix unitaire (au moment du mouvement)",
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Prix total du mouvement",
    )
    performed_at = models.DateTimeField(auto_now_add=True, verbose_name="Effectué le")
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Effectué par",
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="Note")

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Historique des mouvements de stock"
        ordering = ["-performed_at"]

    def __str__(self):
        sign = "-" if self.movement_type == "delivery" else "+"
        return f"{self.asset.name} {sign}{self.quantity}"


def trainer_cv_path(instance, filename):
    """MEDIA_ROOT/trainers/cv/{uuid}_{filename} — uuid avoids relying on a
    pk that doesn't exist yet on first save, and prevents collisions."""
    return f"trainers/cv/{uuid.uuid4().hex}_{filename}"


def trainer_contact_document_path(instance, filename):
    """MEDIA_ROOT/trainers/contact/{uuid}_{filename}."""
    return f"trainers/contact/{uuid.uuid4().hex}_{filename}"


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

    # ----------------------------------------------------------- attachments
    # Viewable later from the trainer detail page — image or PDF only.
    _doc_validator = FileExtensionValidator(
        allowed_extensions=["pdf", "jpg", "jpeg", "png", "webp"]
    )
    cv = models.FileField(
        upload_to=trainer_cv_path,
        blank=True,
        null=True,
        validators=[_doc_validator],
        verbose_name="CV",
        help_text="Image ou PDF.",
    )
    contact_document = models.FileField(
        upload_to=trainer_contact_document_path,
        blank=True,
        null=True,
        validators=[_doc_validator],
        verbose_name="Document de contact",
        help_text="Image ou PDF.",
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

    @staticmethod
    def _is_pdf(field_file):
        return bool(field_file) and field_file.name.lower().endswith(".pdf")

    @property
    def cv_is_pdf(self):
        return self._is_pdf(self.cv)

    @property
    def contact_document_is_pdf(self):
        return self._is_pdf(self.contact_document)
