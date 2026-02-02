from .views_additions import approuver_credit_strict as approuver_credit
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from .models import (
    Membre, Cotisation, CotisationImprevu, Credit, Interet, 
    Remboursement, Association, Suggestion
)
from .forms import (
    LoginForm, MembrePasswordCreationForm, MembreForm, CotisationForm,
    CotisationImprevuForm, CreditDemandeForm, CreditApprovalForm, 
    RemboursementForm, SuggestionForm, RapportMensuelForm, RapportAnnuelForm, 
    MembrePasswordChangeForm
)


# Utilitaires pour vérifier les permissions
def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_gestionnaire)


def is_admin_only(user):
    return user.is_authenticated and user.is_admin


# Vue pour la page d'accueil publique
def index(request):
    """Page d'accueil publique"""
    association = Association.get_association()
    context = {
        'association': association,
    }
    return render(request, 'twiyungunganye/index.html', context)


# Vues d'authentification
def login_view(request):
    """Vue de connexion"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()} !')
            return redirect('dashboard')
    else:
        form = LoginForm()
    
    return render(request, 'twiyungunganye/login.html', {'form': form})


def create_password_view(request):
    """Vue pour créer le premier mot de passe"""
    if request.method == 'POST':
        form = MembrePasswordCreationForm(request.POST)
        if form.is_valid():
            carte_identite = form.cleaned_data['carte_identite']
            password = form.cleaned_data['password1']
            
            membre = Membre.objects.get(carte_identite=carte_identite)
            membre.set_password(password)
            membre.save()
            
            messages.success(request, 'Votre mot de passe a été créé avec succès. Vous pouvez maintenant vous connecter.')
            return redirect('login')
    else:
        form = MembrePasswordCreationForm()
    
    return render(request, 'twiyungunganye/create_password.html', {'form': form})


def logout_view(request):
    """Vue de déconnexion"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('index')


