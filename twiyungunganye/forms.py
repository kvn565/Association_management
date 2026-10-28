from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import Membre, Cotisation, CotisationImprevu, Credit, Remboursement, Suggestion, Depense, DEVISE_CHOICES
from decimal import Decimal


def get_tenant_from_request():
    import inspect
    for frame in inspect.stack():
        request = frame.frame.f_locals.get('request')
        if request and hasattr(request, 'tenant'):
            return request.tenant
    return None


class LoginForm(AuthenticationForm):
    """Formulaire de connexion personnalisé avec sélection d'association"""

    tenant = forms.ModelChoiceField(
        queryset=None,
        label="Association",
        required=False,
        empty_label="Sélectionnez votre association",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
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

    def __init__(self, *args, **kwargs):
        tenant_queryset = kwargs.pop('tenant_queryset', None)
        super().__init__(*args, **kwargs)
        if tenant_queryset is not None:
            self.fields['tenant'].queryset = tenant_queryset


class MembrePasswordCreationForm(forms.Form):
    """Formulaire pour créer le premier mot de passe d'un membre avec sélection d'association"""

    tenant = forms.ModelChoiceField(
        queryset=None,
        label="Association",
        required=False,
        empty_label="Sélectionnez votre association",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

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

    def __init__(self, *args, **kwargs):
        tenant_queryset = kwargs.pop('tenant_queryset', None)
        super().__init__(*args, **kwargs)
        if tenant_queryset is not None:
            self.fields['tenant'].queryset = tenant_queryset
    
    def clean_carte_identite(self):
        carte_identite = self.cleaned_data.get('carte_identite')
        tenant = self.cleaned_data.get('tenant') or get_tenant_from_request()
        try:
            qs = Membre.objects.all()
            if tenant:
                qs = qs.filter(tenant=tenant)
            membre = qs.get(carte_identite=carte_identite)
            if membre.password and membre.has_usable_password():
                raise ValidationError("Ce membre a déjà un mot de passe. Utilisez la connexion normale.")
        except Membre.DoesNotExist:
            raise ValidationError("Aucun membre trouvé avec cette carte d'identité dans cette association.")
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
    
    photo = forms.ImageField(
        label="Photo",
        required=True,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )
    
    class Meta:
        model = Membre
        fields = ['nom', 'prenom', 'carte_identite', 'email', 'telephone', 'adresse', 'photo', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'carte_identite': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ModifierProfilForm(forms.ModelForm):
    """Formulaire pour qu'un dirigeant modifie son propre profil"""

    photo = forms.ImageField(
        label="Photo",
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    class Meta:
        model = Membre
        fields = ['nom', 'prenom', 'email', 'telephone', 'adresse', 'photo']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class AssociationForm(forms.Form):
    """Formulaire pour modifier les informations de l'association (Tenant)"""

    nom = forms.CharField(
        label="Nom de l'association", max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    sigle = forms.CharField(
        label="Sigle", max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        label="Téléphone", max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        label="Email", required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    province = forms.CharField(
        label="Province", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    commune = forms.CharField(
        label="Commune", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    quartier = forms.CharField(
        label="Quartier", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    avenue = forms.CharField(
        label="Avenue", max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    numero = forms.CharField(
        label="Numéro", max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    boite_postale = forms.CharField(
        label="Boîte postale", max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    logo = forms.ImageField(
        label="Logo", required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    montant_cotisation_mensuelle = forms.DecimalField(
        label="Montant cotisation mensuelle", max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    montant_cotisation_imprevu_mensuelle = forms.DecimalField(
        label="Montant cotisation imprévu", max_digits=10, decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    montant_max_credit = forms.DecimalField(
        label="Montant maximal de crédit autorisé", max_digits=12, decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    devise = forms.ChoiceField(
        label="Monnaie (devise)", choices=DEVISE_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    mois_minimum_cotisation_credit = forms.IntegerField(
        label="Mois minimum de cotisation pour crédit", min_value=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Nombre de mois de cotisation requis. 0 = pas de condition."
    )
    duree_remboursement_mois = forms.IntegerField(
        label="Durée de remboursement (mois)", min_value=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text="Nombre de mois max pour rembourser. 0 = pas de limite."
    )
    taux_interet_defaut = forms.DecimalField(
        label="Taux d'intérêt mensuel par défaut (%)", max_digits=5, decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text="Taux appliqué aux nouveaux crédits (ex: 5.00 pour 5%)"
    )
    taux_penalite_cotisation = forms.DecimalField(
        label="Taux de pénalité mensuel (%)", max_digits=5, decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        help_text="Taux de pénalité pour cotisations impayées (ex: 2.00 pour 2%)"
    )

    def __init__(self, *args, **kwargs):
        self.tenant_instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)
        if self.tenant_instance:
            for field in self.fields:
                val = getattr(self.tenant_instance, field, None)
                if val is not None:
                    self.fields[field].initial = val
            from .models import Association
            assoc = Association.get_association(self.tenant_instance)
            if assoc and assoc.devise:
                self.fields['devise'].initial = assoc.devise


class CotisationForm(forms.ModelForm):
    """Formulaire pour enregistrer une cotisation régulière"""
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields['membre'].queryset = Membre.objects.filter(
                tenant=self.tenant, est_actif=True
            )
        if not self.instance.pk:
            from django.utils import timezone
            today = timezone.now()
            self.fields['mois'].initial = today.month
            self.fields['annee'].initial = today.year
            self.fields['date_paiement'].initial = today.date()

    def validate_unique(self):
        if self.instance.pk:
            return
        super().validate_unique()

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



class EncaisserCotisationForm(forms.Form):
    membre = forms.ModelChoiceField(
        queryset=Membre.objects.none(),
        label="Membre",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    montant = forms.DecimalField(
        label="Montant payé",
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'})
    )
    date_paiement = forms.DateField(
        label="Date de paiement",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    type_cotisation = forms.ChoiceField(
        label="Type",
        choices=[('regulier', 'Cotisation régulière'), ('imprevu', 'Imprévu')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields['membre'].queryset = Membre.objects.filter(
                tenant=self.tenant, est_actif=True
            )
            from .models import Association
            assoc = Association.objects.filter(tenant=self.tenant).first()
            if assoc:
                m_reg = assoc.montant_cotisation_mensuelle
                m_imp = assoc.montant_cotisation_imprevu_mensuelle
                self.fields['montant'].help_text = (
                    f"Mensualité régulière: {m_reg:.0f} | Imprévu: {m_imp:.0f}"
                )


class CotisationImprevuForm(forms.ModelForm):
    """Formulaire pour enregistrer une cotisation pour imprévus/cas sociaux"""

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields['membre'].queryset = Membre.objects.filter(
                tenant=self.tenant, est_actif=True
            )
        if not self.instance.pk:
            from django.utils import timezone
            today = timezone.now()
            self.fields['mois'].initial = today.month
            self.fields['annee'].initial = today.year
            self.fields['date_paiement'].initial = today.date()

    def validate_unique(self):
        if self.instance.pk:
            return  # modification : ignorer la validation unique
        super().validate_unique()

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
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
    
    def clean_montant_demande(self):
        montant = self.cleaned_data.get('montant_demande')
        
        if self.membre:
            total_cotisations = self.membre.get_total_cotisations()
            
            if total_cotisations <= 0:
                raise ValidationError(
                    "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée."
                )
            
            # Vérifier le nombre de mois minimum configurable
            from .models import Association
            association = Association.get_association(self.tenant)
            if association:
                mois_min = association.mois_minimum_cotisation_credit
                if mois_min > 0:
                    montant_minimum = association.montant_cotisation_mensuelle * mois_min
                    if total_cotisations < montant_minimum:
                        raise ValidationError(
                            f"Vous devez avoir au moins {montant_minimum} {association.devise} de cotisations payées "
                            f"(équivalent à {mois_min} mois). Vous avez actuellement {total_cotisations} {association.devise}."
                        )
        
        return montant


class CreditApprovalForm(forms.ModelForm):
    """Formulaire pour approuver/rejeter un crédit (par l'admin)"""
    
    class Meta:
        model = Credit
        fields = ['membre', 'montant_accorde', 'taux_interet', 'statut', 'date_accord', 'remarque']
        widgets = {
            'membre': forms.Select(attrs={'class': 'form-select'}),
            'montant_accorde': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'taux_interet': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'date_accord': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'membre': 'Membre bénéficiaire',
            'montant_accorde': 'Montant accordé (FBU)',
            'taux_interet': "Taux d'intérêt mensuel (%)",
            'statut': 'Statut',
            'date_accord': "Date d'accord",
            'remarque': 'Remarque'
        }
    
    def __init__(self, *args, **kwargs):
        tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        if tenant:
            self.fields['membre'].queryset = Membre.objects.filter(tenant=tenant, est_actif=True).order_by('nom', 'prenom')
        else:
            self.fields['membre'].queryset = Membre.objects.none()
        if tenant and not self.instance.pk:
            self.fields['taux_interet'].initial = tenant.taux_interet_defaut


class RemboursementForm(forms.ModelForm):
    """Formulaire pour enregistrer un remboursement"""
    
    class Meta:
        model = Remboursement
        fields = ['credit', 'montant_rembourse', 'mode_paiement', 'date_remboursement', 'remarque']
        widgets = {
            'credit': forms.Select(attrs={'class': 'form-select'}),
            'montant_rembourse': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'mode_paiement': forms.Select(attrs={'class': 'form-select'}),
            'date_remboursement': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'remarque': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'credit': 'Crédit',
            'montant_rembourse': 'Montant remboursé (FBU)',
            'mode_paiement': 'Mode de paiement',
            'date_remboursement': 'Date de remboursement',
            'remarque': 'Remarque'
        }
    
    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop('tenant', None)
        super().__init__(*args, **kwargs)
        qs = Credit.objects.filter(statut__in=['APPROUVE', 'EN_COURS']).select_related('membre')
        if self.tenant:
            qs = qs.filter(tenant=self.tenant)
        self.fields['credit'].queryset = qs
        # Afficher le montant restant dynamique dans le libellé
        def credit_label(obj):
            reste = obj.get_reste_a_rembourser()
            return f"{obj.membre.get_full_name()} — Reste: {reste:,.3f} / {obj.montant_accorde:,.3f} FBU"
        self.fields['credit'].label_from_instance = credit_label
        # Afficher le montant restant dynamique dans la liste déroulante
        from django.utils.html import escape
        choices = []
        for credit in qs:
            reste = credit.get_reste_a_rembourser()
            label = f"{credit.membre.get_full_name()} — Reste: {reste:,.3f} / {credit.montant_accorde:,.3f} FBU"
            choices.append((credit.pk, label))
        self.fields['credit'].choices = choices


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


class ReponseSuggestionForm(forms.ModelForm):
    """Formulaire pour que l'admin réponde à une suggestion"""

    class Meta:
        model = Suggestion
        fields = ['statut', 'reponse_admin']
        widgets = {
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'reponse_admin': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Votre réponse au membre...'
            }),
        }
        labels = {
            'statut': 'Statut',
            'reponse_admin': 'Réponse',
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


class RapportPeriodeForm(forms.Form):
    """Formulaire pour générer un rapport sur une période de mois"""
    
    mois_debut = forms.ChoiceField(
        label="Mois début",
        choices=[(1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                 (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                 (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    annee_debut = forms.IntegerField(
        label="Année début",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    mois_fin = forms.ChoiceField(
        label="Mois fin",
        choices=[(1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'),
                 (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'),
                 (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    annee_fin = forms.IntegerField(
        label="Année fin",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        md = cleaned_data.get('mois_debut')
        ad = cleaned_data.get('annee_debut')
        mf = cleaned_data.get('mois_fin')
        af = cleaned_data.get('annee_fin')

        if md is not None and ad is not None and mf is not None and af is not None:
            md = int(md)
            mf = int(mf)
            ad = int(ad)
            af = int(af)
            if (ad, md) > (af, mf):
                raise forms.ValidationError("La date de début doit être antérieure ou égale à la date de fin.")
        return cleaned_data


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


class DepenseForm(forms.ModelForm):
    class Meta:
        model = Depense
        fields = ['motif', 'description', 'montant', 'date_depense']
        widgets = {
            'motif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Fête de fin d\'année'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description de la dépense...'}),
            'montant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'date_depense': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }
        labels = {
            'motif': 'Motif de la dépense',
            'description': 'Description',
            'montant': 'Montant',
            'date_depense': 'Date de la dépense',
        }


class ReinitialiserMotDePasseMembreForm(forms.Form):
    """Formulaire pour réinitialiser le mot de passe d'un membre (admin association)."""

    password = forms.CharField(
        label="Nouveau mot de passe",
        min_length=6,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum 6 caractères',
            'autocomplete': 'new-password',
        })
    )
    confirm = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Répétez le mot de passe',
            'autocomplete': 'new-password',
        })
    )

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get('password')
        confirm = cleaned.get('confirm')
        if password and confirm and password != confirm:
            self.add_error('confirm', "Les mots de passe ne correspondent pas.")
        return cleaned
