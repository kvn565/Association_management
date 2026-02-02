from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal


class MembreManager(BaseUserManager):
    """Manager personnalisé pour le modèle Membre"""
    
    def create_user(self, carte_identite, nom, prenom, password=None, **extra_fields):
        if not carte_identite:
            raise ValueError("La carte d'identité est obligatoire")
        
        user = self.model(
            carte_identite=carte_identite,
            nom=nom,
            prenom=prenom,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, carte_identite, nom, prenom, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        
        return self.create_user(carte_identite, nom, prenom, password, **extra_fields)


class Membre(AbstractBaseUser, PermissionsMixin):
    """Modèle pour les membres de l'association"""
    
    id_membre = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    carte_identite = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    date_inscription = models.DateField(default=timezone.now)
    est_actif = models.BooleanField(default=True)
    
    # Champs pour l'authentification
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_gestionnaire = models.BooleanField(default=False)  # Droits réduits
    
    objects = MembreManager()
    
    USERNAME_FIELD = 'carte_identite'
    REQUIRED_FIELDS = ['nom', 'prenom']
    
    class Meta:
        db_table = 'membres'
        verbose_name = 'Membre'
        verbose_name_plural = 'Membres'
        ordering = ['nom', 'prenom']
    
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.carte_identite})"
    
    def get_full_name(self):
        return f"{self.prenom} {self.nom}"
    
    def get_short_name(self):
        return self.prenom
    
    def get_total_cotisations(self):
        """Retourne le total des cotisations payées (hors imprévus)"""
        total = self.cotisations.filter(statut='PAYE').aggregate(
            Sum('montant')
        )['montant__sum'] or Decimal('0.00')
        return total
    
    def get_total_cotisations_imprevus(self):
        """Retourne le total des cotisations pour imprévus payées"""
        total = self.cotisations_imprevus.filter(statut='PAYE').aggregate(
            Sum('montant')
        )['montant__sum'] or Decimal('0.00')
        return total


