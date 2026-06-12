from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Tenant, CleActivation, ConfigurationApp
from twiyungunganye.models import Membre


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'nif', 'nom', 'sigle', 'sous_domaine',
            'province', 'commune', 'quartier', 'avenue', 'numero', 'boite_postale',
            'telephone', 'email', 'logo',
            'montant_cotisation_mensuelle', 'montant_cotisation_imprevu_mensuelle',
        ]
        widgets = {
            'nif': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 4000123456'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'autofocus': True}),
            'sigle': forms.TextInput(attrs={'class': 'form-control'}),
            'sous_domaine': forms.TextInput(attrs={
                'class': 'form-control', 'style': 'font-family: monospace;',
                'placeholder': 'Ex: association1'
            }),
            'province': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Bujumbura'}),
            'commune': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Ntahangwa'}),
            'quartier': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Rohero'}),
            'avenue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Avenue de la Paix'}),
            'numero': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 12'}),
            'boite_postale': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
            'montant_cotisation_mensuelle': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'montant_cotisation_imprevu_mensuelle': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'nif': "NIF (Numéro d'Identification Fiscale)",
            'nom': "Nom de l'association",
            'sigle': "Sigle",
            'sous_domaine': "Sous-domaine",
            'province': "Province",
            'commune': "Commune",
            'quartier': "Quartier",
            'avenue': "Avenue",
            'numero': "Numéro",
            'boite_postale': "Boîte postale",
            'logo': "Logo",
            'montant_cotisation_mensuelle': "Montant cotisation mensuelle (FBU)",
            'montant_cotisation_imprevu_mensuelle': "Montant cotisation imprévu (FBU)",
        }

    def clean_sous_domaine(self):
        sd = self.cleaned_data.get('sous_domaine', '').strip().lower()
        if not sd:
            raise forms.ValidationError("Le sous-domaine est obligatoire.")
        if not sd.isalnum():
            raise forms.ValidationError("Le sous-domaine ne doit contenir que des lettres et chiffres.")
        if self.instance.pk is None and Tenant.objects.filter(sous_domaine=sd).exists():
            raise forms.ValidationError("Ce sous-domaine est déjà utilisé.")
        return sd


class SuperadminTenantCreateForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ['nif', 'nom']
        widgets = {
            'nif': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Ex: 4000123456',
                'autofocus': True,
            }),
            'nom': forms.TextInput(attrs={
                'class': 'form-control form-control-lg',
                'placeholder': 'Nom exact de l\'association',
            }),
        }
        labels = {
            'nif': "NIF (Numéro d'Identification Fiscale)",
            'nom': "Nom de l'association",
        }
        help_texts = {
            'nif': "Le NIF servira de sous-domaine et d'identifiant unique pour l'association.",
        }

    def clean_nif(self):
        nif = self.cleaned_data.get('nif', '').strip().upper()
        if not nif:
            raise forms.ValidationError("Le NIF est obligatoire.")
        if Tenant.objects.filter(nif=nif).exists():
            raise forms.ValidationError("Ce NIF est déjà utilisé par une autre association.")
        return nif

    def clean_nom(self):
        nom = self.cleaned_data.get('nom', '').strip()
        if not nom:
            raise forms.ValidationError("Le nom de l'association est obligatoire.")
        return nom

    def save(self, commit=True):
        tenant = super().save(commit=False)
        nif = self.cleaned_data['nif']
        sd = ''.join(c for c in nif.lower() if c.isalnum())
        tenant.sous_domaine = sd
        if commit:
            tenant.save()
        return tenant


