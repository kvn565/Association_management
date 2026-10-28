import json
import datetime
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models.functions import TruncMonth
from .models import Tenant, CleActivation, AuditCle, ConnexionAudit, ConfigurationApp
from .forms import TenantForm, CleActivationForm, ClePayanteForm, InscriptionChefForm, GenererCleForm, SuperadminMembreForm, SuperadminResetPasswordForm, SuperadminTenantSupprimerForm, SuperadminPasswordForm, SuperadminTenantCreateForm, SuperadminProfileForm, ConfigurationAppForm
from twiyungunganye.models import Membre, Cotisation, Association
from twiyungunganye.excel_exports import generer_backup_tenant
from twiyungunganye.pdf_utils import dispo_fichier


def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


def superadmin_login(request):
    """Connexion discrète réservée aux superadmins.

    Cette page n'est liée depuis aucune autre page publique. L'URL est
    configurable via SUPERADMIN_LOGIN_PATH dans .env.
    """
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('superadmin:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_superuser and user.is_active:
                login(request, user)
                return redirect('superadmin:dashboard')
            messages.error(request, "Accès réservé au superadmin.")
    else:
        form = AuthenticationForm(request)

    form.fields['username'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': "Carte d'identité",
    })
    form.fields['password'].widget.attrs.update({
        'class': 'form-control',
        'placeholder': 'Mot de passe',
    })

    return render(request, 'superadmin/login.html', {'form': form})


@login_required
@user_passes_test(is_superadmin)
def dashboard(request):
    total_tenants = Tenant.objects.count()
    total_cles = CleActivation.objects.count()
    total_cles_actives = CleActivation.objects.filter(statut='ACTIVE').count()
    total_cles_expirees = CleActivation.objects.filter(statut='EXPIREE').count()
    total_utilisateurs = Membre.objects.count()
    total_machines = ConnexionAudit.objects.values('ip_address').distinct().count()

    tenants = Tenant.objects.all().order_by('nom')
    tenant_id = request.GET.get('tenant')
    selected_tenant = None

    if tenant_id and tenant_id.isdigit():
        selected_tenant = Tenant.objects.filter(pk=int(tenant_id)).first()

    # Pie chart: répartition des membres par statut
    membres_qs = Membre.objects.filter(tenant=selected_tenant) if selected_tenant else Membre.objects.all()
    membres_actifs = membres_qs.filter(est_actif=True).count()
    membres_inactifs = membres_qs.filter(est_actif=False).count()
    repartition_membres = [
        {'label': 'Actifs', 'total': membres_actifs},
        {'label': 'Inactifs', 'total': membres_inactifs},
    ]

    # Bar chart: cotisations mensuelles (6 derniers mois)
    six_mois = timezone.now() - datetime.timedelta(days=180)
    cotisations_qs = Cotisation.objects.filter(date_paiement__gte=six_mois, statut='PAYE')
    if selected_tenant:
        cotisations_qs = cotisations_qs.filter(tenant=selected_tenant)
    cotisations_par_mois = cotisations_qs.annotate(
        mois_cot=TruncMonth('date_paiement')
    ).values('mois_cot').annotate(
        total=Sum('montant')
    ).order_by('mois_cot')

    def serialize_dashboard(data):
        result = []
        for row in data:
            d = {}
            for k, v in row.items():
                if isinstance(v, (datetime.date, datetime.datetime)):
                    d[k] = v.isoformat()[:7]
                elif isinstance(v, Decimal):
                    d[k] = float(v)
                else:
                    d[k] = v
            result.append(d)
        return result

    context = {
        'total_tenants': total_tenants,
        'total_cles': total_cles,
        'total_cles_actives': total_cles_actives,
        'total_cles_expirees': total_cles_expirees,
        'total_utilisateurs': total_utilisateurs,
        'total_machines': total_machines,
        'tenants': tenants,
        'tenant_id': int(tenant_id) if tenant_id and tenant_id.isdigit() else '',
        'selected_tenant': selected_tenant,
        'repartition_membres': repartition_membres,
        'cotisations_par_mois': serialize_dashboard(cotisations_par_mois),
    }
    return render(request, 'superadmin/dashboard.html', context)