class Cotisation(models.Model):
    """Modèle pour les cotisations mensuelles régulières"""
    
    id_cotisation = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='cotisations')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mois = models.IntegerField()  # 1-12
    annee = models.IntegerField()
    date_paiement = models.DateField(default=timezone.now)
    statut = models.CharField(
        max_length=20,
        choices=[
            ('PAYE', 'Payé'),
            ('EN_ATTENTE', 'En attente'),
            ('RETARD', 'En retard')
        ],
        default='EN_ATTENTE'
    )
    remarque = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'cotisations'
        verbose_name = 'Cotisation'
        verbose_name_plural = 'Cotisations'
        unique_together = ['membre', 'mois', 'annee']
        ordering = ['-annee', '-mois']
    
    def __str__(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return f"{self.membre.get_full_name()} - {mois_noms[self.mois]} {self.annee}"
    
    def get_mois_nom(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return mois_noms[self.mois]


class CotisationImprevu(models.Model):
    """Modèle pour les cotisations pour cas sociaux/imprévus (indépendant des cotisations régulières)"""
    
    id_cotisation_imprevu = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='cotisations_imprevus')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    mois = models.IntegerField()  # 1-12
    annee = models.IntegerField()
    date_paiement = models.DateField(default=timezone.now)
    statut = models.CharField(
        max_length=20,
        choices=[
            ('PAYE', 'Payé'),
            ('EN_ATTENTE', 'En attente'),
            ('RETARD', 'En retard')
        ],
        default='EN_ATTENTE'
    )
    remarque = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'cotisations_imprevus'
        verbose_name = 'Cotisation Imprévus'
        verbose_name_plural = 'Cotisations Imprévus'
        unique_together = ['membre', 'mois', 'annee']
        ordering = ['-annee', '-mois']
    
    def __str__(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return f"Imprévus - {self.membre.get_full_name()} - {mois_noms[self.mois]} {self.annee}"
    
    def get_mois_nom(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return mois_noms[self.mois]


class Credit(models.Model):
    """Modèle pour les crédits accordés aux membres"""
    
    id_credit = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='credits')
    montant_demande = models.DecimalField(max_digits=10, decimal_places=2)
    montant_accorde = models.DecimalField(max_digits=10, decimal_places=2)
    taux_interet = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)  # 5% par défaut
    date_demande = models.DateField(default=timezone.now)
    date_accord = models.DateField(null=True, blank=True)
    statut = models.CharField(
        max_length=20,
        choices=[
            ('EN_ATTENTE', 'En attente'),
            ('APPROUVE', 'Approuvé'),
            ('REJETE', 'Rejeté'),
            ('REMBOURSE', 'Remboursé'),
            ('EN_COURS', 'En cours de remboursement')
        ],
        default='EN_ATTENTE'
    )
    nombre_mois_ecoules = models.IntegerField(default=0)
    remarque = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'credits'
        verbose_name = 'Crédit'
        verbose_name_plural = 'Crédits'
        ordering = ['-date_demande']
    
    def __str__(self):
        return f"Crédit {self.id_credit} - {self.membre.get_full_name()} - {self.montant_accorde} FBU"
    
    def clean(self):
        """Validation : vérifier que le membre a suffisamment de cotisations"""
        # ✅ CORRECTION : Vérifier d'abord si le membre existe
        if not hasattr(self, 'membre') or self.membre is None:
            # Si le membre n'est pas encore assigné, on ne peut pas valider
            # Cette validation sera faite dans la vue
            return
        
        if self.pk is None:  # Nouvelle demande seulement
            total_cotisations = self.membre.get_total_cotisations()
            
            if total_cotisations <= 0:
                raise ValidationError(
                    "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée."
                )
            
            # Optionnel : vérifier un montant minimum de cotisations
            # Par exemple, au moins 3 mois de cotisations
            association = Association.get_association()
            if association:
                montant_minimum = association.montant_cotisation_mensuelle * 3
                if total_cotisations < montant_minimum:
                    raise ValidationError(
                        f"Vous devez avoir au moins {montant_minimum} FBU de cotisations payées "
                        f"(équivalent à 3 mois). Vous avez actuellement {total_cotisations} FBU."
                    )
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def calculer_interet(self):
        """Calcule l'intérêt total basé sur le nombre de mois écoulés"""
        if self.montant_accorde and self.nombre_mois_ecoules:
            interet = self.montant_accorde * (self.taux_interet / 100) * self.nombre_mois_ecoules
            return Decimal(interet).quantize(Decimal('0.01'))
        return Decimal('0.00')
    
    def calculer_montant_total(self):
        """Calcule le montant total à rembourser (capital + intérêts)"""
        return self.montant_accorde + self.calculer_interet()
    
    def get_montant_rembourse(self):
        """Retourne le montant total déjà remboursé"""
        total = sum([r.montant_rembourse for r in self.remboursements.all()])
        return Decimal(total).quantize(Decimal('0.01'))
    
    def get_reste_a_rembourser(self):
        """Calcule le reste à rembourser"""
        return self.calculer_montant_total() - self.get_montant_rembourse()


class Interet(models.Model):
    """Modèle pour suivre les intérêts mensuels sur les crédits"""
    
    id_interet = models.AutoField(primary_key=True)
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='interets')
    mois = models.IntegerField()
    annee = models.IntegerField()
    interet_mensuel = models.DecimalField(max_digits=10, decimal_places=2)
    interet_cumule = models.DecimalField(max_digits=10, decimal_places=2)
    date_calcul = models.DateField(default=timezone.now)
    
    class Meta:
        db_table = 'interets'
        verbose_name = 'Intérêt'
        verbose_name_plural = 'Intérêts'
        unique_together = ['credit', 'mois', 'annee']
        ordering = ['-annee', '-mois']
    
    def __str__(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return f"Intérêt - {self.credit.membre.get_full_name()} - {mois_noms[self.mois]} {self.annee}"


class Remboursement(models.Model):
    """Modèle pour les remboursements de crédits"""
    
    id_rembourse = models.AutoField(primary_key=True)
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='remboursements')
    montant_rembourse = models.DecimalField(max_digits=10, decimal_places=2)
    interet_rembourse = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    reste_a_rembourser = models.DecimalField(max_digits=10, decimal_places=2)
    date_remboursement = models.DateField(default=timezone.now)
    mode_paiement = models.CharField(
        max_length=50,
        choices=[
            ('ESPECES', 'Espèces'),
            ('VIREMENT', 'Virement bancaire'),
            ('MOBILE', 'Mobile Money'),
            ('CHEQUE', 'Chèque')
        ],
        default='ESPECES'
    )
    remarque = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'remboursements'
        verbose_name = 'Remboursement'
        verbose_name_plural = 'Remboursements'
        ordering = ['-date_remboursement']
    
    def __str__(self):
        return f"Remboursement {self.id_rembourse} - {self.credit.membre.get_full_name()} - {self.montant_rembourse} FBU"
    
    def save(self, *args, **kwargs):
        # Calculer le reste à rembourser avant de sauvegarder
        if not self.reste_a_rembourser:
            total_a_rembourser = self.credit.calculer_montant_total()
            total_deja_rembourse = self.credit.get_montant_rembourse() + self.montant_rembourse
            self.reste_a_rembourser = total_a_rembourser - total_deja_rembourse
        
        super().save(*args, **kwargs)
        
        # Mettre à jour le statut du crédit
        if self.reste_a_rembourser <= 0:
            self.credit.statut = 'REMBOURSE'
        elif self.credit.statut == 'APPROUVE':
            self.credit.statut = 'EN_COURS'
        self.credit.save()


