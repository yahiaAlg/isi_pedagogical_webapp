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
        ("nominal_list", "Liste nominale"),
        ("evaluation_list", "Liste des notes d'évaluation"),
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
        return f"{base_name}.docx"

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