class CleActivationForm(forms.ModelForm):
    class Meta:
        model = CleActivation
        fields = ['tenant', 'type_plan', 'date_debut', 'date_fin', 'notes']
        widgets = {
            'tenant': forms.Select(attrs={'class': 'form-control'}),
            'type_plan': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'tenant': 'Association',
            'type_plan': 'Type de plan',
            'date_debut': 'Valide à partir du',
            'date_fin': "Valide jusqu'au",
        }

    def clean(self):
        cleaned = super().clean()
        type_plan = cleaned.get('type_plan')
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')
        tenant = cleaned.get('tenant')
        if tenant and CleActivation.objects.filter(tenant=tenant).exists():
            raise forms.ValidationError(f"Cette association a déjà une ou plusieurs clés. Impossible d'en générer une nouvelle.")
        if type_plan:
            maintenant = timezone.now()
            if not date_debut:
                date_debut = maintenant
                cleaned['date_debut'] = date_debut
            durees_jours = {'ESSAI': 14, '1MOIS': 30, 'STARTER': 182,
                           'BUSINESS': 365, 'ENTERPRISE': 730}
            if not date_fin:
                jours = durees_jours.get(type_plan, 182)
                date_fin = date_debut + timedelta(days=jours)
                cleaned['date_fin'] = date_fin
        if date_debut and date_fin and date_fin <= date_debut:
            raise forms.ValidationError("La date de fin doit être après la date de début.")
        return cleaned


class ClePayanteForm(forms.Form):
    cle_activation = forms.CharField(
        label="Clé de licence",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Ex: ASS-XXXX-12M-AB3D4E',
            'style': 'font-family: monospace; text-transform: uppercase;',
            'autocomplete': 'off',
        }),
    )

    def clean_cle_activation(self):
        cle = self.cleaned_data.get('cle_activation', '').strip().upper()
        if not cle:
            raise forms.ValidationError("Veuillez entrer une clé de licence.")
        return cle

    def verifier_pour_tenant(self, tenant):
        cle_saisie = self.cleaned_data.get('cle_activation')
        try:
            cle = CleActivation.objects.select_related('tenant').get(
                cle_visible=cle_saisie, tenant=tenant
            )
        except CleActivation.DoesNotExist:
            return False, "Clé invalide ou inexistante pour cette association.", None
        if cle.statut == 'REVOQUEE':
            return False, "Cette clé a été révoquée.", None
        if cle.statut == 'EXPIREE':
            return False, "Cette clé est expirée.", None
        if cle.date_fin and cle.date_fin.date() < timezone.now().date():
            return False, "Cette clé est expirée.", None
        if cle.utilisee:
            return False, "Cette clé a déjà été activée.", None
        if cle.statut != 'DISPONIBLE':
            return False, f"Cette clé n'est pas activable (statut: {cle.statut}).", None
        return True, "Clé valide et prête à être activée.", cle