class Association(models.Model):
    """Modèle pour les informations de l'association"""
    
    id_association = models.AutoField(primary_key=True)
    nom = models.CharField(max_length=200)
    sigle = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    montant_cotisation_mensuelle = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_cotisation_imprevu_mensuelle = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        help_text="Montant mensuel pour les cotisations imprévus/cas sociaux"
    )
    date_creation = models.DateField(default=timezone.now)
    
    class Meta:
        db_table = 'associations'
        verbose_name = 'Association'
        verbose_name_plural = 'Associations'
    
    def __str__(self):
        return self.nom
    
    @classmethod
    def get_association(cls):
        """Retourne l'association (il ne devrait y en avoir qu'une seule)"""
        return cls.objects.first()
    
    def get_total_cotisations_disponibles(self):
        """Retourne le total des cotisations régulières disponibles"""
        from django.db.models import Sum
        total = Cotisation.objects.filter(statut='PAYE').aggregate(
            Sum('montant')
        )['montant__sum'] or Decimal('0.00')
        return total
    
    def get_total_cotisations_imprevus_disponibles(self):
        """Retourne le total des cotisations imprévus disponibles"""
        from django.db.models import Sum
        total = CotisationImprevu.objects.filter(statut='PAYE').aggregate(
            Sum('montant')
        )['montant__sum'] or Decimal('0.00')
        return total


class Suggestion(models.Model):
    """Modèle pour les suggestions des membres"""
    
    id_suggestion = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='suggestions')
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date_soumission = models.DateTimeField(default=timezone.now)
    statut = models.CharField(
        max_length=20,
        choices=[
            ('EN_ATTENTE', 'En attente'),
            ('EN_COURS', 'En cours d\'examen'),
            ('ACCEPTEE', 'Acceptée'),
            ('REJETEE', 'Rejetée')
        ],
        default='EN_ATTENTE'
    )
    reponse_admin = models.TextField(blank=True, null=True)
    date_reponse = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'suggestions'
        verbose_name = 'Suggestion'
        verbose_name_plural = 'Suggestions'
        ordering = ['-date_soumission']
    
    def __str__(self):
        return f"{self.titre} - {self.membre.get_full_name()}"
