from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from .models import InstituteInfo, CommitteeMember


class CommitteeMemberForm(forms.ModelForm):
    """Add/edit a default PV committee member (e.g. a director) from the
    Settings page."""

    class Meta:
        model = CommitteeMember
        fields = ["full_name", "role", "order", "is_active"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "dir": "rtl",
                    "placeholder": "لكراش حسين",
                }
            ),
            "role": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "dir": "rtl",
                    "placeholder": "مدير المؤسسة",
                }
            ),
            "order": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


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
