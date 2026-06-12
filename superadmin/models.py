import hashlib
import hmac
import secrets
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.conf import settings


class Tenant(models.Model):
    nif = models.CharField(
        "NIF", max_length=50, unique=True, blank=True, null=True,
        help_text="Numéro d'Identification Fiscale"
    )
    sous_domaine = models.CharField(
        "Sous-domaine", max_length=50, unique=True,
        help_text="Ex: association1 (sera accessible via association1.votredomaine.com)"
    )
    nom = models.CharField("Nom de l'association", max_length=200)
    sigle = models.CharField("Sigle", max_length=50, blank=True, null=True)
    telephone = models.CharField("Téléphone", max_length=20, blank=True, null=True)
    email = models.EmailField("Email", blank=True, null=True)
    logo = models.ImageField("Logo", upload_to='logos/', blank=True, null=True)
    province = models.CharField("Province", max_length=100, blank=True, null=True)
    commune = models.CharField("Commune", max_length=100, blank=True, null=True)
    quartier = models.CharField("Quartier", max_length=100, blank=True, null=True)
    avenue = models.CharField("Avenue", max_length=150, blank=True, null=True)
    numero = models.CharField("Numéro", max_length=20, blank=True, null=True)
    boite_postale = models.CharField("Boîte postale", max_length=50, blank=True, null=True)
    montant_cotisation_mensuelle = models.DecimalField(
        "Montant cotisation mensuelle", max_digits=10, decimal_places=3, default=0
    )
    montant_cotisation_imprevu_mensuelle = models.DecimalField(
        "Montant cotisation imprévu mensuelle", max_digits=10, decimal_places=3, default=0
    )
    taux_interet_defaut = models.DecimalField(
        "Taux d'intérêt par défaut (%)", max_digits=5, decimal_places=2, default=5.00,
        help_text="Taux d'intérêt mensuel appliqué aux crédits (ex: 5.00 pour 5%)"
    )
    taux_penalite_cotisation = models.DecimalField(
        "Taux de pénalité cotisation (%)", max_digits=5, decimal_places=2, default=2.00,
        help_text="Taux de pénalité mensuel pour cotisations régulières impayées (ex: 2.00 pour 2%)"
    )
    date_creation = models.DateField("Date de création", default=timezone.now)
    actif = models.BooleanField("Actif", default=True)
    date_creation_systeme = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Association (Tenant)"
        verbose_name_plural = "Associations (Tenants)"
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.sous_domaine})"

    def get_total_cotisations_disponibles(self):
        from twiyungunganye.models import Cotisation
        total = Cotisation.objects.filter(
            tenant=self, statut='PAYE'
        ).aggregate(models.Sum('montant'))['montant__sum'] or 0
        return total

    def get_total_cotisations_imprevus_disponibles(self):
        from twiyungunganye.models import CotisationImprevu
        total = CotisationImprevu.objects.filter(
            tenant=self, statut='PAYE'
        ).aggregate(models.Sum('montant'))['montant__sum'] or 0
        return total

    @property
    def cle_active(self):
        today = timezone.localdate()
        return self.cles_activation.filter(
            statut='ACTIVE',
            utilisee=True,
            active=True,
            date_fin__date__gte=today,
        ).order_by('-date_creation').first()

    @property
    def licence_valide(self):
        return self.cle_active is not None


