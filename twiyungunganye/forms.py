from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import Membre, Cotisation, CotisationImprevu, Credit, Remboursement, Suggestion
from decimal import Decimal


class LoginForm(AuthenticationForm):
    """Formulaire de connexion personnalisé"""
    
    username = forms.CharField(
        label="Carte d'identité",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro de carte d\'identité'
        })
    )
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Mot de passe'
        })
    )


class MembrePasswordCreationForm(forms.Form):
    """Formulaire pour créer le premier mot de passe d'un membre"""
    
    carte_identite = forms.CharField(
        label="Carte d'identité",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre numéro de carte d\'identité'
        })
    )
    password1 = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Choisissez un mot de passe'
        })
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirmez votre mot de passe'
        })
    )
    
    def clean_carte_identite(self):
        carte_identite = self.cleaned_data.get('carte_identite')
        try:
            membre = Membre.objects.get(carte_identite=carte_identite)
            if membre.has_usable_password():
                raise ValidationError("Ce membre a déjà un mot de passe. Utilisez la connexion normale.")
        except Membre.DoesNotExist:
            raise ValidationError("Aucun membre trouvé avec cette carte d'identité.")
        return carte_identite
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Les mots de passe ne correspondent pas.")
        
        return cleaned_data


class MembreForm(forms.ModelForm):
    """Formulaire pour créer/modifier un membre"""
    
    class Meta:
        model = Membre
        fields = ['nom', 'prenom', 'carte_identite', 'email', 'telephone', 'adresse', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'carte_identite': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CotisationForm(forms.ModelForm):
    """Formulaire pour enregistrer une cotisation régulière"""
    
    class Meta:
        model = Cotisation
        fields = ['membre', 'montant', 'mois', 'annee', 'statut', 'date_paiement', 'remarque']
        widgets = {
            'membre': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mois': forms.Select(attrs={'class': 'form-select'}, choices=[
                (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
            ]),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'date_paiement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class CotisationImprevuForm(forms.ModelForm):
    """Formulaire pour enregistrer une cotisation pour imprévus/cas sociaux"""
    
    class Meta:
        model = CotisationImprevu
        fields = ['membre', 'montant', 'mois', 'annee', 'statut', 'date_paiement', 'remarque']
        widgets = {
            'membre': forms.Select(attrs={'class': 'form-select'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mois': forms.Select(attrs={'class': 'form-select'}, choices=[
                (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
            ]),
            'annee': forms.NumberInput(attrs={'class': 'form-control'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'date_paiement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'membre': 'Membre',
            'montant': 'Montant (FBU)',
            'mois': 'Mois',
            'annee': 'Année',
            'statut': 'Statut',
            'date_paiement': 'Date de paiement',
            'remarque': 'Remarque'
        }


class CreditDemandeForm(forms.ModelForm):
    """Formulaire pour demander un crédit (par les membres)"""
    
    class Meta:
        model = Credit
        fields = ['montant_demande', 'remarque']
        widgets = {
            'montant_demande': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Montant demandé en FBU'
            }),
            'remarque': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Motif de la demande et informations complémentaires'
            }),
        }
        labels = {
            'montant_demande': 'Montant demandé (FBU)',
            'remarque': 'Motif de la demande'
        }
    
    def __init__(self, *args, **kwargs):
        self.membre = kwargs.pop('membre', None)
        super().__init__(*args, **kwargs)
    
    def clean_montant_demande(self):
        montant = self.cleaned_data.get('montant_demande')
        
        if self.membre:
            total_cotisations = self.membre.get_total_cotisations()
            
            if total_cotisations <= 0:
                raise ValidationError(
                    "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée."
                )
            
            # Vérifier qu'il y a au moins 3 mois de cotisations
            from .models import Association
            association = Association.get_association()
            if association:
                montant_minimum = association.montant_cotisation_mensuelle * 3
                if total_cotisations < montant_minimum:
                    raise ValidationError(
                        f"Vous devez avoir au moins {montant_minimum} FBU de cotisations payées "
                        f"(équivalent à 3 mois). Vous avez actuellement {total_cotisations} FBU."
                    )
        
        return montant


class CreditApprovalForm(forms.ModelForm):
    """Formulaire pour approuver/rejeter un crédit (par l'admin)"""
    
    class Meta:
        model = Credit
        fields = ['montant_accorde', 'taux_interet', 'statut', 'date_accord', 'remarque']
        widgets = {
            'montant_accorde': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taux_interet': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'date_accord': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'montant_accorde': 'Montant accordé (FBU)',
            'taux_interet': 'Taux d\'intérêt (%)',
            'statut': 'Statut',
            'date_accord': 'Date d\'accord',
            'remarque': 'Remarque'
        }


class RemboursementForm(forms.ModelForm):
    """Formulaire pour enregistrer un remboursement"""
    
    class Meta:
        model = Remboursement
        fields = ['credit', 'montant_rembourse', 'interet_rembourse', 'mode_paiement', 'date_remboursement', 'remarque']
        widgets = {
            'credit': forms.Select(attrs={'class': 'form-select'}),
            'montant_rembourse': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'interet_rembourse': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mode_paiement': forms.Select(attrs={'class': 'form-select'}),
            'date_remboursement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'credit': 'Crédit',
            'montant_rembourse': 'Montant remboursé (FBU)',
            'interet_rembourse': 'Intérêt remboursé (FBU)',
            'mode_paiement': 'Mode de paiement',
            'date_remboursement': 'Date de remboursement',
            'remarque': 'Remarque'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer uniquement les crédits en cours
        self.fields['credit'].queryset = Credit.objects.filter(
            statut__in=['APPROUVE', 'EN_COURS']
        )


class SuggestionForm(forms.ModelForm):
    """Formulaire pour soumettre une suggestion"""
    
    class Meta:
        model = Suggestion
        fields = ['titre', 'description']
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre de votre suggestion'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Décrivez votre suggestion en détail'
            }),
        }


class RapportMensuelForm(forms.Form):
    """Formulaire pour générer un rapport mensuel"""
    
    mois = forms.ChoiceField(
        label="Mois",
        choices=[
            (1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
            (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
            (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')
        ],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    annee = forms.IntegerField(
        label="Année",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class RapportAnnuelForm(forms.Form):
    """Formulaire pour générer un rapport annuel"""
    
    annee = forms.IntegerField(
        label="Année",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )


class MembrePasswordChangeForm(PasswordChangeForm):
    """Formulaire personnalisé pour changer le mot de passe"""
    
    old_password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password1 = forms.CharField(
        label="Nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password2 = forms.CharField(
        label="Confirmer le nouveau mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
