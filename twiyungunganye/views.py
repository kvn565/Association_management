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


# Dashboard
@login_required
def dashboard(request):
    """Tableau de bord principal"""
    user = request.user
    association = Association.get_association()
    
    # Statistiques pour tous les utilisateurs
    total_membres = Membre.objects.filter(est_actif=True).count()
    
    # Statistiques du mois en cours
    now = timezone.now()
    mois_actuel = now.month
    annee_actuelle = now.year
    
    cotisations_mois = Cotisation.objects.filter(mois=mois_actuel, annee=annee_actuelle)
    total_cotisations_mois = cotisations_mois.aggregate(Sum('montant'))['montant__sum'] or 0
    
    cotisations_imprevus_mois = CotisationImprevu.objects.filter(mois=mois_actuel, annee=annee_actuelle)
    total_cotisations_imprevus_mois = cotisations_imprevus_mois.aggregate(Sum('montant'))['montant__sum'] or 0
    
    # Statistiques des crédits
    credits_en_cours = Credit.objects.filter(statut__in=['APPROUVE', 'EN_COURS']).count()
    total_credits = Credit.objects.filter(statut__in=['APPROUVE', 'EN_COURS']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0
    
    # Statistiques personnelles pour le membre connecté
    mes_cotisations = Cotisation.objects.filter(membre=user)
    mes_cotisations_imprevus = CotisationImprevu.objects.filter(membre=user)
    mes_credits = Credit.objects.filter(membre=user)
    mes_credits_actifs = mes_credits.filter(statut__in=['APPROUVE', 'EN_COURS'])
    
    # Total des cotisations du membre
    total_mes_cotisations = user.get_total_cotisations()
    total_mes_cotisations_imprevus = user.get_total_cotisations_imprevus()
    
    # Dernières activités
    dernieres_cotisations = Cotisation.objects.all().order_by('-date_paiement')[:5]
    dernieres_cotisations_imprevus = CotisationImprevu.objects.all().order_by('-date_paiement')[:5]
    derniers_credits = Credit.objects.all().order_by('-date_demande')[:5]
    
    # Totaux généraux (pour admin/gestionnaire)
    if user.is_admin or user.is_gestionnaire:
        total_cotisations_disponibles = association.get_total_cotisations_disponibles() if association else 0
        total_imprevus_disponibles = association.get_total_cotisations_imprevus_disponibles() if association else 0
    else:
        total_cotisations_disponibles = None
        total_imprevus_disponibles = None
    
    context = {
        'association': association,
        'total_membres': total_membres,
        'total_cotisations_mois': total_cotisations_mois,
        'total_cotisations_imprevus_mois': total_cotisations_imprevus_mois,
        'credits_en_cours': credits_en_cours,
        'total_credits': total_credits,
        'mes_cotisations': mes_cotisations,
        'mes_cotisations_imprevus': mes_cotisations_imprevus,
        'mes_credits': mes_credits,
        'mes_credits_actifs': mes_credits_actifs,
        'total_mes_cotisations': total_mes_cotisations,
        'total_mes_cotisations_imprevus': total_mes_cotisations_imprevus,
        'dernieres_cotisations': dernieres_cotisations,
        'dernieres_cotisations_imprevus': dernieres_cotisations_imprevus,
        'derniers_credits': derniers_credits,
        'mois_actuel': mois_actuel,
        'annee_actuelle': annee_actuelle,
        'total_cotisations_disponibles': total_cotisations_disponibles,
        'total_imprevus_disponibles': total_imprevus_disponibles,
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
def liste_cotisations_imprevus(request):
    """Liste des cotisations pour imprévus/cas sociaux"""
    if request.user.is_admin or request.user.is_gestionnaire:
        cotisations = CotisationImprevu.objects.all().order_by('-annee', '-mois')
    else:
        cotisations = CotisationImprevu.objects.filter(membre=request.user).order_by('-annee', '-mois')
    
    context = {
        'cotisations_imprevus': cotisations,
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
            messages.success(request, f'Cotisation imprévus enregistrée pour {cotisation.membre.get_full_name()}.')
            return redirect('liste_cotisations_imprevus')
    else:
        form = CotisationImprevuForm()
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form, 
        'action': 'Ajouter'
    })


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
@user_passes_test(is_admin_only)
def approuver_credit(request, pk):
    """
    Approuver ou rejeter un crédit avec VALIDATION STRICTE des fonds
    
    LOGIQUE :
    1. Calculer le total des cotisations payées
    2. Calculer le total des crédits déjà accordés et non remboursés
    3. Fonds disponibles = Cotisations - Crédits en cours
    4. BLOQUER si montant demandé > fonds disponibles
    """
    credit = get_object_or_404(Credit, pk=pk)
    association = Association.get_association()
    
    if not association:
        messages.error(request, "⚠️ Erreur : Association non configurée.")
        return redirect('liste_credits')
    
    # ÉTAPE 1 : Calculer le total des cotisations
    total_cotisations = association.get_total_cotisations_disponibles()
    
    # ÉTAPE 2 : Calculer le total des crédits en cours (sauf celui qu'on traite)
    credits_en_cours = Credit.objects.filter(
        statut__in=['APPROUVE', 'EN_COURS']
    ).exclude(pk=credit.pk)
    
    total_credits_accordes = Decimal('0')
    for c in credits_en_cours:
        total_credits_accordes += c.montant_accorde
    
    # ÉTAPE 3 : Calculer les fonds disponibles
    fonds_disponibles = total_cotisations - total_credits_accordes
    
    if request.method == 'POST':
        form = CreditApprovalForm(request.POST, instance=credit)
        
        if form.is_valid():
            # Récupérer le montant qu'on veut accorder
            montant_accorde = form.cleaned_data['montant_accorde']
            nouveau_statut = form.cleaned_data['statut']
            
            # VALIDATION STRICTE : Vérifier si on a assez de fonds
            if nouveau_statut == 'APPROUVE' and montant_accorde > fonds_disponibles:
                messages.error(
                    request,
                    f"❌ FONDS INSUFFISANTS ! "
                    f"Vous ne pouvez pas accorder ce crédit. "
                    f"Fonds disponibles : {fonds_disponibles:,.2f} FBU | "
                    f"Montant demandé : {montant_accorde:,.2f} FBU | "
                    f"Manque : {(montant_accorde - fonds_disponibles):,.2f} FBU"
                )
                
                # Afficher les détails
                messages.info(
                    request,
                    f"📊 Détails : "
                    f"Total cotisations = {total_cotisations:,.2f} FBU | "
                    f"Crédits en cours = {total_credits_accordes:,.2f} FBU"
                )
                
                return redirect('approuver_credit', pk=credit.pk)
            
            # Si validation OK ou si c'est un rejet, sauvegarder
            form.save()
            
            if nouveau_statut == 'APPROUVE':
                # Calculer les nouveaux fonds restants
                nouveaux_fonds = fonds_disponibles - montant_accorde
                
                messages.success(
                    request,
                    f"✅ Crédit accordé avec succès ! "
                    f"Montant : {montant_accorde:,.2f} FBU | "
                    f"Fonds restants : {nouveaux_fonds:,.2f} FBU"
                )
            elif nouveau_statut == 'REJETE':
                messages.warning(request, f"❌ Crédit rejeté.")
            
            return redirect('liste_credits')
    else:
        form = CreditApprovalForm(instance=credit)
    
    # Préparer le contexte avec toutes les informations
    context = {
        'form': form,
        'credit': credit,
        'total_cotisations': total_cotisations,
        'total_credits_accordes': total_credits_accordes,
        'fonds_disponibles': fonds_disponibles,
        'credits_en_cours': credits_en_cours,
        'peut_approuver': fonds_disponibles > 0,
        'montant_max_possible': fonds_disponibles,
    }
    
    return render(request, 'twiyungunganye/credits/approbation.html', context)


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
