"""django-import-export resources for core configuration models."""

from import_export import resources

from .models import CommitteeMember, InstituteInfo


class CommitteeMemberResource(resources.ModelResource):
    """Import/export the default PV committee configuration."""

    class Meta:
        model = CommitteeMember
        fields = ("id", "full_name", "role", "order", "is_active")
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class InstituteInfoResource(resources.ModelResource):
    """Import/export institute settings.

    The logo column contains the stored media path.  Importing a logo path
    therefore expects the corresponding file to already exist in MEDIA_ROOT.
    """

    class Meta:
        model = InstituteInfo
        fields = (
            "id",
            "name_fr",
            "name_ar",
            "logo",
            "address",
            "phone",
            "email",
            "nif",
            "nis",
            "rc",
            "article_imposition",
            "rib",
            "accreditation_number",
            "accreditation_date",
            "if_number",
            "footer_fr",
            "footer_ar",
            "pv_notification_recipients",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
