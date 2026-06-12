from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.core.paginator import Paginator

from .models import GroupeAcces, Membre
from .menu_permissions import MENU_PERMISSIONS


def is_admin_only(user):
    return user.is_authenticated and user.is_admin


def get_tenant(request):
    return getattr(request, 'tenant', None)


# ─── Liste des groupes ───────────────────────────────────────────
@login_required
@user_passes_test(is_admin_only)
def liste_groupes(request):
    tenant = get_tenant(request)
    if not tenant:
        return HttpResponseForbidden("Aucun tenant associé")
    groupes = GroupeAcces.objects.filter(tenant=tenant).order_by('nom')
    paginator = Paginator(groupes, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'twiyungunganye/acces/groupes_liste.html', {
        'page_obj': page_obj,
    })


# ─── Créer un groupe ─────────────────────────────────────────────
@login_required
@user_passes_test(is_admin_only)
def creer_groupe(request):
    tenant = get_tenant(request)
    if not tenant:
        return HttpResponseForbidden("Aucun tenant associé")

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        selected_perms = request.POST.getlist('permissions')

        if not nom:
            messages.error(request, "Le nom du groupe est obligatoire.")
        else:
            GroupeAcces.objects.create(
                tenant=tenant,
                nom=nom,
                description=description,
                permissions=','.join(selected_perms)
            )
            messages.success(request, f"Le groupe « {nom} » a été créé avec succès.")
            return redirect('liste_groupes')

    return render(request, 'twiyungunganye/acces/groupe_form.html', {
        'menu_choices': MENU_PERMISSIONS,
        'selected_perms': [],
        'groupe': None,
    })


# ─── Modifier un groupe ──────────────────────────────────────────
@login_required
@user_passes_test(is_admin_only)
def modifier_groupe(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return HttpResponseForbidden("Aucun tenant associé")
    groupe = get_object_or_404(GroupeAcces, pk=pk, tenant=tenant)

    if request.method == 'POST':
        nom = request.POST.get('nom', '').strip()
        description = request.POST.get('description', '').strip()
        selected_perms = request.POST.getlist('permissions')

        if not nom:
            messages.error(request, "Le nom du groupe est obligatoire.")
        else:
            groupe.nom = nom
            groupe.description = description
            groupe.permissions = ','.join(selected_perms)
            groupe.save()
            messages.success(request, f"Le groupe « {nom} » a été modifié.")
            return redirect('liste_groupes')

    return render(request, 'twiyungunganye/acces/groupe_form.html', {
        'menu_choices': MENU_PERMISSIONS,
        'selected_perms': groupe.get_permissions_list(),
        'groupe': groupe,
    })


# ─── Supprimer un groupe ─────────────────────────────────────────
@login_required
@user_passes_test(is_admin_only)
def supprimer_groupe(request, pk):
    tenant = get_tenant(request)
    if not tenant:
        return HttpResponseForbidden("Aucun tenant associé")
    groupe = get_object_or_404(GroupeAcces, pk=pk, tenant=tenant)

    if request.method == 'POST':
        nom_confirme = request.POST.get('nom_confirme', '').strip()
        if nom_confirme == groupe.nom:
            nom = groupe.nom
            groupe.delete()
            messages.success(request, f"Le groupe « {nom} » a été supprimé.")
            return redirect('liste_groupes')
        else:
            messages.error(request, "Le nom saisi ne correspond pas au nom du groupe.")

    return render(request, 'twiyungunganye/acces/groupe_confirm_delete.html', {
        'groupe': groupe,
        'membres_count': groupe.membres.count(),
    })


# ─── Assigner un groupe à un membre (intégré dans modifier_membre) ─
