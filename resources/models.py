from django.db import models


class Room(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom de la salle")
    capacity = models.IntegerField(verbose_name="Capacité")
    # Spec §5.7 / §2.6a — renamed from `equipment`: free-text description of
    # fixed equipment permanently installed in the room (projector, whiteboard...)
    equipment_notes = models.TextField(blank=True, verbose_name="Équipements fixes")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.capacity} places)"


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