class CleActivation(models.Model):
    TYPE_PLAN = [
        ('ESSAI', 'Essai gratuit (14 jours)'),
        ('1MOIS', '1 Mois'),
        ('STARTER', 'Starter (6 mois)'),
        ('BUSINESS', 'Business (12 mois)'),
        ('ENTERPRISE', 'Enterprise (24 mois)'),
        ('PERSONNALISE', 'Personnalisé'),
    ]

    cle_visible = models.CharField(max_length=50, unique=True, editable=False)
    empreinte_hmac = models.CharField(max_length=64, editable=False, blank=True)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='cles_activation',
        verbose_name="Association"
    )
    type_plan = models.CharField(
        "Type de plan", max_length=20,
        choices=TYPE_PLAN, default='STARTER'
    )
    duree_mois = models.PositiveSmallIntegerField(
        "Durée (mois)", default=6,
        help_text="Calculé automatiquement depuis type_plan. 0 = essai 14 jours."
    )
    STATUT = [
        ('DISPONIBLE', 'Disponible — prête à être activée'),
        ('ACTIVE', 'Active — en cours de validité'),
        ('EXPIREE', 'Expirée'),
        ('REVOQUEE', 'Révoquée par l\'admin'),
    ]
    statut = models.CharField(
        "Statut", max_length=20, choices=STATUT, default='DISPONIBLE'
    )
    date_debut = models.DateTimeField("Valide à partir du", default=timezone.now)
    date_fin = models.DateTimeField("Valide jusqu'au", null=True, blank=True)
    active = models.BooleanField("Activée par l'admin", default=True)
    utilisee = models.BooleanField("Utilisée par le chef", default=False)
    date_utilisation = models.DateTimeField("Date d'activation", null=True, blank=True)
    cree_par = models.CharField(max_length=100, default='superadmin')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    motif_revocation = models.TextField(blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Clé d'activation"
        verbose_name_plural = "Clés d'activation"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.cle_visible} — {self.tenant.nom} [{self.label_plan}]"

    def generer_cle_unique(self):
        alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
        nif = (self.tenant.nif or 'XXXX').upper()
        nom = self.tenant.nom.upper()
        empreinte = hashlib.sha256(f"{nif}:{nom}".encode()).hexdigest().upper()
        prefixe = ''.join(c for c in empreinte if c.isalnum())[:4]
        nif_part = nif.replace('-', '').replace('.', '').replace(' ', '')
        nif_suffix = (nif_part + '000000')[-6:]
        periodes = {'ESSAI': '14J', '1MOIS': '1M', 'STARTER': '6M',
                    'BUSINESS': '12M', 'ENTERPRISE': '24M', 'PERSONNALISE': 'PER'}
        periode = periodes.get(self.type_plan, '6M')
        while True:
            alea = ''.join(secrets.choice(alphabet) for _ in range(6))
            code = f"{prefixe}-{nif_suffix}-{periode}-{alea}"
            if not CleActivation.objects.filter(cle_visible=code).exists():
                return code

    def save(self, *args, **kwargs):
        plan_to_duree = {
            'ESSAI': 14, '1MOIS': 30, 'STARTER': 182,
            'BUSINESS': 365, 'ENTERPRISE': 730, 'PERSONNALISE': 0,
        }
        duree_jours = plan_to_duree.get(self.type_plan, 182)
        if not self.date_debut:
            self.date_debut = timezone.now()
        if not self.date_fin and self.type_plan != 'PERSONNALISE':
            self.date_fin = self.date_debut + timedelta(days=duree_jours)
        if not self.cle_visible:
            self.cle_visible = self.generer_cle_unique()
        if not self.empreinte_hmac:
            self.empreinte_hmac = self._hmac(self.cle_visible, self.tenant.sous_domaine)
        self.statut = self._calculer_statut()
        super().save(*args, **kwargs)

    def _calculer_statut(self):
        if not self.active:
            return 'REVOQUEE'
        if self.utilisee:
            if self.date_fin and timezone.localdate() > self.date_fin.date():
                return 'EXPIREE'
            return 'ACTIVE'
        if self.date_fin and timezone.localdate() > self.date_fin.date():
            return 'EXPIREE'
        return 'DISPONIBLE'

    def est_valide(self):
        if self.statut != 'DISPONIBLE':
            return False
        if not self.date_debut or not self.date_fin:
            return False
        now = timezone.now()
        return self.date_debut <= now <= self.date_fin

    def activer(self):
        self.utilisee = True
        self.statut = 'ACTIVE'
        self.date_utilisation = timezone.now()
        self.save()

    @property
    def jours_restants(self):
        if not self.date_fin:
            return 0
        if self.statut not in ('DISPONIBLE', 'ACTIVE'):
            return 0
        delta = self.date_fin.date() - timezone.localdate()
        return max(0, delta.days)

    @classmethod
    def verifier_pour_setup(cls, cle_saisie, sous_domaine):
        now = timezone.now()
        try:
            obj = cls.objects.select_related('tenant').get(
                cle_visible=cle_saisie.strip().upper()
            )
        except cls.DoesNotExist:
            return False, "Clé d'activation invalide.", None
        if obj.statut == 'ACTIVE':
            return False, "Cette clé a déjà été utilisée.", None
        if obj.statut == 'REVOQUEE':
            return False, "Clé désactivée par l'administrateur.", None
        if obj.statut == 'EXPIREE':
            return False, f"Clé expirée le {obj.date_fin.strftime('%d/%m/%Y')}.", None
        if obj.empreinte_hmac:
            expected = cls._hmac(obj.cle_visible, obj.tenant.sous_domaine)
            if not hmac.compare_digest(expected, obj.empreinte_hmac):
                return False, "Intégrité de la clé compromise.", None
        if not obj.date_fin:
            return False, "Clé sans date d'expiration.", None
        if now > obj.date_fin:
            return False, f"Clé expirée le {obj.date_fin.strftime('%d/%m/%Y')}.", None
        if obj.date_debut and now < obj.date_debut:
            return False, f"Clé active à partir du {obj.date_debut.strftime('%d/%m/%Y')}.", None
        return True, f"Clé valide jusqu'au {obj.date_fin.strftime('%d/%m/%Y')}.", obj

    @classmethod
    def creer_essai(cls, tenant, cree_par='superadmin'):
        now = timezone.now()
        cle = cls(
            tenant=tenant,
            type_plan='ESSAI',
            date_debut=now,
            date_fin=now + timedelta(days=14),
            active=True,
            utilisee=True,
            statut='ACTIVE',
            date_utilisation=now,
            cree_par=cree_par,
            notes="Essai gratuit 14 jours — généré automatiquement",
        )
        cle.save()
        return cle

    @classmethod
    def _hmac(cls, cle_visible, sous_domaine):
        secret = settings.SECRET_KEY.encode()
        msg = f"{cle_visible}:{sous_domaine}".encode()
        return hmac.new(secret, msg, hashlib.sha256).hexdigest()

    @property
    def label_plan(self):
        labels = {
            'ESSAI': 'Essai 14j',
            '1MOIS': '1 Mois',
            'STARTER': 'Starter 6m',
            'BUSINESS': 'Business 12m',
            'ENTERPRISE': 'Enterprise 24m',
            'PERSONNALISE': 'Personnalisé',
        }
        return labels.get(self.type_plan, self.type_plan)

    @property
    def est_essai(self):
        return self.type_plan == 'ESSAI'


