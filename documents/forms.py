from django import forms

from core.models import CommitteeMember
from formations.models import Session


class DocumentGenerationForm(forms.Form):
    session = forms.ModelChoiceField(
        queryset=Session.objects.all(),
        widget=forms.HiddenInput(),
        required=True,
    )

    def __init__(self, *args, **kwargs):
        self.session_obj = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session_obj:
            self.fields["session"].initial = self.session_obj
            self.fields["session"].queryset = Session.objects.filter(pk=self.session_obj.pk)




class CandidateListForm(DocumentGenerationForm):
    PRINT_MODE_CHOICES = [
        ("filled", "Remplie automatiquement avec les données de l’application"),
        ("empty", "Vide — pour remplissage manuel"),
    ]
    print_mode = forms.ChoiceField(
        label="Mode d’impression",
        choices=PRINT_MODE_CHOICES,
        initial="filled",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )


class AttendanceSheetForm(DocumentGenerationForm):
    print_mode = forms.ChoiceField(
        label="Mode d’impression",
        choices=CandidateListForm.PRINT_MODE_CHOICES,
        initial="filled",
        widget=forms.RadioSelect(attrs={"class": "form-check-input"}),
    )
    day_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        label="Numéro du jour",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.session_obj:
            duration = self.session_obj.duration_days
            self.fields["day_number"].widget.attrs["max"] = duration
            self.fields["day_number"].help_text = f"Entre 1 et {duration}"

    def clean_day_number(self):
        day_number = self.cleaned_data["day_number"]
        if self.session_obj and day_number > self.session_obj.duration_days:
            raise forms.ValidationError(
                f"Le numéro de jour ne peut pas dépasser {self.session_obj.duration_days}"
            )
        return day_number


class AttestationGenerationForm(forms.Form):
    session = forms.ModelChoiceField(
        queryset=Session.objects.all(), widget=forms.HiddenInput(), required=True
    )

    def __init__(self, *args, **kwargs):
        self.session_obj = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        if self.session_obj:
            self.fields["session"].initial = self.session_obj
            self.fields["session"].queryset = Session.objects.filter(pk=self.session_obj.pk)
            eligible_participants = self.session_obj.participant_set.filter(attended=True)
            for participant in eligible_participants:
                if participant.result == "passed":
                    self.fields[f"participant_{participant.pk}"] = forms.BooleanField(
                        label=participant.full_name,
                        required=False,
                        initial=True,
                        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
                    )


class CommitteeForm(forms.Form):
    """Build the PV committee snapshot.

    Permanent members come from Core settings and retain their configured role.
    The trainer and the client representative are intentionally entered for each PV.
    """

    trainer_name = forms.CharField(
        label="الأستاذ المكون",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
    )
    trainer_role = forms.CharField(
        label="الصفة",
        max_length=150,
        required=True,
        initial="الأستاذ المكون",
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
    )
    representative_name = forms.CharField(
        label="ممثل الشركة",
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
    )
    representative_role = forms.CharField(
        label="الصفة",
        max_length=150,
        required=True,
        initial="ممثل الشركة",
        widget=forms.TextInput(attrs={"class": "form-control", "dir": "rtl"}),
    )

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)
        self.default_members = list(CommitteeMember.objects.filter(is_active=True))

        existing = self._normalise_existing(
            self.session.committee_members if self.session else []
        )
        trainer = next((m for m in existing if m.get("type") == "trainer"), None)
        representative = next((m for m in existing if m.get("type") == "representative"), None)

        self.fields["trainer_name"].initial = (
            trainer.get("name") if trainer else (self.session.trainer.full_name if self.session else "")
        )
        self.fields["trainer_role"].initial = trainer.get("role") if trainer else "الأستاذ المكون"
        self.fields["representative_name"].initial = (
            representative.get("name") if representative else ""
        )
        self.fields["representative_role"].initial = (
            representative.get("role") if representative else "ممثل الشركة"
        )

    @staticmethod
    def _normalise_existing(value):
        normalised = []
        for member in value or []:
            if isinstance(member, dict):
                name = str(member.get("name", "")).strip()
                role = str(member.get("role", "")).strip()
                member_type = member.get("type", "default")
            else:
                name = str(member).strip()
                role = ""
                member_type = "default"
            if name:
                normalised.append({"name": name, "role": role, "type": member_type})
        return normalised

    def clean(self):
        cleaned = super().clean()
        if any(self.errors.get(field) for field in self.fields):
            return cleaned

        members = [
            {"name": m.full_name.strip(), "role": m.role.strip(), "type": "default"}
            for m in self.default_members
            if m.full_name.strip()
        ]
        members.append(
            {
                "name": cleaned["trainer_name"].strip(),
                "role": cleaned["trainer_role"].strip(),
                "type": "trainer",
            }
        )
        members.append(
            {
                "name": cleaned["representative_name"].strip(),
                "role": cleaned["representative_role"].strip(),
                "type": "representative",
            }
        )

        if len(members) < 2:
            raise forms.ValidationError("Au moins 2 membres du comité sont requis.")
        cleaned["committee_members"] = members
        return cleaned
