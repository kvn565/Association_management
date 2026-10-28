"""
Fichier : pdf_exports.py
Description : Exports PDF pour listes de cotisations, crédits et remboursements
Auteur : Système de gestion Twiyungunganye
"""

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

from .models import Membre, Cotisation, Credit, Remboursement, Interet, Association
from .pdf_utils import save_pdf_and_respond


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and user.is_admin


def get_tenant(request):
    return getattr(request, 'tenant', None)


def qs_for_tenant(request, qs, field='tenant'):
    """Filtre un queryset par le tenant de la requête (fail-closed)."""
    if getattr(request, 'is_superadmin', False):
        return qs
    tenant = get_tenant(request)
    if tenant is None:
        return qs.none()
    return qs.filter(**{field: tenant})


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_liste_cotisations_pdf(request):
    """
    Exporter la liste des cotisations en PDF
    Paramètres GET : mois, annee, membre, statut
    """
    
    # Récupérer les filtres
    mois = request.GET.get('mois')
    annee = request.GET.get('annee')
    membre_id = request.GET.get('membre')
    statut = request.GET.get('statut')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    # Construire la requête
    cotisations = qs_for_tenant(request, Cotisation.objects.all()).select_related('membre')
    
    titre_filtres = []
    
    if date_debut:
        cotisations = cotisations.filter(date_paiement__gte=date_debut)
        titre_filtres.append(f"du_{date_debut}")
    if date_fin:
        cotisations = cotisations.filter(date_paiement__lte=date_fin)
        titre_filtres.append(f"au_{date_fin}")
    
    if mois:
        cotisations = cotisations.filter(mois=int(mois))
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        titre_filtres.append(mois_noms[int(mois)])
    
    if annee:
        cotisations = cotisations.filter(annee=int(annee))
        titre_filtres.append(str(annee))
    
    if membre_id:
        cotisations = cotisations.filter(membre_id=int(membre_id))
    
    if statut:
        cotisations = cotisations.filter(statut=statut)
    
    cotisations = cotisations.order_by('-annee', '-mois', 'membre__nom')
    
    # Créer le PDF
    buffer = BytesIO()
    filename = 'Liste_Cotisations'
    if titre_filtres:
        filename += '_' + '_'.join(titre_filtres).replace(' ', '_')
    filename += '.pdf'
    
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # En-tête
    association = Association.get_association(get_tenant(request))
    if association:
        elements.append(Paragraph(association.nom, title_style))
    devise = association.devise if association and association.devise else "FBU"
    
    elements.append(Paragraph("LISTE DES COTISATIONS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Tableau
    if cotisations.exists():
        data = [['#', 'Membre', 'Carte ID', 'Période', f'Montant ({devise})', 'Statut', 'Date']]
        
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        
        total = Decimal('0')
        
        for i, cot in enumerate(cotisations, 1):
            data.append([
                str(i),
                cot.membre.get_full_name(),
                cot.membre.carte_identite,
                f"{mois_noms[cot.mois]} {cot.annee}",
                f"{cot.montant:,.3f}",
                cot.get_statut_display(),
                cot.date_paiement.strftime("%d/%m/%Y") if cot.date_paiement else '-'
            ])
            if cot.statut == 'PAYE':
                total += cot.montant
        
        data.append(['', '', '', 'TOTAL PAYÉ', f"{total:,.3f} {devise}", '', ''])
        
        table = Table(data, colWidths=[1*cm, 4.5*cm, 2.5*cm, 3.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table)
        
        elements.append(Spacer(1, 0.5*cm))
        stats = f"<b>Total :</b> {cotisations.count()} entrées | <b>Total payé :</b> {total:,.3f} {devise}"
        elements.append(Paragraph(stats, styles['Normal']))
    else:
        elements.append(Paragraph("<i>Aucune cotisation trouvée.</i>", styles['Normal']))
    
    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_liste_credits_pdf(request):
    """Exporter la liste des crédits en PDF"""
    
    statut = request.GET.get('statut')
    membre_id = request.GET.get('membre')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    credits = qs_for_tenant(request, Credit.objects.all()).select_related('membre')
    
    if statut:
        credits = credits.filter(statut=statut)
    if membre_id:
        credits = credits.filter(membre_id=int(membre_id))
    if date_debut:
        credits = credits.filter(date_demande__gte=date_debut)
    if date_fin:
        credits = credits.filter(date_demande__lte=date_fin)
    
    credits = credits.order_by('-date_demande')
    
    buffer = BytesIO()
    filename = 'Liste_Credits.pdf'
    
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    association = Association.get_association(get_tenant(request))
    if association:
        elements.append(Paragraph(association.nom, title_style))
    
    elements.append(Paragraph("LISTE DES CRÉDITS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    if credits.exists():
        data = [['#', 'Membre', 'Demandé', 'Accordé', 'Intérêts', 'Total', 'Remboursé', 'Reste', 'Statut', 'Date']]
        
        total_accorde = Decimal('0')
        total_interets = Decimal('0')
        total_rembourse = Decimal('0')
        
        for i, credit in enumerate(credits, 1):
            interet = credit.calculer_interet()
            total_credit = credit.calculer_montant_total()
            rembourse = credit.get_montant_rembourse()
            reste = credit.get_reste_a_rembourser()
            
            data.append([
                str(i),
                credit.membre.get_full_name(),
                f"{credit.montant_demande:,.3f}",
                f"{credit.montant_accorde:,.3f}",
                f"{interet:,.3f}",
                f"{total_credit:,.3f}",
                f"{rembourse:,.3f}",
                f"{reste:,.3f}",
                credit.get_statut_display(),
                credit.date_demande.strftime("%d/%m/%Y")
            ])
            
            total_accorde += credit.montant_accorde
            total_interets += interet
            total_rembourse += rembourse
        
        data.append([
            '', 'TOTAL', '',
            f"{total_accorde:,.3f}",
            f"{total_interets:,.3f}",
            f"{(total_accorde + total_interets):,.3f}",
            f"{total_rembourse:,.3f}",
            f"{(total_accorde + total_interets - total_rembourse):,.3f}",
            '', ''
        ])
        
        table = Table(data, colWidths=[1*cm, 3.5*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2*cm, 2.5*cm, 2*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fadbd8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table)
    else:
        elements.append(Paragraph("<i>Aucun crédit trouvé.</i>", styles['Normal']))
    
    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_liste_remboursements_pdf(request):
    """Exporter la liste des remboursements en PDF"""
    
    credit_id = request.GET.get('credit')
    membre_id = request.GET.get('membre')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    remboursements = qs_for_tenant(request, Remboursement.objects.all()).select_related('credit__membre')
    
    if credit_id:
        remboursements = remboursements.filter(credit_id=int(credit_id))
    if membre_id:
        remboursements = remboursements.filter(credit__membre_id=int(membre_id))
    if date_debut:
        remboursements = remboursements.filter(date_remboursement__gte=date_debut)
    if date_fin:
        remboursements = remboursements.filter(date_remboursement__lte=date_fin)
    
    remboursements = remboursements.order_by('-date_remboursement')
    
    buffer = BytesIO()
    filename = 'Liste_Remboursements.pdf'
    
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    association = Association.get_association(get_tenant(request))
    if association:
        elements.append(Paragraph(association.nom, title_style))
    devise = association.devise if association and association.devise else "FBU"
    
    elements.append(Paragraph("LISTE DES REMBOURSEMENTS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    if remboursements.exists():
        data = [['#', 'Membre', 'Crédit #', 'Montant', 'Reste', 'Mode', 'Date']]
        
        total_principal = Decimal('0')
        
        for i, remb in enumerate(remboursements, 1):
            data.append([
                str(i),
                remb.credit.membre.get_full_name(),
                str(remb.credit.id_credit),
                f"{remb.montant_rembourse:,.3f}",
                f"{remb.credit.get_reste_a_rembourser():,.3f}",
                remb.get_mode_paiement_display(),
                remb.date_remboursement.strftime("%d/%m/%Y")
            ])
            
            total_principal += remb.montant_rembourse
        
        data.append([
            '', 'TOTAL', '',
            f"{total_principal:,.3f}",
            '', '', ''
        ])
        
        table = Table(data, colWidths=[1*cm, 4*cm, 1.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f4e6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table)
        
        elements.append(Spacer(1, 0.5*cm))
        stats = f"<b>Total :</b> {remboursements.count()} remboursements | <b>Montant total :</b> {total_principal:,.3f} {devise}"
        elements.append(Paragraph(stats, styles['Normal']))
    else:
        elements.append(Paragraph("<i>Aucun remboursement trouvé.</i>", styles['Normal']))
    
    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_credits_restants_pdf(request):
    """Crédits non encore remboursés, groupés par membre"""
    association = Association.get_association(get_tenant(request))
    devise = association.devise if association and association.devise else "FBU"
    buffer = BytesIO()
    filename = 'Credits_Restants.pdf'
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1.5*cm, rightMargin=1.5*cm)
    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'], fontSize=18,
        textColor=colors.HexColor('#1a1a1a'), spaceAfter=12,
        alignment=TA_CENTER, fontName='Helvetica-Bold'
    )
    association = Association.get_association(get_tenant(request))
    if association:
        elements.append(Paragraph(association.nom, title_style))
    elements.append(Paragraph("CRÉDITS NON ENCORE REMBOURSÉS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    date_gen = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_gen}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))

    credits = qs_for_tenant(request, Credit.objects.all()).filter(
        statut__in=['APPROUVE', 'EN_COURS']
    ).select_related('membre').order_by('membre__nom', 'date_accord')

    if not credits.exists():
        elements.append(Paragraph("<i>Aucun crédit en cours.</i>", styles['Normal']))
        doc.build(elements)
        return save_pdf_and_respond(buffer, filename)

    from collections import OrderedDict
    from datetime import date
    today = date.today()
    mois_courant = today.month
    annee_courante = today.year

    membres_data = OrderedDict()

    for credit in credits:
        reste = credit.get_reste_a_rembourser()
        if reste <= 0:
            continue
        membre = credit.membre
        mid = membre.id_membre
        if mid not in membres_data:
            membres_data[mid] = {
                'membre': membre,
                'lignes': [],
                'total_accorde': Decimal('0'),
                'total_rembourse': Decimal('0'),
                'total_reste': Decimal('0'),
            }
        md = membres_data[mid]
        rembourse = credit.get_montant_rembourse()
        md['lignes'].append({
            'credit_id': credit.id_credit,
            'date_accord': credit.date_accord,
            'montant_accorde': credit.montant_accorde,
            'rembourse': rembourse,
            'reste': reste,
        })
        md['total_accorde'] += credit.montant_accorde
        md['total_rembourse'] += rembourse
        md['total_reste'] += reste

    for mid, md in membres_data.items():
        credits_ids = [ligne['credit_id'] for ligne in md['lignes']]
        interets_impayes = sum(
            max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))
            for it in Interet.objects.filter(credit_id__in=credits_ids)
        )
        interets_mois = sum(
            max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))
            for it in Interet.objects.filter(
                credit_id__in=credits_ids,
                mois=mois_courant,
                annee=annee_courante
            )
        )
        md['total_interets_impayes'] = interets_impayes
        md['interets_mois_courant'] = interets_mois
        md['total_a_payer'] = md['total_reste'] + interets_impayes

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    header_style = ParagraphStyle('HeaderCell', parent=styles['Normal'], fontSize=6,
                                  alignment=TA_CENTER, fontName='Helvetica-Bold',
                                  leading=7, spaceBefore=0, spaceAfter=0)
    header = [
        Paragraph('Membre', header_style),
        Paragraph('Crédit #', header_style),
        Paragraph('Date Demande', header_style),
        Paragraph('Mt Accordé', header_style),
        Paragraph('Déjà Remb.', header_style),
        Paragraph('Reste', header_style),
        Paragraph('Total Crédit Restant', header_style),
        Paragraph(f'Int. {mois_noms[mois_courant]}', header_style),
        Paragraph('Total Int. Impayés', header_style),
        Paragraph('Total à Payer', header_style),
    ]
    data = [header]
    span_cmds = []
    current_row = 1

    cell_style = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=6,
                                 alignment=TA_CENTER, leading=7)

    for mid, md in membres_data.items():
        membre_nom = md['membre'].get_full_name()
        lignes = md['lignes']
        n = len(lignes)
        start_row = current_row

        for idx, ligne in enumerate(lignes):
            data.append([
                Paragraph(membre_nom, cell_style) if idx == 0 else '',
                str(ligne['credit_id']),
                ligne['date_accord'].strftime('%d/%m/%Y') if ligne['date_accord'] else '',
                f"{ligne['montant_accorde']:,.3f}",
                f"{ligne['rembourse']:,.3f}",
                f"{ligne['reste']:,.3f}",
                Paragraph(f"{md['total_reste']:,.3f}", cell_style) if idx == 0 else '',
                Paragraph(f"{md['interets_mois_courant']:,.3f}", cell_style) if idx == 0 else '',
                Paragraph(f"{md['total_interets_impayes']:,.3f}", cell_style) if idx == 0 else '',
                Paragraph(f"{md['total_a_payer']:,.3f}", cell_style) if idx == 0 else '',
            ])
            current_row += 1

        if n > 1:
            span_cmds.append(('SPAN', (0, start_row), (0, start_row + n - 1)))
            span_cmds.append(('SPAN', (6, start_row), (6, start_row + n - 1)))
            span_cmds.append(('SPAN', (7, start_row), (7, start_row + n - 1)))
            span_cmds.append(('SPAN', (8, start_row), (8, start_row + n - 1)))
            span_cmds.append(('SPAN', (9, start_row), (9, start_row + n - 1)))

    grand_total_accorde = sum(md['total_accorde'] for md in membres_data.values())
    grand_total_rembourse = sum(md['total_rembourse'] for md in membres_data.values())
    grand_total_reste = sum(md['total_reste'] for md in membres_data.values())
    grand_total_interets_mois = sum(md['interets_mois_courant'] for md in membres_data.values())
    grand_total_interets = sum(md['total_interets_impayes'] for md in membres_data.values())
    grand_total_a_payer = sum(md['total_a_payer'] for md in membres_data.values())
    data.append([Paragraph('TOTAL GÉNÉRAL', cell_style), '', '', f"{grand_total_accorde:,.3f}", f"{grand_total_rembourse:,.3f}",
                 f"{grand_total_reste:,.3f}", f"{grand_total_reste:,.3f}", f"{grand_total_interets_mois:,.3f}",
                 f"{grand_total_interets:,.3f}", f"{grand_total_a_payer:,.3f}"])

    col_widths = [3.5*cm, 1.5*cm, 2*cm, 2.2*cm, 2*cm, 1.8*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm]
    table = Table(data, colWidths=col_widths)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f4e6')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]
    style_cmds.extend(span_cmds)

    row_idx = 1
    color_idx = 0
    colors_bg = [colors.white, colors.HexColor('#fdf2f2')]
    for mid, md in membres_data.items():
        n = len(md['lignes'])
        bg = colors_bg[color_idx % 2]
        for r in range(row_idx, row_idx + n):
            if r < len(data) - 1:
                style_cmds.append(('BACKGROUND', (0, r), (-1, r), bg))
        color_idx += 1
        row_idx += n

    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
