from django.urls import path
from . import views, pdf_reports, pdf_exports, pdf_exports_extended, excel_exports, excel_imports, admin_views, gestion_acces_views, pdf_fiche_membre, pdf_fiche_inscription, pdf_demande_credit
from . import views_additions


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
    path('membres/<int:pk>/supprimer/', views.supprimer_membre, name='supprimer_membre'),
    path('membres/<int:pk>/fiche-pdf/', pdf_fiche_membre.fiche_membre_pdf, name='fiche_membre_pdf'),

    # Gestion des cotisations imprévus (NOUVEAU)
    path('cotisations-imprevus/', views.liste_cotisations_imprevus, name='liste_cotisations_imprevus'),
    path('cotisations-imprevus/ajouter/', views.ajouter_cotisation_imprevu, name='ajouter_cotisation_imprevu'),
    path('cotisations-imprevus/<int:pk>/modifier/', views.modifier_cotisation_imprevu, name='modifier_cotisation_imprevu'),
    path('cotisations-imprevus/<int:pk>/supprimer/', views.supprimer_cotisation_imprevu, name='supprimer_cotisation_imprevu'),
    path('mes-cotisations-imprevus/', views.mes_cotisations_imprevus, name='mes_cotisations_imprevus'),
    
    # Gestion des cotisations
    path('cotisations/', views.liste_cotisations, name='liste_cotisations'),
    path('cotisations/ajouter/', views.ajouter_cotisation, name='ajouter_cotisation'),
    path('cotisations/<int:pk>/modifier/', views.modifier_cotisation, name='modifier_cotisation'),
    path('cotisations/<int:pk>/supprimer/', views.supprimer_cotisation, name='supprimer_cotisation'),
    path('cotisations/encaisser/', views.encaisser_cotisation, name='encaisser_cotisation'),
    
    # Gestion des crédits
    path('credits/', views.liste_credits, name='liste_credits'),
    path('credits/demander/', views.demander_credit, name='demander_credit'),
    path('credits/ajouter-direct/', views.ajouter_credit_direct, name='ajouter_credit_direct'),
    path('credits/<int:pk>/', views.detail_credit, name='detail_credit'),
    path('credits/<int:pk>/approuver/', views.approuver_credit, name='approuver_credit'),
    path('credits/<int:pk>/modifier/', views.modifier_credit, name='modifier_credit'),
    path('credits/<int:pk>/supprimer/', views.supprimer_credit, name='supprimer_credit'),
    
    # Gestion des remboursements
    path('remboursements/ajouter/', views.ajouter_remboursement, name='ajouter_remboursement'),
    path('remboursements/<int:credit_id>/ajouter/', views.ajouter_remboursement, name='ajouter_remboursement_credit'),
    path('remboursements/', views.liste_remboursements, name='liste_remboursements'),
    path('remboursements/<int:pk>/modifier/', views.modifier_remboursement, name='modifier_remboursement'),
    path('remboursements/<int:pk>/supprimer/', views.supprimer_remboursement, name='supprimer_remboursement'),
    path('mes-remboursements/', views.mes_remboursements, name='mes_remboursements'),
    
    # Intérêts
    path('interets/', views.liste_interets, name='liste_interets'),
    path('interets/<int:credit_id>/generer/', views.generer_interets, name='generer_interets'),
    path('interets/generer-tous/', views.generer_tous_interets, name='generer_tous_interets'),
    path('interets/<int:pk>/rembourser/', views.ajouter_interet_rembourse, name='ajouter_interet_rembourse'),
    path('interets/<int:pk>/modifier-remboursement/', views.modifier_interet_rembourse, name='modifier_interet_rembourse'),
    path('interets/<int:pk>/date-remboursement/', views.modifier_date_remboursement_interet, name='modifier_date_remboursement_interet'),
    path('mes-interets/', views.mes_interets, name='mes_interets'),
    
    # Pénalités cotisations
    path('penalites/', views.liste_penalites, name='liste_penalites'),
    path('penalites/pdf/', pdf_reports.penalites_pdf, name='penalites_pdf'),
    path('penalites/generer/', views.generer_penalites, name='generer_penalites'),
    path('penalites/membres-non-payes/', views.membres_non_payes, name='membres_non_payes'),
    path('penalites/<int:pk>/payer/', views.marquer_penalite_payee, name='marquer_penalite_payee'),
    path('penalites/<int:pk>/paiement/', views.payer_penalite, name='payer_penalite'),
    path('penalites/<int:pk>/supprimer/', views.supprimer_penalite, name='supprimer_penalite'),
    path('penalites/<int:pk>/payer-integralement/', views.payer_integralement_penalite, name='payer_integralement_penalite'),
    path('penalites/<int:pk>/date-paiement/', views.modifier_date_paiement_penalite, name='modifier_date_paiement_penalite'),
    path('penalites/<int:pk>/modifier-paiement/', views.modifier_montant_paye_penalite, name='modifier_montant_paye_penalite'),
    path('mes-penalites/', views.mes_penalites, name='mes_penalites'),
    
    # Gestion des suggestions
    path('suggestions/', views.liste_suggestions, name='liste_suggestions'),
    path('suggestions/soumettre/', views.soumettre_suggestion, name='soumettre_suggestion'),
    path('suggestions/<int:pk>/modifier/', views.modifier_suggestion, name='modifier_suggestion'),
    path('suggestions/<int:pk>/repondre/', views.repondre_suggestion, name='repondre_suggestion'),
    
    # Notifications
    path('notifications/', views.notifications_liste, name='notifications_liste'),
    path('notifications/<int:pk>/lire/', views.marquer_notification_lue, name='marquer_notification_lue'),
    path('notifications/tout-lire/', views.marquer_tout_lu, name='marquer_tout_lu'),
    
    # Dépenses de l'association
    path('depenses/', views.liste_depenses, name='liste_depenses'),
    path('depenses/ajouter/', views.ajouter_depense, name='ajouter_depense'),

    # Association profil
    path('association/profil/', views.association_profil, name='association_profil'),
    path('association/modifier/', views.modifier_association, name='modifier_association'),
    
    # Profil dirigeant
    path('mon-profil/modifier/', views.modifier_profil_dirigeant, name='modifier_profil_dirigeant'),
    
    # Gestion des groupes d'accès
    path('acces/groupes/', gestion_acces_views.liste_groupes, name='liste_groupes'),
    path('acces/groupes/creer/', gestion_acces_views.creer_groupe, name='creer_groupe'),
    path('acces/groupes/<int:pk>/modifier/', gestion_acces_views.modifier_groupe, name='modifier_groupe'),
    path('acces/groupes/<int:pk>/supprimer/', gestion_acces_views.supprimer_groupe, name='supprimer_groupe'),
    
    # Rapports
    path('rapports/', views.rapports, name='rapports'),
    path('rapports/mensuel/', views.page_rapport_mensuel, name='page_rapport_mensuel'),
    path('rapports/annuel/', views.page_rapport_annuel, name='page_rapport_annuel'),
    path('rapports/exports/<str:export_type>/', views.page_export_filtre, name='page_export_filtre'),
    path('rapports/mensuel/generer/', views.generer_rapport_mensuel, name='generer_rapport_mensuel'),
    path('rapports/mensuel/generer-excel/', views.generer_rapport_mensuel_excel, name='generer_rapport_mensuel_excel'),
    path('rapports/annuel/generer/', views.generer_rapport_annuel, name='generer_rapport_annuel'),
    path('rapports/periode/', views.page_rapport_periode, name='page_rapport_periode'),
    path('rapports/periode/pdf/<int:mois_debut>/<int:annee_debut>/<int:mois_fin>/<int:annee_fin>/', pdf_reports.rapport_periode_pdf, name='rapport_periode_pdf'),
    path('rapports/mensuel/<int:mois>/<int:annee>/pdf/', pdf_reports.rapport_mensuel_pdf, name='rapport_mensuel_pdf'),
    path('rapports/annuel/<int:annee>/pdf/', pdf_reports.rapport_annuel_pdf, name='rapport_annuel_pdf'),

    # ========== EXPORTS PDF (NOUVEAUX) ==========
    path('exports/cotisations/pdf/', pdf_exports.export_liste_cotisations_pdf, name='export_liste_cotisations_pdf'),
    path('exports/credits/pdf/', pdf_exports.export_liste_credits_pdf, name='export_liste_credits_pdf'),
    path('exports/credits/restants/pdf/', pdf_exports.export_credits_restants_pdf, name='export_credits_restants_pdf'),
    path('exports/remboursements/pdf/', pdf_exports.export_liste_remboursements_pdf, name='export_liste_remboursements_pdf'),
    
    # ========== EXPORTS PDF EXTENDED ==========
    path('exports/membres/pdf/', pdf_exports_extended.export_membres_pdf, name='export_membres_pdf'),
    path('exports/cotisations-imprevus/pdf/', pdf_exports_extended.export_cotisations_imprevus_pdf, name='export_cotisations_imprevus_pdf'),
    path('exports/assistances/pdf/', pdf_exports_extended.export_assistances_pdf, name='export_assistances_pdf'),
    path('exports/interets/pdf/', pdf_exports_extended.export_interets_pdf, name='export_interets_pdf'),
    path('exports/interets/restants/pdf/', pdf_exports_extended.export_interets_restants_pdf, name='export_interets_restants_pdf'),
    
    # ========== EXPORTS EXCEL ==========
    path('exports/membres/excel/', excel_exports.export_membres_excel, name='export_membres_excel'),
    path('imports/membres/excel/', excel_imports.import_membres_excel, name='import_membres_excel'),
    path('exports/cotisations/excel/', excel_exports.export_cotisations_excel, name='export_cotisations_excel'),
    path('exports/cotisations-imprevus/excel/', excel_exports.export_cotisations_imprevus_excel, name='export_cotisations_imprevus_excel'),
    path('exports/assistances/excel/', excel_exports.export_assistances_excel, name='export_assistances_excel'),
    path('exports/interets/excel/', excel_exports.export_interets_excel, name='export_interets_excel'),
    path('exports/penalites/excel/', excel_exports.export_penalites_excel, name='export_penalites_excel'),
    path('exports/remboursements/excel/', excel_exports.export_remboursements_excel, name='export_remboursements_excel'),

    # ========== FICHE DE PAIEMENT & QR CODE ==========
    path('fiche-inscription/', pdf_fiche_inscription.fiche_inscription_pdf, name='fiche_inscription_pdf'),
    path('demande-credit/', pdf_demande_credit.demande_credit_pdf, name='demande_credit_pdf'),
    path('fiche-paiement/', views.fiche_paiement_pdf, name='fiche_paiement_pdf'),
    path('fiche-paiement/<int:pk>/', views.fiche_paiement_pdf, name='fiche_paiement_pdf_pk'),
    path('qr-code-association/', views.qr_code_association, name='qr_code_association'),

    path('exports/rapport-mensuel/<int:mois>/<int:annee>/excel/', excel_exports.export_rapport_mensuel_excel, name='export_rapport_mensuel_excel'),
    
    # ========== ADMINISTRATION (NOUVEAU) ==========
    path(
    'maintenance/reinitialiser/',
    admin_views.reinitialiser_base_donnees,
    name='reinitialiser_base_donnees'
    ),

]