# Dashboard - NOUVELLE VERSION AVEC 3 DERNIERS MOIS + CAPITAL
@login_required
def dashboard(request):
    """
    Tableau de bord avec statistiques des 3 derniers mois
    pour cotisations, crédits et imprévus sociaux + Capital de l'association
    """
    # Date actuelle
    now = datetime.now()
    mois_actuel = now.month
    annee_actuelle = now.year
    
    # Noms des mois en français
    MOIS_NOMS = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
        9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }
    
    # Calculer les 3 derniers mois
    date_actuelle = datetime(annee_actuelle, mois_actuel, 1)
    mois_precedent_1 = date_actuelle - relativedelta(months=1)
    mois_precedent_2 = date_actuelle - relativedelta(months=2)
    
    mois_liste = [mois_precedent_2, mois_precedent_1, date_actuelle]
    
    # ==========================================
    # COTISATIONS RÉGULIÈRES - 3 derniers mois
    # ==========================================
    cotisations_3_derniers_mois = []
    for date_mois in mois_liste:
        cotisations_mois = Cotisation.objects.filter(
            mois=date_mois.month,
            annee=date_mois.year,
            statut='PAYE'
        )
        
        total = cotisations_mois.aggregate(
            montant_total=Sum('montant')
        )['montant_total'] or 0
        
        nombre = cotisations_mois.count()
        
        cotisations_3_derniers_mois.append({
            'mois_nom': MOIS_NOMS[date_mois.month],
            'mois': date_mois.month,
            'annee': date_mois.year,
            'montant': total,
            'nombre_paiements': nombre
        })
    
    # ==========================================
    # CRÉDITS - 3 derniers mois
    # ==========================================
    credits_3_derniers_mois = []
    for date_mois in mois_liste:
        # Crédits approuvés durant ce mois
        credits_mois = Credit.objects.filter(
            date_accord__month=date_mois.month,
            date_accord__year=date_mois.year,
            statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
        )
        
        total = credits_mois.aggregate(
            montant_total=Sum('montant_accorde')
        )['montant_total'] or 0
        
        nombre = credits_mois.count()
        
        credits_3_derniers_mois.append({
            'mois_nom': MOIS_NOMS[date_mois.month],
            'mois': date_mois.month,
            'annee': date_mois.year,
            'montant': total,
            'nombre_credits': nombre
        })
    
    # ==========================================
    # IMPRÉVUS SOCIAUX - 3 derniers mois
    # ==========================================
    imprevus_3_derniers_mois = []
    for date_mois in mois_liste:
        # Imprévus payés durant ce mois
        imprevus_mois = CotisationImprevu.objects.filter(
            mois=date_mois.month,
            annee=date_mois.year,
            statut='PAYE'
        )
        
        # Calculer le total des montants
        total = imprevus_mois.aggregate(
            montant_total=Sum('montant')
        )['montant_total'] or 0
        
        nombre = imprevus_mois.count()
        
        imprevus_3_derniers_mois.append({
            'mois_nom': MOIS_NOMS[date_mois.month],
            'mois': date_mois.month,
            'annee': date_mois.year,
            'montant': total,
            'nombre_imprevus': nombre
        })
    
    # ==========================================
    # TOTAUX DU MOIS ACTUEL
    # ==========================================
    # Total cotisations mois actuel
    total_cotisations_mois_actuel = Cotisation.objects.filter(
        mois=mois_actuel,
        annee=annee_actuelle,
        statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or 0
    
    # Total crédits mois actuel
    total_credits_mois_actuel = Credit.objects.filter(
        date_accord__month=mois_actuel,
        date_accord__year=annee_actuelle,
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0
    
    # Total imprévus mois actuel
    total_imprevus_mois_actuel = CotisationImprevu.objects.filter(
        mois=mois_actuel,
        annee=annee_actuelle,
        statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or 0
    
    # Total général
    total_general_mois_actuel = (
        total_cotisations_mois_actuel + 
        total_credits_mois_actuel + 
        total_imprevus_mois_actuel
    )
    
    # ==========================================
    # CAPITAL DE L'ASSOCIATION
    # ==========================================
    # Total des cotisations imprévus (tous les temps)
    total_imprevus_capital = CotisationImprevu.objects.filter(
        statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or 0
    
    # Total des remboursements reçus (tous les temps)
    total_remboursements = Remboursement.objects.all().aggregate(
        Sum('montant_rembourse')
    )['montant_rembourse__sum'] or 0
    
    # Capital total de l'association = Imprévus + Remboursements
    capital_association = total_imprevus_capital + total_remboursements
    
    # ==========================================
    # STATISTIQUES GLOBALES
    # ==========================================
    total_membres = Membre.objects.filter(est_actif=True).count()
    
    # Solde de la caisse (exemple simplifié)
    total_entrees = Cotisation.objects.filter(
        statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or 0
    
    total_sorties = Credit.objects.filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0
    
    solde_caisse = total_entrees - total_sorties
    
    # Taux de paiement du mois actuel
    cotisations_attendues = total_membres
    cotisations_payees = Cotisation.objects.filter(
        mois=mois_actuel,
        annee=annee_actuelle,
        statut='PAYE'
    ).count()
    
    taux_paiement = (cotisations_payees / cotisations_attendues * 100) if cotisations_attendues > 0 else 0
    
    # ==========================================
    # DERNIÈRES ACTIVITÉS (pour admins)
    # ==========================================
    dernieres_cotisations = Cotisation.objects.filter(
        statut='PAYE'
    ).select_related('membre').order_by('-date_paiement')[:10]
    
    derniers_credits = Credit.objects.all().select_related('membre').order_by('-date_demande')[:10]
    
    # ==========================================
    # STATISTIQUES PERSONNELLES
    # ==========================================
    mes_cotisations = Cotisation.objects.filter(
        membre=request.user,
        statut='PAYE'
    )
    
    mes_credits = Credit.objects.filter(membre=request.user)
    mes_credits_actifs = mes_credits.filter(statut='EN_COURS')
    
    context = {
        # Date actuelle
        'mois_actuel': mois_actuel,
        'annee_actuelle': annee_actuelle,
        'mois_actuel_nom': MOIS_NOMS[mois_actuel],
        
        # Données des 3 derniers mois
        'cotisations_3_derniers_mois': cotisations_3_derniers_mois,
        'credits_3_derniers_mois': credits_3_derniers_mois,
        'imprevus_3_derniers_mois': imprevus_3_derniers_mois,
        
        # Totaux du mois actuel
        'total_cotisations_mois_actuel': total_cotisations_mois_actuel,
        'total_credits_mois_actuel': total_credits_mois_actuel,
        'total_imprevus_mois_actuel': total_imprevus_mois_actuel,
        'total_general_mois_actuel': total_general_mois_actuel,
        
        # Statistiques globales
        'total_membres': total_membres,
        'solde_caisse': solde_caisse,
        'taux_paiement': taux_paiement,
        
        # Capital de l'association
        'total_imprevus_capital': total_imprevus_capital,
        'total_remboursements': total_remboursements,
        'capital_association': capital_association,
        
        # Dernières activités
        'dernieres_cotisations': dernieres_cotisations,
        'derniers_credits': derniers_credits,
        
        # Statistiques personnelles
        'mes_cotisations': mes_cotisations,
        'mes_credits': mes_credits,
        'mes_credits_actifs': mes_credits_actifs,
    }
    
    return render(request, 'twiyungunganye/dashboard.html', context)


# Gestion des membres
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_membres(request):
    """Liste de tous les membres"""
    membres = Membre.objects.all().order_by('nom', 'prenom')
    context = {
        'membres': membres,
    }
    return render(request, 'twiyungunganye/membres/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_membre(request):
    """Ajouter un nouveau membre"""
    if request.method == 'POST':
        form = MembreForm(request.POST)
        if form.is_valid():
            membre = form.save()
            messages.success(request, f'Le membre {membre.get_full_name()} a été ajouté avec succès.')
            return redirect('liste_membres')
    else:
        form = MembreForm()
    
    return render(request, 'twiyungunganye/membres/formulaire.html', {'form': form, 'action': 'Ajouter'})


@login_required
@user_passes_test(is_admin_only)
def modifier_membre(request, pk):
    """Modifier un membre existant"""
    membre = get_object_or_404(Membre, pk=pk)
    
    if request.method == 'POST':
        form = MembreForm(request.POST, instance=membre)
        if form.is_valid():
            form.save()
            messages.success(request, f'Le membre {membre.get_full_name()} a été modifié avec succès.')
            return redirect('liste_membres')
    else:
        form = MembreForm(instance=membre)
    
    return render(request, 'twiyungunganye/membres/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'membre': membre
    })


@login_required
def detail_membre(request, pk):
    """Afficher les détails d'un membre"""
    membre = get_object_or_404(Membre, pk=pk)
    
    # Vérifier les permissions
    if not (request.user.is_admin or request.user.is_gestionnaire or request.user.pk == pk):
        messages.error(request, "Vous n'avez pas la permission de voir ce profil.")
        return redirect('dashboard')
    
    cotisations = Cotisation.objects.filter(membre=membre).order_by('-annee', '-mois')
    cotisations_imprevus = CotisationImprevu.objects.filter(membre=membre).order_by('-annee', '-mois')
    credits = Credit.objects.filter(membre=membre).order_by('-date_demande')
    suggestions = Suggestion.objects.filter(membre=membre).order_by('-date_soumission')
    
    total_cotisations = membre.get_total_cotisations()
    total_cotisations_imprevus = membre.get_total_cotisations_imprevus()
    
    context = {
        'membre': membre,
        'cotisations': cotisations,
        'cotisations_imprevus': cotisations_imprevus,
        'credits': credits,
        'suggestions': suggestions,
        'total_cotisations': total_cotisations,
        'total_cotisations_imprevus': total_cotisations_imprevus,
    }
    
    return render(request, 'twiyungunganye/membres/detail.html', context)


# Gestion des cotisations régulières
@login_required
def liste_cotisations(request):
    """Liste des cotisations régulières"""
    if request.user.is_admin or request.user.is_gestionnaire:
        cotisations = Cotisation.objects.all().order_by('-annee', '-mois')
    else:
        cotisations = Cotisation.objects.filter(membre=request.user).order_by('-annee', '-mois')
    
    context = {
        'cotisations': cotisations,
    }
    return render(request, 'twiyungunganye/cotisations/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_cotisation(request):
    """Ajouter une nouvelle cotisation régulière"""
    if request.method == 'POST':
        form = CotisationForm(request.POST)
        if form.is_valid():
            cotisation = form.save()
            messages.success(request, f'Cotisation enregistrée pour {cotisation.membre.get_full_name()}.')
            return redirect('liste_cotisations')
    else:
        form = CotisationForm()
    
    return render(request, 'twiyungunganye/cotisations/formulaire.html', {'form': form, 'action': 'Ajouter'})


# Gestion des cotisations imprévus
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_cotisations_imprevus(request):
    """Liste de toutes les cotisations pour imprévus/cas sociaux"""
    cotisations_imprevus = CotisationImprevu.objects.all().select_related('membre').order_by('-annee', '-mois')
    
    # Statistiques
    stats = cotisations_imprevus.aggregate(
        total=Sum('montant'),
        nombre_total=Count('id_cotisation_imprevu'),
        payees=Count('id_cotisation_imprevu', filter=Q(statut='PAYE')),
        en_attente=Count('id_cotisation_imprevu', filter=Q(statut='EN_ATTENTE')),
        en_retard=Count('id_cotisation_imprevu', filter=Q(statut='RETARD'))
    )
    
    context = {
        'cotisations_imprevus': cotisations_imprevus,
        'stats': stats,
    }
    
    return render(request, 'twiyungunganye/cotisations_imprevus/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_cotisation_imprevu(request):
    """Ajouter une nouvelle cotisation pour imprévus"""
    if request.method == 'POST':
        form = CotisationImprevuForm(request.POST)
        if form.is_valid():
            cotisation = form.save()
            messages.success(
                request, 
                f'Cotisation imprévus de {cotisation.membre.get_full_name()} enregistrée avec succès.'
            )
            return redirect('liste_cotisations_imprevus')
    else:
        form = CotisationImprevuForm()
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form,
        'action': 'Ajouter'
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_cotisation_imprevu(request, pk):
    """Modifier une cotisation imprévus existante"""
    cotisation = get_object_or_404(CotisationImprevu, pk=pk)
    
    if request.method == 'POST':
        form = CotisationImprevuForm(request.POST, instance=cotisation)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cotisation imprévus modifiée avec succès.')
            return redirect('liste_cotisations_imprevus')
    else:
        form = CotisationImprevuForm(instance=cotisation)
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'cotisation': cotisation
    })


@login_required
def mes_cotisations_imprevus(request):
    """Voir les cotisations imprévus du membre connecté"""
    cotisations = CotisationImprevu.objects.filter(
        membre=request.user
    ).order_by('-annee', '-mois')
    
    total_paye = request.user.get_total_cotisations_imprevus()
    
    context = {
        'cotisations_imprevus': cotisations,
        'total_paye': total_paye,
    }
    
    return render(request, 'twiyungunganye/cotisations_imprevus/mes_cotisations.html', context)


# Gestion des crédits
@login_required
def liste_credits(request):
    """Liste des crédits"""
    if request.user.is_admin or request.user.is_gestionnaire:
        credits = Credit.objects.all().order_by('-date_demande')
    else:
        credits = Credit.objects.filter(membre=request.user).order_by('-date_demande')
    
    context = {
        'credits': credits,
    }
    return render(request, 'twiyungunganye/credits/liste.html', context)


@login_required
def demander_credit(request):
    """Demander un crédit"""
    # Vérifier d'abord si le membre a des cotisations
    total_cotisations = request.user.get_total_cotisations()
    
    if total_cotisations <= 0:
        messages.error(
            request,
            "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée."
        )
        return redirect('liste_credits')
    
    # Vérifier le montant minimum (3 mois)
    association = Association.get_association()
    if association:
        montant_minimum = association.montant_cotisation_mensuelle * 3
        if total_cotisations < montant_minimum:
            messages.error(
                request,
                f"Vous devez avoir au moins {montant_minimum} FBU de cotisations payées "
                f"(équivalent à 3 mois). Vous avez actuellement {total_cotisations} FBU."
            )
            return redirect('liste_credits')
    
    if request.method == 'POST':
        form = CreditDemandeForm(request.POST, membre=request.user)
        if form.is_valid():
            credit = form.save(commit=False)
            credit.membre = request.user
            credit.montant_accorde = 0  # Sera défini par l'admin
            credit.save()
            messages.success(request, 'Votre demande de crédit a été soumise avec succès.')
            return redirect('liste_credits')
    else:
        form = CreditDemandeForm(membre=request.user)
    
    context = {
        'form': form,
        'total_cotisations': total_cotisations,
    }
    
    return render(request, 'twiyungunganye/credits/demande.html', context)


@login_required
def detail_credit(request, pk):
    """Afficher les détails d'un crédit"""
    credit = get_object_or_404(Credit, pk=pk)
    
    # Vérifier les permissions
    if not (request.user.is_admin or request.user.is_gestionnaire or credit.membre == request.user):
        messages.error(request, "Vous n'avez pas la permission de voir ce crédit.")
        return redirect('liste_credits')
    
    remboursements = Remboursement.objects.filter(credit=credit).order_by('-date_remboursement')
    
    context = {
        'credit': credit,
        'remboursements': remboursements,
    }
    
    return render(request, 'twiyungunganye/credits/detail.html', context)


# Gestion des remboursements
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_remboursement(request, credit_id=None):
    """Ajouter un remboursement"""
    if request.method == 'POST':
        form = RemboursementForm(request.POST)
        if form.is_valid():
            remboursement = form.save()
            messages.success(request, f'Remboursement enregistré pour {remboursement.credit.membre.get_full_name()}.')
            return redirect('detail_credit', pk=remboursement.credit.pk)
    else:
        initial = {}
        if credit_id:
            initial['credit'] = credit_id
        form = RemboursementForm(initial=initial)
    
    return render(request, 'twiyungunganye/remboursements/formulaire.html', {'form': form})


# Gestion des suggestions
@login_required
def liste_suggestions(request):
    """Liste des suggestions"""
    if request.user.is_admin or request.user.is_gestionnaire:
        suggestions = Suggestion.objects.all().order_by('-date_soumission')
    else:
        suggestions = Suggestion.objects.filter(membre=request.user).order_by('-date_soumission')
    
    context = {
        'suggestions': suggestions,
    }
    return render(request, 'twiyungunganye/suggestions/liste.html', context)


@login_required
def soumettre_suggestion(request):
    """Soumettre une suggestion"""
    if request.method == 'POST':
        form = SuggestionForm(request.POST)
        if form.is_valid():
            suggestion = form.save(commit=False)
            suggestion.membre = request.user
            suggestion.save()
            messages.success(request, 'Votre suggestion a été soumise avec succès.')
            return redirect('liste_suggestions')
    else:
        form = SuggestionForm()
    
    return render(request, 'twiyungunganye/suggestions/formulaire.html', {'form': form})


# Rapports
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapports(request):
    """Page des rapports"""
    form_mensuel = RapportMensuelForm()
    form_annuel = RapportAnnuelForm()
    
    context = {
        'form_mensuel': form_mensuel,
        'form_annuel': form_annuel,
    }
    
    return render(request, 'twiyungunganye/rapports/index.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def generer_rapport_mensuel(request):
    """Générer un rapport mensuel"""
    if request.method == 'POST':
        form = RapportMensuelForm(request.POST)
        if form.is_valid():
            mois = int(form.cleaned_data['mois'])
            annee = int(form.cleaned_data['annee'])
            
            # Rediriger vers la vue de génération PDF
            return redirect('rapport_mensuel_pdf', mois=mois, annee=annee)
    
    return redirect('rapports')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def generer_rapport_annuel(request):
    """Générer un rapport annuel"""
    if request.method == 'POST':
        form = RapportAnnuelForm(request.POST)
        if form.is_valid():
            annee = int(form.cleaned_data['annee'])
            
            # Rediriger vers la vue de génération PDF
            return redirect('rapport_annuel_pdf', annee=annee)
    
    return redirect('rapports')
