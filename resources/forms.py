from django import forms
from django.db import models
from .models import Trainer, Room, Local, Equipment, AssetCategory, PedagogicalAsset


class TrainerForm(forms.ModelForm):
    class Meta:
        model = Trainer
        fields = [
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "specialty",
            "professional_address",
            "phone",
            "email",
            "employment_type",
            "qualifications",  # spec §10.5 — M2M added in round 1
            "default_cost_mode",
            "default_cost_percentage",
            "default_cost_amount",
            "cv",
            "contact_document",
            "is_active",
        ]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name": forms.TextInput(attrs={"class": "form-control"}),
            "first_name_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "last_name_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "specialty": forms.TextInput(attrs={"class": "form-control"}),
            "professional_address": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "employment_type": forms.Select(attrs={"class": "form-select"}),
            "qualifications": forms.CheckboxSelectMultiple(),
            "default_cost_mode": forms.Select(attrs={"class": "form-select"}),
            "default_cost_percentage": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0", "max": "100"}
            ),
            "default_cost_amount": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01", "min": "0"}
            ),
            "cv": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
            ),
            "contact_document": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png,.webp"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if (
            email
            and Trainer.objects.filter(email=email)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            raise forms.ValidationError("Cette adresse email est déjà utilisée.")
        return email


class RoomForm(forms.ModelForm):
    # Spec §new — equipment homed in this room, as a multi-select
    # (replaces relying on free-text `equipment_notes` for movable gear).
    # Backed by the reverse FK `Equipment.room`, applied manually in the view.
    equipment = forms.ModelMultipleChoiceField(
        queryset=Equipment.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label="Équipements disponibles dans la salle",
        help_text="Équipements homologués à cette salle. Un équipement déjà "
        "alloué activement ailleurs (session en cours) ne peut pas être "
        "réaffecté tant qu'il n'est pas libéré.",
    )

    class Meta:
        model = Room
        fields = ["name", "capacity", "equipment_notes", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control"}),
            "equipment_notes": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only equipment already homed here or currently unassigned to a
        # room/local can be picked — an item homed in another room must be
        # released from there first (edited from that room, or from the
        # equipment page).
        qs = Equipment.objects.filter(
            models.Q(room=self.instance) | models.Q(room__isnull=True, local__isnull=True)
        ) if self.instance and self.instance.pk else Equipment.objects.filter(
            room__isnull=True, local__isnull=True
        )
        self.fields["equipment"].queryset = qs.distinct()
        if self.instance and self.instance.pk:
            self.fields["equipment"].initial = Equipment.objects.filter(
                room=self.instance
            )


class LocalForm(forms.ModelForm):
    class Meta:
        model = Local
        fields = ["name", "local_type", "address", "description", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "local_type": forms.Select(attrs={"class": "form-select"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            "name",
            "category",
            "inventory_code",
            "quantity",
            "unit_price",
            "total_price",
            "status",
            "room",
            "local",
            "acquisition_date",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "inventory_code": forms.TextInput(attrs={"class": "form-control"}),
            "quantity": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01",
                       "placeholder": "Prix unitaire"}
            ),
            "total_price": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01",
                       "placeholder": "Prix total (quantité entière)"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "room": forms.Select(attrs={"class": "form-select"}),
            "local": forms.Select(attrs={"class": "form-select"}),
            "acquisition_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("room") and cleaned.get("local"):
            raise forms.ValidationError(
                "Un équipement ne peut être assigné qu'à une salle OU un local, pas les deux."
            )
        return cleaned


# ---------------------------------------------------------------------------
# Pedagogical assets — spec §new (consumable supplies, refilled/exhausted)
# ---------------------------------------------------------------------------


class PedagogicalAssetForm(forms.ModelForm):
    class Meta:
        model = PedagogicalAsset
        fields = [
            "name",
            "category",
            "reference",
            "unit",
            "quantity_in_stock",
            "minimum_stock",
            "unit_price",
            "total_price",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "reference": forms.TextInput(attrs={"class": "form-control"}),
            "unit": forms.Select(attrs={"class": "form-select"}),
            "quantity_in_stock": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "minimum_stock": forms.NumberInput(
                attrs={"class": "form-control", "min": 0}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01",
                       "placeholder": "Prix unitaire"}
            ),
            "total_price": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": "0.01",
                       "placeholder": "Valeur totale du stock"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = AssetCategory.objects.all()
        # Stock is set via restock()/deliver() movements, never edited
        # directly here — that would desync the audit trail. On create it
        # simply starts at 0 (optionally seeded via the separate
        # "initial stock" input handled in the view); on edit it's shown
        # read-only.
        self.fields["quantity_in_stock"].required = False
        if self.instance.pk:
            self.fields["quantity_in_stock"].disabled = True
            self.fields["quantity_in_stock"].help_text = (
                "Utilisez « Réapprovisionner » pour ajuster le stock."
            )


class AssetRestockForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        label="Quantité à ajouter",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )
    unit_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Prix unitaire (optionnel)",
        help_text="Laisser vide pour reprendre le prix unitaire actuel de l'actif.",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "step": "0.01"}
        ),
    )
    note = forms.CharField(
        required=False,
        label="Note",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ex : livraison fournisseur"}
        ),
    )


class AssetReturnForm(forms.Form):
    """Spec §new — return previously delivered stock (surplus, wrong
    item...). Increases stock back, logged as its own 'return' movement,
    optionally tied to the session it came back from."""

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantité retournée",
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )
    unit_price = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Prix unitaire (optionnel)",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "min": 0, "step": "0.01"}
        ),
    )
    note = forms.CharField(
        required=False,
        label="Motif du retour",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Ex : surplus non utilisé"}
        ),
    )
