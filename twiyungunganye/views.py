from .views_additions import approuver_credit_strict as approuver_credit
import os, io as io_module, qrcode
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.cache import cache
from django.db.models import Sum, Count, Q, F
from django.db import IntegrityError
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from dateutil.relativedelta import relativedelta


def tronquer(montant):
    """Retourne le montant sans arrondi (l'affichage via floatformat:3 gère les 3 décimales)"""
    return Decimal(str(montant))

def parse_montant(valeur):
    """Convertit une saisie utilisateur en Decimal (format burundais).
       Le point (.) = séparateur milliers, la virgule (,) = séparateur décimal.
       Ex: '5.800' → 5800, '5,8' → 5.8, '1.200,50' → 1200.50
    """
    s = str(valeur).strip().replace(' ', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif s.count('.') > 1:
        parts = s.split('.')
        s = ''.join(parts[:-1]) + '.' + parts[-1]
    return Decimal(s)

from .pdf_utils import save_pdf_and_respond, dispo_fichier
from .models import (
    Membre, Cotisation, CotisationImprevu, Credit, Interet, 
    Remboursement, Association, Suggestion, Notification, PenaliteCotisation, Depense
)
from superadmin.models import Tenant as TenantModel
from .forms import (
    LoginForm, MembrePasswordCreationForm, MembreForm, CotisationForm,
    CotisationImprevuForm, CreditDemandeForm, CreditApprovalForm, 
    RemboursementForm, SuggestionForm, ReponseSuggestionForm, RapportMensuelForm, RapportAnnuelForm, RapportPeriodeForm,
    AssociationForm, ModifierProfilForm, MembrePasswordChangeForm, DepenseForm,
    EncaisserCotisationForm, ReinitialiserMotDePasseMembreForm,
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
    """Filtre un queryset par le tenant de la requête (fail-closed)."""
    if getattr(request, 'is_superadmin', False):
        return qs
    tenant = get_tenant(request)
    if tenant is None:
        return qs.none()
    return qs.filter(**{field: tenant})


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
def _login_throttle_key(request, username):
    ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
    return f"login_fail:{ip}:{(username or '').strip().lower()}"


def _login_is_locked(request, username):
    from django.conf import settings
    key = _login_throttle_key(request, username)
    attempts = cache.get(key, 0)
    return attempts >= getattr(settings, 'LOGIN_MAX_ATTEMPTS', 5)


def _login_register_failure(request, username):
    from django.conf import settings
    key = _login_throttle_key(request, username)
    attempts = cache.get(key, 0) + 1
    cache.set(key, attempts, getattr(settings, 'LOGIN_LOCKOUT_SECONDS', 900))


def _login_reset_failures(request, username):
    cache.delete(_login_throttle_key(request, username))


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
        username = request.POST.get('username', '')
        if _login_is_locked(request, username):
            messages.error(
                request,
                "Trop de tentatives échouées. Veuillez réessayer dans quelques minutes."
            )
            form = LoginForm(request, data=request.POST, tenant_queryset=tenants)
            return render(request, 'twiyungunganye/login.html', {
                'form': form, 'tenants': tenants, 'tenants_page': tenants_page,
                'tenant_courant': tenant_courant,
            })

        form = LoginForm(request, data=request.POST, tenant_queryset=tenants)
        if form.is_valid():
            user = form.get_user()
            if not getattr(user, 'est_actif', True):
                messages.error(request, "Ce compte est désactivé. Contactez l'administrateur.")
                return render(request, 'twiyungunganye/login.html', {
                    'form': form, 'tenants': tenants, 'tenants_page': tenants_page,
                })
            if user.tenant_id and not user.is_superuser:
                if not user.tenant or not user.tenant.actif:
                    messages.error(request, "Cette association est suspendue.")
                    return render(request, 'twiyungunganye/login.html', {
                        'form': form, 'tenants': tenants, 'tenants_page': tenants_page,
                    })
            tenant_choisi = form.cleaned_data.get('tenant') or tenant_courant
            if tenant_choisi and user.tenant_id and user.tenant_id != tenant_choisi.pk:
                messages.error(request, "Ce membre n'appartient pas à cette association.")
                return render(request, 'twiyungunganye/login.html', {
                    'form': form, 'tenants': tenants, 'tenants_page': tenants_page,
                    'tenant_courant': tenant_courant,
                })
            _login_reset_failures(request, username)
            login(request, user)
            messages.success(request, f'Bienvenue {user.get_full_name()} !')
            if user.is_superuser:
                return redirect('superadmin:dashboard')
            return redirect('dashboard')
        else:
            _login_register_failure(request, username)
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


@require_POST
def logout_view(request):
    """Vue de déconnexion (POST uniquement pour éviter le CSRF logout)"""
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
    # Intérêts / Pénalités / Remboursements (globaux)
    base_interets = qs_for_tenant(request, Interet.objects.all())
    base_penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False))
    trm = base_remboursements.filter(date_remboursement__month=mois_actuel, date_remboursement__year=annee_actuelle).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0
    tipm = base_interets.filter(date_remboursement__month=mois_actuel, date_remboursement__year=annee_actuelle).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or 0

    # Solde de caisse (uniquement le mois en cours)
    from .models import Depense
    base_depenses = qs_for_tenant(request, Depense.objects.all()) if hasattr(request, 'tenant') else Depense.objects.none()
    total_depenses = base_depenses.aggregate(Sum('montant'))['montant__sum'] or 0

    total_membres = base_membres.filter(est_actif=True).count()
    cotisations_payees = base_cotisations.filter(mois=mois_actuel, annee=annee_actuelle, statut='PAYE').count()
    taux_paiement = (cotisations_payees / total_membres * 100) if total_membres > 0 else 0

    # Activités
    dernieres_cotisations = base_cotisations.filter(statut='PAYE').select_related('membre').order_by('-date_paiement')[:10]
    derniers_credits = base_credits.select_related('membre').order_by('-date_demande')[:10]

    # Intérêts / Pénalités / Remboursements (globaux)
    total_penalites_payees = base_penalites.aggregate(Sum('montant_paye'))['montant_paye__sum'] or 0
    total_penalites_payees_mois = base_penalites.filter(date_paiement__month=mois_actuel, date_paiement__year=annee_actuelle).aggregate(Sum('montant_paye'))['montant_paye__sum'] or 0

    solde_caisse = tcm + trm + tipm + total_penalites_payees_mois - tcrm

    total_credits_restants = Decimal('0')
    for c in base_credits.filter(statut__in=['APPROUVE', 'EN_COURS']).iterator():
        total_credits_restants += c.get_reste_a_rembourser()

    total_interets_percus = base_interets.filter(date_remboursement__isnull=False).aggregate(
        Sum('interet_rembourse')
    )['interet_rembourse__sum'] or 0

    capital_association = solde_caisse + total_credits_restants

    context.update({
        'cotisations_3_derniers_mois': cotisations_3_derniers_mois,
        'credits_3_derniers_mois': credits_3_derniers_mois,
        'imprevus_3_derniers_mois': imprevus_3_derniers_mois,
        'total_cotisations_mois_actuel': tcm,
        'total_credits_mois_actuel': tcrm,
        'total_imprevus_mois_actuel': tim,
        'total_remboursements_mois': trm,
        'total_interets_percus_mois': tipm,
        'total_penalites_payees_mois': total_penalites_payees_mois,
        'total_revenus_mois': tcm + tim + trm + tipm + total_penalites_payees_mois,
        'total_general_mois_actuel': (tcm + tim + trm + tipm + total_penalites_payees_mois) - tcrm,
        'total_membres': total_membres,
        'solde_caisse': solde_caisse,
        'taux_paiement': taux_paiement,
        'total_imprevus_capital': base_imprevus.filter(statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or 0,
        'total_remboursements': base_remboursements.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0,
        'total_depenses': total_depenses,
        'total_penalites_payees': total_penalites_payees,
        'capital_association': capital_association,
        'total_credits_restants': total_credits_restants,
        'total_interets_percus': total_interets_percus,
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


@login_required
@user_passes_test(is_admin_only)
def reinitialiser_mot_de_passe_membre(request, pk):
    """Permet à l'admin de l'association de réinitialiser le mot de passe d'un membre."""
    membre = get_object_or_404(qs_for_tenant(request, Membre.objects.all()), pk=pk)

    if membre.is_superuser and not request.user.is_superuser:
        messages.error(request, "Vous ne pouvez pas réinitialiser le mot de passe de ce compte.")
        return redirect('liste_membres')

    if membre.pk == request.user.pk:
        messages.info(
            request,
            "Utilisez la page « Changer mon mot de passe » pour modifier votre propre mot de passe."
        )
        return redirect('changer_mot_de_passe')

    if request.method == 'POST':
        form = ReinitialiserMotDePasseMembreForm(request.POST)
        if form.is_valid():
            membre.set_password(form.cleaned_data['password'])
            membre.save(update_fields=['password'])
            messages.success(
                request,
                f"Mot de passe réinitialisé pour {membre.prenom} {membre.nom}."
            )
            return redirect('detail_membre', pk=membre.pk)
    else:
        form = ReinitialiserMotDePasseMembreForm()

    return render(request, 'twiyungunganye/membres/reinitialiser_mot_de_passe.html', {
        'form': form,
        'membre': membre,
    })


@login_required
@user_passes_test(is_admin_only)
def supprimer_membre(request, pk):
    """Supprimer un membre"""
    membre = get_object_or_404(qs_for_tenant(request, Membre.objects.all()), pk=pk)

    if request.method == 'POST':
        nom = membre.get_full_name()
        membre.delete()
        messages.success(request, f'Le membre {nom} a été supprimé.')
        return redirect('liste_membres')

    return render(request, 'twiyungunganye/confirmer_suppression.html', {
        'objet': membre,
        'titre': f'Membre : {membre.get_full_name()}',
        'message': f'Supprimer le membre {membre.get_full_name()} (carte: {membre.carte_identite}) ? Cette action est irréversible.',
        'url_supprimer': 'supprimer_membre',
        'url_annuler': 'liste_membres',
    })


# Gestion des cotisations régulières
@login_required
@user_passes_test(is_admin_or_gestionnaire)
def encaisser_cotisation(request):
    """Encaisser un paiement qui peut couvrir plusieurs mois"""
    from decimal import Decimal

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    if request.method == 'POST':
        form = EncaisserCotisationForm(request.POST, tenant=get_tenant(request))
        if form.is_valid():
            membre = form.cleaned_data['membre']
            montant = form.cleaned_data['montant']
            date_paiement = form.cleaned_data['date_paiement']
            type_cot = form.cleaned_data['type_cotisation']

            tenant = get_tenant(request)
            assoc = Association.get_association(tenant)
            mensualite = assoc.montant_cotisation_mensuelle if type_cot == 'regulier' else assoc.montant_cotisation_imprevu_mensuelle

            if mensualite <= 0:
                messages.error(request, "Le montant mensuel n'est pas configuré pour ce type de cotisation.")
                return redirect('encaisser_cotisation')

            nb_mois = int(montant // mensualite)
            reste = montant % mensualite

            # Trouver les mois impayés les plus anciens
            Model = Cotisation if type_cot == 'regulier' else CotisationImprevu

            cotisations_existantes = qs_for_tenant(request, Model.objects.filter(membre=membre)).values_list('annee', 'mois')
            cotise_set = set(cotisations_existantes)

            now = datetime.now()
            annee_courante = now.year
            mois_courant = now.month

            mois_a_couvrir = []
            for an in range(annee_courante, annee_courante - 5, -1):
                for m in range(12, 0, -1):
                    if (an, m) not in cotise_set and (an < annee_courante or (an == annee_courante and m <= mois_courant)):
                        mois_a_couvrir.append((an, m))
                        if len(mois_a_couvrir) >= max(nb_mois, 1):
                            break
                if len(mois_a_couvrir) >= max(nb_mois, 1):
                    break
            mois_a_couvrir.reverse()  # du plus ancien au plus récent

            if nb_mois < 1:
                # Montant insuffisant → créer un mois en EN_ATTENTE
                an, m = mois_a_couvrir[0] if mois_a_couvrir else (annee_courante, mois_courant)
                Model.objects.update_or_create(
                    membre=membre, mois=m, annee=an,
                    defaults={
                        'montant': montant,
                        'statut': 'EN_ATTENTE',
                        'date_paiement': date_paiement,
                        'tenant': tenant,
                    }
                )
                messages.warning(
                    request,
                    f"Montant insuffisant ({montant}) pour un mois complet ({mensualite}). "
                    f"La cotisation de {membre.get_full_name()} pour {mois_noms[m]} {an} "
                    f"est enregistrée comme <b>impayée</b> (EN_ATTENTE)."
                )
                return redirect('liste_cotisations')

            if len(mois_a_couvrir) < nb_mois:
                messages.warning(
                    request,
                    f"Seulement {len(mois_a_couvrir)} mois impayés trouvés, "
                    f"mais le montant couvre {nb_mois} mois. "
                    f"{len(mois_a_couvrir)} mois seront couverts."
                )

            cree = 0
            for an, m in mois_a_couvrir[:nb_mois]:
                Model.objects.update_or_create(
                    membre=membre,
                    mois=m,
                    annee=an,
                    defaults={
                        'montant': mensualite,
                        'statut': 'PAYE',
                        'date_paiement': date_paiement,
                        'tenant': tenant,
                    }
                )
                cree += 1

            # Nettoyer les pénalités pour les mois couverts
            if type_cot == 'regulier':
                from django.db.models import Q
                from .models import PenaliteCotisation
                q_filter = Q(membre=membre, mois=0, annee=0)
                for an, m in mois_a_couvrir[:nb_mois]:
                    q_filter |= Q(membre=membre, mois=m, annee=an)
                PenaliteCotisation.objects.filter(q_filter).delete()
                messages.success(
                    request,
                    f"{cree} mois de cotisation régulière enregistrés pour {membre.get_full_name()} "
                    f"(total: {montant}). Pénalités correspondantes supprimées."
                )
            else:
                # Imprévu : recalculer les pénalités pour refléter la nouvelle base
                PenaliteCotisation.generer_toutes_penalites()
                messages.success(
                    request,
                    f"{cree} mois d'imprévu enregistrés pour {membre.get_full_name()} "
                    f"(total: {montant}). Pénalités mises à jour."
                )

            if reste > 0:
                messages.info(request, f"Reste non distribué: {reste:.3f} (inférieur à la mensualité de {mensualite}).")

            return redirect('liste_cotisations')
    else:
        form = EncaisserCotisationForm(tenant=get_tenant(request))

    return render(request, 'twiyungunganye/cotisations/encaisser.html', {
        'form': form,
    })


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
            try:
                cotisation = form.save(commit=False)
                tenant = get_tenant(request)
                if tenant:
                    cotisation.tenant = tenant
                cotisation.save()
                messages.success(request, f'Cotisation enregistrée pour {cotisation.membre.get_full_name()}.')
                return redirect('liste_cotisations')
            except IntegrityError:
                messages.error(request, 'Cette combinaison Membre + Mois + Année existe déjà.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f"{label}: {error}")
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
            try:
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
            except IntegrityError:
                messages.error(request, 'Cette combinaison Membre + Mois + Année existe déjà.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f"{label}: {error}")
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
            try:
                form.save()
                messages.success(request, 'Cotisation imprévus modifiée avec succès.')
                return redirect('liste_cotisations_imprevus')
            except IntegrityError:
                messages.error(request, 'Cette combinaison Membre + Mois + Année existe déjà.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    label = form.fields[field].label if field in form.fields else field
                    messages.error(request, f"{label}: {error}")
    else:
        form = CotisationImprevuForm(instance=cotisation, tenant=get_tenant(request))
    
    return render(request, 'twiyungunganye/cotisations_imprevus/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'cotisation': cotisation
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_cotisation(request, pk):
    """Modifier une cotisation régulière existante"""
    cotisation = get_object_or_404(
        qs_for_tenant(request, Cotisation.objects.all()), pk=pk
    )

    if request.method == 'POST':
        form = CotisationForm(request.POST, instance=cotisation, tenant=get_tenant(request))
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Cotisation modifiée avec succès.')
                return redirect('liste_cotisations')
            except IntegrityError:
                messages.error(request, 'Cette combinaison Membre + Mois + Année existe déjà.')
    else:
        form = CotisationForm(instance=cotisation, tenant=get_tenant(request))

    return render(request, 'twiyungunganye/cotisations/formulaire.html', {
        'form': form,
        'action': 'Modifier',
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def supprimer_cotisation(request, pk):
    """Supprimer une cotisation régulière"""
    cotisation = get_object_or_404(
        qs_for_tenant(request, Cotisation.objects.all()), pk=pk
    )

    if request.method == 'POST':
        membre_nom = cotisation.membre.get_full_name()
        cotisation.delete()
        messages.success(request, f'Cotisation de {membre_nom} supprimée avec succès.')
        return redirect('liste_cotisations')

    return render(request, 'twiyungunganye/confirmer_suppression.html', {
        'objet': cotisation,
        'titre': f'Cotisation de {cotisation.membre.get_full_name()} — {cotisation.get_mois_nom} {cotisation.annee}',
        'message': f'Supprimer la cotisation de {cotisation.membre.get_full_name()} pour {cotisation.get_mois_nom} {cotisation.annee} d\'un montant de {cotisation.montant} ?',
        'url_supprimer': 'supprimer_cotisation',
        'url_annuler': 'liste_cotisations',
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def supprimer_cotisation_imprevu(request, pk):
    """Supprimer une cotisation imprévus"""
    cotisation = get_object_or_404(
        qs_for_tenant(request, CotisationImprevu.objects.all()), pk=pk
    )

    if request.method == 'POST':
        membre_nom = cotisation.membre.get_full_name()
        cotisation.delete()
        messages.success(request, f'Cotisation imprévus de {membre_nom} supprimée avec succès.')
        return redirect('liste_cotisations_imprevus')

    return render(request, 'twiyungunganye/confirmer_suppression.html', {
        'objet': cotisation,
        'titre': f'Cotisation imprévus de {cotisation.membre.get_full_name()} — {cotisation.get_mois_nom} {cotisation.annee}',
        'message': f'Supprimer la cotisation imprévus de {cotisation.membre.get_full_name()} pour {cotisation.get_mois_nom} {cotisation.annee} d\'un montant de {cotisation.montant} ?',
        'url_supprimer': 'supprimer_cotisation_imprevu',
        'url_annuler': 'liste_cotisations_imprevus',
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
@user_passes_test(is_admin_or_gestionnaire)
def modifier_credit(request, pk):
    """Modifier un crédit existant"""
    from .forms import CreditApprovalForm
    credit = get_object_or_404(
        qs_for_tenant(request, Credit.objects.all()), pk=pk
    )
    if request.method == 'POST':
        form = CreditApprovalForm(request.POST, instance=credit, tenant=get_tenant(request))
        if form.is_valid():
            form.save()
            messages.success(request, f'Crédit #{credit.id_credit} modifié avec succès.')
            return redirect('liste_credits')
    else:
        form = CreditApprovalForm(instance=credit, tenant=get_tenant(request))
    return render(request, 'twiyungunganye/credits/formulaire_modifier.html', {
        'form': form,
        'credit': credit,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def supprimer_credit(request, pk):
    """Supprimer un crédit"""
    credit = get_object_or_404(
        qs_for_tenant(request, Credit.objects.all()), pk=pk
    )
    if request.method == 'POST':
        membre_nom = credit.membre.get_full_name()
        credit.delete()
        messages.success(request, f'Crédit #{credit.id_credit} de {membre_nom} supprimé.')
        return redirect('liste_credits')
    return render(request, 'twiyungunganye/confirmer_suppression.html', {
        'objet': credit,
        'titre': f'Crédit #{credit.id_credit} — {credit.membre.get_full_name()}',
        'message': f'Supprimer le crédit #{credit.id_credit} de {credit.membre.get_full_name()} d\'un montant de {credit.montant_accorde} FBU ?',
        'url_supprimer': 'supprimer_credit',
        'url_annuler': 'liste_credits',
    })


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
            return redirect('liste_remboursements')
    else:
        initial = {}
        if credit_id:
            initial['credit'] = credit_id
        form = RemboursementForm(initial=initial, tenant=tenant)
    
    return render(request, 'twiyungunganye/remboursements/formulaire.html', {'form': form})


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_remboursement(request, pk):
    """Modifier un remboursement existant"""
    remboursement = get_object_or_404(
        qs_for_tenant(request, Remboursement.objects.all()), pk=pk
    )
    if request.method == 'POST':
        form = RemboursementForm(request.POST, instance=remboursement, tenant=get_tenant(request))
        if form.is_valid():
            form.save()
            messages.success(request, 'Remboursement modifié avec succès.')
            return redirect('liste_remboursements')
    else:
        form = RemboursementForm(instance=remboursement, tenant=get_tenant(request))
    return render(request, 'twiyungunganye/remboursements/formulaire.html', {
        'form': form,
        'action': 'Modifier',
        'remboursement': remboursement
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def supprimer_remboursement(request, pk):
    """Supprimer un remboursement"""
    remboursement = get_object_or_404(
        qs_for_tenant(request, Remboursement.objects.all()), pk=pk
    )
    if request.method == 'POST':
        remboursement.delete()
        messages.success(request, 'Remboursement supprimé avec succès.')
        return redirect('liste_remboursements')
    return render(request, 'twiyungunganye/confirmer_suppression.html', {
        'objet': remboursement,
        'titre': f'Remboursement #{remboursement.id_rembourse} — {remboursement.credit.membre.get_full_name()}',
        'message': f'Supprimer le remboursement de {remboursement.montant_rembourse} FBU effectué le {remboursement.date_remboursement} ?',
        'url_supprimer': 'supprimer_remboursement',
        'url_annuler': 'liste_remboursements',
    })


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
    """Liste des intérêts mensuels calculés, groupés par membre"""
    from django.db.models import Sum
    from collections import OrderedDict
    from datetime import date

    credit_filter = request.GET.get('credit', '')
    annee_filter = request.GET.get('annee', '')
    mois_filter = request.GET.get('mois', '')

    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre')
    if credit_filter:
        credits = credits.filter(pk=credit_filter)

    has_filters = bool(annee_filter) or bool(mois_filter)
    today = timezone.now().date()

    membres_map = OrderedDict()

    for credit in credits:
        if not credit.date_accord:
            continue

        membre = credit.membre
        mid = membre.id_membre
        if mid not in membres_map:
            membres_map[mid] = {
                'membre': membre,
                'credits': [],
                'total_interets_tous_credits': Decimal('0'),
                'total_rembourse_tous_credits': Decimal('0'),
            }

        taux = Decimal(str(credit.taux_interet)) / Decimal('100') if credit.taux_interet else Decimal('0')
        remboursements = list(credit.remboursements.order_by('date_remboursement')) if credit.pk else []

        interets_existants = credit.interets.all().order_by('-annee', '-mois')
        if annee_filter:
            interets_existants = interets_existants.filter(annee=annee_filter)
        if mois_filter:
            interets_existants = interets_existants.filter(mois=mois_filter)

        mois_details = []
        total_calcule = Decimal('0')
        total_rembourse = Decimal('0')
        for it in interets_existants:
            interet_calcule = it.interet_mensuel
            if interet_calcule <= 0 and it.interet_rembourse <= 0:
                continue
            total_calcule += interet_calcule
            total_rembourse += it.interet_rembourse
            mois_details.append({
                'pk': it.pk,
                'mois': it.mois,
                'annee': it.annee,
                'mois_nom': it.get_mois_nom(),
                'interet_mensuel': it.interet_mensuel,
                'interet_rembourse': it.interet_rembourse,
                'date_remboursement': it.date_remboursement,
                'reste': tronquer(max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))),
                'credit_id': credit.id_credit,
                'montant_accorde': credit.montant_accorde,
                'taux_interet': credit.taux_interet,
                'date_accord': credit.date_accord,
            })

        if not has_filters or mois_details:
            membres_map[mid]['credits'].append({
                'credit': credit,
                'montant_accorde': credit.montant_accorde,
                'taux_interet': credit.taux_interet,
                'date_accord': credit.date_accord,
                'total_calcule': total_calcule,
                'total_rembourse': total_rembourse,
                'reste_cumule': tronquer(max(total_calcule - total_rembourse, Decimal('0'))),
                'mois_details': mois_details,
            })
            membres_map[mid]['total_interets_tous_credits'] += total_calcule
            membres_map[mid]['total_rembourse_tous_credits'] += total_rembourse

    for md in membres_map.values():
        md['total_reste_tous_credits'] = tronquer(max(
            md['total_interets_tous_credits'] - md['total_rembourse_tous_credits'],
            Decimal('0')
        ))

    interets_data = list(membres_map.values())

    base_interets_tenant = Interet.objects.filter(
        credit__in=qs_for_tenant(request, Credit.objects.all())
    )
    if credit_filter:
        base_interets_tenant = base_interets_tenant.filter(credit_id=credit_filter)
    annees_disponibles = base_interets_tenant.values_list('annee', flat=True).distinct().order_by('-annee')

    paginator = Paginator(interets_data, 3)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'interets_data': page_obj,
        'page_obj': page_obj,
        'today': today,
        'annee_courante': today.year,
        'annee_filter': int(annee_filter) if annee_filter else None,
        'mois_filter': int(mois_filter) if mois_filter else None,
        'annees_disponibles': annees_disponibles,
        'credit_filter': credit_filter,
        'mois_list': [(1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'), (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')],
    }
    return render(request, 'twiyungunganye/interets/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def generer_interets(request, credit_id):
    """Générer les intérêts mensuels pour un crédit (mois calendaire)"""
    credit = get_object_or_404(qs_for_tenant(request, Credit.objects.all()), pk=credit_id)

    if credit.statut not in ['APPROUVE', 'EN_COURS', 'REMBOURSE']:
        messages.error(request, "Ce crédit ne peut pas générer d'intérêts.")
        return redirect('liste_interets')

    if not credit.date_accord:
        messages.error(request, "Ce crédit n'a pas de date d'accord.")
        return redirect('liste_interets')

    from calendar import monthrange
    from datetime import date

    tenant = get_tenant(request)
    today = timezone.now().date()

    interets_crees = 0

    current = date(credit.date_accord.year, credit.date_accord.month, 1)

    while current < today:
        last_day = monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, last_day)

        if month_end > today:
            break

        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)

        capital = credit._capital_au(next_month)
        if capital <= 0:
            break

        taux = Decimal(credit.taux_interet) / Decimal(100)
        interet_mensuel = tronquer(capital * taux)
        interet_cumule = credit.calculer_interet(jusqua_date=month_end)

        interet, created = Interet.objects.get_or_create(
            credit=credit,
            mois=current.month,
            annee=current.year,
            defaults={
                'tenant': tenant,
                'interet_mensuel': interet_mensuel,
                'interet_cumule': interet_cumule,
                'date_calcul': month_end,
            }
        )
        if created:
            interets_crees += 1
        else:
            interet.interet_mensuel = interet_mensuel
            interet.interet_cumule = interet_cumule
            interet.date_calcul = month_end
            interet.save(update_fields=['interet_mensuel', 'interet_cumule', 'date_calcul'])

        current = next_month

    if interets_crees > 0:
        messages.success(request, f"{interets_crees} intérêts générés pour le crédit #{credit.id_credit}.")
    else:
        messages.info(request, "Tous les intérêts étaient déjà générés.")

    return redirect('liste_interets')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def generer_tous_interets(request):
    """Générer les intérêts pour tous les crédits actifs (mois calendaire)"""
    from calendar import monthrange
    from datetime import date
    
    tenant = get_tenant(request)
    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre')
    
    total_interets_crees = 0
    today = timezone.now().date()

    for credit in credits:
        if not credit.date_accord:
            continue

        current = date(credit.date_accord.year, credit.date_accord.month, 1)

        while current < today:
            last_day = monthrange(current.year, current.month)[1]
            month_end = date(current.year, current.month, last_day)

            if month_end > today:
                break

            if current.month == 12:
                next_month = date(current.year + 1, 1, 1)
            else:
                next_month = date(current.year, current.month + 1, 1)

            capital = credit._capital_au(next_month)
            if capital <= 0:
                break

            taux = Decimal(credit.taux_interet) / Decimal(100)
            interet_mensuel = tronquer(capital * taux)
            interet_cumule = credit.calculer_interet(jusqua_date=month_end)

            interet, created = Interet.objects.get_or_create(
                credit=credit,
                mois=current.month,
                annee=current.year,
                defaults={
                    'tenant': tenant,
                    'interet_mensuel': interet_mensuel,
                    'interet_cumule': interet_cumule,
                    'date_calcul': month_end,
                }
            )
            if created:
                total_interets_crees += 1
            else:
                interet.interet_mensuel = interet_mensuel
                interet.interet_cumule = interet_cumule
                interet.date_calcul = month_end
                interet.save(update_fields=['interet_mensuel', 'interet_cumule', 'date_calcul'])

            current = next_month
    
    if total_interets_crees > 0:
        messages.success(request, f"{total_interets_crees} intérêts générés pour tous les crédits.")
    else:
        messages.info(request, "Tous les intérêts étaient déjà générés.")
    
    return redirect('liste_interets')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def ajouter_interet_rembourse(request, pk):
    """Ajouter un remboursement d'intérêt pour un mois spécifique"""
    interet = get_object_or_404(qs_for_tenant(request, Interet.objects.all()), pk=pk)
    credit = interet.credit

    interet_calcule = interet.interet_mensuel
    reste_calcule = tronquer(max(interet_calcule - interet.interet_rembourse, Decimal('0')))

    if request.method == 'POST':
        montant_str = request.POST.get('montant_rembourse', '0')
        date_str = request.POST.get('date_remboursement', '')
        try:
            montant = parse_montant(montant_str)
        except (InvalidOperation, TypeError):
            montant = Decimal('0')

        if montant > 0:
            date_paiement = timezone.now().date()
            if date_str:
                from datetime import datetime
                try:
                    date_paiement = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            
            # Créer un historique dans Remboursement
            remb = Remboursement(
                credit=interet.credit,
                tenant=interet.tenant,
                montant_rembourse=Decimal('0'),
                interet_rembourse=tronquer(montant),
                date_remboursement=date_paiement,
                mode_paiement='ESPECES',
                remarque=f"Paiement intérêt ({interet.get_mois_nom()} {interet.annee})"
            )
            remb.save()

            interet.interet_rembourse += tronquer(montant)
            interet.date_remboursement = date_paiement
            interet.save(update_fields=['interet_rembourse', 'date_remboursement'])
            
            messages.success(
                request,
                f"Intérêt remboursé de {montant} enregistré pour {interet.credit.membre.get_full_name()} "
                f"({interet.get_mois_nom()} {interet.annee})."
            )
        else:
            messages.error(request, "Le montant doit être supérieur à 0.")

        return redirect('liste_interets')

    return render(request, 'twiyungunganye/interets/rembourser.html', {
        'interet': interet,
        'interet_mensuel_calcule': interet_calcule,
        'reste': reste_calcule,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_interet_rembourse(request, pk):
    """Modifier le montant remboursé d'un intérêt (remplace, pas ajouter)"""
    interet = get_object_or_404(qs_for_tenant(request, Interet.objects.all()), pk=pk)
    credit = interet.credit

    interet_calcule = interet.interet_mensuel
    reste = tronquer(max(interet_calcule - interet.interet_rembourse, Decimal('0')))

    if request.method == 'POST':
        montant_str = request.POST.get('montant_rembourse', '0')
        date_str = request.POST.get('date_remboursement', '')
        try:
            montant = parse_montant(montant_str)
        except (InvalidOperation, TypeError):
            montant = Decimal('0')

        if montant >= 0:
            if date_str:
                from datetime import datetime
                try:
                    interet.date_remboursement = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            else:
                interet.date_remboursement = None
            
            interet.interet_rembourse = tronquer(montant)
            interet.save(update_fields=['interet_rembourse', 'date_remboursement'])
            
            # Synchroniser avec Remboursement pour l'historique
            signature_1 = f"Paiement intérêt ({interet.get_mois_nom()} {interet.annee})"
            signature_2 = f"Migration automatique paiement interet ({interet.get_mois_nom()} {interet.annee})"
            from django.db.models import Q
            Remboursement.objects.filter(
                credit=interet.credit,
                montant_rembourse=Decimal('0')
            ).filter(
                Q(remarque=signature_1) | Q(remarque=signature_2)
            ).delete()

            if montant > 0:
                date_paiement = interet.date_remboursement or timezone.now().date()
                remb = Remboursement(
                    credit=interet.credit,
                    tenant=interet.tenant,
                    montant_rembourse=Decimal('0'),
                    interet_rembourse=tronquer(montant),
                    date_remboursement=date_paiement,
                    mode_paiement='ESPECES',
                    remarque=signature_1
                )
                remb.save()

            messages.success(
                request,
                f"Remboursement modifié pour {interet.credit.membre.get_full_name()} "
                f"({interet.get_mois_nom()} {interet.annee}) : {interet.interet_rembourse} FBU."
            )
        else:
            messages.error(request, "Le montant doit être supérieur ou égal à 0.")

        return redirect('liste_interets')

    return render(request, 'twiyungunganye/interets/modifier_remboursement.html', {
        'interet': interet,
        'interet_mensuel_calcule': interet_calcule,
        'reste': reste,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_date_remboursement_interet(request, pk):
    """Modifier la date de remboursement d'un intérêt (page dédiée)"""
    interet = get_object_or_404(qs_for_tenant(request, Interet.objects.all()), pk=pk)
    
    if request.method == 'POST':
        date_str = request.POST.get('date_remboursement', '')
        if date_str:
            from datetime import datetime
            try:
                interet.date_remboursement = datetime.strptime(date_str, '%Y-%m-%d').date()
                interet.save(update_fields=['date_remboursement'])
                messages.success(request, "Date de remboursement mise à jour.")
            except (ValueError, TypeError):
                messages.error(request, "Format de date invalide.")
        else:
            interet.date_remboursement = None
            interet.save(update_fields=['date_remboursement'])
            messages.success(request, "Date de remboursement effacée.")
        return redirect('liste_interets')
    
    return render(request, 'twiyungunganye/interets/definir_date.html', {
        'interet': interet,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def liste_penalites(request):
    """Liste des pénalités de cotisations impayées"""
    from dateutil.relativedelta import relativedelta

    tenant = get_tenant(request)
    annee_filter = request.GET.get('annee', '')
    mois_filter = request.GET.get('mois', '')
    statut_filter = request.GET.get('statut', '')

    penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)).filter(membre__est_actif=True).select_related('membre', 'cotisation')
    if annee_filter:
        penalites = penalites.filter(annee=annee_filter)
    if mois_filter:
        penalites = penalites.filter(mois=mois_filter)
    if statut_filter == 'payee':
        penalites = penalites.filter(montant_paye__gte=F('penalite_cumulee'))
    elif statut_filter == 'impayee':
        penalites = penalites.filter(montant_paye__lt=F('penalite_cumulee'))

    penalites = penalites.order_by('-annee', '-mois')

    # Statistiques depuis la DB
    total_paye = penalites.aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0.000')
    stats = penalites.aggregate(
        total_penalites=Sum('penalite_cumulee'),
        count_total=Count('id_penalite'),
    )
    total_penalites_val = stats['total_penalites'] or Decimal('0.000')
    stats['total_penalites'] = total_penalites_val
    stats['total_payees'] = total_paye
    stats['total_attente'] = total_penalites_val - total_paye

    paginator = Paginator(penalites, 3)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Ajuster reste_a_payer pour les impayées
    for pen in page_obj:
        if pen.reste_a_payer > pen.montant_paye:
            pen.reste_a_payer = pen.penalite_cumulee

    annees_disponibles = PenaliteCotisation.objects.filter(
        tenant=tenant
    ).values_list('annee', flat=True).distinct().order_by('-annee') if tenant else []

    context = {
        'page_obj': page_obj,
        'penalites': page_obj,
        'stats': stats,
        'annee_courante': timezone.now().year,
        'annee_filter': int(annee_filter) if annee_filter else None,
        'mois_filter': int(mois_filter) if mois_filter else None,
        'statut_filter': statut_filter,
        'annees_disponibles': annees_disponibles,
        'mois_list': [(1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'), (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')],
    }
    return render(request, 'twiyungunganye/penalites/liste.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def generer_penalites(request):
    """Générer les pénalités pour les membres du tenant courant"""
    total = PenaliteCotisation.generer_toutes_penalites(tenant=get_tenant(request))
    if total > 0:
        messages.success(request, f"{total} pénalités générées/mises à jour.")
    else:
        messages.info(request, "Aucune nouvelle pénalité générée.")
    return redirect('liste_penalites')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def membres_non_payes(request):
    """Liste des membres qui n'ont pas payé régulier ET/OU imprévu pour un mois donné"""
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    tenant = get_tenant(request)
    now = timezone.now()
    mois = int(request.GET.get('mois', now.month))
    annee = int(request.GET.get('annee', now.year))

    # Mois précédent/suivant
    mois_prec = mois - 1 if mois > 1 else 12
    annee_prec = annee if mois > 1 else annee - 1
    mois_suiv = mois + 1 if mois < 12 else 1
    annee_suiv = annee if mois < 12 else annee + 1

    # Membres du tenant actif non-admin avec au moins une cotisation
    membres = Membre.objects.filter(tenant=tenant, est_actif=True, is_admin=False)
    membres = membres.filter(
        Q(cotisations__isnull=False) | Q(cotisations_imprevus__isnull=False)
    ).distinct()

    # Regroupement par statut
    membres_payes = []
    membres_non_payes = []
    membres_non_payes_imp = []

    for m in membres:
        a_paye_reg = Cotisation.objects.filter(membre=m, mois=mois, annee=annee, statut='PAYE').exists()
        a_paye_imp = CotisationImprevu.objects.filter(membre=m, mois=mois, annee=annee, statut='PAYE').exists()

        if not a_paye_reg and not a_paye_imp:
            membres_non_payes.append(m)
        elif not a_paye_reg:
            membres_non_payes.append(m)
        elif not a_paye_imp:
            membres_non_payes_imp.append(m)
        else:
            membres_payes.append(m)

    context = {
        'mois': mois,
        'annee': annee,
        'mois_nom': mois_noms[mois],
        'mois_prec': mois_prec,
        'annee_prec': annee_prec,
        'mois_suiv': mois_suiv,
        'annee_suiv': annee_suiv,
        'membres_payes': membres_payes,
        'membres_non_payes': membres_non_payes,
        'membres_non_payes_imp': membres_non_payes_imp,
        'total_non_payes': len(membres_non_payes),
        'total_payes': len(membres_payes),
        'annees': range(now.year - 2, now.year + 2),
        'mois_list': list(enumerate(mois_noms))[1:],
    }
    return render(request, 'twiyungunganye/penalites/membres_non_payes.html', context)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def marquer_penalite_payee(request, pk):
    """Marquer une pénalité comme payée"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)), pk=pk)
    penalite.montant_paye = penalite.reste_a_payer
    penalite.est_payee = True
    penalite.date_paiement = timezone.now().date()
    penalite.save(update_fields=['montant_paye', 'est_payee', 'date_paiement'])
    messages.success(request, f"Pénalité marquée comme payée.")
    return redirect('liste_penalites')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def payer_penalite(request, pk):
    """Enregistrer un paiement partiel sur une pénalité"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)), pk=pk)

    if request.method == 'POST':
        montant_str = request.POST.get('montant_paye', '0')
        date_str = request.POST.get('date_paiement', '')
        try:
            montant = parse_montant(montant_str)
        except (InvalidOperation, TypeError):
            montant = Decimal('0')

        if montant > 0:
            reste_max = tronquer(max(penalite.reste_a_payer - penalite.montant_paye, Decimal('0')))
            if montant > reste_max:
                messages.error(request, f"Le montant ne peut pas dépasser le reste à payer ({reste_max} ).")
                return redirect('payer_penalite', pk=penalite.pk)

            penalite.montant_paye += tronquer(montant)
            if date_str:
                from datetime import datetime
                try:
                    penalite.date_paiement = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            if penalite.montant_paye >= penalite.reste_a_payer:
                penalite.est_payee = True
            penalite.save()
            messages.success(
                request,
                f"Paiement de {montant} enregistré pour la pénalité de {penalite.membre.get_full_name()} "
                f"({penalite.get_mois_nom} {penalite.annee})."
            )
        else:
            messages.error(request, "Le montant doit être supérieur à 0.")

        return redirect('liste_penalites')

    return render(request, 'twiyungunganye/penalites/payer.html', {
        'penalite': penalite,
        'reste': tronquer(max(penalite.reste_a_payer - penalite.montant_paye, Decimal('0'))),
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def payer_integralement_penalite(request, pk):
    """Payer intégralement une pénalité en un clic"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)), pk=pk)
    montant = tronquer(max(penalite.reste_a_payer - penalite.montant_paye, Decimal('0')))
    penalite.montant_paye += montant
    penalite.est_payee = True
    penalite.date_paiement = timezone.now().date()
    penalite.save()
    messages.success(
        request,
        f"Pénalité payée intégralement : {penalite.membre.get_full_name()} "
        f"({penalite.get_mois_nom} {penalite.annee}) — {montant}"
    )
    return redirect('liste_penalites')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_montant_paye_penalite(request, pk):
    """Modifier le montant payé d'une pénalité (remplace, pas ajouter)"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)), pk=pk)
    reste = tronquer(max(penalite.reste_a_payer, Decimal('0')))

    if request.method == 'POST':
        montant_str = request.POST.get('montant_paye', '0')
        date_str = request.POST.get('date_paiement', '')
        try:
            montant = parse_montant(montant_str)
        except (InvalidOperation, TypeError):
            montant = Decimal('0')

        if montant >= 0:
            penalite.montant_paye = tronquer(montant)
            penalite.est_payee = penalite.montant_paye >= penalite.reste_a_payer
            if date_str:
                from datetime import datetime
                try:
                    penalite.date_paiement = datetime.strptime(date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    pass
            else:
                penalite.date_paiement = None
            penalite.save()
            messages.success(
                request,
                f"Paiement modifié pour la pénalité de {penalite.membre.get_full_name()} "
                f"({penalite.get_mois_nom()} {penalite.annee}) : {penalite.montant_paye} FBU."
            )
        else:
            messages.error(request, "Le montant doit être supérieur ou égal à 0.")

        return redirect('liste_penalites')

    return render(request, 'twiyungunganye/penalites/modifier_paiement.html', {
        'penalite': penalite,
        'reste': reste,
    })


@login_required
@user_passes_test(is_admin_or_gestionnaire)
@require_POST
def supprimer_penalite(request, pk):
    """Exclure une pénalité spécifique (au lieu de supprimer)"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.all()), pk=pk)
    membre_nom = penalite.membre.get_full_name()
    periode = f"{penalite.get_mois_nom} {penalite.annee}"
    penalite.exclu = True
    penalite.save(update_fields=['exclu'])
    messages.success(request, f"Pénalité exclue : {membre_nom} ({periode})")
    return redirect('liste_penalites')


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def modifier_date_paiement_penalite(request, pk):
    """Modifier la date de paiement d'une pénalité"""
    penalite = get_object_or_404(qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)), pk=pk)
    
    if request.method == 'POST':
        date_str = request.POST.get('date_paiement', '')
        if date_str:
            from datetime import datetime
            try:
                penalite.date_paiement = datetime.strptime(date_str, '%Y-%m-%d').date()
                penalite.save(update_fields=['date_paiement'])
                messages.success(request, "Date de paiement mise à jour.")
            except (ValueError, TypeError):
                messages.error(request, "Format de date invalide.")
        else:
            penalite.date_paiement = None
            penalite.save(update_fields=['date_paiement'])
            messages.success(request, "Date de paiement effacée.")
        return redirect('liste_penalites')
    
    return render(request, 'twiyungunganye/penalites/definir_date.html', {
        'penalite': penalite,
    })


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
    """Liste des intérêts du membre connecté, groupés par crédit."""
    today = timezone.now().date()

    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        membre=request.user,
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).select_related('membre').order_by('-date_accord', '-id_credit')

    credits_data = []
    total_interets = Decimal('0')
    total_rembourse = Decimal('0')

    for credit in credits:
        if not credit.date_accord:
            continue

        interets_existants = credit.interets.all().order_by('-annee', '-mois')
        mois_details = []
        total_calcule = Decimal('0')
        total_rembourse_credit = Decimal('0')

        for it in interets_existants:
            if it.interet_mensuel <= 0 and it.interet_rembourse <= 0:
                continue
            total_calcule += it.interet_mensuel
            total_rembourse_credit += it.interet_rembourse
            mois_details.append({
                'pk': it.pk,
                'mois': it.mois,
                'annee': it.annee,
                'mois_nom': it.get_mois_nom(),
                'interet_mensuel': it.interet_mensuel,
                'interet_rembourse': it.interet_rembourse,
                'date_remboursement': it.date_remboursement,
                'reste': tronquer(max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))),
            })

        reste = tronquer(max(total_calcule - total_rembourse_credit, Decimal('0')))
        credits_data.append({
            'credit': credit,
            'montant_accorde': credit.montant_accorde,
            'taux_interet': credit.taux_interet,
            'date_accord': credit.date_accord,
            'statut': credit.get_statut_display(),
            'total_calcule': total_calcule,
            'total_rembourse': total_rembourse_credit,
            'reste_cumule': reste,
            'mois_details': mois_details,
        })
        total_interets += total_calcule
        total_rembourse += total_rembourse_credit

    total_reste = tronquer(max(total_interets - total_rembourse, Decimal('0')))

    return render(request, 'twiyungunganye/interets/mes_interets.html', {
        'credits_data': credits_data,
        'total_interets': total_interets,
        'total_rembourse': total_rembourse,
        'total_reste': total_reste,
        'today': today,
        'mes_interets': True,
    })


@login_required
def mes_penalites(request):
    """Liste des pénalités du membre connecté"""
    from django.db.models import Sum
    from dateutil.relativedelta import relativedelta
    penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)).filter(
        membre=request.user
    ).select_related('membre', 'cotisation').order_by('-annee', '-mois')
    
    total_paye = penalites.aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0.000')
    stats = penalites.aggregate(
        total_penalites=Sum('penalite_cumulee'),
        count_total=Count('id_penalite'),
    )
    total_penalites_val = stats['total_penalites'] or Decimal('0.000')
    stats['total_penalites'] = total_penalites_val
    stats['total_payees'] = total_paye
    stats['total_attente'] = total_penalites_val - total_paye
    
    paginator = Paginator(penalites, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    today = timezone.now().date()
    for pen in page_obj:
        if pen.reste_a_payer > pen.montant_paye:
            pen.reste_a_payer = pen.penalite_cumulee

    return render(request, 'twiyungunganye/penalites/liste.html', {
        'page_obj': page_obj,
        'penalites': page_obj,
        'stats': stats,
        'mes_penalites': True,
        'annee_filter': None,
        'mois_filter': None,
        'statut_filter': '',
        'annees_disponibles': [],
        'mois_list': [(1, 'Janvier'), (2, 'Février'), (3, 'Mars'), (4, 'Avril'), (5, 'Mai'), (6, 'Juin'), (7, 'Juillet'), (8, 'Août'), (9, 'Septembre'), (10, 'Octobre'), (11, 'Novembre'), (12, 'Décembre')],
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
            credit.montant_demande = credit.montant_accorde
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
    suggestion = get_object_or_404(qs_for_tenant(request, Suggestion.objects.all()), pk=pk)
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
    suggestion = get_object_or_404(qs_for_tenant(request, Suggestion.objects.all()), pk=pk)

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


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def page_rapport_periode(request):
    """Rapport sur une période de mois : participants + récapitulatif complet"""
    from dateutil.relativedelta import relativedelta
    from calendar import monthrange

    tenant = get_tenant(request)
    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_imprevus = qs_for_tenant(request, CotisationImprevu.objects.all())
    base_remboursements = qs_for_tenant(request, Remboursement.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_interets = qs_for_tenant(request, Interet.objects.all())
    from cas_assistance.models import CasAssistance
    base_assistances = qs_for_tenant(request, CasAssistance.objects.all())
    from .models import Depense
    base_depenses = qs_for_tenant(request, Depense.objects.all())
    base_penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False))

    mois_data = None
    totals = None
    participants = None
    mois_list = []
    form = RapportPeriodeForm()

    if request.method == 'POST':
        form = RapportPeriodeForm(request.POST)
        if form.is_valid():
            md = int(form.cleaned_data['mois_debut'])
            ad = int(form.cleaned_data['annee_debut'])
            mf = int(form.cleaned_data['mois_fin'])
            af = int(form.cleaned_data['annee_fin'])

            date_debut = date(ad, md, 1)
            date_fin = date(af, mf, monthrange(af, mf)[1])

            mois_list = list(_iter_mois_names(md, ad, mf, af))

            # Collecter tous les membres uniques ayant effectué un paiement sur la période
            membres_ids = set()
            current = date_debut
            while current <= date_fin:
                m, a = current.month, current.year
                mids = base_cotisations.filter(
                    mois=m, annee=a, statut='PAYE'
                ).values_list('membre_id', flat=True).distinct()
                membres_ids.update(mids)
                mids_imp = base_imprevus.filter(
                    mois=m, annee=a, statut='PAYE'
                ).values_list('membre_id', flat=True).distinct()
                membres_ids.update(mids_imp)
                current += relativedelta(months=1)

            membres_ids.update(
                base_remboursements.filter(
                    date_remboursement__range=(date_debut, date_fin)
                ).values_list('credit__membre_id', flat=True).distinct()
            )
            membres_ids.update(
                base_interets.filter(
                    date_remboursement__range=(date_debut, date_fin), interet_rembourse__gt=0
                ).values_list('credit__membre_id', flat=True).distinct()
            )
            membres_ids.update(
                base_penalites.filter(
                    date_paiement__range=(date_debut, date_fin)
                ).values_list('membre_id', flat=True).distinct()
            )

            membres = Membre.objects.filter(id_membre__in=membres_ids).order_by('nom', 'prenom')

            # Matrice participants : cotisations, imprévus, intérêts, remboursements, pénalités par membre/mois
            participants = []
            for membre in membres:
                row = {'membre': membre}
                mois_cotises = 0
                for m, a in mois_list:
                    cot = base_cotisations.filter(
                        membre=membre, mois=m, annee=a, statut='PAYE'
                    ).first()
                    imp = base_imprevus.filter(
                        membre=membre, mois=m, annee=a, statut='PAYE'
                    ).first()
                    interet_qs = base_interets.filter(
                        credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
                    )
                    remb_qs = base_remboursements.filter(
                        credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
                    )
                    pen_qs = base_penalites.filter(
                        membre=membre, date_paiement__month=m, date_paiement__year=a
                    )
                    row[f'{m}-{a}'] = {
                        'cotisation': cot.montant if cot else None,
                        'imprevu': imp.montant if imp else None,
                        'interet': interet_qs.aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0'),
                        'remboursement': remb_qs.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0'),
                        'penalite': pen_qs.aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0'),
                    }
                    if cot:
                        mois_cotises += 1
                row['mois_cotises'] = mois_cotises
                participants.append(row)

            mois_data = []
            cumul = Decimal('0')
            current = date_debut
            while current <= date_fin:
                m, a = current.month, current.year

                cot_mois = base_cotisations.filter(mois=m, annee=a, statut='PAYE').aggregate(
                    Sum('montant'))['montant__sum'] or Decimal('0')
                imp_mois = base_imprevus.filter(mois=m, annee=a, statut='PAYE').aggregate(
                    Sum('montant'))['montant__sum'] or Decimal('0')
                remb_mois = base_remboursements.filter(date_remboursement__month=m,
                    date_remboursement__year=a).aggregate(
                    Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0')
                int_mois = base_interets.filter(date_remboursement__month=m,
                    date_remboursement__year=a).aggregate(
                    Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0')
                cred_mois = base_credits.filter(date_accord__month=m, date_accord__year=a,
                    statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(
                    Sum('montant_accorde'))['montant_accorde__sum'] or Decimal('0')
                pen_mois = base_penalites.filter(date_paiement__month=m, date_paiement__year=a).aggregate(
                    Sum('montant_paye'))['montant_paye__sum'] or Decimal('0')
                assistance_mois = base_assistances.filter(date_assistance__month=m, date_assistance__year=a).aggregate(
                    Sum('montant'))['montant__sum'] or Decimal('0')
                dep_mois = base_depenses.filter(date_depense__month=m, date_depense__year=a).aggregate(
                    Sum('montant'))['montant__sum'] or Decimal('0')

                effectif = base_cotisations.filter(mois=m, annee=a, statut='PAYE').values(
                    'membre').distinct().count()

                reste_imprevus = imp_mois - assistance_mois

                # Solde du mois = mêmes formules que le rapport mensuel
                entrees = cot_mois + remb_mois + int_mois + pen_mois
                sorties = cred_mois + dep_mois
                solde_mois = entrees - sorties
                cumul += solde_mois
                reste_caisse = max(solde_mois, Decimal('0'))

                mois_data.append({
                    'mois': m, 'annee': a,
                    'effectif': effectif,
                    'cotisations': cot_mois,
                    'imprevus': imp_mois,
                    'assistances': assistance_mois,
                    'reste_imprevus': reste_imprevus,
                    'remboursements': remb_mois,
                    'interets': int_mois,
                    'penalites': pen_mois,
                    'credits': cred_mois,
                    'depenses': dep_mois,
                    'solde_mois': solde_mois,
                    'reste_caisse': reste_caisse,
                    'cumul': cumul,
                })
                current += relativedelta(months=1)

            totals = {
                'effectif': max(d['effectif'] for d in mois_data) if mois_data else 0,
                'cotisations': sum(d['cotisations'] for d in mois_data),
                'imprevus': sum(d['imprevus'] for d in mois_data),
                'assistances': sum(d['assistances'] for d in mois_data),
                'reste_imprevus': sum(d['reste_imprevus'] for d in mois_data),
                'remboursements': sum(d['remboursements'] for d in mois_data),
                'interets': sum(d['interets'] for d in mois_data),
                'penalites': sum(d['penalites'] for d in mois_data),
                'credits': sum(d['credits'] for d in mois_data),
                'depenses': sum(d['depenses'] for d in mois_data),
            }

    MOIS_NOMS = {1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
                 7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre'}

    # Nouveau tableau : paiements totaux par membre et par mois
    paiements_par_membre = None
    if mois_data and mois_list:
        # Collecter tous les membres ayant au moins un paiement sur la période
        all_membre_ids = set()
        for m, a in mois_list:
            all_membre_ids.update(base_cotisations.filter(mois=m, annee=a, statut='PAYE').values_list('membre_id', flat=True))
            all_membre_ids.update(base_imprevus.filter(mois=m, annee=a, statut='PAYE').values_list('membre_id', flat=True))
            all_membre_ids.update(base_remboursements.filter(date_remboursement__month=m, date_remboursement__year=a).values_list('credit__membre_id', flat=True))
            all_membre_ids.update(base_interets.filter(date_remboursement__month=m, date_remboursement__year=a).values_list('credit__membre_id', flat=True))
            all_membre_ids.update(base_penalites.filter(date_paiement__month=m, date_paiement__year=a, montant_paye__gt=0).values_list('membre_id', flat=True))
        all_membres = Membre.objects.filter(id_membre__in=all_membre_ids).order_by('nom', 'prenom')

        paiements_par_membre = []
        for membre in all_membres:
            row = {'membre': membre, 'total_general': Decimal('0')}
            for m, a in mois_list:
                cot_val = base_cotisations.filter(
                    membre=membre, mois=m, annee=a, statut='PAYE'
                ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
                imp_val = base_imprevus.filter(
                    membre=membre, mois=m, annee=a, statut='PAYE'
                ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
                remb_val = base_remboursements.filter(
                    credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
                ).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0')
                int_val = base_interets.filter(
                    credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
                ).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0')
                pen_val = base_penalites.filter(
                    membre=membre, date_paiement__month=m, date_paiement__year=a
                ).aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0')
                total_mois = cot_val + imp_val + remb_val + int_val + pen_val
                row[f'{m}-{a}'] = {
                    'cotisation': cot_val,
                    'imprevu': imp_val,
                    'remboursement': remb_val,
                    'interet': int_val,
                    'penalite': pen_val,
                    'total': total_mois,
                }
                row['total_general'] += total_mois
            paiements_par_membre.append(row)

    return render(request, 'twiyungunganye/rapports/rapport_periode.html', {
        'form': form,
        'mois_data': mois_data,
        'totals': totals,
        'participants': participants,
        'paiements_par_membre': paiements_par_membre,
        'MOIS_NOMS': MOIS_NOMS,
        'mois_list': mois_list,
    })


def _iter_mois_names(md, ad, mf, af):
    """Retourne les tuples (mois, annee) entre deux dates"""
    from calendar import monthrange
    from dateutil.relativedelta import relativedelta
    from datetime import date
    d = date(ad, md, 1)
    fin = date(af, mf, monthrange(af, mf)[1])
    while d <= fin:
        yield (d.month, d.year)
        d += relativedelta(months=1)


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
    'penalites': {
        'label': 'Pénalités',
        'icone': 'bi-exclamation-triangle',
        'description': 'Liste des pénalités de cotisations impayées',
        'url_pdf': None,
        'url_excel': 'export_penalites_excel',
        'filtres': ['mois', 'annee', 'statut', 'membre'],
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

    elif export_type == 'penalites':
        qs = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False)).select_related('membre')
        for f in ['mois', 'annee']:
            v = request.GET.get(f) or request.POST.get(f)
            if v:
                filtres_actifs[f] = v
                qs = qs.filter(**{f: int(v) if f in ('mois', 'annee') else v})
        statut = request.GET.get('statut') or request.POST.get('statut')
        if statut:
            filtres_actifs['statut'] = statut
            if statut == 'payee':
                qs = qs.filter(montant_paye__gte=F('penalite_cumulee'))
            elif statut == 'impayee':
                qs = qs.filter(montant_paye__lt=F('penalite_cumulee'))
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
def changer_mot_de_passe(request):
    """Permet à chaque membre de changer son propre mot de passe."""
    if request.method == 'POST':
        form = MembrePasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Votre mot de passe a été modifié avec succès.")
            return redirect('changer_mot_de_passe')
    else:
        form = MembrePasswordChangeForm(request.user)

    return render(request, 'twiyungunganye/membres/changer_mot_de_passe.html', {
        'form': form,
    })


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
@user_passes_test(is_admin_only)
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
@require_POST
def marquer_notification_lue(request, pk):
    """Marquer une notification comme lue"""
    Notification.objects.filter(pk=pk, destinataire=request.user).update(est_lu=True)
    return redirect('notifications_liste')


@login_required
@require_POST
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
                        headers={'Content-Disposition': dispo_fichier(f"qr_{tenant.sous_domaine}.png")})


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
    from .models import (
        Cotisation, CotisationImprevu, Credit, Remboursement,
        Interet, PenaliteCotisation,
    )
    from decimal import Decimal
    from io import BytesIO

    if pk is not None:
        membre = get_object_or_404(qs_for_tenant(request, Membre.objects.all()), pk=pk)
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

    mensuel_regulier = (association.montant_cotisation_mensuelle if association else Decimal('0')) or Decimal('0')
    mensuel_imprevu = (association.montant_cotisation_imprevu_mensuelle if association else Decimal('0')) or Decimal('0')

    def montant_du_mois(model, mensuel):
        """Montant encore dû pour le mois courant (0 si déjà payé)."""
        obj = model.objects.filter(membre=membre, mois=mois, annee=annee).first()
        if obj is None:
            return tronquer(mensuel)
        if obj.statut == 'PAYE':
            return Decimal('0.000')
        if obj.montant and obj.montant > 0:
            return tronquer(obj.montant)
        return tronquer(mensuel)

    # Cotisations impayées du mois courant
    cotisation_mois = montant_du_mois(Cotisation, mensuel_regulier)
    cotisation_imprevu_mois = montant_du_mois(CotisationImprevu, mensuel_imprevu)

    # Crédits réellement en cours (les demandes en attente ne sont pas des dettes)
    credits_actifs = qs_for_tenant(request, Credit.objects.all()).filter(
        membre=membre, statut__in=['APPROUVE', 'EN_COURS']
    )

    # Détail du crédit restant (affiché pour information, non ajouté au total à payer)
    credits_info = []
    remboursement_du = Decimal('0.000')
    interets_impayes = Decimal('0.000')
    for credit in credits_actifs:
        capital_restant = credit.get_reste_a_rembourser()
        interets_credit = sum(
            (
                max(it.interet_mensuel - it.interet_rembourse, Decimal('0.000'))
                for it in credit.interets.all()
            ),
            Decimal('0.000')
        )
        remboursement_du += capital_restant
        interets_impayes += interets_credit
        if capital_restant > 0 or interets_credit > 0:
            credits_info.append({
                'credit': credit,
                'capital_restant': capital_restant,
                'interets_impayes': interets_credit,
                'total': tronquer(capital_restant + interets_credit),
            })
    total_credit_restant = tronquer(remboursement_du + interets_impayes)

    penalites_qs = qs_for_tenant(
        request, PenaliteCotisation.objects.filter(membre=membre, exclu=False)
    )
    total_penalites = penalites_qs.aggregate(
        total=Sum('penalite_cumulee')
    )['total'] or Decimal('0.000')
    total_penalites_payees = penalites_qs.aggregate(
        total=Sum('montant_paye')
    )['total'] or Decimal('0.000')
    penalites_impayees = tronquer(max(total_penalites - total_penalites_payees, Decimal('0.000')))

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
    # Le total à payer ne contient que les cotisations impayées + pénalités.
    # Le crédit restant est affiché séparément, à titre informatif.
    total = tronquer(cotisation_mois + cotisation_imprevu_mois + penalites_impayees)

    data = [
        [Paragraph("<b>Rubrique</b>", hdr_style),
         Paragraph(f"<b>Montant ({devise})</b>", hdr_style),
         Paragraph("<b>Date</b>", hdr_style)],
        [Paragraph("Cotisation du mois (impayée)", cell_style),
         Paragraph(f"{cotisation_mois:,.0f}", cell_style),
         Paragraph(f"{mois:02d}/{annee}", cell_style)],
        [Paragraph("Cotisation imprévus (impayée)", cell_style),
         Paragraph(f"{cotisation_imprevu_mois:,.0f}", cell_style),
         Paragraph(f"{mois:02d}/{annee}", cell_style)],
        [Paragraph("Pénalités impayées", cell_style),
         Paragraph(f"{penalites_impayees:,.0f}", cell_style),
         Paragraph("En cours", cell_style)],
    ]

    data.append([
        Paragraph("<b>TOTAL À PAYER</b>", ParagraphStyle('Total', fontSize=11,
            fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)),
        Paragraph(f"<b>{total:,.0f}</b>", ParagraphStyle('TotalVal', fontSize=11,
            fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)),
        Paragraph("Cotisations + pénalités", cell_style),
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

    # Crédit restant : information uniquement, non ajouté au total
    if credits_info:
        elements.append(Paragraph(
            "Crédit restant (information — non inclus dans le total à payer)",
            ParagraphStyle('CreditTitle', fontSize=10, fontName='Helvetica-Bold',
                           textColor=colors.HexColor('#1a3a5c'), spaceAfter=4)))
        credit_hdr = ParagraphStyle('CreditHdr', fontSize=9, fontName='Helvetica-Bold',
                                    textColor=colors.white, alignment=TA_CENTER)
        credit_cell = ParagraphStyle('CreditCell', fontSize=9, fontName='Helvetica',
                                     alignment=TA_CENTER)
        credit_data = [
            [Paragraph("<b>Crédit #</b>", credit_hdr),
             Paragraph("<b>Capital restant</b>", credit_hdr),
             Paragraph("<b>Intérêts impayés</b>", credit_hdr),
             Paragraph("<b>Total</b>", credit_hdr)],
        ]
        for ci in credits_info:
            credit_data.append([
                Paragraph(f"#{ci['credit'].id_credit}", credit_cell),
                Paragraph(f"{ci['capital_restant']:,.0f}", credit_cell),
                Paragraph(f"{ci['interets_impayes']:,.0f}", credit_cell),
                Paragraph(f"{ci['total']:,.0f}", credit_cell),
            ])
        credit_data.append([
            Paragraph("<b>TOTAL CRÉDIT RESTANT</b>", ParagraphStyle('CreditTotal', fontSize=9,
                fontName='Helvetica-Bold', textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER)),
            Paragraph(f"<b>{remboursement_du:,.0f}</b>", credit_cell),
            Paragraph(f"<b>{interets_impayes:,.0f}</b>", credit_cell),
            Paragraph(f"<b>{total_credit_restant:,.0f}</b>", credit_cell),
        ])
        credit_table = Table(credit_data, colWidths=[3.5*cm, 4.5*cm, 4.5*cm, 4.5*cm])
        credit_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#6c757d')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -2), 0.5, border_c),
            ('BOX', (0, -1), (-1, -1), 1, colors.HexColor('#6c757d')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f3f5')),
            ('BACKGROUND', (0, 1), (-1, -2), fill_c),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(credit_table)
        elements.append(Spacer(1, 0.15*cm))
        elements.append(Paragraph(
            "Ce montant est affiché pour information et n'est pas ajouté au total à payer.",
            note))
        elements.append(Spacer(1, 0.4*cm))

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
