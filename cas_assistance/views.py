from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from twiyungunganye.pdf_utils import save_pdf_and_respond
from decimal import Decimal

from .models import CasAssistance
from .forms import CasAssistanceForm
from .utils import generer_rapport_assistance_pdf
from twiyungunganye.models import CotisationImprevu


def get_tenant(request):
    return getattr(request, 'tenant', None)


def qs_for_tenant(request, qs, field='tenant'):
    tenant = get_tenant(request)
    if tenant and not getattr(request, 'is_superadmin', False):
        return qs.filter(**{field: tenant})
    return qs


def is_dirigeant(user):
    return user.is_authenticated and user.is_admin


@login_required
def liste_assistance(request):
    recherche = request.GET.get('q', '')

    cas_list = qs_for_tenant(request, CasAssistance.objects.all()).order_by('-date_creation')

    if recherche:
        cas_list = cas_list.filter(
            Q(membre__nom__icontains=recherche) |
            Q(membre__prenom__icontains=recherche) |
            Q(motif__icontains=recherche)
        )

    paginator = Paginator(cas_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    base_cas = qs_for_tenant(request, CasAssistance.objects.all())
    base_imprevus = qs_for_tenant(request, CotisationImprevu.objects.all())
    total_assistance = base_cas.aggregate(total=Sum('montant'))['total'] or Decimal('0.000')
    total_imprevus = base_imprevus.aggregate(total=Sum('montant'))['total'] or Decimal('0.000')
    reste = total_imprevus - total_assistance

    context = {
        'cas_list': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'page_obj': page_obj,
        'recherche': recherche,
        'total_assistance': total_assistance,
        'total_imprevus': total_imprevus,
        'reste': reste,
    }
    return render(request, 'cas_assistance/liste_cas_assistance.html', context)


@login_required
@user_passes_test(is_dirigeant)
def creer_assistance(request):
    tenant = get_tenant(request)
    form = CasAssistanceForm(request.POST or None, tenant=tenant)
    if form.is_valid():
        assistance = form.save(commit=False)
        assistance.cree_par = request.user
        if tenant:
            assistance.tenant = tenant
        assistance.save()
        messages.success(request, "Le cas d'assistance a été enregistré avec succès.")
        return redirect('cas_assistance:liste')

    return render(request, 'cas_assistance/form_cas_assistance.html', {'form': form})


@login_required
@user_passes_test(is_dirigeant)
def modifier_assistance(request, pk):
    assistance = get_object_or_404(
        qs_for_tenant(request, CasAssistance.objects.all()), pk=pk
    )
    form = CasAssistanceForm(request.POST or None, instance=assistance, tenant=get_tenant(request))
    if form.is_valid():
        form.save()
        messages.success(request, "Le cas d'assistance a été modifié avec succès.")
        return redirect('cas_assistance:liste')

    return render(request, 'cas_assistance/form_cas_assistance.html', {'form': form})


@login_required
@user_passes_test(is_dirigeant)
def supprimer_assistance(request, pk):
    assistance = get_object_or_404(
        qs_for_tenant(request, CasAssistance.objects.all()), pk=pk
    )
    assistance.delete()
    messages.success(request, "Le cas d'assistance a été supprimé.")
    return redirect('cas_assistance:liste')


@login_required
@user_passes_test(is_dirigeant)
def rapport_assistance_pdf(request, mois, annee):
    tenant = get_tenant(request)
    buffer = generer_rapport_assistance_pdf(mois, annee, tenant=tenant)
    return save_pdf_and_respond(buffer, "rapport_assistance.pdf")
