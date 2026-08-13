from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import InstituteInfo, PVDefaultSignatory, SequenceCounter


class InstituteInfoForm(forms.ModelForm):
    class Meta:
        model = InstituteInfo
        fields = [
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
        ]
        widgets = {
            "name_fr": forms.TextInput(attrs={"class": "form-control"}),
            "name_ar": forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
            "logo": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "nif": forms.TextInput(attrs={"class": "form-control"}),
            "nis": forms.TextInput(attrs={"class": "form-control"}),
            "rc": forms.TextInput(attrs={"class": "form-control"}),
            "article_imposition": forms.TextInput(attrs={"class": "form-control"}),
            "rib": forms.TextInput(attrs={"class": "form-control"}),
            "accreditation_number": forms.TextInput(attrs={"class": "form-control"}),
            "accreditation_date": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "if_number": forms.TextInput(attrs={"class": "form-control"}),
            "footer_fr": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "footer_ar": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "dir": "rtl"}
            ),
            "pv_notification_recipients": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "directeur@isi.dz\nqualite@isi.dz",
                }
            ),
        }

    def clean_pv_notification_recipients(self):
        raw = self.cleaned_data.get("pv_notification_recipients", "")
        entries = [e.strip() for e in raw.replace(",", "\n").splitlines() if e.strip()]
        invalid = []
        for email in entries:
            try:
                validate_email(email)
            except ValidationError:
                invalid.append(email)
        if invalid:
            raise forms.ValidationError(
                f"Adresse(s) email invalide(s) : {', '.join(invalid)}"
            )
        return raw


class PVDefaultSignatoryForm(forms.ModelForm):
    class Meta:
        model = PVDefaultSignatory
        fields = ["full_name", "role", "order", "is_active"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl", "placeholder": "لكراش حسين"}
            ),
            "role": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl", "placeholder": "مدير المؤسسة"}
            ),
            "order": forms.NumberInput(attrs={"class": "form-control"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class SequenceCounterForm(forms.ModelForm):
    """
    Manual override for a numbering counter (PV or certificate), for edge
    cases: resuming a paper-based series, correcting an operator mistake,
    aligning the app with numbers already handed out outside the system,
    etc. Only `last_value` is editable — `kind` and `period_key` define
    which counter this is and are never changed here.

    Nothing else needs to be touched: SequenceCounter.next_value() always
    reads the stored last_value and increments it by one, so as soon as
    this is saved, the very next PV/certificate printed picks up right
    after the new value — both the pv/certificate print flow and this
    form share the exact same counter row.
    """

    class Meta:
        model = SequenceCounter
        fields = ["last_value"]
        widgets = {
            "last_value": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }
        labels = {
            "last_value": "Dernier numéro attribué",
        }

    def clean_last_value(self):
        value = self.cleaned_data["last_value"]
        if value < 0:
            raise forms.ValidationError("La valeur doit être positive ou nulle.")
        return value