class AuditCle(models.Model):
    ACTION = [
        ('CREEE', 'Clé créée'),
        ('ACTIVEE', 'Clé activée'),
        ('REVOQUEE', 'Clé révoquée'),
        ('ECHEC', 'Tentative échouée'),
        ('SUSPENDUE', 'Association suspendue'),
        ('REACTIVEE', 'Association réactivée'),
        ('PROLONGEE', 'Clé prolongée'),
    ]
    cle = models.ForeignKey(
        CleActivation, on_delete=models.SET_NULL, null=True, blank=True
    )
    tenant = models.ForeignKey(
        Tenant, on_delete=models.CASCADE,
        related_name='audits', null=True, blank=True
    )
    action = models.CharField(max_length=20, choices=ACTION)
    message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    date_action = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_action']

    def __str__(self):
        nom = self.tenant.nom if self.tenant else 'N/A'
        d = self.date_action.strftime('%d/%m/%Y %H:%M')
        return f"{nom} | {self.action} | {d}"


class ConnexionAudit(models.Model):
    utilisateur_nom = models.CharField("Nom complet", max_length=200, blank=True)
    utilisateur_carte = models.CharField("Carte ID", max_length=50, blank=True)
    tenant = models.ForeignKey(
        Tenant, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Association"
    )
    ip_address = models.GenericIPAddressField("Adresse IP", null=True, blank=True)
    user_agent = models.TextField("User-Agent", blank=True)
    appareil = models.CharField("Appareil", max_length=50, blank=True,
                                help_text="Mobile, Tablette, Desktop")
    marque = models.CharField("Marque", max_length=100, blank=True,
                              help_text="Samsung, Huawei, Tecno, Apple, etc.")
    navigateur = models.CharField("Navigateur", max_length=100, blank=True)
    systeme = models.CharField("Système d'exploitation", max_length=100, blank=True)
    date_connexion = models.DateTimeField("Date de connexion", auto_now_add=True)
    chemin = models.CharField("Chemin", max_length=500, blank=True)

    class Meta:
        verbose_name = "Connexion audit"
        verbose_name_plural = "Audit des connexions"
        ordering = ['-date_connexion']

    def __str__(self):
        return f"{self.utilisateur_nom or 'Anonyme'} | {self.ip_address or 'N/A'} | {self.date_connexion.strftime('%d/%m/%Y %H:%M')}"


