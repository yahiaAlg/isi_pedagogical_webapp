from django import forms
from formations.models import Session
from .models import HotEvaluation, EmployeeMissionOrder

class DocumentGenerationForm(forms.Form):
    """Base form for document generation"""
    session = forms.ModelChoiceField(
        queryset=Session.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.session_obj = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)
        
        if self.session_obj:
            self.fields['session'].initial = self.session_obj
            self.fields['session'].queryset = Session.objects.filter(pk=self.session_obj.pk)

class AttendanceSheetForm(DocumentGenerationForm):
    """Form for generating attendance sheets"""
    day_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        label="Numéro du jour"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.session_obj:
            duration = self.session_obj.duration_days
            self.fields['day_number'].widget.attrs['max'] = duration
            self.fields['day_number'].help_text = f"Entre 1 et {duration}"
    
    def clean_day_number(self):
        day_number = self.cleaned_data['day_number']
        if self.session_obj:
            if day_number > self.session_obj.duration_days:
                raise forms.ValidationError(
                    f"Le numéro de jour ne peut pas dépasser {self.session_obj.duration_days}"
                )
        return day_number

class AttestationGenerationForm(forms.Form):
    """Form for batch attestation generation"""
    session = forms.ModelChoiceField(
        queryset=Session.objects.all(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.session_obj = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)
        
        if self.session_obj:
            self.fields['session'].initial = self.session_obj
            self.fields['session'].queryset = Session.objects.filter(pk=self.session_obj.pk)
            
            # Add checkboxes for each eligible participant
            eligible_participants = self.session_obj.participant_set.filter(
                attended=True
            )
            
            for participant in eligible_participants:
                if participant.result == 'passed':
                    field_name = f'participant_{participant.pk}'
                    self.fields[field_name] = forms.BooleanField(
                        label=participant.full_name,
                        required=False,
                        initial=True,
                        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                    )

class CommitteeForm(forms.Form):
    """
    Form for entering the محضر مداولات committee.

    Rows are posted as parallel arrays `member_name[]` / `member_role[]`
    (built dynamically in the template with add/remove-row JS), not as a
    single free-text textarea, so each member carries a distinct الصفة.
    """

    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop("session", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        names = self.data.getlist("member_name") if hasattr(self.data, "getlist") else []
        roles = self.data.getlist("member_role") if hasattr(self.data, "getlist") else []

        members = []
        for name, role in zip(names, roles):
            name = (name or "").strip()
            role = (role or "").strip()
            if name and role:
                members.append({"name": name, "role": role})

        if len(members) < 2:
            raise forms.ValidationError(
                "Au moins 2 membres du comité sont requis (nom ET صفة pour chacun)."
            )

        cleaned_data["committee_members"] = members
        return cleaned_data


class HotEvaluationForm(forms.ModelForm):
    """
    Transcription form for the paper « Fiche d'évaluation à chaud » —
    one radio-style choice (A/B/C/D) per criterion plus the overall
    smiley appreciation. Used to enter what the candidate ticked by hand
    so the "filled" print view can reproduce it.
    """

    class Meta:
        model = HotEvaluation
        fields = [
            "grade_1", "grade_2", "grade_3", "grade_4",
            "grade_5", "grade_6", "grade_7", "grade_8",
            "overall_satisfaction", "comments",
        ]
        widgets = {
            "grade_1": forms.RadioSelect,
            "grade_2": forms.RadioSelect,
            "grade_3": forms.RadioSelect,
            "grade_4": forms.RadioSelect,
            "grade_5": forms.RadioSelect,
            "grade_6": forms.RadioSelect,
            "grade_7": forms.RadioSelect,
            "grade_8": forms.RadioSelect,
            "overall_satisfaction": forms.RadioSelect,
            "comments": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def criteria_fields(self):
        """(criterion metadata, bound field) pairs in display order, so
        the template can render each row without hardcoding grade_1..8."""
        pairs = []
        for i, (key, label_fr, label_ar) in enumerate(HotEvaluation.CRITERIA, start=1):
            pairs.append(
                {
                    "number": i,
                    "label_fr": label_fr,
                    "label_ar": label_ar,
                    "field": self[f"grade_{i}"],
                }
            )
        return pairs

class EmployeeMissionOrderForm(forms.ModelForm):
    """Global (session-independent) ordre de mission for a non-formateur
    employee — filled directly on the quick-access page."""

    class Meta:
        model = EmployeeMissionOrder
        fields = [
            "employee_name",
            "job_title",
            "professional_address",
            "destination",
            "motif",
            "date_start",
            "time_start",
            "date_end",
            "transport_means",
        ]
        widgets = {
            "employee_name": forms.TextInput(attrs={"class": "form-control"}),
            "job_title": forms.TextInput(attrs={"class": "form-control"}),
            "professional_address": forms.TextInput(attrs={"class": "form-control"}),
            "destination": forms.TextInput(attrs={"class": "form-control"}),
            "motif": forms.TextInput(attrs={"class": "form-control"}),
            "date_start": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "time_start": forms.TimeInput(
                attrs={"class": "form-control", "type": "time"}
            ),
            "date_end": forms.DateInput(
                attrs={"class": "form-control", "type": "date"}
            ),
            "transport_means": forms.Select(attrs={"class": "form-select"}),
        }