@login_required
@user_passes_test(is_superadmin)
def tenant_liste(request):
    tenants = Tenant.objects.annotate(
        nb_cles=Count('cles_activation')
    ).order_by('nom')
    paginator = Paginator(tenants, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    for t in page_obj:
        cle = t.cle_active
        t.cle_active_obj = cle
        t.jours_restants = cle.jours_restants if cle else 0
    context = {'page_obj': page_obj}
    return render(request, 'superadmin/tenant_liste.html', context)


@login_required
@user_passes_test(is_superadmin)
def tenant_creer(request):
    if request.method == 'POST':
        form = SuperadminTenantCreateForm(request.POST)
        if form.is_valid():
            tenant = form.save()
            CleActivation.creer_essai(tenant, cree_par=str(request.user))
            AuditCle.objects.create(
                tenant=tenant, action='CREEE',
                message=f"Association créée + clé essai auto",
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, f"Association '{tenant.nom}' créée avec clé d'essai 14 jours.")
            return redirect('superadmin:tenant_detail', pk=tenant.pk)
    else:
        form = SuperadminTenantCreateForm()
    return render(request, 'superadmin/tenant_form.html', {'form': form, 'action': 'Créer'})


@login_required
@user_passes_test(is_superadmin)
def tenant_detail(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    cles = CleActivation.objects.filter(tenant=tenant).order_by('-date_creation')
    audits = AuditCle.objects.filter(tenant=tenant).order_by('-date_action')[:20]
    context = {
        'tenant': tenant,
        'cles': cles,
        'audits': audits,
        'cle_active': tenant.cle_active,
        'a_deja_une_cle': CleActivation.objects.filter(tenant=tenant, statut__in=['ACTIVE', 'DISPONIBLE'], active=True, date_fin__gte=timezone.now()).exists(),
    }
    return render(request, 'superadmin/tenant_detail.html', context)


@login_required
@user_passes_test(is_superadmin)
def tenant_modifier(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    if request.method == 'POST':
        form = TenantForm(request.POST, request.FILES, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, "Association modifiée avec succès.")
            return redirect('superadmin:tenant_detail', pk=tenant.pk)
    else:
        form = TenantForm(instance=tenant)
    return render(request, 'superadmin/tenant_form.html', {
        'form': form, 'action': 'Modifier', 'tenant': tenant
    })


@login_required
@user_passes_test(is_superadmin)
@require_POST
def tenant_toggle(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    tenant.actif = not tenant.actif
    tenant.save()
    action = 'REACTIVEE' if tenant.actif else 'SUSPENDUE'
    AuditCle.objects.create(
        tenant=tenant, action=action,
        message=f"Association {'réactivée' if tenant.actif else 'suspendue'}",
        ip_address=request.META.get('REMOTE_ADDR', ''),
    )
    messages.success(request, f"Association {'réactivée' if tenant.actif else 'suspendue'}.")
    return redirect('superadmin:tenant_detail', pk=tenant.pk)


@login_required
@user_passes_test(is_superadmin)
def cle_generer(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    deja_cle = CleActivation.objects.filter(tenant=tenant, statut__in=['ACTIVE', 'DISPONIBLE'], active=True, date_fin__gte=timezone.now()).exists()
    if request.method == 'POST':
        if deja_cle:
            messages.error(request, f"L'association « {tenant.nom} » a déjà une ou plusieurs clés actives. Impossible d'en générer une nouvelle.")
            return redirect('superadmin:tenant_detail', pk=tenant.pk)
        form = CleActivationForm(request.POST)
        if form.is_valid():
            cle = form.save(commit=False)
            cle.tenant = tenant
            cle.cree_par = str(request.user)
            cle.save()
            AuditCle.objects.create(
                cle=cle, tenant=tenant, action='CREEE',
                message=f"Clé {cle.type_plan} générée",
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, f"Clé {cle.cle_visible} générée avec succès.")
            return redirect('superadmin:tenant_detail', pk=tenant.pk)
    else:
        form = CleActivationForm(initial={'tenant': tenant})
        form.fields['tenant'].queryset = Tenant.objects.filter(pk=tenant.pk)
    return render(request, 'superadmin/cle_form.html', {
        'form': form, 'tenant': tenant, 'action': 'Générer', 'deja_cle': deja_cle,
        'cles_existantes': CleActivation.objects.filter(tenant=tenant) if deja_cle else [],
    })


@login_required
@user_passes_test(is_superadmin)
def generer_cle(request):
    """Générer une clé pour n'importe quelle association avec choix du plan."""
    if request.method == 'POST':
        form = GenererCleForm(request.POST)
        if form.is_valid():
            cle = form.save(commit=False)
            cle.cree_par = str(request.user)
            cle.save()
            AuditCle.objects.create(
                cle=cle, tenant=cle.tenant, action='CREEE',
                message=f"Clé {cle.type_plan} générée depuis l'interface des clés",
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            messages.success(request, f"Clé {cle.cle_visible} générée pour {cle.tenant.nom}.")
            return redirect('superadmin:cle_liste')
    else:
        form = GenererCleForm()

    tenants_data = [
        {'id': t.pk, 'nom': t.nom, 'nif': t.nif or '—'}
        for t in Tenant.objects.all().order_by('nom')
    ]
    return render(request, 'superadmin/generer_cle.html', {
        'form': form,
        'action': 'Générer la clé',
        'tenants_json': tenants_data,
    })


@login_required
@user_passes_test(is_superadmin)
def cle_liste(request):
    cles = CleActivation.objects.select_related('tenant').order_by('-date_creation')
    paginator = Paginator(cles, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    context = {'page_obj': page_obj}
    return render(request, 'superadmin/cle_liste.html', context)


@login_required
@user_passes_test(is_superadmin)
def cle_detail(request, pk):
    cle = get_object_or_404(CleActivation, pk=pk)
    audits = AuditCle.objects.filter(cle=cle).order_by('-date_action')[:20]
    context = {'cle': cle, 'audits': audits}
    return render(request, 'superadmin/cle_detail.html', context)


@login_required
@user_passes_test(is_superadmin)
def cle_revoquer(request, pk):
    cle = get_object_or_404(CleActivation, pk=pk)
    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        cle.active = False
        cle.motif_revocation = motif
        cle.save()
        AuditCle.objects.create(
            cle=cle, tenant=cle.tenant, action='REVOQUEE',
            message=f"Révocation: {motif}" if motif else "Révocation sans motif",
            ip_address=request.META.get('REMOTE_ADDR', ''),
        )
        messages.warning(request, f"Clé {cle.cle_visible} révoquée.")
        return redirect('superadmin:cle_detail', pk=cle.pk)
    return render(request, 'superadmin/cle_revoquer.html', {'cle': cle})


# ─────────────────────────────────────────────
# GESTION DES UTILISATEURS (superadmin)
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def membre_liste(request):
    membres = Membre.objects.select_related('tenant').order_by('tenant__nom', 'nom', 'prenom')
    tenant_id = request.GET.get('tenant')
    if tenant_id and tenant_id.isdigit():
        membres = membres.filter(tenant_id=int(tenant_id))
    paginator = Paginator(membres, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    tenants = Tenant.objects.all().order_by('nom')
    context = {
        'page_obj': page_obj,
        'tenants': tenants,
        'tenant_id_selected': int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
    }
    return render(request, 'superadmin/membre_liste.html', context)


@login_required
@user_passes_test(is_superadmin)
def membre_creer(request):
    if request.method == 'POST':
        form = SuperadminMembreForm(request.POST)
        if form.is_valid():
            membre = form.save()
            messages.success(
                request,
                f"Utilisateur {membre.prenom} {membre.nom} créé dans {membre.tenant.nom}."
            )
            return redirect('superadmin:membre_liste')
    else:
        form = SuperadminMembreForm()
    return render(request, 'superadmin/membre_form.html', {
        'form': form, 'action': 'Créer un utilisateur'
    })


@login_required
@user_passes_test(is_superadmin)
def membre_modifier(request, pk):
    membre = get_object_or_404(Membre.objects.select_related('tenant'), pk=pk)
    if request.method == 'POST':
        form = SuperadminMembreForm(request.POST, instance=membre)
        if form.is_valid():
            form.save()
            messages.success(request, f"Utilisateur {membre.prenom} {membre.nom} modifié.")
            return redirect('superadmin:membre_liste')
    else:
        form = SuperadminMembreForm(instance=membre)
    return render(request, 'superadmin/membre_form.html', {
        'form': form, 'action': 'Modifier un utilisateur', 'membre': membre
    })


@login_required
@user_passes_test(is_superadmin)
def membre_supprimer(request, pk):
    membre = get_object_or_404(Membre, pk=pk)
    nom = membre.prenom + ' ' + membre.nom
    if request.method == 'POST':
        membre.delete()
        messages.success(request, f"Utilisateur {nom} supprimé.")
        return redirect('superadmin:membre_liste')
    return render(request, 'superadmin/membre_confirm_delete.html', {
        'membre': membre
    })


@login_required
@user_passes_test(is_superadmin)
def membre_reset_password(request, pk):
    membre = get_object_or_404(Membre, pk=pk)
    if request.method == 'POST':
        form = SuperadminResetPasswordForm(request.POST)
        if form.is_valid():
            membre.set_password(form.cleaned_data['password'])
            membre.save()
            messages.success(
                request,
                f"Mot de passe réinitialisé pour {membre.prenom} {membre.nom}."
            )
            return redirect('superadmin:membre_liste')
    else:
        form = SuperadminResetPasswordForm()
    return render(request, 'superadmin/membre_reset_password.html', {
        'form': form, 'membre': membre
    })


@login_required
@user_passes_test(is_superadmin)
def tenant_supprimer(request, pk):
    tenant = get_object_or_404(Tenant, pk=pk)
    nom = tenant.nom
    if request.method == 'POST':
        form = SuperadminTenantSupprimerForm(request.POST)
        if form.is_valid():
            raison = form.cleaned_data.get('raison', '')
            AuditCle.objects.create(
                tenant=tenant, action='SUSPENDUE',
                message=f"Association supprimée. Motif: {raison}" if raison else "Association supprimée",
                ip_address=request.META.get('REMOTE_ADDR', ''),
            )
            tenant.delete()
            messages.success(request, f"L'association '{nom}' a été supprimée.")
            return redirect('superadmin:tenant_liste')
    else:
        form = SuperadminTenantSupprimerForm()
    return render(request, 'superadmin/tenant_supprimer.html', {
        'form': form, 'tenant': tenant
    })


# ─────────────────────────────────────────────
# AUDIT DES CONNEXIONS
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def connexion_liste(request):
    connexions = ConnexionAudit.objects.select_related('tenant').order_by('-date_connexion')
    tenant_id = request.GET.get('tenant')
    if tenant_id and tenant_id.isdigit():
        connexions = connexions.filter(tenant_id=int(tenant_id))
    appareil = request.GET.get('appareil')
    if appareil:
        connexions = connexions.filter(appareil=appareil)
    paginator = Paginator(connexions, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    tenants = Tenant.objects.all().order_by('nom')
    stats = {
        'total': ConnexionAudit.objects.count(),
        'mobiles': ConnexionAudit.objects.filter(appareil='Mobile').count(),
        'tablettes': ConnexionAudit.objects.filter(appareil='Tablette').count(),
        'desktops': ConnexionAudit.objects.filter(appareil='Desktop').count(),
    }
    context = {
        'page_obj': page_obj,
        'tenants': tenants,
        'tenant_id_selected': int(tenant_id) if tenant_id and tenant_id.isdigit() else None,
        'appareil_selected': appareil,
        'stats': stats,
    }
    return render(request, 'superadmin/connexion_liste.html', context)


@login_required
def licence_expiree(request):
    return render(request, 'superadmin/licence_expiree.html', {'hide_sidebar': True})


@login_required
def saisir_cle_payante(request):
    if not (request.user.is_admin or request.user.is_superuser):
        messages.error(request, "Accès réservé au dirigeant de l'association.")
        return redirect('dashboard')
    tenant = getattr(request, 'tenant', None)
    if not tenant:
        messages.error(request, "Association non trouvée.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = ClePayanteForm(request.POST)
        if form.is_valid():
            success, msg, cle = form.verifier_pour_tenant(tenant)
            if success and cle:
                cle.activer()
                AuditCle.objects.create(
                    cle=cle, tenant=tenant, action='ACTIVEE',
                    message=f"Clé payante activée par le chef",
                    ip_address=request.META.get('REMOTE_ADDR', ''),
                )
                messages.success(request, f"Licence activée ! {msg}")
                return redirect('dashboard')
            else:
                messages.error(request, msg)
    else:
        form = ClePayanteForm()

    context = {
        'form': form,
        'tenant': tenant,
        'cle_active': tenant.cle_active,
    }
    return render(request, 'superadmin/saisir_cle_payante.html', context)


def ajax_lookup_nif(request):
    """AJAX endpoint: given a NIF, return the association name + locality data."""
    nif = request.GET.get('nif', '').strip().upper()
    if not nif:
        return JsonResponse({'found': False, 'error': 'NIF requis'})
    try:
        tenant = Tenant.objects.get(nif=nif)
        if not tenant.actif:
            return JsonResponse({'found': False, 'error': 'Association désactivée'})
        if Membre.objects.filter(tenant=tenant, is_admin=True).exists():
            return JsonResponse({'found': False, 'error': 'Un administrateur est déjà inscrit pour cette association'})
        return JsonResponse({
            'found': True,
            'nom': tenant.nom,
            'sigle': tenant.sigle or '',
            'province': tenant.province or '',
            'commune': tenant.commune or '',
            'quartier': tenant.quartier or '',
            'avenue': tenant.avenue or '',
            'numero': tenant.numero or '',
            'boite_postale': tenant.boite_postale or '',
        })
    except Tenant.DoesNotExist:
        return JsonResponse({'found': False, 'error': 'NIF introuvable dans le système'})


@login_required
@user_passes_test(is_superadmin)
def tenant_keys_check(request, pk):
    """AJAX endpoint: check if a tenant already has keys."""
    tenant = get_object_or_404(Tenant, pk=pk)
    a_des_cles = CleActivation.objects.filter(tenant=tenant, statut__in=['ACTIVE', 'DISPONIBLE'], active=True, date_fin__gte=timezone.now()).exists()
    return JsonResponse({'a_des_cles': a_des_cles, 'tenant': tenant.nom})


def inscription_chef(request):
    """
    Inscription du chef/directeur d'une association.
    - Le chef saisit son NIF pour identifier l'association
    - Le nom de l'association s'affiche automatiquement
    - Complète les informations de localité et son compte
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    tenant = None

    if request.method == 'POST':
        form = InscriptionChefForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    cd = form.cleaned_data
                    tenant = cd['_tenant']
                    cle_active = cd['_cle_active']

                    if not tenant or not cle_active:
                        messages.error(request, "Erreur de validation du NIF.")
                        return render(request, 'superadmin/inscription_chef.html', {'form': form})

                    # Mettre à jour les infos de localité du tenant
                    for field in ('province', 'commune', 'quartier', 'avenue', 'numero', 'boite_postale', 'email', 'telephone'):
                        val = cd.get(field, '').strip()
                        if val:
                            setattr(tenant, field, val)
                    tenant.save(update_fields=['province', 'commune', 'quartier', 'avenue', 'numero', 'boite_postale', 'email', 'telephone'])

                    # Créer le compte directeur
                    membre = Membre.objects.create_user(
                        carte_identite=cd['carte_identite'],
                        nom=cd['nom'],
                        prenom=cd['prenom'],
                        password=cd['password1'],
                        email=cd.get('email', ''),
                        telephone=cd.get('telephone', ''),
                        tenant=tenant,
                        is_admin=True,
                        is_staff=True,
                    )

                    # Créer ou mettre à jour l'Association liée au tenant
                    adresse = ", ".join(filter(None, [
                        tenant.boite_postale or "",
                        tenant.avenue or "",
                        tenant.quartier or "",
                        tenant.commune or "",
                        tenant.province or "",
                    ]))
                    Association.objects.get_or_create(
                        tenant=tenant,
                        defaults={
                            'nom': tenant.nom,
                            'sigle': tenant.sigle or '',
                            'adresse': adresse,
                            'telephone': tenant.telephone or '',
                            'email': tenant.email or '',
                            'montant_cotisation_mensuelle': tenant.montant_cotisation_mensuelle,
                            'montant_cotisation_imprevu_mensuelle': tenant.montant_cotisation_imprevu_mensuelle,
                        }
                    )

                    # Activer la clé si elle ne l'est pas déjà
                    if not cle_active.utilisee:
                        cle_active.activer()

                    AuditCle.objects.create(
                        tenant=tenant,
                        action='ACTIVEE',
                        message=f"Inscription du directeur {membre.get_full_name()} pour {tenant.nom}",
                        ip_address=request.META.get('REMOTE_ADDR', ''),
                    )

                    # Connexion automatique
                    login(request, membre)
                    messages.success(
                        request,
                        f"Bienvenue {membre.get_full_name()} ! "
                        f"Votre association '{tenant.nom}' est configurée."
                    )
                    return redirect('dashboard')

            except Exception as e:
                messages.error(request, f"Erreur lors de l'inscription : {str(e)}")
    else:
        form = InscriptionChefForm()

    # Si le formulaire a été soumis mais invalide, essayer de retrouver le tenant
    tenant_info = None
    if request.method == 'POST':
        nif_val = request.POST.get('nif', '').strip().upper()
        if nif_val:
            try:
                t = Tenant.objects.get(nif=nif_val)
                if t.actif and not Membre.objects.filter(tenant=t, is_admin=True).exists():
                    tenant_info = t
            except Tenant.DoesNotExist:
                pass

    return render(request, 'superadmin/inscription_chef.html', {
        'form': form,
        'tenant_info': tenant_info,
    })


# ─────────────────────────────────────────────
# PROFIL SUPERADMIN
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def profil(request):
    """Page de profil superadmin : photo + infos + changement mot de passe"""
    if request.method == 'POST':
        if 'profile_submit' in request.POST:
            profile_form = SuperadminProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profil mis à jour avec succès.")
                return redirect('superadmin:profil')
        elif 'password_submit' in request.POST:
            password_form = SuperadminPasswordForm(request.POST, user=request.user)
            if password_form.is_valid():
                request.user.set_password(password_form.cleaned_data['new_password'])
                request.user.save(update_fields=['password'])
                messages.success(request, "Mot de passe changé avec succès.")
                return redirect('superadmin:profil')
    else:
        profile_form = SuperadminProfileForm(instance=request.user)
        password_form = SuperadminPasswordForm(user=request.user)

    return render(request, 'superadmin/profil.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })


@login_required
@user_passes_test(is_superadmin)
def configurer_app(request):
    config = ConfigurationApp.objects.first()
    if not config:
        config = ConfigurationApp.objects.create()

    form = ConfigurationAppForm(request.POST or None, request.FILES or None, instance=config)
    if form.is_valid():
        form.save()
        messages.success(request, "Configuration de l'application mise à jour avec succès.")
        return redirect('superadmin:configurer_app')

    return render(request, 'superadmin/config_app.html', {
        'form': form,
        'config': config,
    })


# ─────────────────────────────────────────────
# EXTRACTION DES DONNÉES (BACKUP EXCEL)
# ─────────────────────────────────────────────

@login_required
@user_passes_test(is_superadmin)
def extraction_donnees(request):
    tenants = Tenant.objects.all().order_by('nom')
    if request.method == 'POST':
        tenant_id = request.POST.get('tenant', '')
        if not tenant_id or not tenant_id.isdigit():
            messages.error(request, "Veuillez sélectionner une association.")
            return redirect('superadmin:extraction_donnees')
        tenant = get_object_or_404(Tenant, pk=int(tenant_id))
        try:
            buffer, nom_tenant, now = generer_backup_tenant(tenant, request)
            from django.http import HttpResponse
            response = HttpResponse(buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = dispo_fichier(f"Backup_{nom_tenant}_{now}.xlsx")
            return response
        except Exception as e:
            messages.error(request, f"Erreur lors de l'extraction : {str(e)}")
            return redirect('superadmin:extraction_donnees')
    return render(request, 'superadmin/extraction_donnees.html', {'tenants': tenants})
