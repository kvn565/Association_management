from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal, ROUND_DOWN
from django.conf import settings

DEVISE_CHOICES = [
    ('FBU', 'FBU — Franc Burundais'),
    ('USD', 'USD — Dollar Américain'),
    ('EUR', 'EUR — Euro'),
    ('CDF', 'CDF — Franc Congolais'),
    ('RWF', 'RWF — Franc Rwandais'),
    ('KES', 'KES — Shilling Kenyan'),
    ('TZS', 'TZS — Shilling Tanzanien'),
    ('UGX', 'UGX — Shilling Ougandais'),
    ('GBP', 'GBP — Livre Sterling'),
]

def tronquer(montant):
    """Tronque un montant à 3 décimales sans arrondissement (ROUND_DOWN)"""
    return Decimal(str(montant)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)
from datetime import date
from dateutil.relativedelta import relativedelta


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
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='membres', null=True, blank=True
    )
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    carte_identite = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=255, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    photo = models.ImageField("Photo", upload_to='photos_membres/', blank=True, null=True)
    date_inscription = models.DateField(default=timezone.now)
    est_actif = models.BooleanField(default=True)
    
    # Champs pour l'authentification
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_admin = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    groupe_acces = models.ForeignKey(
        'GroupeAcces', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='membres', verbose_name="Groupe d'accès"
    )
    
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
        )['montant__sum'] or Decimal('0.000')
        return total
    
    def get_total_cotisations_imprevus(self):
        """Retourne le total des cotisations pour imprévus payées"""
        total = self.cotisations_imprevus.filter(statut='PAYE').aggregate(
            Sum('montant')
        )['montant__sum'] or Decimal('0.000')
        return total

    @property
    def notifications_non_lues(self):
        return self.notifications.filter(est_lu=False).count()

    def save(self, *args, **kwargs):
        if not self.password:
            self.set_unusable_password()
        super().save(*args, **kwargs)


class Cotisation(models.Model):
    """Modèle pour les cotisations mensuelles régulières"""
    
    id_cotisation = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='cotisations')
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='cotisations', null=True, blank=True
    )
    montant = models.DecimalField(max_digits=10, decimal_places=3)
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
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='cotisations_imprevus', null=True, blank=True
    )
    montant = models.DecimalField(max_digits=10, decimal_places=3)
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
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='credits', null=True, blank=True
    )
    montant_demande = models.DecimalField(max_digits=10, decimal_places=3)
    montant_accorde = models.DecimalField(max_digits=10, decimal_places=3)
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
        if not hasattr(self, 'membre') or self.membre is None:
            return
        
        if self.pk is None:
            total_cotisations = self.membre.get_total_cotisations()
            
            if total_cotisations <= 0:
                raise ValidationError(
                    "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée."
                )
            
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
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def calculer_interet(self):
        """Calcule l'intérêt sur le montant restant dû (dégressif mois par mois)"""
        if not self.montant_accorde or not self.date_accord:
            return Decimal('0')

        today = timezone.now().date()
        mois = (today.year - self.date_accord.year) * 12 + today.month - self.date_accord.month
        if mois <= 0:
            return Decimal('0')

        taux = Decimal(self.taux_interet) / Decimal(100)
        repayments = []
        if self.pk:
            repayments = list(self.remboursements.order_by('date_remboursement'))

        montant_restant = self.montant_accorde
        total_interet = Decimal('0')

        for m in range(mois):
            interet_mois = tronquer(montant_restant * taux)
            total_interet += interet_mois

            mois_courant = self.date_accord.month + m
            annee_courante = self.date_accord.year + (mois_courant - 1) // 12
            mois_courant = ((mois_courant - 1) % 12) + 1

            principal_rembourse = sum(
                r.montant_rembourse for r in repayments
                if r.date_remboursement.month == mois_courant
                and r.date_remboursement.year == annee_courante
            )
            montant_restant -= principal_rembourse
            if montant_restant <= 0:
                break

        return tronquer(max(total_interet, Decimal('0')))
    
    def calculer_montant_total(self):
        """Calcule le montant total à rembourser (capital + intérêts)"""
        return self.montant_accorde + self.calculer_interet()
    
    def get_montant_rembourse(self):
        """Retourne le montant total déjà remboursé"""
        total = sum([r.montant_rembourse + r.interet_rembourse for r in self.remboursements.all()])
        return tronquer(total)
    
    def get_reste_a_rembourser(self):
        """Calcule le reste à rembourser (troncature 3 décimales)"""
        reste = self.calculer_montant_total() - self.get_montant_rembourse()
        return tronquer(max(reste, Decimal('0')))


