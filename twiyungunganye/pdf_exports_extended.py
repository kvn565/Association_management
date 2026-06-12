from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from .models import Membre, Cotisation, CotisationImprevu, Credit, Interet, Remboursement, Association
from cas_assistance.models import CasAssistance
from .pdf_utils import save_pdf_and_respond


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_admin)


def get_tenant(request):
    return getattr(request, 'tenant', None)


def qs_for_tenant(request, qs, field='tenant'):
    tenant = get_tenant(request)
    if tenant and not getattr(request, 'is_superadmin', False):
        return qs.filter(**{field: tenant})
    return qs


def get_devise(request):
    tenant = get_tenant(request)
    assoc = Association.get_association(tenant)
    return assoc.devise if assoc and assoc.devise else 'FBU'


def _build_pdf_response(request, title, filename):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=18,
        textColor=colors.HexColor('#1a1a1a'), spaceAfter=12,
        alignment=TA_CENTER, fontName='Helvetica-Bold'
    )
    tenant = get_tenant(request)
    association = Association.get_association(tenant)
    if association:
        elements.append(Paragraph(association.nom, title_style))
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.5*cm))
    date_gen = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_gen}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    return buffer, doc, elements, styles


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_membres_pdf(request):
    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "LISTE DES MEMBRES", "Membres.pdf"
    )

    membres = qs_for_tenant(request, Membre.objects.all()).order_by('nom', 'prenom')

    if membres.exists():
        data = [['#', 'Nom', 'Prénom', 'Carte ID', 'Téléphone', 'Actif',
                 f'Total Cot. ({devise})', f'Total Impr. ({devise})']]
        for i, m in enumerate(membres, 1):
            data.append([
                str(i), m.nom, m.prenom, m.carte_identite,
                m.telephone or '-', 'Oui' if m.est_actif else 'Non',
                f"{m.get_total_cotisations():,.3f}", f"{m.get_total_cotisations_imprevus():,.3f}"
            ])
        table = Table(data, colWidths=[1*cm, 3*cm, 3*cm, 3*cm, 3*cm, 1.5*cm, 3*cm, 3*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.3*cm))
        elements.append(
            Paragraph(f"<b>Total :</b> {membres.count()} membres", styles['Normal'])
        )
    else:
        elements.append(Paragraph("<i>Aucun membre trouvé.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Membres.pdf")


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_cotisations_imprevus_pdf(request):
    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "LISTE DES COTISATIONS IMPRÉVUS", "Cotisations_Imprevus.pdf"
    )

    cotisations = qs_for_tenant(request, CotisationImprevu.objects.all()).select_related('membre').order_by('-annee', '-mois')
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    if cotisations.exists():
        data = [['#', 'Membre', 'Carte ID', 'Montant', 'Mois', 'Statut', 'Date']]
        total = Decimal('0')
        for i, c in enumerate(cotisations, 1):
            data.append([
                str(i), c.membre.get_full_name(), c.membre.carte_identite,
                f"{c.montant:,.3f}", f"{mois_noms[c.mois]} {c.annee}",
                c.get_statut_display(),
                c.date_paiement.strftime("%d/%m/%Y") if c.date_paiement else '-'
            ])
            if c.statut == 'PAYE':
                total += c.montant

        data.append(['', 'TOTAL', '', f"{total:,.3f}", '', '', ''])
        table = Table(data, colWidths=[1*cm, 4.5*cm, 3*cm, 2.5*cm, 3*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e67e22')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fef5e7')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("<i>Aucune cotisation imprévus trouvée.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Cotisations_Imprevus.pdf")


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_assistances_pdf(request):
    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "LISTE DES CAS D'ASSISTANCE", "Assistances.pdf"
    )

    assistances = qs_for_tenant(request, CasAssistance.objects.all()).select_related('membre', 'cree_par').order_by('-date_assistance')

    if assistances.exists():
        data = [['#', 'Membre', 'Montant', 'Motif', 'Date', 'Créé par']]
        total = Decimal('0')
        for i, a in enumerate(assistances, 1):
            data.append([
                str(i), a.membre.get_full_name(),
                f"{a.montant:,.3f}",
                a.motif[:50] + ('...' if len(a.motif) > 50 else ''),
                a.date_assistance.strftime("%d/%m/%Y") if a.date_assistance else '-',
                a.cree_par.get_full_name() if a.cree_par else '-'
            ])
            total += a.montant

        data.append(['', 'TOTAL', f"{total:,.3f}", '', '', ''])
        table = Table(data, colWidths=[1*cm, 4*cm, 3*cm, 6*cm, 2.5*cm, 3.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9b59b6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f4ecf7')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("<i>Aucun cas d'assistance trouvé.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Assistances.pdf")


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_interets_pdf(request):
    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "LISTE DES INTÉRÊTS", "Interets.pdf"
    )

    interets = qs_for_tenant(request, Interet.objects.all()).select_related('credit__membre').order_by('-annee', '-mois')
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    if interets.exists():
        data = [['#', 'Membre', 'Crédit #', 'Période', 'Int. mensuel', 'Int. cumulé', 'Date calcul']]
        total_mens = Decimal('0')
        total_cum = Decimal('0')
        for i, it in enumerate(interets, 1):
            data.append([
                str(i), it.credit.membre.get_full_name(), str(it.credit.id_credit),
                f"{mois_noms[it.mois]} {it.annee}",
                f"{it.interet_mensuel:,.3f}", f"{it.interet_cumule:,.3f}",
                it.date_calcul.strftime("%d/%m/%Y") if it.date_calcul else '-'
            ])
            total_mens += it.interet_mensuel
            total_cum += it.interet_cumule

        data.append(['', 'TOTAL', '', '', f"{total_mens:,.3f}", f"{total_cum:,.3f}", ''])
        table = Table(data, colWidths=[1*cm, 4*cm, 2*cm, 3.5*cm, 3*cm, 3*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f5e3')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("<i>Aucun intérêt trouvé.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Interets.pdf")
