"""django-import-export resources for the formations app.

The resources use model primary keys for relationships so a full database
export can be re-imported without relying on translated display names.
ParticipantResource also retains the application's existing session/capacity
validation hook used by the dedicated participant import workflow.
"""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, Widget
import json

from clients.models import Client
from resources.models import Room, Trainer

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
        column_name="branch_id",
        widget=ForeignKeyWidget(Branch, "pk"),
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
        column_name="category_id",
        widget=ForeignKeyWidget(Category, "pk"),
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


class JSONWidget(Widget):
    """Stable JSON <-> text conversion for CSV/XLSX import/export."""

    def clean(self, value, row=None, **kwargs):
        if value in (None, "", {}):
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"JSON invalide: {value}") from exc

    def render(self, value, obj=None, **kwargs):
        if value in (None, ""):
            return ""
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class SessionResource(resources.ModelResource):
    formation = fields.Field(
        attribute="formation",
        column_name="formation_id",
        widget=ForeignKeyWidget(Formation, "pk"),
    )
    client = fields.Field(
        attribute="client",
        column_name="client_id",
        widget=ForeignKeyWidget(Client, "pk"),
    )
    trainer = fields.Field(
        attribute="trainer",
        column_name="trainer_id",
        widget=ForeignKeyWidget(Trainer, "pk"),
    )
    room = fields.Field(
        attribute="room",
        column_name="room_id",
        widget=ForeignKeyWidget(Room, "pk"),
    )
    committee_members = fields.Field(
        attribute="committee_members",
        column_name="committee_members",
        widget=JSONWidget(),
    )
    parent_session = fields.Field(
        attribute="parent_session",
        column_name="parent_session_id",
        widget=ForeignKeyWidget(Session, "pk"),
    )

    class Meta:
        model = Session
        fields = (
            "id",
            "formation",
            "client",
            "trainer",
            "reference",
            "date_start",
            "date_end",
            "location_type",
            "room",
            "external_location",
            "capacity",
            "status",
            "cancellation_reason",
            "committee_members",
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
    session = fields.Field(
        attribute="session",
        column_name="session_id",
        widget=ForeignKeyWidget(Session, "pk"),
    )
    employer_client = fields.Field(
        attribute="employer_client",
        column_name="employer_client_id",
        widget=ForeignKeyWidget(Client, "pk"),
    )
    attendance_per_day = fields.Field(
        attribute="attendance_per_day",
        column_name="attendance_per_day",
        widget=JSONWidget(),
    )
    source_participant = fields.Field(
        attribute="source_participant",
        column_name="source_participant_id",
        widget=ForeignKeyWidget(Participant, "pk"),
    )

    class Meta:
        model = Participant
        fields = (
            "id",
            "session",
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "date_of_birth",
            "place_of_birth",
            "place_of_birth_ar",
            "job_title",
            "employer",
            "employer_client",
            "phone",
            "email",
            "attended",
            "attendance_per_day",
            "score_theory",
            "score_practice",
            "exam_score_manual",
            "exam_score",
            "source_participant",
            "certificate_number",
            "certificate_issued",
            "qr_payload",
            "notes",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """Keep the existing required-name validation for participant imports."""
        if not row.get("first_name") or not row.get("last_name"):
            # Also accept the legacy French column names used by older sheets.
            if not row.get("Prénom") or not row.get("Nom"):
                raise ValueError("Prénom et Nom sont requis")

    def skip_row(self, instance, original, *args, **kwargs):
        """Respect the existing capacity/duplicate rules for session imports."""
        session = getattr(self, "_session", None)
        if session is None:
            return super().skip_row(instance, original, **kwargs)

        if session.available_spots <= 0 and getattr(instance, "pk", None) is None:
            return True

        return Participant.objects.filter(
            session=session,
            first_name=instance.first_name,
            last_name=instance.last_name,
        ).exclude(pk=getattr(instance, "pk", None)).exists()

    def before_save_instance(self, instance, *args, **kwargs):
        session = getattr(self, "_session", None)
        if session is not None:
            instance.session = session
