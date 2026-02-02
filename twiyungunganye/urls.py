from django.urls import path
from . import views, pdf_reports, pdf_exports, admin_views


urlpatterns = [
    # Pages publiques
    path('', views.index, name='index'),
    
    # Authentification
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('creer-mot-de-passe/', views.create_password_view, name='create_password'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Gestion des membres
    path('membres/', views.liste_membres, name='liste_membres'),
    path('membres/ajouter/', views.ajouter_membre, name='ajouter_membre'),
    path('membres/<int:pk>/', views.detail_membre, name='detail_membre'),
    path('membres/<int:pk>/modifier/', views.modifier_membre, name='modifier_membre'),

    # Gestion des cotisations imprévus (NOUVEAU)
    path('cotisations-imprevus/', views.liste_cotisations_imprevus, name='liste_cotisations_imprevus'),
    path('cotisations-imprevus/ajouter/', views.ajouter_cotisation_imprevu, name='ajouter_cotisation_imprevu'),
    path('cotisations-imprevus/<int:pk>/modifier/', views.modifier_cotisation_imprevu, name='modifier_cotisation_imprevu'),
    path('mes-cotisations-imprevus/', views.mes_cotisations_imprevus, name='mes_cotisations_imprevus'),
    
    # Gestion des cotisations
    path('cotisations/', views.liste_cotisations, name='liste_cotisations'),
    path('cotisations/ajouter/', views.ajouter_cotisation, name='ajouter_cotisation'),
    
    # Gestion des crédits
    path('credits/', views.liste_credits, name='liste_credits'),
    path('credits/demander/', views.demander_credit, name='demander_credit'),
    path('credits/<int:pk>/', views.detail_credit, name='detail_credit'),
    path('credits/<int:pk>/approuver/', views.approuver_credit, name='approuver_credit'),
    
    # Gestion des remboursements
    path('remboursements/ajouter/', views.ajouter_remboursement, name='ajouter_remboursement'),
    path('remboursements/<int:credit_id>/ajouter/', views.ajouter_remboursement, name='ajouter_remboursement_credit'),
    
    # Gestion des suggestions
    path('suggestions/', views.liste_suggestions, name='liste_suggestions'),
    path('suggestions/soumettre/', views.soumettre_suggestion, name='soumettre_suggestion'),
    
    # Rapports
    path('rapports/', views.rapports, name='rapports'),
    path('rapports/mensuel/generer/', views.generer_rapport_mensuel, name='generer_rapport_mensuel'),
    path('rapports/annuel/generer/', views.generer_rapport_annuel, name='generer_rapport_annuel'),
    path('rapports/mensuel/<int:mois>/<int:annee>/pdf/', pdf_reports.rapport_mensuel_pdf, name='rapport_mensuel_pdf'),
    path('rapports/annuel/<int:annee>/pdf/', pdf_reports.rapport_annuel_pdf, name='rapport_annuel_pdf'),

    # ========== EXPORTS PDF (NOUVEAUX) ==========
    path('exports/cotisations/pdf/', pdf_exports.export_liste_cotisations_pdf, name='export_liste_cotisations_pdf'),
    path('exports/credits/pdf/', pdf_exports.export_liste_credits_pdf, name='export_liste_credits_pdf'),
    path('exports/remboursements/pdf/', pdf_exports.export_liste_remboursements_pdf, name='export_liste_remboursements_pdf'),
    
    # ========== ADMINISTRATION (NOUVEAU) ==========
    path(
    'maintenance/reinitialiser/',
    admin_views.reinitialiser_base_donnees,
    name='reinitialiser_base_donnees'
    ),

]
