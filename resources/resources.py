"""django-import-export resources for rooms, premises, equipment and trainers."""

from import_export import fields, resources
from import_export.widgets import ForeignKeyWidget, ManyToManyWidget

from formations.models import Formation
from .models import Equipment, Local, Room, Trainer, PedagogicalAsset, AssetCategory


class RoomResource(resources.ModelResource):
    class Meta:
        model = Room
        fields = ("id", "name", "capacity", "equipment_notes", "is_active")
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class LocalResource(resources.ModelResource):
    class Meta:
        model = Local
        fields = (
            "id",
            "name",
            "local_type",
            "address",
            "description",
            "is_active",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class EquipmentResource(resources.ModelResource):
    room = fields.Field(
        attribute="room",
        column_name="room_id",
        widget=ForeignKeyWidget(Room, "pk"),
    )
    local = fields.Field(
        attribute="local",
        column_name="local_id",
        widget=ForeignKeyWidget(Local, "pk"),
    )

    class Meta:
        model = Equipment
        fields = (
            "id",
            "name",
            "category",
            "inventory_code",
            "quantity",
            "status",
            "room",
            "local",
            "acquisition_date",
            "notes",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class PedagogicalAssetResource(resources.ModelResource):
    category = fields.Field(
        attribute="category",
        column_name="category_id",
        widget=ForeignKeyWidget(AssetCategory, "pk"),
    )

    class Meta:
        model = PedagogicalAsset
        fields = (
            "id",
            "name",
            "category",
            "reference",
            "unit",
            "quantity_in_stock",
            "minimum_stock",
            "is_active",
            "notes",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True


class TrainerResource(resources.ModelResource):
    qualifications = fields.Field(
        attribute="qualifications",
        column_name="qualification_ids",
        widget=ManyToManyWidget(Formation, field="pk", separator=";"),
    )

    class Meta:
        model = Trainer
        fields = (
            "id",
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "specialty",
            "professional_address",
            "phone",
            "email",
            "employment_type",
            "qualifications",
            "is_active",
            "created_at",
            "updated_at",
        )
        export_order = fields
        import_id_fields = ("id",)
        skip_unchanged = True
        report_skipped = True
