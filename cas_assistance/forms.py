from django import forms
from .models import CasAssistance
from django.forms import DateInput, NumberInput, TextInput, Select
from twiyungunganye.models import Membre


class CasAssistanceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields['membre'].queryset = Membre.objects.filter(
                tenant=self.tenant, est_actif=True
            )

    class Meta:
        model = CasAssistance
        fields = [
            'membre',
            'montant',
            'motif',
            'date_assistance'
        ]

        widgets = {
            'membre': Select(
                attrs={
                    'class': 'form-select',
                }
            ),
            'montant': NumberInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': "Entrez le montant de l'assistance"
                }
            ),
            'motif': TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': "Motif de l'assistance"
                }
            ),
            'date_assistance': DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
        }
