"""django-import-export resource for generated documents.

Generated documents are technical artifacts. Their ``file`` value is exported
as the stored media-relative path; importing that path does not upload bytes,
so the matching file must already exist in the configured media storage.
"""

from django.contrib.auth.models import User
from import_export import fields, resources
from import_export.widgets import CharWidget, ForeignKeyWidget

from formations.models import Participant, Session
from .models import GeneratedDocument


class GeneratedDocumentResource(resources.ModelResource):
    file = fields.Field(
        attribute="file",
        column_name="file",
        widget=CharWidget(),
    )
    session = fields.Field(
        attribute="session",
        column_name="session_reference",
        widget=ForeignKeyWidget(Session, "reference"),
    )
    participant = fields.Field(
        attribute="participant",
        column_name="participant_id",
        widget=ForeignKeyWidget(Participant, "pk"),
    )
    generated_by = fields.Field(
        attribute="generated_by",
        column_name="generated_by_username",
        widget=ForeignKeyWidget(User, "username"),
    )

    class Meta:
        model = GeneratedDocument
        fields = (
            "id",
            "session",
            "participant",
            "doc_type",
            "file",
            "generated_at",
            "generated_by",
            "is_latest",
            "day_number",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
