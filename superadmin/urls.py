from django.urls import path
from . import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('tenants/', views.tenant_liste, name='tenant_liste'),
    path('tenants/creer/', views.tenant_creer, name='tenant_creer'),
    path('tenants/<int:pk>/', views.tenant_detail, name='tenant_detail'),
    path('tenants/<int:pk>/modifier/', views.tenant_modifier, name='tenant_modifier'),
    path('tenants/<int:pk>/toggle/', views.tenant_toggle, name='tenant_toggle'),
    path('tenants/<int:pk>/cle/', views.cle_generer, name='cle_generer'),
    path('cles/generer/', views.generer_cle, name='generer_cle'),
    path('api/tenant-keys/<int:pk>/', views.tenant_keys_check, name='tenant_keys_check'),
    path('cles/', views.cle_liste, name='cle_liste'),
    path('cles/<int:pk>/', views.cle_detail, name='cle_detail'),
    path('cles/<int:pk>/revoquer/', views.cle_revoquer, name='cle_revoquer'),

    # ========== GESTION DES UTILISATEURS ==========
    path('membres/', views.membre_liste, name='membre_liste'),
    path('membres/creer/', views.membre_creer, name='membre_creer'),
    path('membres/<int:pk>/modifier/', views.membre_modifier, name='membre_modifier'),
    path('membres/<int:pk>/supprimer/', views.membre_supprimer, name='membre_supprimer'),
    path('membres/<int:pk>/reset-password/', views.membre_reset_password, name='membre_reset_password'),

    # ========== AUDIT DES CONNEXIONS ==========
    path('connexions/', views.connexion_liste, name='connexion_liste'),

    # ========== SUPPRESSION D'ASSOCIATION ==========
    path('tenants/<int:pk>/supprimer/', views.tenant_supprimer, name='tenant_supprimer'),

    path('licence-expiree/', views.licence_expiree, name='licence_expiree'),
    path('saisir-cle-payante/', views.saisir_cle_payante, name='saisir_cle_payante'),

    # ========== API (AJAX) ==========
    path('api/lookup-nif/', views.ajax_lookup_nif, name='ajax_lookup_nif'),

    # ========== PROFIL SUPERADMIN ==========
    path('profil/', views.profil, name='profil'),

    # ========== CONFIGURATION DE L'APPLICATION ==========
    path('configuration/', views.configurer_app, name='configurer_app'),

    # ========== EXTRACTION DES DONNÉES ==========
    path('extraction-donnees/', views.extraction_donnees, name='extraction_donnees'),
]
