from django import forms
from formations.models import Formation
from resources.models import Trainer


class DateRangeForm(forms.Form):
    """Universal date-range filter used across all reports (spec §14.2 / §14.3)."""
    date_from = forms.DateField(
        required=False,
        label="Du",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    date_to = forms.DateField(
        required=False,
        label="Au",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean(self):
        cleaned = super().clean()
        date_from = cleaned.get('date_from')
        date_to = cleaned.get('date_to')
        if date_from and date_to and date_to < date_from:
            raise forms.ValidationError("La date de fin doit être après la date de début.")
        return cleaned


class SessionFilterForm(DateRangeForm):
    """Extended filter with formation, trainer and status (fill-rate report §14.2)."""
    formation = forms.ModelChoiceField(
        queryset=Formation.objects.filter(is_active=True),
        required=False,
        empty_label="Toutes les formations",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    trainer = forms.ModelChoiceField(
        queryset=Trainer.objects.filter(is_active=True),
        required=False,
        empty_label="Tous les formateurs",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    status = forms.ChoiceField(
        choices=[('', 'Tous les statuts')] + [
            ('planned',     'Planifiée'),
            ('in_progress', 'En cours'),
            ('completed',   'Terminée'),
            ('archived',    'Archivée'),
            ('cancelled',   'Annulée'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
