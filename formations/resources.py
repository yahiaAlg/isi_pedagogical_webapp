"""
formations/resources.py

django-import-export ModelResource for Participant.

NOTE: The canonical import implementation with full spec compliance
(capacity stop + 3-count reporting) lives in formations/utils.py ::
import_participants_from_file.  This resource is kept for admin-level
bulk export only.  The participant_import VIEW must use utils.py.
"""

from import_export import resources, fields
from import_export.widgets import DateWidget, ForeignKeyWidget
from .models import Branch, Category, Formation, Participant, Session, Specialty


class CategoryResource(resources.ModelResource):
    class Meta:
        model = Category
        fields = ("id", "name", "description", "color")
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class BranchResource(resources.ModelResource):
    class Meta:
        model = Branch
        fields = (
            "id",
            "abbreviation",
            "name",
            "name_ar",
            "curriculum_type",
            "curriculum_min_months",
            "curriculum_max_months",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class SpecialtyResource(resources.ModelResource):
    branch = fields.Field(
        attribute="branch",
        column_name="branch_abbreviation",
        widget=ForeignKeyWidget(Branch, "abbreviation"),
    )

    class Meta:
        model = Specialty
        fields = ("id", "branch", "code", "title", "title_ar")
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class FormationResource(resources.ModelResource):
    category = fields.Field(
        attribute="category",
        column_name="category_name",
        widget=ForeignKeyWidget(Category, "name"),
    )
    specialty = fields.Field(
        attribute="specialty",
        column_name="specialty_id",
        widget=ForeignKeyWidget(Specialty, "pk"),
    )

    class Meta:
        model = Formation
        fields = (
            "id",
            "title",
            "title_ar",
            "code",
            "category",
            "specialty",
            "attestation_type",
            "description",
            "duration_days",
            "duration_hours",
            "min_participants",
            "max_participants",
            "base_price",
            "evaluation_type",
            "passing_score",
            "max_score",
            "min_attendance_days",
            "produces_certificate",
            "accreditation_body",
            "legal_references",
            "is_active",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class SessionResource(resources.ModelResource):
    formation = fields.Field(
        attribute="formation",
        column_name="formation_code",
        widget=ForeignKeyWidget(Formation, "code"),
    )
    client = fields.Field(
        attribute="client",
        column_name="client_name",
        widget=ForeignKeyWidget("clients.Client", "name"),
    )
    trainer = fields.Field(
        attribute="trainer",
        column_name="trainer_id",
        widget=ForeignKeyWidget("resources.Trainer", "pk"),
    )
    room = fields.Field(
        attribute="room",
        column_name="room_id",
        widget=ForeignKeyWidget("resources.Room", "pk"),
    )
    parent_session = fields.Field(
        attribute="parent_session",
        column_name="parent_session_reference",
        widget=ForeignKeyWidget(Session, "reference"),
    )

    class Meta:
        model = Session
        fields = (
            "id",
            "reference",
            "formation",
            "client",
            "trainer",
            "date_start",
            "date_end",
            "location_type",
            "room",
            "external_location",
            "capacity",
            "status",
            "cancellation_reason",
            "specialty_code",
            "session_number",
            "is_primary",
            "parent_session",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


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
