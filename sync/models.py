from django.db import models


class SyncState(models.Model):
    """Tiny key/value store (e.g. the feed cursor, last pull time)."""

    key = models.CharField(max_length=50, unique=True)
    value = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get(cls, key, default=""):
        row = cls.objects.filter(key=key).first()
        return row.value if row else default

    @classmethod
    def put(cls, key, value):
        cls.objects.update_or_create(key=key, defaults={"value": str(value)})


class SyncJob(models.Model):
    """Outbox: something to push to the website (currently: a formation)."""

    KIND_FORMATION = "formation"
    KIND_FORMATION_DELETED = "formation_deleted"
    PENDING, DONE, FAILED = "pending", "done", "failed"
    STATUS_CHOICES = [(PENDING, "En attente"), (DONE, "Envoyé"), (FAILED, "Échec")]

    kind = models.CharField(max_length=20, default=KIND_FORMATION)
    object_id = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Envoi vers le site"
        verbose_name_plural = "Envois vers le site"

    def __str__(self):
        return f"{self.kind}#{self.object_id} [{self.status}]"


class RemoteClient(models.Model):
    """A website client and the ISI Client it maps to. All website *individuals*
    map to the single shared 'Particuliers' ISI client."""

    ext_id = models.PositiveIntegerField(unique=True)
    client = models.ForeignKey(
        "clients.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="remote_links"
    )
    is_individual = models.BooleanField(default=False)
    created_client = models.BooleanField(
        default=False, help_text="Le client ISI a été créé par la synchronisation."
    )
    last_snapshot = models.JSONField(default=dict, blank=True)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Client du site"
        verbose_name_plural = "Clients du site"

    def __str__(self):
        return f"site#{self.ext_id} -> {self.client_id}"


class RosterEntry(models.Model):
    """One person the website says will attend a formation for a client (a
    company roster line, or an individual's enrollment). Kept at CLIENT level
    because ISI participants only exist inside a Session: when a matching
    planned session exists (or is created later) the entry is seeded into it."""

    IDENTITY_FIELDS = (
        "first_name", "last_name", "first_name_ar", "last_name_ar", "gender",
        "date_of_birth", "place_of_birth", "place_of_birth_ar",
        "job_title", "employer", "phone", "email",
    )

    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="roster_entries")
    remote_client_ext_id = models.PositiveIntegerField(db_index=True)
    ext_id = models.CharField(max_length=24, unique=True)
    formation = models.ForeignKey(
        "formations.Formation", null=True, blank=True, on_delete=models.SET_NULL, related_name="roster_entries"
    )
    offering_code = models.CharField(max_length=30, blank=True)
    offering_title = models.CharField(max_length=200, blank=True)
    offering_ref = models.JSONField(default=dict, blank=True)
    enrollment_status = models.CharField(max_length=20, blank=True)

    first_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50, blank=True)
    first_name_ar = models.CharField(max_length=50, blank=True)
    last_name_ar = models.CharField(max_length=50, blank=True)
    gender = models.CharField(max_length=1, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    place_of_birth = models.CharField(max_length=100, blank=True)
    place_of_birth_ar = models.CharField(max_length=100, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    participant = models.ForeignKey(
        "formations.Participant", null=True, blank=True, on_delete=models.SET_NULL, related_name="roster_entries"
    )
    removed_on_site = models.BooleanField(
        default=False,
        help_text="Retiré de la liste sur le site alors que le participant est déjà dans une session "
        "(notes, attestation ou session commencée) : conservé ici, à vérifier par le personnel.",
    )
    last_values = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["offering_title", "last_name", "first_name"]
        verbose_name = "Participant du site"
        verbose_name_plural = "Participants du site"

    def __str__(self):
        return f"{self.display_name} — {self.offering_title}"

    @property
    def display_name(self):
        fr = f"{self.first_name} {self.last_name}".strip()
        ar = f"{self.first_name_ar} {self.last_name_ar}".strip()
        return fr or ar or "(sans nom)"

    @property
    def has_complete_name(self):
        return bool((self.first_name and self.last_name) or (self.first_name_ar and self.last_name_ar))

    @property
    def state(self):
        from .seeding import seedable_statuses

        if self.removed_on_site:
            return "removed"
        if self.participant_id:
            return "seeded"
        if self.enrollment_status not in seedable_statuses():
            return "awaiting_validation"
        return "pending"
