from django.db import models


class Room(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom de la salle")
    capacity = models.IntegerField(verbose_name="Capacité")
    equipment = models.TextField(blank=True, verbose_name="Équipements")
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.capacity} places)"


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
