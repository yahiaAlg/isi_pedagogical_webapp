"""django-import-export resources for the accounts app."""

from django.contrib.auth.models import User
from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget

from .models import UserProfile


class UserProfileResource(resources.ModelResource):
    """Import/export user profiles using the stable Django username."""

    id = fields.Field(attribute="id", column_name="id")
    username = fields.Field(
        attribute="user",
        column_name="username",
        widget=ForeignKeyWidget(User, "username"),
    )
    role = fields.Field(attribute="role", column_name="role")
    phone = fields.Field(attribute="phone", column_name="phone")

    class Meta:
        model = UserProfile
        fields = ("id", "username", "role", "phone")
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
