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


class SelfReferenceWidget(ForeignKeyWidget):
    """ForeignKeyWidget for self-referencing FKs (Session.parent_session,
    Participant.source_participant).

    A row that references a parent/source appearing *later* in the same
    import file would otherwise blow up with "<Model> matching query does
    not exist", because that target hasn't been created yet — which in turn
    causes the entire row (and anything imported afterwards that depends on
    it, e.g. participants under a still-missing session) to fail.

    Here, clean() returns None instead of raising when the target isn't
    found yet, so the row still imports; the resource then relinks the
    real value in a second pass (see before_import/after_import below),
    once every row in the file is guaranteed to exist.
    """

    def clean(self, value, row=None, **kwargs):
        try:
            return super().clean(value, row=row, **kwargs)
        except self.model.DoesNotExist:
            return None


class SelfReferenceLinkingMixin:
    """Defers a self-referencing FK column to a second pass after import.

    Subclasses set `self_ref_field` (model field name) and
    `self_ref_column` (source column name in the dataset).
    """

    self_ref_field = None
    self_ref_column = None

    def before_import(self, dataset, **kwargs):
        self._self_ref_links = {}
        if (
            dataset is not None
            and "id" in dataset.headers
            and self.self_ref_column in dataset.headers
        ):
            id_idx = dataset.headers.index("id")
            ref_idx = dataset.headers.index(self.self_ref_column)
            for row in dataset:
                row_id = row[id_idx]
                ref_id = row[ref_idx]
                if row_id not in (None, "") and ref_id not in (None, ""):
                    self._self_ref_links[row_id] = ref_id
        super().before_import(dataset, **kwargs)

    def after_import(self, dataset, result, **kwargs):
        super().after_import(dataset, result, **kwargs)
        links = getattr(self, "_self_ref_links", {})
        if not links:
            return
        model = self._meta.model
        for row_id, ref_id in links.items():
            model.objects.filter(pk=row_id).update(**{self.self_ref_field: ref_id})


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


class SessionResource(SelfReferenceLinkingMixin, resources.ModelResource):
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
        widget=SelfReferenceWidget(Session, "pk"),
    )

    self_ref_field = "parent_session_id"
    self_ref_column = "parent_session_id"

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


class ParticipantResource(SelfReferenceLinkingMixin, resources.ModelResource):
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
        widget=SelfReferenceWidget(Participant, "pk"),
    )

    self_ref_field = "source_participant_id"
    self_ref_column = "source_participant_id"

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
