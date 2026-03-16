from django import forms
from .models import Trainer, Room


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
    class Meta:
        model = Room
        fields = ["name", "capacity", "equipment", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control"}),
            "equipment": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
