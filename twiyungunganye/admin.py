from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    Membre, Cotisation, CotisationImprevu, Credit, Interet, 
    Remboursement, Association, Suggestion
)


class MembreAdmin(BaseUserAdmin):
    """Configuration de l'admin pour le modèle Membre"""
    
    list_display = ['carte_identite', 'nom', 'prenom', 'email', 'telephone', 'est_actif', 'is_admin']
    list_filter = ['tenant', 'est_actif', 'is_admin', 'date_inscription']
    search_fields = ['carte_identite', 'nom', 'prenom', 'email']
    ordering = ['nom', 'prenom']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('carte_identite', 'nom', 'prenom', 'email', 'telephone', 'adresse')
        }),
        ('Statut', {
            'fields': ('est_actif', 'date_inscription')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_admin', 'is_superuser', 'groups', 'user_permissions')
        }),
        ('Mot de passe', {
            'fields': ('password',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('carte_identite', 'nom', 'prenom', 'email', 'password1', 'password2', 'is_admin'),
        }),
    )
    
    filter_horizontal = ('groups', 'user_permissions',)


class CotisationAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Cotisation"""
    
    list_display = ['get_membre_name', 'montant_fbu', 'get_mois_display', 'annee', 'statut', 'date_paiement']
    list_filter = ['tenant', 'statut', 'annee', 'mois']
    search_fields = ['membre__nom', 'membre__prenom', 'membre__carte_identite']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_paiement'
    
    fieldsets = (
        ('Informations de cotisation', {
            'fields': ('membre', 'montant', 'mois', 'annee')
        }),
        ('Statut et paiement', {
            'fields': ('statut', 'date_paiement', 'remarque')
        }),
    )
    
    def get_membre_name(self, obj):
        return obj.membre.get_full_name()
    get_membre_name.short_description = 'Membre'
    
    def montant_fbu(self, obj):
        return format_html('<strong>{} FBU</strong>', obj.montant)
    montant_fbu.short_description = 'Montant'
    
    def get_mois_display(self, obj):
        return obj.get_mois_nom()
    get_mois_display.short_description = 'Mois'


class CotisationImprevuAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle CotisationImprevu"""
    
    list_display = ['get_membre_name', 'montant_fbu', 'get_mois_display', 'annee', 'statut', 'date_paiement']
    list_filter = ['tenant', 'statut', 'annee', 'mois']
    search_fields = ['membre__nom', 'membre__prenom', 'membre__carte_identite']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_paiement'
    
    fieldsets = (
        ('Informations de cotisation imprévus', {
            'fields': ('membre', 'montant', 'mois', 'annee')
        }),
        ('Statut et paiement', {
            'fields': ('statut', 'date_paiement', 'remarque')
        }),
    )
    
    def get_membre_name(self, obj):
        return obj.membre.get_full_name()
    get_membre_name.short_description = 'Membre'
    
    def montant_fbu(self, obj):
        return format_html('<strong style="color: #0066cc;">{} FBU</strong>', obj.montant)
    montant_fbu.short_description = 'Montant'
    
    def get_mois_display(self, obj):
        return obj.get_mois_nom()
    get_mois_display.short_description = 'Mois'


class RemboursementInline(admin.TabularInline):
    """Inline pour afficher les remboursements dans l'admin des crédits"""
    model = Remboursement
    extra = 0
    readonly_fields = ['reste_a_rembourser']


class CreditAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Credit"""
    
    list_display = ['id_credit', 'get_membre_name', 'montant_accorde_fbu', 'get_interet', 'get_total', 'statut', 'date_demande']
    list_filter = ['tenant', 'statut', 'date_demande', 'date_accord']
    search_fields = ['membre__nom', 'membre__prenom', 'membre__carte_identite']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_demande'
    inlines = [RemboursementInline]
    
    fieldsets = (
        ('Informations du crédit', {
            'fields': ('membre', 'montant_demande', 'montant_accorde', 'taux_interet')
        }),
        ('Dates et statut', {
            'fields': ('date_demande', 'date_accord', 'statut', 'nombre_mois_ecoules')
        }),
        ('Remarques', {
            'fields': ('remarque',)
        }),
    )
    
    readonly_fields = ['date_demande']
    
    def get_membre_name(self, obj):
        return obj.membre.get_full_name()
    get_membre_name.short_description = 'Membre'
    
    def montant_accorde_fbu(self, obj):
        return format_html('<strong>{} FBU</strong>', obj.montant_accorde)
    montant_accorde_fbu.short_description = 'Montant accordé'
    
    def get_interet(self, obj):
        interet = obj.calculer_interet()
        return format_html('<span style="color: orange;">{} FBU</span>', interet)
    get_interet.short_description = 'Intérêts'
    
    def get_total(self, obj):
        total = obj.calculer_montant_total()
        return format_html('<span style="font-weight: bold;">{} FBU</span>', total)
    get_total.short_description = 'Total à rembourser'


class InteretAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Interet"""
    
    list_display = ['get_membre_name', 'get_credit_id', 'get_mois_display', 'annee', 'interet_mensuel_fbu', 'interet_cumule_fbu', 'date_calcul']
    list_filter = ['tenant', 'annee', 'mois', 'date_calcul']
    search_fields = ['credit__membre__nom', 'credit__membre__prenom']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_calcul'
    
    def get_membre_name(self, obj):
        return obj.credit.membre.get_full_name()
    get_membre_name.short_description = 'Membre'
    
    def get_credit_id(self, obj):
        return f"Crédit #{obj.credit.id_credit}"
    get_credit_id.short_description = 'Crédit'
    
    def get_mois_display(self, obj):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return mois_noms[obj.mois]
    get_mois_display.short_description = 'Mois'
    
    def interet_mensuel_fbu(self, obj):
        return f"{obj.interet_mensuel} FBU"
    interet_mensuel_fbu.short_description = 'Intérêt mensuel'
    
    def interet_cumule_fbu(self, obj):
        return f"{obj.interet_cumule} FBU"
    interet_cumule_fbu.short_description = 'Intérêt cumulé'


class RemboursementAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Remboursement"""
    
    list_display = ['id_rembourse', 'get_membre_name', 'get_credit_id', 'montant_rembourse_fbu', 'interet_rembourse_fbu', 'reste_a_rembourser_fbu', 'date_remboursement', 'mode_paiement']
    list_filter = ['tenant', 'mode_paiement', 'date_remboursement']
    search_fields = ['credit__membre__nom', 'credit__membre__prenom']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_remboursement'
    
    fieldsets = (
        ('Informations du remboursement', {
            'fields': ('credit', 'montant_rembourse', 'interet_rembourse', 'reste_a_rembourser')
        }),
        ('Détails du paiement', {
            'fields': ('date_remboursement', 'mode_paiement', 'remarque')
        }),
    )
    
    readonly_fields = ['reste_a_rembourser']
    
    def get_membre_name(self, obj):
        return obj.credit.membre.get_full_name()
    get_membre_name.short_description = 'Membre'
    
    def get_credit_id(self, obj):
        return f"Crédit #{obj.credit.id_credit}"
    get_credit_id.short_description = 'Crédit'
    
    def montant_rembourse_fbu(self, obj):
        return f"{obj.montant_rembourse} FBU"
    montant_rembourse_fbu.short_description = 'Montant remboursé'
    
    def interet_rembourse_fbu(self, obj):
        return f"{obj.interet_rembourse} FBU"
    interet_rembourse_fbu.short_description = 'Intérêt remboursé'
    
    def reste_a_rembourser_fbu(self, obj):
        return f"{obj.credit.get_reste_a_rembourser()} FBU"
    reste_a_rembourser_fbu.short_description = 'Reste à rembourser'


class AssociationAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Association"""
    
    list_display = ['nom', 'sigle', 'telephone', 'email', 'montant_cotisation_mensuelle_fbu', 'montant_cotisation_imprevu_fbu']
    list_filter = ['tenant']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'sigle', 'logo')
        }),
        ('Coordonnées', {
            'fields': ('adresse', 'telephone', 'email')
        }),
        ('Configuration des cotisations', {
            'fields': ('montant_cotisation_mensuelle', 'montant_cotisation_imprevu_mensuelle', 'date_creation')
        }),
    )
    
    def montant_cotisation_mensuelle_fbu(self, obj):
        return format_html('<strong>{} FBU</strong>', obj.montant_cotisation_mensuelle)
    montant_cotisation_mensuelle_fbu.short_description = 'Cotisation mensuelle'
    
    def montant_cotisation_imprevu_fbu(self, obj):
        return format_html('<strong style="color: #0066cc;">{} FBU</strong>', obj.montant_cotisation_imprevu_mensuelle)
    montant_cotisation_imprevu_fbu.short_description = 'Cotisation imprévus'
    
    def has_add_permission(self, request):
        # Limiter à une seule association
        if Association.objects.exists():
            return False
        return super().has_add_permission(request)
    
    def has_delete_permission(self, request, obj=None):
        # Seul le superadmin (createsuperuser) peut supprimer l'association.
        return request.user.is_superuser


class SuggestionAdmin(admin.ModelAdmin):
    """Configuration de l'admin pour le modèle Suggestion"""
    
    list_display = ['titre', 'get_membre_name', 'date_soumission', 'statut']
    list_filter = ['tenant', 'statut', 'date_soumission']
    search_fields = ['titre', 'description', 'membre__nom', 'membre__prenom']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if not request.user.is_superuser:
            tenant = getattr(request, 'tenant', None)
            if tenant:
                qs = qs.filter(tenant=tenant)
        return qs
    date_hierarchy = 'date_soumission'
    
    fieldsets = (
        ('Suggestion', {
            'fields': ('membre', 'titre', 'description', 'date_soumission')
        }),
        ('Réponse administrative', {
            'fields': ('statut', 'reponse_admin', 'date_reponse')
        }),
    )
    
    readonly_fields = ['date_soumission', 'membre']
    
    def get_membre_name(self, obj):
        return obj.membre.get_full_name()
    get_membre_name.short_description = 'Membre'


# Enregistrement des modèles dans l'admin
admin.site.register(Membre, MembreAdmin)
admin.site.register(Cotisation, CotisationAdmin)
admin.site.register(CotisationImprevu, CotisationImprevuAdmin)
admin.site.register(Credit, CreditAdmin)
admin.site.register(Interet, InteretAdmin)
admin.site.register(Remboursement, RemboursementAdmin)
admin.site.register(Association, AssociationAdmin)
admin.site.register(Suggestion, SuggestionAdmin)

# Personnalisation de l'interface d'administration
admin.site.site_header = "Administration - Gestion des Cotisations"
admin.site.site_title = "Gestion des Cotisations"
admin.site.index_title = "Tableau de bord"
