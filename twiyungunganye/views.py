from .views_additions import approuver_credit_strict as approuver_credit
import os, io as io_module, qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, date
from decimal import Decimal, ROUND_DOWN
from dateutil.relativedelta import relativedelta


def tronquer(montant):
    """Tronque un montant à 3 décimales sans arrondissement"""
    return Decimal(str(montant)).quantize(Decimal('0.001'), rounding=ROUND_DOWN)

from .pdf_utils import save_pdf_and_respond
from .models import (
    Membre, Cotisation, CotisationImprevu, Credit, Interet, 
    Remboursement, Association, Suggestion, Notification, PenaliteCotisation, Depense
)
from superadmin.models import Tenant as TenantModel
from .forms import (
    LoginForm, MembrePasswordCreationForm, MembreForm, CotisationForm,
    CotisationImprevuForm, CreditDemandeForm, CreditApprovalForm, 
    RemboursementForm,     SuggestionForm, ReponseSuggestionForm, RapportMensuelForm, RapportAnnuelForm,
    AssociationForm, ModifierProfilForm, MembrePasswordChangeForm, DepenseForm
)


def get_tenant(request):
    """Helper pour récupérer le tenant depuis la requête"""
    tenant = getattr(request, 'tenant', None)
    
    # Si le middleware n'a pas défini de tenant mais qu'il y a un tenant_id dans l'URL
    if not tenant:
        # Le middleware devrait avoir défini request.tenant
        pass
        
    return tenant


def qs_for_tenant(request, qs, field='tenant'):
    """Filtre un queryset par le tenant de la requête"""
    tenant = get_tenant(request)
    if tenant and not getattr(request, 'is_superadmin', False):
        return qs.filter(**{field: tenant})
    return qs


# Utilitaires pour vérifier les permissions
def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin)


def is_admin_only(user):
    return user.is_authenticated and user.is_admin


# Vue pour la page d'accueil publique
def index(request):
    """Page d'accueil publique"""
    tenant = get_tenant(request)
    association = Association.get_association(tenant)
    from superadmin.models import Tenant as TenantModel
    tenants = TenantModel.objects.filter(actif=True)
    context = {
        'association': association,
        'tenants': tenants,
        'tenant_courant': tenant,
    }
    return render(request, 'twiyungunganye/index.html', context)


# Vues d'authentification
def login_view(request):
    """Vue de connexion"""
    if request.user.is_authenticated:
        if request.user.is_superuser:
            return redirect('superadmin:dashboard')
        return redirect('dashboard')
    
    # Récupérer toutes les associations actives pour le sélecteur
    from superadmin.models import Tenant as TenantModel
    tenants = TenantModel.objects.filter(actif=True)
    tenant_courant = get_tenant(request)
    
    # Pagination pour la liste des associations disponibles
    paginator = Paginator(tenants, 10)
    page_number = request.GET.get('page')
    tenants_page = paginator.get_page(page_number)
    
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST, tenant_queryset=tenants)
        if form.is_valid():
            user = form.get_user()
            tenant_choisi = form.cleaned_data.get('tenant') or tenant_courant
            if tenant_choisi and user.tenant_id and user.tenant_id != tenant_choisi.pk:
                messages.error(request, "Ce membre n'appartient pas à cette association.")
                return render(request, 'twiyungunganye/login.html', {'form': form, 'tenants': tenants, 'tenants_page': tenants_page})
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()} !')
            if user.is_superuser:
                return redirect('superadmin:dashboard')
            return redirect('dashboard')
    else:
        form = LoginForm(tenant_queryset=tenants)
    
    return render(request, 'twiyungunganye/login.html', {
        'form': form,
        'tenants': tenants,
        'tenants_page': tenants_page,
        'tenant_courant': tenant_courant,
    })


def create_password_view(request):
    """Vue pour créer le premier mot de passe"""
    from superadmin.models import Tenant as TenantModel
    tenants = TenantModel.objects.filter(actif=True)
    tenant_courant = get_tenant(request)

    paginator = Paginator(tenants, 10)
    page_number = request.GET.get('page')
    tenants_page = paginator.get_page(page_number)

    if request.method == 'POST':
        form = MembrePasswordCreationForm(request.POST, tenant_queryset=tenants)
        if form.is_valid():
            carte_identite = form.cleaned_data['carte_identite']
            password = form.cleaned_data['password1']
            tenant = form.cleaned_data.get('tenant') or tenant_courant

            membres = Membre.objects.filter(carte_identite=carte_identite)
            if tenant:
                membres = membres.filter(tenant=tenant)
            membre = membres.first()
            if not membre:
                messages.error(request, "Aucun membre trouvé avec cette carte d'identité dans cette association.")
                return render(request, 'twiyungunganye/create_password.html', {'form': form, 'tenants': tenants, 'tenants_page': tenants_page, 'tenant_courant': tenant_courant})
            membre.set_password(password)
            membre.save()

            messages.success(request, 'Votre mot de passe a été créé avec succès. Vous pouvez maintenant vous connecter.')
            return redirect('login')
    else:
        form = MembrePasswordCreationForm(tenant_queryset=tenants)

    return render(request, 'twiyungunganye/create_password.html', {
        'form': form,
        'tenants': tenants,
        'tenants_page': tenants_page,
        'tenant_courant': tenant_courant,
    })


def logout_view(request):
    """Vue de déconnexion"""
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('index')