class GenererCleForm(forms.ModelForm):
    class Meta:
        model = CleActivation
        fields = ['tenant', 'type_plan', 'date_debut', 'date_fin', 'notes']
        widgets = {
            'tenant': forms.Select(attrs={'class': 'form-control'}),
            'type_plan': forms.Select(attrs={'class': 'form-control'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'tenant': 'Association',
            'type_plan': 'Type de plan',
            'date_debut': 'Valide à partir du',
            'date_fin': "Valide jusqu'au",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tenant'].queryset = Tenant.objects.all().order_by('nom')
        self.fields['date_debut'].required = False
        self.fields['date_fin'].required = False
        self.fields['notes'].required = False

    def clean(self):
        cleaned = super().clean()
        type_plan = cleaned.get('type_plan')
        date_debut = cleaned.get('date_debut')
        date_fin = cleaned.get('date_fin')
        tenant = cleaned.get('tenant')
        if tenant and CleActivation.objects.filter(tenant=tenant).exists():
            raise forms.ValidationError(f"Cette association a déjà une ou plusieurs clés. Impossible d'en générer une nouvelle.")

        if type_plan == 'PERSONNALISE':
            if not date_debut:
                self.add_error('date_debut', "La date de début est requise pour un plan personnalisé.")
            if not date_fin:
                self.add_error('date_fin', "La date de fin est requise pour un plan personnalisé.")
        else:
            maintenant = timezone.now()
            if not date_debut:
                cleaned['date_debut'] = maintenant
            durees_jours = {'ESSAI': 14, '1MOIS': 30, 'STARTER': 182,
                           'BUSINESS': 365, 'ENTERPRISE': 730}
            if not date_fin:
                debut = cleaned.get('date_debut', maintenant)
                jours = durees_jours.get(type_plan, 182)
                cleaned['date_fin'] = debut + timedelta(days=jours)

        if cleaned.get('date_debut') and cleaned.get('date_fin'):
            if cleaned['date_fin'] <= cleaned['date_debut']:
                raise forms.ValidationError("La date de fin doit être après la date de début.")

        return cleaned


class SuperadminMembreForm(forms.ModelForm):
    """Formulaire superadmin pour créer/modifier un utilisateur dans n'importe quelle association"""

    tenant = forms.ModelChoiceField(
        label="Association",
        queryset=Tenant.objects.all().order_by('nom'),
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    password = forms.CharField(
        label="Mot de passe",
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Laisser vide pour ne pas changer',
            'autocomplete': 'new-password',
        }),
        help_text="Laisser vide pour conserver le mot de passe actuel (en modification)."
    )

    class Meta:
        model = Membre
        fields = ['tenant', 'nom', 'prenom', 'carte_identite', 'email', 'telephone',
                  'adresse', 'photo', 'is_admin', 'est_actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'carte_identite': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Carte d\'identité'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse'}),
            'is_admin': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'est_actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'is_admin': 'Administrateur (dirigeant)',
            'est_actif': 'Membre actif',
        }

    def clean_carte_identite(self):
        ci = self.cleaned_data.get('carte_identite', '').strip()
        qs = Membre.objects.filter(carte_identite=ci)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette carte d'identité est déjà utilisée.")
        return ci

    def save(self, commit=True):
        membre = super().save(commit=False)
        pwd = self.cleaned_data.get('password')
        if pwd:
            membre.set_password(pwd)
        if commit:
            membre.save()
        return membre


class SuperadminResetPasswordForm(forms.Form):
    """Formulaire pour réinitialiser le mot de passe d'un membre"""

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
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('confirm', "Les mots de passe ne correspondent pas.")
        return cleaned


class SuperadminTenantSupprimerForm(forms.Form):
    """Formulaire de confirmation pour supprimer une association"""
    confirmation = forms.CharField(
        label="Tapez 'SUPPRIMER' pour confirmer",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SUPPRIMER'}),
    )
    raison = forms.CharField(
        label="Motif de la suppression",
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Motif (optionnel)'}),
    )

    def clean_confirmation(self):
        val = self.cleaned_data.get('confirmation', '').strip()
        if val != 'SUPPRIMER':
            raise forms.ValidationError("Veuillez taper 'SUPPRIMER' pour confirmer.")
        return val


class InscriptionChefForm(forms.Form):
    """Formulaire d'inscription du chef/directeur d'une association"""

    nif = forms.CharField(
        label="NIF (Numéro d'Identification Fiscale)",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'id': 'id_nif_input',
            'placeholder': 'Ex: 4000123456',
            'autocomplete': 'off',
        }),
        help_text="Saisissez le NIF fourni par l'administrateur système. Le nom de l'association s'affichera automatiquement."
    )

    # ─── Localité de l'association ───────────────────────────
    province = forms.CharField(
        label="Province", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Bujumbura'})
    )
    commune = forms.CharField(
        label="Commune", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Ntahangwa'})
    )
    quartier = forms.CharField(
        label="Quartier", max_length=100, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Rohero'})
    )
    avenue = forms.CharField(
        label="Avenue", max_length=150, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Avenue de la Paix'})
    )
    numero = forms.CharField(
        label="Numéro", max_length=20, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 12'})
    )
    boite_postale = forms.CharField(
        label="Boîte postale", max_length=50, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 1234'})
    )

    # ─── Informations personnelles du dirigeant ──────────────
    nom = forms.CharField(
        label="Nom",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre nom'})
    )
    prenom = forms.CharField(
        label="Prénom",
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre prénom'})
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre@email.com'})
    )
    telephone = forms.CharField(
        label="Téléphone",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Votre téléphone'})
    )
    carte_identite = forms.CharField(
        label="Carte d'identité (nom d'utilisateur)",
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Numéro de carte d\'identité',
            'autocomplete': 'off',
        }),
        help_text="Ce sera votre identifiant de connexion."
    )
    password1 = forms.CharField(
        label="Mot de passe",
        min_length=6,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Minimum 6 caractères'})
    )
    password2 = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Répétez le mot de passe'})
    )

    def clean_nif(self):
        nif = self.cleaned_data.get('nif', '').strip().upper()
        try:
            tenant = Tenant.objects.get(nif=nif)
        except Tenant.DoesNotExist:
            raise forms.ValidationError("Ce NIF n'existe pas dans le système. Contactez l'administrateur.")

        if not tenant.actif:
            raise forms.ValidationError("Cette association a été désactivée.")

        # Vérifier qu'un admin n'est pas déjà inscrit
        if Membre.objects.filter(tenant=tenant, is_admin=True).exists():
            raise forms.ValidationError("Un administrateur est déjà inscrit pour cette association.")

        # Vérifier la licence
        now = timezone.now()
        cle_disponible = tenant.cles_activation.filter(
            statut__in=['DISPONIBLE', 'ACTIVE'],
            active=True,
            date_debut__lte=now,
            date_fin__gte=now,
        ).first()
        if not cle_disponible:
            raise forms.ValidationError(
                "Aucune licence valide disponible pour ce NIF. "
                "Contactez l'administrateur pour obtenir une clé d'activation."
            )

        self._tenant = tenant
        self._cle_active = cle_disponible
        return nif

    def clean_carte_identite(self):
        ci = self.cleaned_data.get('carte_identite', '').strip()
        if Membre.objects.filter(carte_identite=ci).exists():
            raise forms.ValidationError("Cette carte d'identité est déjà utilisée.")
        return ci

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', "Les mots de passe ne correspondent pas.")
        cleaned['_tenant'] = getattr(self, '_tenant', None)
        cleaned['_cle_active'] = getattr(self, '_cle_active', None)
        return cleaned