class Interet(models.Model):
    """Modèle pour suivre les intérêts mensuels sur les crédits"""
    
    id_interet = models.AutoField(primary_key=True)
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='interets')
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='interets', null=True, blank=True
    )
    mois = models.IntegerField()
    annee = models.IntegerField()
    interet_mensuel = models.DecimalField(max_digits=10, decimal_places=3)
    interet_cumule = models.DecimalField(max_digits=10, decimal_places=3)
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


class PenaliteCotisation(models.Model):
    """Modèle pour suivre les pénalités mensuelles sur les cotisations régulières impayées"""
    
    id_penalite = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='penalites')
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='penalites_cotisation', null=True, blank=True
    )
    cotisation = models.ForeignKey(
        Cotisation, on_delete=models.CASCADE, related_name='penalites',
        null=True, blank=True,
        help_text="La cotisation concernée (si elle existe)"
    )
    mois = models.IntegerField()
    annee = models.IntegerField()
    montant_cotisation = models.DecimalField(max_digits=10, decimal_places=3)
    taux_penalite = models.DecimalField(max_digits=5, decimal_places=2)
    penalite_mensuelle = models.DecimalField(max_digits=10, decimal_places=3)
    penalite_cumulee = models.DecimalField(max_digits=10, decimal_places=3)
    date_calcul = models.DateField(default=timezone.now)
    est_payee = models.BooleanField(default=False)
    date_paiement = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'penalites_cotisation'
        verbose_name = 'Pénalité cotisation'
        verbose_name_plural = 'Pénalités cotisations'
        unique_together = ['membre', 'mois', 'annee']
        ordering = ['-annee', '-mois']
    
    def __str__(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return f"Pénalité - {self.membre.get_full_name()} - {mois_noms[self.mois]} {self.annee}"
    
    @classmethod
    def calculer_pour_membre(cls, membre, mois, annee, taux_penalite=None):
        """Calcule la pénalité pour un membre sur un mois donné"""
        from superadmin.models import Tenant
        
        tenant = membre.tenant
        if not tenant:
            return None
        
        if taux_penalite is None:
            taux_penalite = tenant.taux_penalite_cotisation
        
        # Vérifier si la cotisation existe
        try:
            cotisation = Cotisation.objects.get(membre=membre, mois=mois, annee=annee)
            montant_cotisation = cotisation.montant
        except Cotisation.DoesNotExist:
            # Si pas de cotisation, utiliser le montant par défaut de l'association
            from twiyungunganye.models import Association
            association = Association.get_association(tenant)
            if association:
                montant_cotisation = association.montant_cotisation_mensuelle
            else:
                return None
        
        taux = Decimal(str(taux_penalite)) / Decimal('100')
        penalite_mensuelle = tronquer(montant_cotisation * taux)
        
        # Calculer combien de mois de retard
        today = timezone.now().date()
        date_echeance = date(annee, mois, 1)  # Premier du mois
        delta = relativedelta(today, date_echeance)
        mois_retard = delta.years * 12 + delta.months
        if mois_retard < 0:
            mois_retard = 0
        
        penalite_cumulee = tronquer(penalite_mensuelle * max(1, mois_retard))
        
        # Créer ou mettre à jour la pénalité
        penalite, created = cls.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=annee,
            defaults={
                'tenant': tenant,
                'cotisation': cotisation if 'cotisation' in locals() else None,
                'montant_cotisation': montant_cotisation,
                'taux_penalite': taux_penalite,
                'penalite_mensuelle': penalite_mensuelle,
                'penalite_cumulee': penalite_cumulee,
                'date_calcul': today,
            }
        )
        
        if not created:
            penalite.penalite_cumulee = penalite_cumulee
            penalite.save(update_fields=['penalite_cumulee'])
        
        return penalite
    
    @classmethod
    def generer_toutes_penalites(cls, tenant=None):
        """Génère les pénalités pour tous les membres ayant des cotisations impayées"""
        from dateutil.relativedelta import relativedelta
        from django.db.models import Q
        
        if tenant is None:
            # Générer pour tous les tenants
            from superadmin.models import Tenant
            tenants = Tenant.objects.filter(actif=True)
        else:
            tenants = Tenant.objects.filter(pk=tenant.pk)
        
        total_crees = 0
        today = timezone.now().date()
        
        for t in tenants:
            taux = t.taux_penalite_cotisation
            membres = Membre.objects.filter(tenant=t, est_actif=True)
            
            for membre in membres:
                # Vérifier les 12 derniers mois
                for i in range(12):
                    date_check = today - relativedelta(months=i)
                    mois = date_check.month
                    annee = date_check.year
                    
                    # Vérifier si la cotisation est impayée
                    cotisation = Cotisation.objects.filter(
                        membre=membre, mois=mois, annee=annee
                    ).first()
                    
                    if cotisation and cotisation.statut in ['EN_ATTENTE', 'RETARD']:
                        cls.calculer_pour_membre(membre, mois, annee, taux)
                        total_crees += 1
        
        return total_crees