class ConfigurationApp(models.Model):
    """Configuration globale de l'application (superadmin)"""
    nom_app = models.CharField("Nom de l'application", max_length=100, default='Twiyungunganye')
    logo = models.ImageField("Logo principal", upload_to='config/', blank=True, null=True,
                              help_text="Logo affiché dans la barre de navigation")
    favicon = models.ImageField("Favicon", upload_to='config/', blank=True, null=True,
                                 help_text="Icône de l'onglet du navigateur")
    email_contact = models.EmailField("Email de contact", blank=True, null=True)
    telephone_contact = models.CharField("Téléphone de contact", max_length=20, blank=True, null=True)
    adresse = models.TextField("Adresse", blank=True, null=True)
    description = models.TextField("Description de l'application", blank=True, null=True,
                                    help_text="Brève description affichée sur la page d'accueil")
    footer_texte = models.TextField("Texte du footer", blank=True, null=True,
                                     help_text="Texte affiché dans le pied de page. Utilisez {annee} pour l'année courante.")
    liens_sociaux = models.TextField("Liens sociaux (JSON)", blank=True, null=True,
                                      help_text='JSON : {"facebook":"url","twitter":"url","linkedin":"url"}')
    hero_slides_json = models.TextField(
        "Slides du carrousel (JSON)", blank=True, null=True,
        help_text='JSON : [{"titre":"...","sous_titre":"...","description":"...","image":"URL"}]'
    )
    slide_image_1 = models.ImageField("Image slide 1", upload_to='slides/', blank=True, null=True,
                                        help_text="Image téléchargée pour le slide 1 (remplace l'URL de l'image dans le JSON)")
    slide_image_2 = models.ImageField("Image slide 2", upload_to='slides/', blank=True, null=True,
                                        help_text="Image téléchargée pour le slide 2")
    slide_image_3 = models.ImageField("Image slide 3", upload_to='slides/', blank=True, null=True,
                                        help_text="Image téléchargée pour le slide 3")
    features_json = models.TextField(
        "Fonctionnalités (JSON)", blank=True, null=True,
        help_text='JSON : [{"icone":"...","titre":"...","description":"...","couleur":"..."}]'
    )
    about_mission = models.TextField(
        "Mission de l'application", blank=True, null=True,
        help_text="Texte décrivant la mission affiché sur la page d'accueil"
    )
    apropos_contenu = models.TextField(
        "Contenu « À propos »", blank=True, null=True,
        help_text="Texte principal de la section À propos sur la page d'accueil. Vous pouvez utiliser du HTML simple."
    )
    date_modification = models.DateTimeField("Dernière modification", auto_now=True)

    class Meta:
        verbose_name = "Configuration de l'application"
        verbose_name_plural = "Configuration de l'application"

    def save(self, *args, **kwargs):
        if not self.pk and ConfigurationApp.objects.exists():
            existing = ConfigurationApp.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom_app or "Configuration de l'application"
