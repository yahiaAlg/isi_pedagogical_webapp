from django import forms
from .models import InstituteInfo


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
        }