class SuperadminProfileForm(forms.ModelForm):
    """Formulaire de modification du profil superadmin"""
    
    class Meta:
        model = Membre
        fields = ['nom', 'prenom', 'carte_identite', 'email', 'telephone', 'adresse', 'photo']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom'}),
            'prenom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prénom'}),
            'carte_identite': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Carte d\'identité'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'telephone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Téléphone'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'carte_identite': "Carte d'identité (identifiant de connexion)",
        }

    def clean_carte_identite(self):
        ci = self.cleaned_data.get('carte_identite', '').strip()
        qs = Membre.objects.filter(carte_identite=ci)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Cette carte d'identité est déjà utilisée.")
        return ci


class SuperadminPasswordForm(forms.Form):
    """Formulaire de changement de mot de passe pour le superadmin"""
    current_password = forms.CharField(
        label="Mot de passe actuel", max_length=128,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    new_password = forms.CharField(
        label="Nouveau mot de passe", max_length=128,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    confirm_password = forms.CharField(
        label="Confirmer le mot de passe", max_length=128,
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        pwd = self.cleaned_data['current_password']
        if self.user and not self.user.check_password(pwd):
            raise forms.ValidationError("Mot de passe actuel incorrect.")
        return pwd

    def clean(self):
        cleaned = super().clean()
        np = cleaned.get('new_password')
        cp = cleaned.get('confirm_password')
        if np and cp and np != cp:
            self.add_error('confirm_password', "Les mots de passe ne correspondent pas.")
        return cleaned


class ConfigurationAppForm(forms.ModelForm):
    class Meta:
        model = ConfigurationApp
        fields = '__all__'
        widgets = {
            'nom_app': forms.TextInput(attrs={'class': 'form-control'}),
            'email_contact': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'contact@exemple.com'}),
            'telephone_contact': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+257 XX XX XX XX'}),
            'adresse': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Adresse physique'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Brève description...'}),
            'footer_texte': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '© {annee} Mon Application — Tous droits réservés'}),
            'liens_sociaux': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': '{"facebook":"url","twitter":"url"}'}),
            'slide_image_1': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'slide_image_2': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'slide_image_3': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'hero_slides_json': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': '[{"titre":"...","sous_titre":"...","description":"...","image":"URL"}]'}),
        }
