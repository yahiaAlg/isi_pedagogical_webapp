from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def grant_duration():
    """How long an approved edit request stays usable (hours, setting-driven)."""
    return timedelta(hours=getattr(settings, "APPROVAL_GRANT_HOURS", 24))


class ApprovalRequest(models.Model):
    """A pedagogical agent's request to the administrators about a catalogue
    formation.

    * ``formation_create`` — agents cannot create formations. The admin does it
      in their place (``fulfilled`` once the formation exists) or refuses.
    * ``formation_edit``   — the admin approves; the agent then gets access to
      the edit form until the modification is saved (``fulfilled``) or the
      grant expires.
    """

    KIND_CREATE = "formation_create"
    KIND_EDIT = "formation_edit"
    KIND_CHOICES = [
        (KIND_CREATE, "Création de formation"),
        (KIND_EDIT, "Modification de formation"),
    ]

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_FULFILLED = "fulfilled"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_APPROVED, "Approuvée"),
        (STATUS_REJECTED, "Refusée"),
        (STATUS_FULFILLED, "Traitée"),
        (STATUS_CANCELLED, "Annulée"),
    ]

    requester = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="approval_requests"
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_PENDING, db_index=True
    )

    # Edit requests point at the formation; create requests carry a proposal.
    formation = models.ForeignKey(
        "formations.Formation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approval_requests",
    )
    formation_label = models.CharField(
        max_length=255, blank=True, help_text="Snapshot kept if the formation is deleted."
    )
    created_formation = models.ForeignKey(
        "formations.Formation",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    proposed_title = models.CharField(max_length=200, blank=True)
    proposed_code = models.CharField(max_length=20, blank=True)

    message = models.TextField(blank=True, verbose_name="Motif / détails")
    review_note = models.TextField(blank=True, verbose_name="Note de l'administrateur")
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_approval_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Demande d'approbation"
        verbose_name_plural = "Demandes d'approbation"
        indexes = [models.Index(fields=["requester", "status"])]

    def __str__(self):
        return f"{self.get_kind_display()} — {self.subject} ({self.get_status_display()})"

    # ── Display helpers ─────────────────────────────────────────────────────
    @property
    def subject(self):
        if self.kind == self.KIND_CREATE:
            return self.proposed_title or "(sans titre)"
        if self.formation_id:
            return str(self.formation)
        return self.formation_label or "(formation supprimée)"

    @property
    def expires_at(self):
        if self.kind == self.KIND_EDIT and self.status == self.STATUS_APPROVED:
            return (self.reviewed_at or self.created_at) + grant_duration()
        return None

    @property
    def is_expired(self):
        exp = self.expires_at
        return bool(exp and exp <= timezone.now())

    @property
    def is_usable(self):
        """An approved edit request the agent can still use to open the form."""
        return (
            self.kind == self.KIND_EDIT
            and self.status == self.STATUS_APPROVED
            and not self.is_expired
        )

    @property
    def display_status(self):
        if self.status == self.STATUS_APPROVED and self.is_expired:
            return "Expirée"
        return self.get_status_display()

    @property
    def badge_class(self):
        if self.status == self.STATUS_APPROVED and self.is_expired:
            return "gray"
        return {
            self.STATUS_PENDING: "amber",
            self.STATUS_APPROVED: "blue",
            self.STATUS_FULFILLED: "green",
            self.STATUS_REJECTED: "red",
            self.STATUS_CANCELLED: "gray",
        }[self.status]

    # ── Lookups used by the formation views / templates ─────────────────────
    @classmethod
    def usable_edit_grant(cls, user, formation):
        """Newest still-valid approved edit request of ``user`` for ``formation``."""
        qs = cls.objects.filter(
            requester=user,
            kind=cls.KIND_EDIT,
            formation=formation,
            status=cls.STATUS_APPROVED,
        ).order_by("-reviewed_at")
        return next((r for r in qs if r.is_usable), None)

    @classmethod
    def open_edit_request(cls, user, formation):
        """Pending edit request (not yet answered) of ``user`` for ``formation``."""
        return cls.objects.filter(
            requester=user,
            kind=cls.KIND_EDIT,
            formation=formation,
            status=cls.STATUS_PENDING,
        ).first()


class Notification(models.Model):
    """One bell entry for one user (the e-mail twin is sent by services.py)."""

    KIND_NEW_REQUEST = "new_request"
    KIND_APPROVED = "approved"
    KIND_REJECTED = "rejected"
    KIND_FULFILLED = "fulfilled"
    KIND_CANCELLED = "cancelled"
    KIND_EDIT_DONE = "edit_done"
    KIND_CHOICES = [
        (KIND_NEW_REQUEST, "Nouvelle demande"),
        (KIND_APPROVED, "Demande approuvée"),
        (KIND_REJECTED, "Demande refusée"),
        (KIND_FULFILLED, "Demande traitée"),
        (KIND_CANCELLED, "Demande annulée"),
        (KIND_EDIT_DONE, "Modification effectuée"),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    request = models.ForeignKey(
        ApprovalRequest,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=12, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    body = models.CharField(max_length=500, blank=True)
    url = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["recipient", "is_read", "-created_at"])]

    def __str__(self):
        return f"{self.recipient} — {self.title}"

    @property
    def icon(self):
        return {
            self.KIND_NEW_REQUEST: "bi-inbox-fill",
            self.KIND_APPROVED: "bi-check-circle-fill",
            self.KIND_REJECTED: "bi-x-circle-fill",
            self.KIND_FULFILLED: "bi-patch-check-fill",
            self.KIND_CANCELLED: "bi-slash-circle-fill",
            self.KIND_EDIT_DONE: "bi-pencil-square",
        }[self.kind]

    @property
    def tone(self):
        return {
            self.KIND_NEW_REQUEST: "amber",
            self.KIND_APPROVED: "green",
            self.KIND_REJECTED: "red",
            self.KIND_FULFILLED: "green",
            self.KIND_CANCELLED: "gray",
            self.KIND_EDIT_DONE: "blue",
        }[self.kind]
