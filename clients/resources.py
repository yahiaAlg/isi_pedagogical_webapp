"""django-import-export resources for the clients app."""

from import_export import resources

from .models import Client


class ClientResource(resources.ModelResource):
    """Complete client master-data import/export resource."""

    class Meta:
        model = Client
        fields = (
            "id",
            "name",
            "name_ar",
            "address",
            "city",
            "phone",
            "email",
            "contact_person",
            "nif",
            "nis",
            "rc",
            "is_active",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
