from django.contrib import admin
from .models import Tenant, CleActivation, AuditCle


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['nom', 'sous_domaine', 'telephone', 'email', 'actif', 'date_creation']
    list_filter = ['actif']
    search_fields = ['nom', 'sous_domaine', 'email']
    fieldsets = (
        ('Identification', {
            'fields': ('nom', 'sigle', 'sous_domaine', 'logo', 'actif')
        }),
        ('Coordonnées', {
            'fields': ('province', 'commune', 'quartier', 'avenue', 'numero', 'boite_postale', 'telephone', 'email')
        }),
        ('Configuration des cotisations', {
            'fields': ('montant_cotisation_mensuelle', 'montant_cotisation_imprevu_mensuelle', 'date_creation')
        }),
    )


@admin.register(CleActivation)
class CleActivationAdmin(admin.ModelAdmin):
    list_display = ['cle_visible', 'tenant', 'type_plan', 'statut', 'date_debut', 'date_fin', 'utilisee']
    list_filter = ['statut', 'type_plan', 'active']
    search_fields = ['cle_visible', 'tenant__nom', 'tenant__sous_domaine']
    date_hierarchy = 'date_creation'
    raw_id_fields = ['tenant']


@admin.register(AuditCle)
class AuditCleAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'action', 'date_action', 'ip_address']
    list_filter = ['action', 'date_action']
    search_fields = ['tenant__nom', 'message']