class Remboursement(models.Model):
    """Modèle pour les remboursements de crédits"""
    
    id_rembourse = models.AutoField(primary_key=True)
    credit = models.ForeignKey(Credit, on_delete=models.CASCADE, related_name='remboursements')
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='remboursements', null=True, blank=True
    )
    montant_rembourse = models.DecimalField(max_digits=10, decimal_places=3)
    interet_rembourse = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    reste_a_rembourser = models.DecimalField(max_digits=10, decimal_places=3)
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
        if not self.credit_id:
            return super().save(*args, **kwargs)

        total_a_rembourser = self.credit.calculer_montant_total()
        autres_remb = Remboursement.objects.filter(credit=self.credit)
        if self.pk:
            autres_remb = autres_remb.exclude(pk=self.pk)
        total_deja = sum(r.montant_rembourse + r.interet_rembourse for r in autres_remb)
        total_verse = total_deja + self.montant_rembourse + self.interet_rembourse
        self.reste_a_rembourser = tronquer(total_a_rembourser - total_verse)
        if self.reste_a_rembourser < 0:
            self.reste_a_rembourser = tronquer(0)

        super().save(*args, **kwargs)

        nouveau_statut = 'REMBOURSE' if self.reste_a_rembourser <= 0 else (
            'EN_COURS' if self.credit.statut == 'APPROUVE' else self.credit.statut
        )
        if nouveau_statut != self.credit.statut:
            self.credit.statut = nouveau_statut
            self.credit.save(update_fields=['statut'])


class Association(models.Model):
    """Modèle pour les informations de l'association (lié à un tenant)"""
    
    id_association = models.AutoField(primary_key=True)
    tenant = models.OneToOneField(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='association_config', null=True, blank=True
    )
    nom = models.CharField(max_length=200)
    sigle = models.CharField(max_length=50, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    montant_cotisation_mensuelle = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    montant_cotisation_imprevu_mensuelle = models.DecimalField(
        max_digits=10, 
        decimal_places=3, 
        default=0,
        help_text="Montant mensuel pour les cotisations imprévus/cas sociaux"
    )
    montant_max_credit = models.DecimalField(
        "Montant maximal de crédit autorisé",
        max_digits=12,
        decimal_places=3,
        default=500000,
        help_text="Montant maximum qu'un membre peut demander comme crédit"
    )
    devise = models.CharField(
        "Monnaie",
        max_length=10,
        choices=DEVISE_CHOICES,
        default='FBU',
    )
    mois_minimum_cotisation_credit = models.PositiveIntegerField(
        "Mois minimum de cotisation pour crédit",
        default=3,
        help_text="Nombre de mois de cotisation requis avant de pouvoir demander un crédit. 0 = pas de condition."
    )
    duree_remboursement_mois = models.PositiveIntegerField(
        "Durée de remboursement (mois)",
        default=12,
        help_text="Nombre de mois maximum pour rembourser un crédit. 0 = pas de limite."
    )
    date_creation = models.DateField(default=timezone.now)
    
    class Meta:
        db_table = 'associations'
        verbose_name = 'Association'
        verbose_name_plural = 'Associations'
    
    def __str__(self):
        return self.nom
    
    @classmethod
    def get_association(cls, tenant=None):
        """Retourne l'association pour un tenant donné"""
        if tenant:
            return cls.objects.filter(tenant=tenant).first()
        return None
    
    def get_total_cotisations_disponibles(self):
        """Retourne le total des cotisations régulières disponibles"""
        from django.db.models import Sum
        qs = Cotisation.objects.filter(statut='PAYE')
        if self.tenant_id:
            qs = qs.filter(tenant=self.tenant)
        total = qs.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
        return total
    
    def get_total_cotisations_imprevus_disponibles(self):
        """Retourne le total des cotisations imprévus disponibles"""
        from django.db.models import Sum
        qs = CotisationImprevu.objects.filter(statut='PAYE')
        if self.tenant_id:
            qs = qs.filter(tenant=self.tenant)
        total = qs.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
        return total


class GroupeAcces(models.Model):
    """Groupe de permissions pour contrôler l'accès aux menus"""
    id_groupe = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='groupes_acces'
    )
    nom = models.CharField("Nom du groupe", max_length=100)
    description = models.TextField("Description", blank=True, null=True)
    permissions = models.TextField(
        "Permissions",
        help_text="Codes des menus autorisés, séparés par des virgules. Ex: dashboard,membres,cotisations,credits"
    )
    date_creation = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'groupes_acces'
        verbose_name = "Groupe d'accès"
        verbose_name_plural = "Groupes d'accès"

    def __str__(self):
        return self.nom

    def get_permissions_list(self):
        if self.permissions:
            return [p.strip() for p in self.permissions.split(',') if p.strip()]
        return []

    def has_permission(self, code):
        return code in self.get_permissions_list()


