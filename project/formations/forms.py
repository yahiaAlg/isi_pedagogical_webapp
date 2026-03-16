from django import forms
from django.core.exceptions import ValidationError
from .models import Formation, Category, Session, Participant
from resources.models import Trainer, Room
from clients.models import Client


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "color"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "color": forms.TextInput(attrs={"class": "form-control", "type": "color"}),
        }


class FormationForm(forms.ModelForm):
    class Meta:
        model = Formation
        fields = [
            "title",
            "title_ar",
            "code",
            "category",
            "description",
            "duration_days",
            "duration_hours",
            "min_participants",
            "max_participants",
            "base_price",
            "evaluation_type",
            "passing_score",
            "produces_certificate",
            "accreditation_body",
            "legal_references",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "title_ar": forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
            "code": forms.TextInput(attrs={"class": "form-control"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "duration_days": forms.NumberInput(attrs={"class": "form-control"}),
            "duration_hours": forms.NumberInput(attrs={"class": "form-control"}),
            "min_participants": forms.NumberInput(attrs={"class": "form-control"}),
            "max_participants": forms.NumberInput(attrs={"class": "form-control"}),
            "base_price": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "evaluation_type": forms.Select(attrs={"class": "form-select"}),
            "passing_score": forms.NumberInput(
                attrs={"class": "form-control", "step": "0.01"}
            ),
            "produces_certificate": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "accreditation_body": forms.TextInput(attrs={"class": "form-control"}),
            "legal_references": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_code(self):
        code = self.cleaned_data["code"].upper()
        if Formation.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Ce code existe déjà.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        min_p = cleaned_data.get("min_participants")
        max_p = cleaned_data.get("max_participants")
        if min_p and max_p and min_p > max_p:
            raise ValidationError("Le minimum ne peut pas être supérieur au maximum.")
        return cleaned_data


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = [
            "formation",
            "client",
            "trainer",
            "date_start",
            "date_end",
            "location_type",
            "room",
            "external_location",
            "capacity",
            "specialty_code",
            "session_number",
            "committee_members",
        ]
        widgets = {
            "formation": forms.Select(attrs={"class": "form-select"}),
            "client": forms.Select(attrs={"class": "form-select"}),
            "trainer": forms.Select(attrs={"class": "form-select"}),
            "date_start": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "date_end": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "location_type": forms.Select(attrs={"class": "form-select"}),
            "room": forms.Select(attrs={"class": "form-select"}),
            "external_location": forms.TextInput(attrs={"class": "form-control"}),
            "capacity": forms.NumberInput(attrs={"class": "form-control"}),
            "specialty_code": forms.TextInput(attrs={"class": "form-control"}),
            "session_number": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["formation"].queryset = Formation.objects.filter(is_active=True)
        self.fields["client"].queryset = Client.objects.filter(is_active=True)
        self.fields["trainer"].queryset = Trainer.objects.filter(is_active=True)
        self.fields["room"].queryset = Room.objects.filter(is_active=True)
        self.fields["room"].required = False
        self.fields["external_location"].required = False

        if self.instance.pk and self.instance.formation_id:
            self.fields["capacity"].initial = self.instance.formation.max_participants

    def clean(self):
        cleaned_data = super().clean()
        location_type = cleaned_data.get("location_type")
        room = cleaned_data.get("room")
        external_location = cleaned_data.get("external_location")

        if location_type == "institute" and not room:
            raise ValidationError(
                "Une salle doit être sélectionnée pour une formation à l'institut."
            )
        if location_type == "on_site" and not external_location:
            raise ValidationError("Le lieu externe doit être spécifié.")

        date_start = cleaned_data.get("date_start")
        date_end = cleaned_data.get("date_end")
        if date_start and date_end and date_end < date_start:
            raise ValidationError("La date de fin doit être après la date de début.")
        return cleaned_data


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "first_name",
            "last_name",
            "first_name_ar",
            "last_name_ar",
            "date_of_birth",
            "place_of_birth",
            "place_of_birth_ar",
            "job_title",
            "employer",
            "employer_client",  # spec §10.4
            "phone",
            "email",
            "notes",
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
            "date_of_birth": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "place_of_birth": forms.TextInput(attrs={"class": "form-control"}),
            "place_of_birth_ar": forms.TextInput(
                attrs={"class": "form-control", "dir": "rtl"}
            ),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "employer": forms.TextInput(attrs={"class": "form-control"}),
            "employer_client": forms.Select(attrs={"class": "form-select"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        self.fields["employer_client"].queryset = Client.objects.filter(is_active=True)
        self.fields["employer_client"].required = False

    def clean(self):
        cleaned_data = super().clean()
        first_name = cleaned_data.get("first_name")
        last_name = cleaned_data.get("last_name")

        if self.session and first_name and last_name:
            existing = Participant.objects.filter(
                session=self.session,
                first_name=first_name,
                last_name=last_name,
            ).exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    "Un participant avec ce nom existe déjà dans cette session."
                )
        return cleaned_data


class SessionStatusForm(forms.Form):
    new_status = forms.ChoiceField(
        choices=Session.STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cancellation_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)

        if self.session:
            valid = [
                (s, l)
                for s, l in Session.STATUS_CHOICES
                if self.session.can_transition_to(s)
            ]
            self.fields["new_status"].choices = valid

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get("new_status")
        cancellation_reason = cleaned_data.get("cancellation_reason")

        if new_status == "cancelled" and not cancellation_reason:
            raise ValidationError("Une raison d'annulation est requise.")

        if self.session and not self.session.can_transition_to(new_status):
            raise ValidationError(f"Transition vers '{new_status}' non autorisée.")

        return cleaned_data


class AttendanceForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)

        if self.session:
            for participant in self.session.participant_set.all():
                self.fields[f"participant_{participant.id}"] = forms.BooleanField(
                    label=participant.full_name,
                    required=False,
                    initial=participant.attended,
                    widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                )


class ScoreForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)

        if self.session:
            eval_type = self.session.formation.evaluation_type
            for participant in self.session.participant_set.all():
                if eval_type in ["theory_only", "both"]:
                    self.fields[f"theory_{participant.id}"] = forms.DecimalField(
                        label=f"{participant.full_name} - Théorique",
                        max_digits=4,
                        decimal_places=2,
                        min_value=0,
                        max_value=20,
                        required=False,
                        initial=participant.score_theory,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control", "step": "0.01"}
                        ),
                    )
                if eval_type in ["practice_only", "both"]:
                    self.fields[f"practice_{participant.id}"] = forms.DecimalField(
                        label=f"{participant.full_name} - Pratique",
                        max_digits=4,
                        decimal_places=2,
                        min_value=0,
                        max_value=20,
                        required=False,
                        initial=participant.score_practice,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control", "step": "0.01"}
                        ),
                    )


class ParticipantImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(
            attrs={"class": "form-control", "accept": ".csv,.xlsx,.xls"}
        )
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file:
            name = file.name.lower()
            if not (
                name.endswith(".csv") or name.endswith(".xlsx") or name.endswith(".xls")
            ):
                raise ValidationError("Seuls les fichiers CSV et Excel sont acceptés.")
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("Le fichier ne peut pas dépasser 5 Mo.")
        return file