# Dashboard - NOUVELLE VERSION AVEC 3 DERNIERS MOIS + CAPITAL
@login_required
def dashboard(request):
    if request.user.is_superuser:
        return redirect('superadmin:dashboard')

    now = datetime.now()
    mois_actuel = now.month
    annee_actuelle = now.year

    MOIS_NOMS = {
        1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril',
        5: 'Mai', 6: 'Juin', 7: 'Juillet', 8: 'Août',
        9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'
    }

    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_imprevus = qs_for_tenant(request, CotisationImprevu.objects.all())
    base_membres = qs_for_tenant(request, Membre.objects.all())
    base_remboursements = qs_for_tenant(request, Remboursement.objects.all())

    # ==========================================
    # STATISTIQUES PERSONNELLES (pour tous)
    # ==========================================
    total_mes_cotisations = base_cotisations.filter(
        membre=request.user, statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or 0

    mes_credits_actifs = base_credits.filter(membre=request.user, statut='EN_COURS')
    total_mes_credits_actifs = mes_credits_actifs.aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0

    mes_remboursements_qs = base_remboursements.filter(credit__membre=request.user)
    total_mes_remboursements = mes_remboursements_qs.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0
    total_mes_interets_rembourses = mes_remboursements_qs.aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or 0

    mes_cotisations_en_retard = base_cotisations.filter(
        membre=request.user, statut='RETARD'
    ).count()

    # Ma cotisation du mois actuel
    ma_cotisation_mois = base_cotisations.filter(
        membre=request.user, mois=mois_actuel, annee=annee_actuelle
    ).first()
    statut_cotisation_mois = ma_cotisation_mois.statut if ma_cotisation_mois else 'NON_FAITE'

    context = {
        'mois_actuel': mois_actuel,
        'annee_actuelle': annee_actuelle,
        'mois_actuel_nom': MOIS_NOMS[mois_actuel],
        'total_mes_cotisations': total_mes_cotisations,
        'total_mes_credits_actifs': total_mes_credits_actifs,
        'total_mes_remboursements': total_mes_remboursements,
        'total_mes_interets_rembourses': total_mes_interets_rembourses,
        'mes_cotisations_en_retard': mes_cotisations_en_retard,
        'statut_cotisation_mois': statut_cotisation_mois,
    }

    # Si membre simple → que ses stats personnelles + total membres
    if not request.user.is_admin:
        total_membres = base_membres.filter(est_actif=True).count()
        context['total_membres'] = total_membres
        context['est_membre'] = True

        # Ses crédits en cours (simplifié)
        context['mes_credits_actifs_liste'] = mes_credits_actifs.select_related('membre')[:5]
        context['nombre_credits_actifs'] = mes_credits_actifs.count()

        # Ses pénalités impayées
        from .models import PenaliteCotisation
        penalites_impayees = qs_for_tenant(request, PenaliteCotisation.objects.filter(
            membre=request.user, est_payee=False
        )).aggregate(Sum('penalite_cumulee'))['penalite_cumulee__sum'] or 0
        context['mes_penalites_impayees'] = penalites_impayees

        return render(request, 'twiyungunganye/dashboard_membre.html', context)

    # ==========================================
    # ADMIN : données globales complètes
    # ==========================================
    date_actuelle = datetime(annee_actuelle, mois_actuel, 1)
    mois_precedent_1 = date_actuelle - relativedelta(months=1)
    mois_precedent_2 = date_actuelle - relativedelta(months=2)
    mois_liste = [mois_precedent_2, mois_precedent_1, date_actuelle]

    # 3 derniers mois
    cotisations_3_derniers_mois = []
    credits_3_derniers_mois = []
    imprevus_3_derniers_mois = []
    for date_mois in mois_liste:
        cm = base_cotisations.filter(mois=date_mois.month, annee=date_mois.year, statut='PAYE')
        tot_c = cm.aggregate(t=Sum('montant'))['t'] or 0
        cotisations_3_derniers_mois.append({'mois_nom': MOIS_NOMS[date_mois.month], 'mois': date_mois.month, 'annee': date_mois.year, 'montant': tot_c, 'nombre_paiements': cm.count()})

        cr = base_credits.filter(date_accord__month=date_mois.month, date_accord__year=date_mois.year, statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE'])
        tot_r = cr.aggregate(t=Sum('montant_accorde'))['t'] or 0
        credits_3_derniers_mois.append({'mois_nom': MOIS_NOMS[date_mois.month], 'mois': date_mois.month, 'annee': date_mois.year, 'montant': tot_r, 'nombre_credits': cr.count()})

        im = base_imprevus.filter(mois=date_mois.month, annee=date_mois.year, statut='PAYE')
        tot_i = im.aggregate(t=Sum('montant'))['t'] or 0
        imprevus_3_derniers_mois.append({'mois_nom': MOIS_NOMS[date_mois.month], 'mois': date_mois.month, 'annee': date_mois.year, 'montant': tot_i, 'nombre_imprevus': im.count()})

    # Totaux mois actuel
    tcm = base_cotisations.filter(mois=mois_actuel, annee=annee_actuelle, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0
    tcrm = base_credits.filter(date_accord__month=mois_actuel, date_accord__year=annee_actuelle, statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0
    tim = base_imprevus.filter(mois=mois_actuel, annee=annee_actuelle, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0

    # Capital de l'association
    # Formule : (cotisations + imprevus + remboursements_principal + interets_percus) 
    #         - (depenses + credits_accordes)
    from .models import Depense
    base_depenses = qs_for_tenant(request, Depense.objects.all()) if hasattr(request, 'tenant') else Depense.objects.none()
    total_depenses = base_depenses.aggregate(Sum('montant'))['montant__sum'] or 0

    total_membres = base_membres.filter(est_actif=True).count()
    total_entrees = (base_cotisations.filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0) + (base_imprevus.filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0) + (base_remboursements.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0) + (base_remboursements.aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or 0)
    total_sorties = total_depenses + (base_credits.filter(statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0)
    solde_caisse = total_entrees - total_sorties

    cotisations_payees = base_cotisations.filter(mois=mois_actuel, annee=annee_actuelle, statut='PAYE').count()
    taux_paiement = (cotisations_payees / total_membres * 100) if total_membres > 0 else 0

    # Activités
    dernieres_cotisations = base_cotisations.filter(statut='PAYE').select_related('membre').order_by('-date_paiement')[:10]
    derniers_credits = base_credits.select_related('membre').order_by('-date_demande')[:10]

    # Intérêts / Pénalités / Remboursements (globaux)
    from .models import Interet, PenaliteCotisation
    base_interets = qs_for_tenant(request, Interet.objects.all())
    base_penalites = qs_for_tenant(request, PenaliteCotisation.objects.all())

    context.update({
        'cotisations_3_derniers_mois': cotisations_3_derniers_mois,
        'credits_3_derniers_mois': credits_3_derniers_mois,
        'imprevus_3_derniers_mois': imprevus_3_derniers_mois,
        'total_cotisations_mois_actuel': tcm,
        'total_credits_mois_actuel': tcrm,
        'total_imprevus_mois_actuel': tim,
        'total_general_mois_actuel': tcm + tcrm + tim,
        'total_membres': total_membres,
        'solde_caisse': solde_caisse,
        'taux_paiement': taux_paiement,
        'total_imprevus_capital': base_imprevus.filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0,
        'total_remboursements': base_remboursements.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0,
        'total_depenses': total_depenses,
        'capital_association': solde_caisse,
        'total_credits_accordes': base_credits.filter(statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0,
        'total_interets_mois': base_interets.filter(mois=mois_actuel, annee=annee_actuelle).aggregate(Sum('interet_mensuel'))['interet_mensuel__sum'] or 0,
        'total_interets_cumules': base_interets.aggregate(Sum('interet_cumule'))['interet_cumule__sum'] or 0,
        'total_penalites_mois': base_penalites.filter(mois=mois_actuel, annee=annee_actuelle).aggregate(Sum('penalite_cumulee'))['penalite_cumulee__sum'] or 0,
        'total_penalites_impayees': base_penalites.filter(est_payee=False).aggregate(Sum('penalite_cumulee'))['penalite_cumulee__sum'] or 0,
        'total_remboursements_mois': base_remboursements.filter(date_remboursement__month=mois_actuel, date_remboursement__year=annee_actuelle).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0,
        'cotisations_en_retard': base_cotisations.filter(mois=mois_actuel, annee=annee_actuelle, statut='RETARD').count(),
        'dernieres_cotisations': dernieres_cotisations,
        'derniers_credits': derniers_credits,
        'est_membre': False,
    })

    # Chart data (6 mois)
    from datetime import date
    chart_labels, chart_cotisations, chart_credits, chart_imprevus = [], [], [], []
    for i in range(5, -1, -1):
        d = date(annee_actuelle, mois_actuel, 1) - relativedelta(months=i)
        chart_labels.append(MOIS_NOMS[d.month][:3])
        chart_cotisations.append(float(base_cotisations.filter(mois=d.month, annee=d.year, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0))
        chart_credits.append(float(base_credits.filter(date_accord__month=d.month, date_accord__year=d.year, statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0))
        chart_imprevus.append(float(base_imprevus.filter(mois=d.month, annee=d.year, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0))
    context.update({'chart_labels': chart_labels, 'chart_cotisations': chart_cotisations, 'chart_credits': chart_credits, 'chart_imprevus': chart_imprevus})

    return render(request, 'twiyungunganye/dashboard.html', context)


# Gestion des membres
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_membres(request):
    """Liste de tous les membres avec statut crédit"""
    from django.db.models import Prefetch, Q

    membres = qs_for_tenant(request, Membre.objects.all()).order_by('nom', 'prenom')

    credit_filter = request.GET.get('credit')
    if credit_filter == 'avec':
        membres = membres.filter(credits__isnull=False).distinct()
    elif credit_filter == 'sans':
        membres = membres.filter(credits__isnull=True).distinct()
    elif credit_filter == 'encours':
        membres = membres.filter(credits__statut__in=['APPROUVE', 'EN_COURS']).distinct()
    elif credit_filter == 'rembourse':
        membres = membres.filter(credits__statut='REMBOURSE').distinct()

    paginator = Paginator(membres, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    total_membres = qs_for_tenant(request, Membre.objects.all()).count()
    avec_credit = qs_for_tenant(request, Membre.objects.filter(credits__isnull=False)).distinct().count()
    encours = qs_for_tenant(request, Membre.objects.filter(credits__statut__in=['APPROUVE', 'EN_COURS'])).distinct().count()

    context = {
        'page_obj': page_obj,
        'total_membres': total_membres,
        'avec_credit': avec_credit,
        'encours_credit': encours,
        'sans_credit': total_membres - avec_credit,
        'credit_filter': credit_filter,
        'statuts_credit': dict(Membre.objects.filter(tenant=get_tenant(request)).values_list('pk', 'credits__statut')),
    }
    return render(request, 'twiyungunganye/membres/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_membre(request):
    """Ajouter un nouveau membre"""
    if request.method == 'POST':
        form = MembreForm(request.POST, request.FILES)
        if form.is_valid():
            membre = form.save(commit=False)
            tenant = get_tenant(request)
            if tenant:
                membre.tenant = tenant
            membre.save()
            messages.success(request, f'Le membre {membre.get_full_name()} a été ajouté avec succès.')
            return redirect('liste_membres')
    else:
        form = MembreForm()
    
    return render(request, 'twiyungunganye/membres/formulaire.html', {
        'form': form,
        'action': 'Ajouter',
        'membre': None,
    })


@login_required
@user_passes_test(is_admin_only)
def modifier_membre(request, pk):
    """Modifier un membre existant"""
    from .models import GroupeAcces
    
    membre = get_object_or_404(qs_for_tenant(request, Membre.objects.all()), pk=pk)
    tenant = get_tenant(request)
    
    if request.method == 'POST':
        form = MembreForm(request.POST, request.FILES, instance=membre)
        if form.is_valid():
            membre = form.save(commit=False)
            groupe_id = request.POST.get('groupe_acces')
            if groupe_id:
                membre.groupe_acces_id = int(groupe_id)
            else:
                membre.groupe_acces = None
            membre.save()
            messages.success(request, f'Le membre {membre.get_full_name()} a été modifié avec succès.')
            return redirect('liste_membres')
    else:
        form = MembreForm(instance=membre)
    
    groupes = GroupeAcces.objects.filter(tenant=tenant) if tenant else []
    
    return render(request, 'twiyungunganye/membres/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'membre': membre,
        'groupes': groupes,
    })


@login_required
def detail_membre(request, pk):
    """Afficher les détails d'un membre"""
    membre = get_object_or_404(qs_for_tenant(request, Membre.objects.all()), pk=pk)
    
    # Vérifier les permissions
    if not (request.user.is_admin or request.user.pk == membre.pk):
        messages.error(request, "Vous n'avez pas la permission de voir ce profil.")
        return redirect('dashboard')
    
    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_imprevus = qs_for_tenant(request, CotisationImprevu.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_suggestions = qs_for_tenant(request, Suggestion.objects.all())
    
    cotisations = base_cotisations.filter(membre=membre).order_by('-annee', '-mois')
    cotisations_imprevus = base_imprevus.filter(membre=membre).order_by('-annee', '-mois')
    credits = base_credits.filter(membre=membre).order_by('-date_demande')
    suggestions = base_suggestions.filter(membre=membre).order_by('-date_soumission')
    
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
    base = qs_for_tenant(request, Cotisation.objects.all())
    if request.user.is_admin:
        cotisations = base.order_by('-annee', '-mois')
    else:
        cotisations = base.filter(membre=request.user).order_by('-annee', '-mois')
    paginator = Paginator(cotisations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'twiyungunganye/cotisations/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_cotisation(request):
    """Ajouter une nouvelle cotisation régulière"""
    if request.method == 'POST':
        form = CotisationForm(request.POST, tenant=get_tenant(request))
        if form.is_valid():
            cotisation = form.save(commit=False)
            tenant = get_tenant(request)
            if tenant:
                cotisation.tenant = tenant
            cotisation.save()
            messages.success(request, f'Cotisation enregistrée pour {cotisation.membre.get_full_name()}.')
            return redirect('liste_cotisations')
    else:
        form = CotisationForm(tenant=get_tenant(request))
    
    return render(request, 'twiyungunganye/cotisations/formulaire.html', {'form': form, 'action': 'Ajouter'})


# Gestion des cotisations imprévus
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_cotisations_imprevus(request):
    """Liste de toutes les cotisations pour imprévus/cas sociaux"""
    cotisations_imprevus = qs_for_tenant(
        request, CotisationImprevu.objects.all()
    ).select_related('membre').order_by('-annee', '-mois')
    
    # Statistiques
    stats = cotisations_imprevus.aggregate(
        total=Sum('montant'),
        nombre_total=Count('id_cotisation_imprevu'),
        payees=Count('id_cotisation_imprevu', filter=Q(statut='PAYE')),
        en_attente=Count('id_cotisation_imprevu', filter=Q(statut='EN_ATTENTE')),
        en_retard=Count('id_cotisation_imprevu', filter=Q(statut='RETARD'))
    )
    
    paginator = Paginator(cotisations_imprevus, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'stats': stats,
    }
    
    return render(request, 'twiyungunganye/cotisations_imprevus/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_cotisation_imprevu(request):
    """Ajouter une nouvelle cotisation pour imprévus"""
    if request.method == 'POST':
        form = CotisationImprevuForm(request.POST, tenant=get_tenant(request))
        if form.is_valid():
            cotisation = form.save(commit=False)
            tenant = get_tenant(request)
            if tenant:
                cotisation.tenant = tenant
            cotisation.save()
            messages.success(
                request, 
                f'Cotisation imprévus de {cotisation.membre.get_full_name()} enregistrée avec succès.'
            )
            return redirect('liste_cotisations_imprevus')
    else:
        form = CotisationImprevuForm(tenant=get_tenant(request))
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form,
        'action': 'Ajouter'
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_cotisation_imprevu(request, pk):
    """Modifier une cotisation imprévus existante"""
    cotisation = get_object_or_404(
        qs_for_tenant(request, CotisationImprevu.objects.all()), pk=pk
    )
    
    if request.method == 'POST':
        form = CotisationImprevuForm(request.POST, instance=cotisation, tenant=get_tenant(request))
        if form.is_valid():
            form.save()
            messages.success(request, 'Cotisation imprévus modifiée avec succès.')
            return redirect('liste_cotisations_imprevus')
    else:
        form = CotisationImprevuForm(instance=cotisation, tenant=get_tenant(request))
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'cotisation': cotisation
    })


@login_required
def mes_cotisations_imprevus(request):
    """Voir les cotisations imprévus du membre connecté"""
    cotisations = qs_for_tenant(
        request, CotisationImprevu.objects.all()
    ).filter(membre=request.user).order_by('-annee', '-mois')
    
    total_paye = request.user.get_total_cotisations_imprevus()
    paginator = Paginator(cotisations, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'total_paye': total_paye,
    }
    
    return render(request, 'twiyungunganye/cotisations_imprevus/mes_cotisations.html', context)


# Gestion des crédits
@login_required
def liste_credits(request):
    """Liste des crédits"""
    base = qs_for_tenant(request, Credit.objects.all())
    if request.user.is_admin:
        credits = base.order_by('-date_demande')
    else:
        credits = base.filter(membre=request.user).order_by('-date_demande')
    paginator = Paginator(credits, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
    }
    return render(request, 'twiyungunganye/credits/liste.html', context)


@login_required
def demander_credit(request):
    """Demander un crédit"""
    tenant = get_tenant(request)
    total_cotisations = request.user.get_total_cotisations()
    
    if total_cotisations <= 0:
        messages.error(request, "Vous ne pouvez pas demander un crédit car vous n'avez aucune cotisation payée.")
        return redirect('liste_credits')
    
    association = Association.get_association(tenant)
    if association:
        mois_min = association.mois_minimum_cotisation_credit
        if mois_min > 0:
            montant_minimum = association.montant_cotisation_mensuelle * mois_min
            if total_cotisations < montant_minimum:
                messages.error(request, f"Vous devez avoir au moins {montant_minimum} {association.devise} de cotisations payées (équivalent à {mois_min} mois). Vous avez actuellement {total_cotisations} {association.devise}.")
                return redirect('liste_credits')
    
    montant_demande = request.POST.get('montant_demande', 0) if request.method == 'POST' else 0
    if association and float(association.montant_max_credit) > 0 and float(montant_demande) > float(association.montant_max_credit):
        messages.error(request, f"Le montant demandé dépasse le plafond autorisé de {association.montant_max_credit:,.0f} {association.devise}.")
        return redirect('demander_credit')
    
    if request.method == 'POST':
        form = CreditDemandeForm(request.POST, membre=request.user, tenant=tenant)
        if form.is_valid():
            credit = form.save(commit=False)
            credit.membre = request.user
            credit.montant_accorde = 0
            if tenant:
                credit.tenant = tenant
            credit.save()

            # Notification au(x) dirigeant(s)
            admins = Membre.objects.filter(tenant=tenant, is_admin=True).exclude(pk=request.user.pk)
            for admin in admins:
                Notification.objects.create(
                    destinataire=admin,
                    expediteur=request.user,
                    type_notification='DEMANDE_CREDIT',
                    titre=f"Nouvelle demande de crédit de {request.user.get_full_name()}",
                    message=f"Montant demandé : {credit.montant_demande:,.0f} FBU",
                    lien=f"/credits/{credit.pk}/",
                )

            messages.success(request, 'Votre demande de crédit a été soumise avec succès. Vous recevrez une notification dès qu\'elle sera traitée.')
            return redirect('liste_credits')
    else:
        form = CreditDemandeForm(membre=request.user, tenant=tenant)
    
    context = {
        'form': form,
        'total_cotisations': total_cotisations,
        'montant_max_credit': association.montant_max_credit if association else 0,
        'association': association,
    }
    
    return render(request, 'twiyungunganye/credits/demande.html', context)


@login_required
def detail_credit(request, pk):
    """Afficher les détails d'un crédit"""
    credit = get_object_or_404(qs_for_tenant(request, Credit.objects.all()), pk=pk)
    
    # Vérifier les permissions
    if not (request.user.is_admin or credit.membre == request.user):
        messages.error(request, "Vous n'avez pas la permission de voir ce crédit.")
        return redirect('liste_credits')
    
    remboursements = Remboursement.objects.filter(credit=credit).select_related('credit__membre').order_by('-date_remboursement')
    
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
    tenant = get_tenant(request)
    if request.method == 'POST':
        form = RemboursementForm(request.POST, tenant=tenant)
        if form.is_valid():
            remboursement = form.save(commit=False)
            if tenant:
                remboursement.tenant = tenant
            remboursement.save()
            messages.success(request, f'Remboursement enregistré pour {remboursement.credit.membre.get_full_name()}.')
            return redirect('detail_credit', pk=remboursement.credit.pk)
    else:
        initial = {}
        if credit_id:
            initial['credit'] = credit_id
        form = RemboursementForm(initial=initial, tenant=tenant)
    
    return render(request, 'twiyungunganye/remboursements/formulaire.html', {'form': form})


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_remboursements(request):
    """Liste de tous les remboursements"""
    remboursements = qs_for_tenant(
        request, Remboursement.objects.all()
    ).select_related('credit__membre').order_by('-date_remboursement')
    
    paginator = Paginator(remboursements, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'remboursements': page_obj,
    }
    return render(request, 'twiyungunganye/remboursements/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_interets(request):
    """Liste des intérêts mensuels calculés"""
    from django.db.models import Sum
    
    tenant = get_tenant(request)
    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre')
    
    interets_data = []
    today = timezone.now().date()
    
    for credit in credits:
        if not credit.date_accord:
            continue
        
        # Calculer le nombre de mois écoulés depuis l'accord
        from dateutil.relativedelta import relativedelta
        delta = relativedelta(today, credit.date_accord)
        mois_ecoules = delta.years * 12 + delta.months
        
        if mois_ecoules <= 0:
            mois_ecoules = 1
        
        # Calculer l'intérêt mensuel
        taux = Decimal(str(credit.taux_interet)) / Decimal('100')
        interet_mensuel = tronquer(credit.montant_accorde * taux)
        
        # Calculer l'intérêt cumulé
        interet_cumule = tronquer(interet_mensuel * mois_ecoules)
        
        # Récupérer les intérêts déjà enregistrés
        interets_existants = credit.interets.all().order_by('-annee', '-mois')
        total_enregistre = interets_existants.aggregate(Sum('interet_mensuel'))['interet_mensuel__sum'] or Decimal('0.000')
        
        interets_data.append({
            'credit': credit,
            'membre': credit.membre,
            'montant_accorde': credit.montant_accorde,
            'taux_interet': credit.taux_interet,
            'date_accord': credit.date_accord,
            'mois_ecoules': mois_ecoules,
            'interet_mensuel': interet_mensuel,
            'interet_cumule': interet_cumule,
            'total_enregistre': total_enregistre,
            'interets_existants': interets_existants,
        })
    
    context = {
        'interets_data': interets_data,
        'today': today,
    }
    return render(request, 'twiyungunganye/interets/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def generer_interets(request, credit_id):
    """Générer les intérêts mensuels pour un crédit"""
    from dateutil.relativedelta import relativedelta
    from decimal import Decimal
    
    credit = get_object_or_404(qs_for_tenant(request, Credit.objects.all()), pk=credit_id)
    
    if credit.statut not in ['APPROUVE', 'EN_COURS', 'REMBOURSE']:
        messages.error(request, "Ce crédit ne peut pas générer d'intérêts.")
        return redirect('liste_interets')
    
    if not credit.date_accord:
        messages.error(request, "Ce crédit n'a pas de date d'accord.")
        return redirect('liste_interets')
    
    tenant = get_tenant(request)
    today = timezone.now().date()
    
    # Calculer le nombre de mois écoulés
    delta = relativedelta(today, credit.date_accord)
    mois_ecoules = delta.years * 12 + delta.months
    if mois_ecoules <= 0:
        mois_ecoules = 1
    
    taux = Decimal(str(credit.taux_interet)) / Decimal('100')
    interet_mensuel = tronquer(credit.montant_accorde * taux)
    
    interets_crees = 0
    for i in range(1, mois_ecoules + 1):
        date_mois = credit.date_accord + relativedelta(months=i-1)
        mois = date_mois.month
        annee = date_mois.year
        
        # Vérifier si l'intérêt existe déjà
        interet, created = Interet.objects.get_or_create(
            credit=credit,
            mois=mois,
            annee=annee,
            defaults={
                'tenant': tenant,
                'interet_mensuel': interet_mensuel,
                'interet_cumule': tronquer(interet_mensuel * i),
                'date_calcul': date_mois,
            }
        )
        if created:
            interets_crees += 1
        else:
            # Mettre à jour l'intérêt cumulé
            interet.interet_cumule = tronquer(interet_mensuel * i)
            interet.save(update_fields=['interet_cumule'])
    
    if interets_crees > 0:
        messages.success(request, f"{interets_crees} intérêts générés pour le crédit #{credit.id_credit}.")
    else:
        messages.info(request, "Tous les intérêts étaient déjà générés.")
    
    return redirect('liste_interets')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def generer_tous_interets(request):
    """Générer les intérêts pour tous les crédits actifs"""
    from dateutil.relativedelta import relativedelta
    from decimal import Decimal
    
    tenant = get_tenant(request)
    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre')
    
    total_interets_crees = 0
    today = timezone.now().date()
    
    for credit in credits:
        if not credit.date_accord:
            continue
        
        delta = relativedelta(today, credit.date_accord)
        mois_ecoules = delta.years * 12 + delta.months
        if mois_ecoules <= 0:
            mois_ecoules = 1
        
        taux = Decimal(str(credit.taux_interet)) / Decimal('100')
        interet_mensuel = tronquer(credit.montant_accorde * taux)
        
        for i in range(1, mois_ecoules + 1):
            date_mois = credit.date_accord + relativedelta(months=i-1)
            mois = date_mois.month
            annee = date_mois.year
            
            interet, created = Interet.objects.get_or_create(
                credit=credit,
                mois=mois,
                annee=annee,
                defaults={
                    'tenant': tenant,
                    'interet_mensuel': interet_mensuel,
                    'interet_cumule': tronquer(interet_mensuel * i),
                    'date_calcul': date_mois,
                }
            )
            if created:
                total_interets_crees += 1
            else:
                interet.interet_cumule = tronquer(interet_mensuel * i)
                interet.save(update_fields=['interet_cumule'])
    
    if total_interets_crees > 0:
        messages.success(request, f"{total_interets_crees} intérêts générés pour tous les crédits.")
    else:
        messages.info(request, "Tous les intérêts étaient déjà générés.")
    
    return redirect('liste_interets')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_penalites(request):
    """Liste des pénalités de cotisations impayées"""
    from django.db.models import Sum
    
    tenant = get_tenant(request)
    penalites = qs_for_tenant(request, PenaliteCotisation.objects.all()).select_related('membre', 'cotisation').order_by('-annee', '-mois')
    
    # Statistiques
    stats = penalites.aggregate(
        total_penalites=Sum('penalite_cumulee'),
        total_payees=Sum('penalite_cumulee', filter=Q(est_payee=True)),
        count_total=Sum('id_penalite'),
        count_payees=Sum('id_penalite', filter=Q(est_payee=True)),
    )
    
    paginator = Paginator(penalites, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    context = {
        'page_obj': page_obj,
        'penalites': page_obj,
        'stats': stats,
    }
    return render(request, 'twiyungunganye/penalites/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def generer_penalites(request):
    """Générer les pénalités pour tous les membres"""
    total = PenaliteCotisation.generer_toutes_penalites()
    if total > 0:
        messages.success(request, f"{total} pénalités générées/mises à jour.")
    else:
        messages.info(request, "Aucune nouvelle pénalité générée.")
    return redirect('liste_penalites')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def marquer_penalite_payee(request, pk):
    """Marquer une pénalité comme payée"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.all()), pk=pk)
    penalite.est_payee = True
    penalite.date_paiement = timezone.now().date()
    penalite.save(update_fields=['est_payee', 'date_paiement'])
    messages.success(request, f"Pénalité marquée comme payée.")
    return redirect('liste_penalites')


@login_required
def mes_remboursements(request):
    """Liste des remboursements du membre connecté"""
    remboursements = qs_for_tenant(
        request, Remboursement.objects.all()
    ).filter(credit__membre=request.user).select_related('credit__membre').order_by('-date_remboursement')
    
    paginator = Paginator(remboursements, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'twiyungunganye/remboursements/liste.html', {
        'page_obj': page_obj,
        'mes_remboursements': True,
    })


@login_required
def mes_interets(request):
    """Liste des intérêts du membre connecté"""
    from django.db.models import Sum
    from decimal import Decimal
    from dateutil.relativedelta import relativedelta
    
    today = timezone.now().date()
    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        membre=request.user,
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre')
    
    interets_data = []
    for credit in credits:
        if not credit.date_accord:
            continue
        delta = relativedelta(today, credit.date_accord)
        mois_ecoules = delta.years * 12 + delta.months
        if mois_ecoules <= 0:
            mois_ecoules = 1
        taux = Decimal(str(credit.taux_interet)) / Decimal('100')
        interet_mensuel = tronquer(credit.montant_accorde * taux)
        interet_cumule = tronquer(interet_mensuel * mois_ecoules)
        interets_existants = credit.interets.all().order_by('-annee', '-mois')
        total_enregistre = interets_existants.aggregate(Sum('interet_mensuel'))['interet_mensuel__sum'] or Decimal('0.000')
        interets_data.append({
            'credit': credit,
            'membre': credit.membre,
            'montant_accorde': credit.montant_accorde,
            'taux_interet': credit.taux_interet,
            'date_accord': credit.date_accord,
            'mois_ecoules': mois_ecoules,
            'interet_mensuel': interet_mensuel,
            'interet_cumule': interet_cumule,
            'total_enregistre': total_enregistre,
            'interets_existants': interets_existants,
        })
    
    return render(request, 'twiyungunganye/interets/liste.html', {
        'interets_data': interets_data,
        'today': today,
        'mes_interets': True,
    })


@login_required
def mes_penalites(request):
    """Liste des pénalités du membre connecté"""
    from django.db.models import Sum
    penalites = qs_for_tenant(request, PenaliteCotisation.objects.all()).filter(
        membre=request.user
    ).select_related('membre', 'cotisation').order_by('-annee', '-mois')
    
    stats = penalites.aggregate(
        total_penalites=Sum('penalite_cumulee'),
        total_payees=Sum('penalite_cumulee', filter=Q(est_payee=True)),
    )
    
    paginator = Paginator(penalites, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    return render(request, 'twiyungunganye/penalites/liste.html', {
        'page_obj': page_obj,
        'penalites': page_obj,
        'stats': stats,
        'mes_penalites': True,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_credit_direct(request):
    """Ajouter un crédit directement par admin/gestionnaire"""
    from .forms import CreditApprovalForm
    
    tenant = get_tenant(request)
    if request.method == 'POST':
        form = CreditApprovalForm(request.POST, tenant=tenant)
        if form.is_valid():
            credit = form.save(commit=False)
            if tenant:
                credit.tenant = tenant
            credit.save()
            messages.success(request, f'Crédit #{credit.id_credit} ajouté pour {credit.membre.get_full_name()}.')
            return redirect('detail_credit', pk=credit.pk)
    else:
        form = CreditApprovalForm(tenant=tenant)
    
    return render(request, 'twiyungunganye/credits/ajouter_direct.html', {'form': form})


# Gestion des suggestions
@login_required
def liste_suggestions(request):
    """Liste des suggestions"""
    base = qs_for_tenant(request, Suggestion.objects.all())
    if request.user.is_admin:
        suggestions = base.order_by('-date_soumission')
    else:
        suggestions = base.filter(membre=request.user).order_by('-date_soumission')
    paginator = Paginator(suggestions, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
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
            tenant = get_tenant(request)
            if tenant:
                suggestion.tenant = tenant
            suggestion.save()

            # Notification aux dirigeants
            from .models import Notification
            admins = Membre.objects.filter(tenant=tenant, is_admin=True).exclude(pk=request.user.pk)
            for admin in admins:
                Notification.objects.create(
                    destinataire=admin,
                    expediteur=request.user,
                    type_notification='NOUVELLE_SUGGESTION',
                    titre=f"Nouvelle suggestion de {request.user.get_full_name()}",
                    message=f"{suggestion.titre}",
                    lien=f"/suggestions/",
                )

            messages.success(request, 'Votre suggestion a été soumise avec succès.')
            return redirect('liste_suggestions')
    else:
        form = SuggestionForm()
    
    return render(request, 'twiyungunganye/suggestions/formulaire.html', {'form': form})


@login_required
def modifier_suggestion(request, pk):
    """Modifier une suggestion (membre, seulement si EN_ATTENTE)"""
    suggestion = get_object_or_404(Suggestion, pk=pk)
    if suggestion.membre != request.user:
        messages.error(request, "Vous ne pouvez modifier que vos propres suggestions.")
        return redirect('liste_suggestions')
    if suggestion.statut != 'EN_ATTENTE':
        messages.error(request, "Vous ne pouvez modifier qu'une suggestion en attente.")
        return redirect('liste_suggestions')

    if request.method == 'POST':
        form = SuggestionForm(request.POST, instance=suggestion)
        if form.is_valid():
            form.save()
            messages.success(request, 'Votre suggestion a été modifiée.')
            return redirect('liste_suggestions')
    else:
        form = SuggestionForm(instance=suggestion)

    return render(request, 'twiyungunganye/suggestions/formulaire.html', {
        'form': form,
        'edit_mode': True,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def repondre_suggestion(request, pk):
    """Permet au dirigeant de répondre à une suggestion (statut + réponse)"""
    suggestion = get_object_or_404(Suggestion, pk=pk)

    if request.method == 'POST':
        form = ReponseSuggestionForm(request.POST, instance=suggestion)
        if form.is_valid():
            suggestion = form.save(commit=False)
            from django.utils import timezone
            suggestion.date_reponse = timezone.now()
            suggestion.save()

            # Notification au membre
            from .models import Notification
            Notification.objects.create(
                destinataire=suggestion.membre,
                expediteur=request.user,
                type_notification='REPONSE_SUGGESTION',
                titre=f"Réponse à votre suggestion : {suggestion.titre}",
                message=f"Statut : {suggestion.get_statut_display()}. {suggestion.reponse_admin or ''}",
                lien="/suggestions/",
            )

            messages.success(request, f"Réponse enregistrée. Le membre {suggestion.membre.get_full_name()} sera notifié.")
            return redirect('liste_suggestions')
    else:
        form = ReponseSuggestionForm(instance=suggestion)

    return render(request, 'twiyungunganye/suggestions/repondre.html', {
        'form': form,
        'suggestion': suggestion,
    })


# Profil de l'association
@login_required
def association_profil(request):
    """Page de profil de l'association (tenant)"""
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, "Association non trouvée.")
        return redirect('dashboard')

    association = Association.get_association(tenant)
    cle_active = getattr(request, 'cle_active', None)
    jours_restants = getattr(request, 'jours_restants', 0)

    membres = qs_for_tenant(request, Membre.objects.all()).filter(est_actif=True)
    total_cotisations = qs_for_tenant(request, Cotisation.objects.filter(statut='PAYE')).aggregate(
        Sum('montant')
    )['montant__sum'] or 0

    context = {
        'association': association,
        'tenant': tenant,
        'cle_active': cle_active,
        'jours_restants': jours_restants,
        'total_membres': membres.count(),
        'total_cotisations': total_cotisations,
    }
    return render(request, 'twiyungunganye/association/profil.html', context)


# Rapports
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapports(request):
    """Page des rapports"""
    context = {
        'export_types': EXPORT_TYPES,
    }
    
    return render(request, 'twiyungunganye/rapports/index.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def page_rapport_mensuel(request):
    """Page dédiée au rapport mensuel avec filtre"""
    form = RapportMensuelForm()
    if request.method == 'POST':
        form = RapportMensuelForm(request.POST)
        if form.is_valid():
            mois = int(form.cleaned_data['mois'])
            annee = int(form.cleaned_data['annee'])
            format = request.POST.get('format', 'pdf')
            if format == 'excel':
                return redirect('export_rapport_mensuel_excel', mois=mois, annee=annee)
            return redirect('rapport_mensuel_pdf', mois=mois, annee=annee)
    return render(request, 'twiyungunganye/rapports/rapport_mensuel.html', {'form': form})


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def page_rapport_annuel(request):
    """Page dédiée au rapport annuel avec filtre"""
    form = RapportAnnuelForm()
    if request.method == 'POST':
        form = RapportAnnuelForm(request.POST)
        if form.is_valid():
            annee = int(form.cleaned_data['annee'])
            return redirect('rapport_annuel_pdf', annee=annee)
    return render(request, 'twiyungunganye/rapports/rapport_annuel.html', {'form': form})


# Types d'export avec leurs infos (champs de filtre, URLs)
EXPORT_TYPES = {
    'membres': {
        'label': 'Membres',
               'icone': 'bi-people',
        'description': 'Liste de tous les membres avec leurs cotisations totales',
        'url_pdf': 'export_membres_pdf',
        'url_excel': 'export_membres_excel',
        'filtres': [],
    },
    'cotisations': {
        'label': 'Cotisations',
        'icone': 'bi-cash-coin',
        'description': 'Liste des cotisations régulières avec filtres',
        'url_pdf': 'export_liste_cotisations_pdf',
        'url_excel': 'export_cotisations_excel',
        'filtres': ['mois', 'annee', 'statut', 'membre'],
    },
    'cotisations_imprevus': {
        'label': 'Cotisations Imprévus',
        'icone': 'bi-exclamation-triangle',
        'description': 'Liste des cotisations pour imprévus sociaux',
        'url_pdf': 'export_cotisations_imprevus_pdf',
        'url_excel': 'export_cotisations_imprevus_excel',
        'filtres': ['mois', 'annee', 'statut', 'membre'],
    },
    'credits': {
        'label': 'Crédits',
        'icone': 'bi-credit-card',
        'description': 'Liste des crédits avec état et montants',
        'url_pdf': 'export_liste_credits_pdf',
        'url_excel': None,
        'filtres': ['statut', 'membre'],
    },
    'remboursements': {
        'label': 'Remboursements',
        'icone': 'bi-arrow-return-left',
        'description': 'Liste des remboursements effectués',
        'url_pdf': 'export_liste_remboursements_pdf',
        'url_excel': 'export_remboursements_excel',
        'filtres': ['membre'],
    },
    'interets': {
        'label': 'Intérêts',
        'icone': 'bi-graph-up',
        'description': 'Liste des intérêts générés par crédit',
        'url_pdf': 'export_interets_pdf',
        'url_excel': 'export_interets_excel',
        'filtres': [],
    },
}


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def page_export_filtre(request, export_type):
    """Page dédiée à un type d'export avec filtres"""
    info = EXPORT_TYPES.get(export_type)
    if not info:
        messages.error(request, "Type d'export inconnu.")
        return redirect('rapports')

    # Récupérer les membres pour les filtres
    membres = qs_for_tenant(request, Membre.objects.filter(est_actif=True)).order_by('nom', 'prenom')

    # Appliquer les filtres pour l'aperçu
    filtres_actifs = {}
    queryset = None

    if export_type == 'cotisations':
        qs = qs_for_tenant(request, Cotisation.objects.all()).select_related('membre')
        for f in ['mois', 'annee', 'statut']:
            v = request.GET.get(f) or request.POST.get(f)
            if v:
                filtres_actifs[f] = v
                qs = qs.filter(**{f: int(v) if f in ('mois', 'annee') else v})
        membre_id = request.GET.get('membre') or request.POST.get('membre')
        if membre_id:
            filtres_actifs['membre'] = membre_id
            qs = qs.filter(membre_id=int(membre_id))
        queryset = qs[:20]

    elif export_type == 'credits':
        qs = qs_for_tenant(request, Credit.objects.all()).select_related('membre')
        statut = request.GET.get('statut') or request.POST.get('statut')
        if statut:
            filtres_actifs['statut'] = statut
            qs = qs.filter(statut=statut)
        membre_id = request.GET.get('membre') or request.POST.get('membre')
        if membre_id:
            filtres_actifs['membre'] = membre_id
            qs = qs.filter(membre_id=int(membre_id))
        queryset = qs[:20]

    elif export_type == 'remboursements':
        qs = qs_for_tenant(request, Remboursement.objects.all()).select_related('credit__membre')
        membre_id = request.GET.get('membre') or request.POST.get('membre')
        if membre_id:
            filtres_actifs['membre'] = membre_id
            qs = qs.filter(credit__membre_id=int(membre_id))
        queryset = qs[:20]

    elif export_type == 'cotisations_imprevus':
        qs = qs_for_tenant(request, CotisationImprevu.objects.all()).select_related('membre')
        for f in ['mois', 'annee', 'statut']:
            v = request.GET.get(f) or request.POST.get(f)
            if v:
                filtres_actifs[f] = v
                qs = qs.filter(**{f: int(v) if f in ('mois', 'annee') else v})
        membre_id = request.GET.get('membre') or request.POST.get('membre')
        if membre_id:
            filtres_actifs['membre'] = membre_id
            qs = qs.filter(membre_id=int(membre_id))
        queryset = qs[:20]

    context = {
        'export_type': export_type,
        'info': info,
        'membres': membres,
        'filtres_actifs': filtres_actifs,
        'apercu': queryset,
        'mois_noms': ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                      'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'],
    }
    return render(request, 'twiyungunganye/rapports/export_filtre.html', context)


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
def generer_rapport_mensuel_excel(request):
    """Générer un rapport mensuel en Excel"""
    if request.method == 'POST':
        form = RapportMensuelForm(request.POST)
        if form.is_valid():
            mois = int(form.cleaned_data['mois'])
            annee = int(form.cleaned_data['annee'])
            
            return redirect('export_rapport_mensuel_excel', mois=mois, annee=annee)
    
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


@login_required
def modifier_profil_dirigeant(request):
    """Permet au dirigeant de modifier son propre profil"""
    membre = request.user

    if request.method == 'POST':
        form = ModifierProfilForm(request.POST, request.FILES, instance=membre)
        if form.is_valid():
            form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('modifier_profil_dirigeant')
    else:
        form = ModifierProfilForm(instance=membre)

    return render(request, 'twiyungunganye/membres/formulaire.html', {
        'form': form,
        'action': 'Modifier mon profil',
        'membre': membre,
        'profil_dirigeant': True,
    })


@login_required
def modifier_association(request):
    """Permet au dirigeant de modifier les informations de l'association"""
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, "Association non trouvée.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = AssociationForm(request.POST, request.FILES, instance=tenant)
        if form.is_valid():
            assoc_fields = {'devise', 'montant_max_credit', 'mois_minimum_cotisation_credit', 'duree_remboursement_mois'}
            assoc_vals = {}
            for f in assoc_fields:
                if f in form.cleaned_data:
                    assoc_vals[f] = form.cleaned_data.pop(f)
            for field in form.fields:
                val = form.cleaned_data.get(field)
                if field == 'logo' and val:
                    tenant.logo = val
                elif field != 'logo' and val is not None:
                    setattr(tenant, field, val)
            tenant.save()

            adresse = ", ".join(filter(None, [
                tenant.boite_postale or "",
                tenant.avenue or "",
                tenant.quartier or "",
                tenant.commune or "",
                tenant.province or "",
            ]))
            Association.objects.update_or_create(
                tenant=tenant,
                defaults={
                    'nom': tenant.nom,
                    'sigle': tenant.sigle or '',
                    'adresse': adresse,
                    'telephone': tenant.telephone or '',
                    'email': tenant.email or '',
                    'montant_cotisation_mensuelle': tenant.montant_cotisation_mensuelle,
                    'montant_cotisation_imprevu_mensuelle': tenant.montant_cotisation_imprevu_mensuelle,
                    'montant_max_credit': assoc_vals.get('montant_max_credit') or 500000,
                    'devise': assoc_vals.get('devise') or 'FBU',
                    'mois_minimum_cotisation_credit': assoc_vals.get('mois_minimum_cotisation_credit') or 0,
                    'duree_remboursement_mois': assoc_vals.get('duree_remboursement_mois') or 0,
                }
            )

            messages.success(request, "Les informations de l'association ont été mises à jour.")
            return redirect('association_profil')
    else:
        form = AssociationForm(instance=tenant)

    return render(request, 'twiyungunganye/association/modifier.html', {
        'form': form,
        'tenant': tenant,
    })


@login_required
def notifications_liste(request):
    """Liste des notifications de l'utilisateur connecté"""
    non_lues = Notification.objects.filter(destinataire=request.user, est_lu=False).count()
    notifs = Notification.objects.filter(destinataire=request.user).order_by('-date_creation')
    paginator = Paginator(notifs, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    if request.method == 'POST':
        notif_id = request.POST.get('notif_id')
        if notif_id and notif_id.isdigit():
            Notification.objects.filter(pk=int(notif_id), destinataire=request.user).update(est_lu=True)
        return redirect('notifications_liste')

    context = {
        'page_obj': page_obj,
        'non_lues': non_lues,
    }
    return render(request, 'twiyungunganye/notifications/liste.html', context)


@login_required
def marquer_notification_lue(request, pk):
    """Marquer une notification comme lue"""
    Notification.objects.filter(pk=pk, destinataire=request.user).update(est_lu=True)
    return redirect(request.META.get('HTTP_REFERER', 'notifications_liste'))


@login_required
def marquer_tout_lu(request):
    """Marquer toutes les notifications comme lues"""
    Notification.objects.filter(destinataire=request.user, est_lu=False).update(est_lu=True)
    messages.success(request, "Toutes les notifications ont été marquées comme lues.")
    return redirect('notifications_liste')


import io as io_module
import qrcode
from django.http import HttpResponse

@login_required
def qr_code_association(request):
    """Télécharger le QR code de l'association"""
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, "Aucune association trouvée.")
        return redirect('dashboard')

    association = Association.get_association(tenant)
    lines = []
    if association:
        lines.append(f"Association: {association.nom}")
        if association.sigle:
            lines.append(f"Sigle: {association.sigle}")
    if tenant:
        if tenant.nif:
            lines.append(f"NIF: {tenant.nif}")
        parts = []
        for f in ('province', 'commune', 'quartier', 'avenue', 'numero'):
            v = getattr(tenant, f, None)
            if v:
                parts.append(str(v))
        if parts:
            lines.append(f"Adresse: {', '.join(parts)}")
        if tenant.boite_postale:
            lines.append(f"B.P.: {tenant.boite_postale}")
        if tenant.telephone:
            lines.append(f"Tél.: {tenant.telephone}")
        if tenant.email:
            lines.append(f"Email: {tenant.email}")

    content = '\n'.join(lines)
    img = qrcode.make(content, box_size=10, border=2)
    buf = io_module.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    return HttpResponse(buf.getvalue(), content_type='image/png',
                        headers={'Content-Disposition': f'attachment; filename="qr_{tenant.sous_domaine}.png"'})


# ========== DÉPENSES DE L'ASSOCIATION ==========
@login_required
def liste_depenses(request):
    """Liste toutes les dépenses de l'association"""
    depenses = Depense.objects.all()
    depenses = qs_for_tenant(request, depenses)
    paginator = Paginator(depenses, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    total_depenses = depenses.aggregate(Sum('montant'))['montant__sum'] or 0
    return render(request, 'twiyungunganye/depenses/liste.html', {
        'page_obj': page_obj,
        'total_depenses': total_depenses,
    })


@login_required
@user_passes_test(is_admin_only)
def ajouter_depense(request):
    """Ajouter une nouvelle dépense (réservé au dirigeant)"""
    tenant = get_tenant(request)
    if not tenant:
        messages.error(request, "Aucune association trouvée.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = DepenseForm(request.POST)
        if form.is_valid():
            depense = form.save(commit=False)
            depense.tenant = tenant
            depense.cree_par = request.user
            depense.save()
            messages.success(request, "Dépense enregistrée avec succès.")
            return redirect('liste_depenses')
    else:
        form = DepenseForm()

    return render(request, 'twiyungunganye/depenses/ajouter.html', {
        'form': form,
    })


@login_required
def fiche_paiement_pdf(request, pk=None):
    """Génère une fiche de paiement pour un membre"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.platypus.flowables import HRFlowable
    from .models import Cotisation, CotisationImprevu, Credit, Remboursement
    from decimal import Decimal
    from io import BytesIO

    if pk is not None:
        membre = get_object_or_404(Membre, pk=pk)
        if membre.pk != request.user.pk and not request.user.is_admin:
            messages.error(request, "Vous n'avez pas les droits pour voir cette fiche.")
            return redirect('dashboard')
    else:
        membre = request.user
    tenant = get_tenant(request)
    association = Association.get_association(tenant)
    devise = "FBU"
    if association and association.devise:
        devise = association.devise

    now = timezone.now()
    mois = now.month
    annee = now.year

    # Données du mois courant
    cotisation_mois = Cotisation.objects.filter(
        membre=membre, mois=mois, annee=annee
    ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

    cotisation_imprevu_mois = CotisationImprevu.objects.filter(
        membre=membre, mois=mois, annee=annee
    ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

    remboursement_du = sum(
        credit.get_reste_a_rembourser()
        for credit in Credit.objects.filter(membre=membre).exclude(statut='REMBOURSE').exclude(statut='REJETE')
    ) or Decimal('0.000')

    credits_demandes = Credit.objects.filter(
        membre=membre
    ).order_by('-date_demande')[:3]

    buffer = BytesIO()
    filename = f"Fiche_Paiement_{membre.nom}_{membre.prenom}.pdf"

    doc = SimpleDocTemplate(buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm)
    elements = []
    W = 17*cm

    # En-tête avec QR code
    qr_buf = None
    try:
        lines = []
        if association:
            lines.append(f"Association: {association.nom}")
            if association.sigle:
                lines.append(f"Sigle: {association.sigle}")
        if tenant:
            if tenant.nif:
                lines.append(f"NIF: {tenant.nif}")
            if tenant.telephone:
                lines.append(f"Tél.: {tenant.telephone}")
            if tenant.email:
                lines.append(f"Email: {tenant.email}")
        if lines:
            qr_img = qrcode.make('\n'.join(lines), box_size=4, border=1)
            qr_buf = io_module.BytesIO()
            qr_img.save(qr_buf, format='PNG')
            qr_buf.seek(0)
    except Exception:
        pass

    logo_path = None
    if association and association.logo:
        try:
            p = association.logo.path
            if os.path.exists(p):
                logo_path = p
        except Exception:
            pass

    title_style = ParagraphStyle('Title', fontSize=16, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)
    label = ParagraphStyle('Label', fontSize=10, fontName='Helvetica-Bold',
                            textColor=colors.HexColor('#333333'))
    value = ParagraphStyle('Value', fontSize=11, fontName='Helvetica',
                            textColor=colors.HexColor('#111111'))
    note = ParagraphStyle('Note', fontSize=8, fontName='Helvetica',
                           textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
    center = ParagraphStyle('Center', fontSize=10, fontName='Helvetica',
                             alignment=TA_CENTER)

    header_cells = []
    if logo_path:
        try:
            limg = Image(logo_path, width=2.5*cm, height=2.5*cm)
            header_cells.append(limg)
        except Exception:
            header_cells.append(Paragraph("", title_style))
    else:
        header_cells.append(Paragraph("", title_style))

    header_cells.append(Paragraph(
        f"<b>{(association.nom if association else 'Association')}</b>",
        title_style))

    if qr_buf:
        try:
            qr_cell = Image(qr_buf, width=2.5*cm, height=2.5*cm)
            header_cells.append(qr_cell)
        except Exception:
            header_cells.append(Paragraph("", title_style))
    else:
        header_cells.append(Paragraph("", title_style))

    header_table = Table([header_cells], colWidths=[3*cm, W-6*cm, 3*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))

    elements.append(Paragraph("FICHE DE PAIEMENT", ParagraphStyle('FicheTitle', fontSize=14,
        fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
        spaceBefore=4, spaceAfter=8, backColor=colors.HexColor('#eef4fa'))))
    elements.append(Spacer(1, 0.2*cm))

    # Date et Heure
    dh_style = ParagraphStyle('DH', fontSize=11, fontName='Helvetica', alignment=TA_CENTER, spaceAfter=4)
    elements.append(Paragraph(
        "Date : ______ / ______ / ______          Heure : ______ : ______",
        dh_style))
    elements.append(Spacer(1, 0.3*cm))

    # Nom du membre
    info = [
        [Paragraph("Membre :", label), Paragraph(f"<b>{membre.prenom} {membre.nom}</b>", value)],
        [Paragraph("Carte d'identité :", label), Paragraph(str(membre.carte_identite), value)],
    ]
    info_t = Table(info, colWidths=[4*cm, W-4*cm])
    info_t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(info_t)
    elements.append(Spacer(1, 0.4*cm))

    # Tableau des montants
    border_c = colors.HexColor('#cccccc')
    fill_c = colors.HexColor('#f9fafb')
    hdr_style = ParagraphStyle('Hdr', fontSize=10, fontName='Helvetica-Bold', textColor=colors.white, alignment=TA_CENTER)
    cell_style = ParagraphStyle('Cell', fontSize=10, fontName='Helvetica', alignment=TA_CENTER)
    total = cotisation_mois + cotisation_imprevu_mois + remboursement_du
    for c in credits_demandes:
        if c.statut == 'DEMANDE' or c.statut == 'APPROUVE':
            total += Decimal(str(c.montant_demande or 0))

    data = [
        [Paragraph("<b>Rubrique</b>", hdr_style),
         Paragraph(f"<b>Montant ({devise})</b>", hdr_style),
         Paragraph("<b>Date</b>", hdr_style)],
        [Paragraph("Cotisation du mois", cell_style),
         Paragraph(f"{cotisation_mois:,.0f}", cell_style),
         Paragraph(f"{mois:02d}/{annee}", cell_style)],
        [Paragraph("Cotisation imprévus", cell_style),
         Paragraph(f"{cotisation_imprevu_mois:,.0f}", cell_style),
         Paragraph(f"{mois:02d}/{annee}", cell_style)],
        [Paragraph("Remboursement dû", cell_style),
         Paragraph(f"{remboursement_du:,.0f}", cell_style),
         Paragraph("En cours", cell_style)],
    ]
    for c in credits_demandes[:2]:
        data.append([
            Paragraph(f"Crédit #{c.pk} ({c.get_statut_display})", cell_style),
            Paragraph(f"{c.montant_demande:,.0f}", cell_style),
            Paragraph(c.date_demande.strftime('%d/%m/%Y'), cell_style),
        ])

    data.append([
        Paragraph("<b>TOTAL À PAYER</b>", ParagraphStyle('Total', fontSize=11,
            fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)),
        Paragraph(f"<b>{total:,.0f}</b>", ParagraphStyle('TotalVal', fontSize=11,
            fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)),
        Paragraph("", cell_style),
    ])

    pay_table = Table(data, colWidths=[7*cm, 5*cm, 5*cm])
    pay_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -2), 0.5, border_c),
        ('BOX', (0, -1), (-1, -1), 1, colors.HexColor('#1a3a5c')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#eef4fa')),
        ('BACKGROUND', (0, 1), (-1, -2), fill_c),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(pay_table)
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("Observation :", label))
    elements.append(Paragraph(
        "_________________________________________________________________________________",
        ParagraphStyle('Obs', fontSize=10, fontName='Helvetica', textColor=colors.HexColor('#cccccc'))))
    elements.append(Spacer(1, 0.8*cm))

    # Signature
    sign = Table([
        [Paragraph("", ParagraphStyle('S', fontSize=10, spaceBefore=20)),
         Paragraph("", ParagraphStyle('S', fontSize=10, spaceBefore=20))],
        [Paragraph("Signature du membre", note),
         Paragraph("Signature du caissier", note)],
    ], colWidths=[W/2, W/2])
    sign.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(sign)

    elements.append(Spacer(1, 0.3*cm))
    if tenant and (tenant.telephone or tenant.email):
        contact = []
        if tenant.telephone:
            contact.append(f"Tél: {tenant.telephone}")
        if tenant.email:
            contact.append(f"Email: {tenant.email}")
        elements.append(Paragraph(" | ".join(contact), note))

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
