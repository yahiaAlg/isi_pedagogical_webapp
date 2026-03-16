from django import forms
from formations.models import Session

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
    """Form for entering committee members"""
    committee_members = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        label="Membres du comité",
        help_text="Un membre par ligne (minimum 2 membres requis)"
    )
    
    def __init__(self, *args, **kwargs):
        self.session = kwargs.pop('session', None)
        super().__init__(*args, **kwargs)
        
        if self.session and self.session.committee_members:
            # Pre-populate with existing committee members
            members = self.session.committee_members
            if isinstance(members, list):
                self.fields['committee_members'].initial = '\n'.join(members)
    
    def clean_committee_members(self):
        members_text = self.cleaned_data['committee_members']
        members = [line.strip() for line in members_text.split('\n') if line.strip()]
        
        if len(members) < 2:
            raise forms.ValidationError("Au moins 2 membres du comité sont requis.")
        
        return members