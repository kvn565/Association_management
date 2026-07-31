from django.db import models
from django.db.models import Sum
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
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
    """Retourne le montant sans arrondi (l'affichage via floatformat:3 gère les 3 décimales)"""
    return Decimal(str(montant))


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
    
    @staticmethod
    def _mois_entre(d1, d2):
        """Nombre de mois calendaires entre deux dates."""
        return max(0, (d2.year - d1.year) * 12 + (d2.month - d1.month))

    def _capital_au(self, date):
        """Capital restant à une date donnée (avant les remboursements de ce jour)."""
        capital_rembourse = sum(
            r.montant_rembourse for r in self.remboursements.all()
            if r.date_remboursement < date
        ) if self.pk else Decimal('0')
        return max(self.montant_accorde - capital_rembourse, Decimal('0'))

    def calculer_interet(self, jusqua_date=None):
        """Calcule l'intérêt cumulé par mois calendaire complet.
        - Démarre au mois de date_accord (pas de mois gratuit)
        - Intérêt = capital au DERNIER jour du mois × taux mensuel"""
        if not self.montant_accorde or not self.date_accord:
            return Decimal('0')

        if jusqua_date is None:
            jusqua_date = timezone.now().date()

        from calendar import monthrange
        from datetime import date

        taux = Decimal(self.taux_interet) / Decimal(100)
        total_interet = Decimal('0')

        current = date(self.date_accord.year, self.date_accord.month, 1)

        while current < jusqua_date:
            last_day = monthrange(current.year, current.month)[1]
            month_end = date(current.year, current.month, last_day)

            if month_end > jusqua_date:
                break

            if current.month == 12:
                next_month = date(current.year + 1, 1, 1)
            else:
                next_month = date(current.year, current.month + 1, 1)

            capital = self._capital_au(next_month)
            if capital <= 0:
                break

            total_interet += tronquer(capital * taux)
            current = next_month

        return tronquer(max(total_interet, Decimal('0')))
    
    def calculer_montant_total(self):
        """Calcule le montant total à rembourser (capital + intérêts)"""
        return self.montant_accorde + self.calculer_interet()
    
    def get_montant_rembourse(self):
        """Retourne le montant total déjà remboursé"""
        total = sum([r.montant_rembourse + r.interet_rembourse for r in self.remboursements.all()])
        return tronquer(total)
    
    def get_reste_a_rembourser(self):
        """Calcule le capital restant à rembourser (hors intérêts)"""
        total_capital_rembourse = sum(r.montant_rembourse for r in self.remboursements.all())
        return tronquer(max(self.montant_accorde - total_capital_rembourse, Decimal('0')))


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
    interet_rembourse = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    date_remboursement = models.DateField(null=True, blank=True, help_text="Date à laquelle l'intérêt a été remboursé")
    date_calcul = models.DateField(default=timezone.now)

    @property
    def reste_a_payer(self):
        return tronquer(max(self.interet_mensuel - self.interet_rembourse, Decimal('0')))
    
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

    def get_mois_nom(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return mois_noms[self.mois]


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
    montant_cotisation_base = models.DecimalField(max_digits=10, decimal_places=3, default=0,
        help_text="Montant de la cotisation régulière impayée")
    montant_imprevu_base = models.DecimalField(max_digits=10, decimal_places=3, default=0,
        help_text="Montant de l'imprévu impayé")
    taux_penalite = models.DecimalField(max_digits=5, decimal_places=2)
    penalite_mensuelle = models.DecimalField(max_digits=10, decimal_places=3)
    penalite_cumulee = models.DecimalField(max_digits=10, decimal_places=3)
    date_calcul = models.DateField(default=timezone.now)
    est_payee = models.BooleanField(default=False)
    date_paiement = models.DateField(null=True, blank=True)
    montant_paye = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    exclu = models.BooleanField(default=False,
        help_text="Exclure cette pénalité (au lieu de supprimer)")
    reste_a_payer = models.DecimalField(max_digits=10, decimal_places=3, default=0,
        help_text="Montant de la pénalité à payer (éditable)")

    @property
    def montant_restant(self):
        return tronquer(max(self.reste_a_payer - self.montant_paye, Decimal('0')))

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

    def get_mois_nom(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return mois_noms[self.mois]

    @classmethod
    def calculer_pour_membre(cls, membre, mois, annee, taux_penalite=None, montant_base=None,
                              montant_cotisation_base=None, montant_imprevu_base=None):
        """Calcule la pénalité pour un membre sur un mois donné"""
        from superadmin.models import Tenant
        
        tenant = membre.tenant
        if not tenant:
            return None
        
        if taux_penalite is None:
            taux_penalite = tenant.taux_penalite_cotisation
        
        if montant_base is not None:
            montant_cotisation = montant_base
        elif montant_cotisation_base is not None and montant_imprevu_base is not None:
            montant_cotisation = montant_cotisation_base + montant_imprevu_base
        else:
            try:
                cotisation = Cotisation.objects.get(membre=membre, mois=mois, annee=annee)
                montant_cotisation = cotisation.montant
            except Cotisation.DoesNotExist:
                from twiyungunganye.models import Association
                association = Association.get_association(tenant)
                if association:
                    montant_cotisation = association.montant_cotisation_mensuelle
                else:
                    return None
        
        taux = Decimal(str(taux_penalite)) / Decimal('100')
        penalite_mensuelle = tronquer(montant_cotisation * taux)
        
        today = timezone.now().date()
        penalite_cumulee = penalite_mensuelle
        
        defaults = {
            'tenant': tenant,
            'montant_cotisation': montant_cotisation,
            'taux_penalite': taux_penalite,
            'penalite_mensuelle': penalite_mensuelle,
            'penalite_cumulee': penalite_cumulee,
            'reste_a_payer': penalite_cumulee,
            'date_calcul': today,
        }
        if montant_cotisation_base is not None:
            defaults['montant_cotisation_base'] = montant_cotisation_base
        if montant_imprevu_base is not None:
            defaults['montant_imprevu_base'] = montant_imprevu_base

        penalite, created = cls.objects.get_or_create(
            membre=membre,
            mois=mois,
            annee=annee,
            defaults=defaults,
        )
        
        if not created:
            penalite.penalite_cumulee = penalite_cumulee
            penalite.reste_a_payer = penalite_cumulee
            penalite.penalite_mensuelle = penalite_mensuelle
            penalite.montant_cotisation = montant_cotisation
            penalite.taux_penalite = taux_penalite
            update_fields = ['penalite_cumulee', 'reste_a_payer', 'penalite_mensuelle', 'montant_cotisation', 'taux_penalite']
            if montant_cotisation_base is not None:
                penalite.montant_cotisation_base = montant_cotisation_base
                update_fields.append('montant_cotisation_base')
            if montant_imprevu_base is not None:
                penalite.montant_imprevu_base = montant_imprevu_base
                update_fields.append('montant_imprevu_base')
            penalite.save(update_fields=update_fields)
        
        return penalite
    
    @classmethod
    def generer_toutes_penalites(cls, tenant=None):
        """Génère les pénalités pour tous les membres ayant des cotisations impayées.
        Régulier et Imprévu : cumulatif (total payé < total dû → pénalité).
        Gère les paiements en avance (135000 en mars couvre 9 mois).
        Supprime les pénalités des mois devenus couverts."""
        from dateutil.relativedelta import relativedelta
        
        if tenant is None:
            from superadmin.models import Tenant
            tenants = Tenant.objects.filter(actif=True)
        else:
            tenants = Tenant.objects.filter(pk=tenant.pk)
        
        total_crees = 0
        today = timezone.now().date()
        
        for t in tenants:
            taux = t.taux_penalite_cotisation
            membres = Membre.objects.filter(tenant=t, est_actif=True)
            association = Association.get_association(t)
            if not association:
                continue
            
            mensualite_reg = association.montant_cotisation_mensuelle
            mensualite_imp = association.montant_cotisation_imprevu_mensuelle
            
            # Mois de début global du tenant (première cotisation tous membres confondus)
            premiere_cot_tenant = Cotisation.objects.filter(
                membre__tenant=t
            ).order_by('annee', 'mois').values('annee', 'mois').first()
            premiere_imp_tenant = CotisationImprevu.objects.filter(
                membre__tenant=t
            ).order_by('annee', 'mois').values('annee', 'mois').first()
            mois_debut_tenant = None
            if premiere_cot_tenant:
                md = premiere_cot_tenant['annee'] * 12 + premiere_cot_tenant['mois']
                mois_debut_tenant = md if mois_debut_tenant is None else min(mois_debut_tenant, md)
            if premiere_imp_tenant:
                md = premiere_imp_tenant['annee'] * 12 + premiere_imp_tenant['mois']
                mois_debut_tenant = md if mois_debut_tenant is None else min(mois_debut_tenant, md)
            
            for membre in membres:
                # Déterminer le début pour chaque type
                premiere_cotisation = Cotisation.objects.filter(
                    membre=membre
                ).order_by('annee', 'mois').first()
                
                premiere_imprevu = CotisationImprevu.objects.filter(
                    membre=membre
                ).order_by('annee', 'mois').first()
                
                # Date de début régulier (minimum entre le membre et le tenant)
                if premiere_cotisation:
                    debut_mois_reg = premiere_cotisation.mois
                    debut_annee_reg = premiere_cotisation.annee
                    if mois_debut_tenant is not None:
                        debut_membre = debut_annee_reg * 12 + debut_mois_reg
                        if mois_debut_tenant < debut_membre:
                            debut_annee_reg = mois_debut_tenant // 12
                            debut_mois_reg = mois_debut_tenant % 12
                            if debut_mois_reg == 0:
                                debut_mois_reg = 12
                                debut_annee_reg -= 1
                else:
                    debut_mois_reg = None
                    debut_annee_reg = None
                
                # Date de début imprévus (minimum entre le membre et le tenant)
                if premiere_imprevu:
                    debut_mois_imp = premiere_imprevu.mois
                    debut_annee_imp = premiere_imprevu.annee
                    if mois_debut_tenant is not None:
                        debut_membre = debut_annee_imp * 12 + debut_mois_imp
                        if mois_debut_tenant < debut_membre:
                            debut_annee_imp = mois_debut_tenant // 12
                            debut_mois_imp = mois_debut_tenant % 12
                            if debut_mois_imp == 0:
                                debut_mois_imp = 12
                                debut_annee_imp -= 1
                else:
                    debut_mois_imp = None
                    debut_annee_imp = None
                
                # Mois de référence
                mois_ref = today.year * 12 + today.month
                
                # Déterminer le mois de début (uniquement types qui ont des enregistrements)
                debut_options = []
                if debut_annee_reg is not None:
                    debut_options.append(debut_annee_reg * 12 + debut_mois_reg)
                if debut_annee_imp is not None:
                    debut_options.append(debut_annee_imp * 12 + debut_mois_imp)
                if not debut_options:
                    # Aucun enregistrement → supprimer toutes ses pénalités existantes
                    cls.objects.filter(membre=membre).delete()
                    continue
                mois_debut = min(debut_options)

                # Supprimer les pénalités avant le mois de début
                annee_debut = mois_debut // 12
                mois_debut_num = mois_debut % 12
                if mois_debut_num == 0:
                    mois_debut_num = 12
                    annee_debut -= 1
                cls.objects.filter(membre=membre, annee__lt=annee_debut).delete()
                cls.objects.filter(membre=membre, annee=annee_debut, mois__lt=mois_debut_num).delete()
                mois_max_check = mois_ref - 1 if mois_ref > mois_debut else mois_debut

                # Calculer debut_reg et debut_imp pour la boucle
                debut_reg = debut_annee_reg * 12 + debut_mois_reg if debut_annee_reg is not None else mois_max_check + 1
                if debut_annee_imp is not None and debut_annee_reg is not None:
                    debut_imp = min(debut_annee_imp * 12 + debut_mois_imp, debut_annee_reg * 12 + debut_mois_reg)
                else:
                    debut_imp = debut_annee_imp * 12 + debut_mois_imp if debut_annee_imp is not None else mois_max_check + 1
                
                # Supprimer pénalités après le mois max (mois courant et futurs)
                max_annee = mois_max_check // 12
                max_mois_num = mois_max_check % 12
                if max_mois_num == 0:
                    max_mois_num = 12
                    max_annee -= 1
                cls.objects.filter(
                    membre=membre, exclu=False,
                    annee__gt=max_annee
                ).delete()
                cls.objects.filter(
                    membre=membre, exclu=False,
                    annee=max_annee, mois__gt=max_mois_num
                ).delete()
                
                # Suivre les mois qui ONT une pénalité
                mois_avec_penalite = set()
                
                # Ensembles des mois PAYÉS (pour lookup rapide)
                cotisations_payees = set(Cotisation.objects.filter(
                    membre=membre, statut='PAYE'
                ).values_list('annee', 'mois'))
                imprevus_payes = set(CotisationImprevu.objects.filter(
                    membre=membre, statut='PAYE'
                ).values_list('annee', 'mois'))
                
                # Itérer sur chaque mois à vérifier
                for mois_idx in range(mois_debut, mois_max_check + 1):
                    annee = mois_idx // 12
                    mois = mois_idx % 12
                    if mois == 0:
                        mois = 12
                        annee -= 1
                    
                    position_mois_reg = mois_idx - debut_reg + 1
                    position_mois_imp = mois_idx - debut_imp + 1
                    
                    # Ne pas regénérer une pénalité exclue manuellement
                    if cls.objects.filter(membre=membre, mois=mois, annee=annee, exclu=True).exists():
                        continue
                    
                    est_impaye = False
                    montant_base = Decimal('0')
                    mnt_cot = Decimal('0')
                    mnt_imp = Decimal('0')
                    
                    # Régulier : impayé si pas de PAYE pour ce mois exact
                    if position_mois_reg > 0 and (annee, mois) not in cotisations_payees:
                        est_impaye = True
                        montant_base += mensualite_reg
                        mnt_cot = mensualite_reg
                    
                    # Imprévus : impayé si pas de PAYE pour ce mois exact
                    if position_mois_imp > 0 and (annee, mois) not in imprevus_payes:
                        est_impaye = True
                        montant_base += mensualite_imp
                        mnt_imp = mensualite_imp
                    
                    if est_impaye and montant_base > 0:
                        mois_avec_penalite.add((annee, mois))
                        cls.calculer_pour_membre(membre, mois, annee, taux, montant_base=montant_base,
                                                  montant_cotisation_base=mnt_cot, montant_imprevu_base=mnt_imp)
                        total_crees += 1
                
                # Supprimer les pénalités des mois devenus couverts
                for pen in cls.objects.filter(membre=membre, exclu=False):
                    if (pen.annee, pen.mois) not in mois_avec_penalite and pen.reste_a_payer > pen.montant_paye:
                        pen.delete()
        
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
    
    @staticmethod
    def _synchroniser_interets(credit):
        """Recalcule interet_mensuel (capital fin de mois) sans toucher interet_rembourse"""
        from calendar import monthrange
        from datetime import date
        from decimal import Decimal

        taux = Decimal(str(credit.taux_interet or '0')) / Decimal('100')
        interets = Interet.objects.filter(credit=credit).order_by('annee', 'mois')
        for interet in interets:
            if interet.mois == 12:
                next_month = date(interet.annee + 1, 1, 1)
            else:
                next_month = date(interet.annee, interet.mois + 1, 1)
            capital = credit._capital_au(next_month)
            interet.interet_mensuel = tronquer(capital * taux) if capital > 0 else Decimal('0')

        Interet.objects.bulk_update(interets, ['interet_mensuel'])

    def delete(self, *args, **kwargs):
        credit = self.credit
        super().delete(*args, **kwargs)
        Remboursement._synchroniser_interets(credit)

    def save(self, *args, **kwargs):
        if not self.credit_id:
            return super().save(*args, **kwargs)

        autres_remb = Remboursement.objects.filter(credit=self.credit)
        if self.pk:
            autres_remb = autres_remb.exclude(pk=self.pk)
        total_capital_rembourse = sum(r.montant_rembourse for r in autres_remb)
        self.reste_a_rembourser = tronquer(max(
            self.credit.montant_accorde - total_capital_rembourse - self.montant_rembourse,
            Decimal('0')
        ))

        super().save(*args, **kwargs)

        Remboursement._synchroniser_interets(self.credit)

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