class Suggestion(models.Model):
    """Modèle pour les suggestions des membres"""
    
    id_suggestion = models.AutoField(primary_key=True)
    membre = models.ForeignKey(Membre, on_delete=models.CASCADE, related_name='suggestions')
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='suggestions', null=True, blank=True
    )
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


class Notification(models.Model):
    """Modèle pour les notifications internes"""

    TYPE_CHOICES = [
        ('DEMANDE_CREDIT', 'Nouvelle demande de crédit'),
        ('APPROBATION_CREDIT', 'Crédit approuvé'),
        ('REJET_CREDIT', 'Crédit rejeté'),
        ('NOUVELLE_SUGGESTION', 'Nouvelle suggestion'),
        ('REPONSE_SUGGESTION', 'Réponse à une suggestion'),
        ('INFO', 'Information générale'),
    ]

    id_notification = models.AutoField(primary_key=True)
    destinataire = models.ForeignKey(
        Membre, on_delete=models.CASCADE, related_name='notifications'
    )
    expediteur = models.ForeignKey(
        Membre, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notifications_envoyees'
    )
    type_notification = models.CharField(
        "Type", max_length=30, choices=TYPE_CHOICES, default='INFO'
    )
    titre = models.CharField(max_length=200)
    message = models.TextField(blank=True)
    lien = models.CharField(
        "Lien", max_length=300, blank=True,
        help_text="URL vers la ressource concernée (ex: /credits/5/)"
    )
    est_lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-date_creation']

    def __str__(self):
        return f"[{self.get_type_notification_display()}] {self.titre}"


# ─── Signal : auto-créer Association lors de la création d'un Tenant ───
from django.db.models.signals import post_save
from django.dispatch import receiver
from superadmin.models import Tenant


@receiver(post_save, sender=Tenant)
def auto_create_association(sender, instance, created, **kwargs):
    adresse = ", ".join(filter(None, [
        instance.boite_postale or "",
        instance.avenue or "",
        instance.quartier or "",
        instance.commune or "",
        instance.province or "",
    ]))
    Association.objects.get_or_create(
        tenant=instance,
        defaults={
            'nom': instance.nom,
            'sigle': instance.sigle or '',
            'adresse': adresse,
            'telephone': instance.telephone or '',
            'email': instance.email or '',
            'montant_cotisation_mensuelle': instance.montant_cotisation_mensuelle,
            'montant_cotisation_imprevu_mensuelle': instance.montant_cotisation_imprevu_mensuelle,
            'devise': getattr(instance, 'devise', 'FBU') or 'FBU',
        }
    )


class Depense(models.Model):
    """Modèle pour les dépenses de l'association (fêtes, matériel, etc.)"""

    id_depense = models.AutoField(primary_key=True)
    tenant = models.ForeignKey(
        'superadmin.Tenant', on_delete=models.CASCADE,
        related_name='depenses', null=True, blank=True
    )
    motif = models.CharField("Motif", max_length=200)
    description = models.TextField("Description", blank=True, null=True)
    montant = models.DecimalField(max_digits=10, decimal_places=3)
    date_depense = models.DateField("Date de la dépense", default=timezone.now)
    cree_par = models.ForeignKey(
        'Membre', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='depenses_crees', verbose_name="Créé par"
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'depenses'
        verbose_name = 'Dépense'
        verbose_name_plural = 'Dépenses'
        ordering = ['-date_depense', '-date_creation']

    def __str__(self):
        return f"{self.motif} - {self.montant} FBU ({self.date_depense})"
