"""
formations/resources.py

django-import-export ModelResource for Participant.

NOTE: The canonical import implementation with full spec compliance
(capacity stop + 3-count reporting) lives in formations/utils.py ::
import_participants_from_file.  This resource is kept for admin-level
bulk export only.  The participant_import VIEW must use utils.py.
"""

from import_export import resources, fields
from import_export.widgets import DateWidget
from .models import Participant


class ParticipantResource(resources.ModelResource):
    first_name = fields.Field(attribute="first_name", column_name="Prénom")
    last_name = fields.Field(attribute="last_name", column_name="Nom")
    first_name_ar = fields.Field(attribute="first_name_ar", column_name="Prénom AR")
    last_name_ar = fields.Field(attribute="last_name_ar", column_name="Nom AR")
    date_of_birth = fields.Field(
        attribute="date_of_birth",
        column_name="Date naissance",
        widget=DateWidget(format="%d/%m/%Y"),
    )
    place_of_birth = fields.Field(
        attribute="place_of_birth", column_name="Lieu naissance"
    )
    place_of_birth_ar = fields.Field(
        attribute="place_of_birth_ar", column_name="Lieu naissance AR"
    )
    job_title = fields.Field(attribute="job_title", column_name="Fonction")
    employer = fields.Field(attribute="employer", column_name="Employeur")
    phone = fields.Field(attribute="phone", column_name="Téléphone")
    email = fields.Field(attribute="email", column_name="Email")

    class Meta:
        model = Participant
        skip_unchanged = True
        report_skipped = True
        fields = (
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "date_of_birth",
            "place_of_birth",
            "place_of_birth_ar",
            "job_title",
            "employer",
            "phone",
            "email",
        )
        export_order = fields

    # ----------------------------------------------------------------- import
    def before_import_row(self, row, **kwargs):
        """Validate required fields; skip row gracefully instead of aborting."""
        if not row.get("Prénom") or not row.get("Nom"):
            raise ValueError("Prénom et Nom sont requis")

    def skip_row(self, instance, original):
        """
        Skip duplicates.
        Spec §13.3 capacity check: if capacity is reached, every remaining
        row must be rejected.  This is enforced by the view/utils layer
        (import_participants_from_file) which stops iteration at capacity.
        The django-import-export library does not support mid-import halting
        with a remaining-count report; use utils.import_participants_from_file
        in the participant_import view instead of this resource for imports.
        """
        if hasattr(self, "_session"):
            if self._session.available_spots <= 0:
                # Signal rejection — caller must count remaining rows
                return True
            return Participant.objects.filter(
                session=self._session,
                first_name=instance.first_name,
                last_name=instance.last_name,
            ).exists()
        return False

    def before_save_instance(self, instance, using_transactions, dry_run):
        if hasattr(self, "_session"):
            instance.session = self._session
