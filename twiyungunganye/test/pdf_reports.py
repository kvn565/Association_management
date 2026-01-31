from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Count
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
from decimal import Decimal

from .models import Membre, Cotisation, Credit, Remboursement, Association


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_gestionnaire)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapport_mensuel_pdf(request, mois, annee):
    """Génère un rapport mensuel en PDF"""
    
    # Créer le document PDF
    response = HttpResponse(content_type='application/pdf')
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    filename = f"Rapport_Mensuel_{mois_noms[mois]}_{annee}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Créer le document
    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
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
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Récupérer les informations de l'association
    association = Association.get_association()
    
    # Titre du rapport
    if association:
        elements.append(Paragraph(association.nom, title_style))
    else:
        elements.append(Paragraph("Association de Cotisation", title_style))
    
    elements.append(Paragraph(f"Rapport du mois de {mois_noms[mois]} {annee}", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Date de génération
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Section 1: Cotisations du mois
    elements.append(Paragraph("<b>1. COTISATIONS DU MOIS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    cotisations = Cotisation.objects.filter(mois=mois, annee=annee).select_related('membre')
    
    if cotisations.exists():
        data_cotisations = [['#', 'Nom Complet', 'N° Carte ID', 'Montant (FBU)', 'Statut', 'Date Paiement']]
        
        for i, cot in enumerate(cotisations, 1):
            data_cotisations.append([
                str(i),
                cot.membre.get_full_name(),
                cot.membre.carte_identite,
                f"{cot.montant:,.2f}",
                cot.get_statut_display(),
                cot.date_paiement.strftime("%d/%m/%Y")
            ])
        
        # Total des cotisations
        total_cotisations = cotisations.aggregate(Sum('montant'))['montant__sum'] or 0
        data_cotisations.append(['', '', 'TOTAL', f"{total_cotisations:,.2f} FBU", '', ''])
        
        table_cotisations = Table(data_cotisations, colWidths=[1.5*cm, 5*cm, 3.5*cm, 3*cm, 3*cm, 3*cm])
        table_cotisations.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table_cotisations)
    else:
        elements.append(Paragraph("<i>Aucune cotisation enregistrée pour ce mois.</i>", styles['Normal']))
    
    elements.append(Spacer(1, 0.8*cm))
    
    # Section 2: Crédits en cours
    elements.append(Paragraph("<b>2. CRÉDITS EN COURS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    credits = Credit.objects.filter(
        statut__in=['APPROUVE', 'EN_COURS'],
        date_accord__lte=datetime(annee, mois, 1)
    ).select_related('membre')
    
    if credits.exists():
        data_credits = [['#', 'Nom Complet', 'Montant Crédit', 'Intérêts', 'Total à Rembourser', 'Déjà Remboursé', 'Reste']]
        
        total_credits_montant = Decimal('0')
        total_interets = Decimal('0')
        total_a_rembourser = Decimal('0')
        total_rembourse = Decimal('0')
        total_reste = Decimal('0')
        
        for i, credit in enumerate(credits, 1):
            interet = credit.calculer_interet()
            montant_total = credit.calculer_montant_total()
            deja_rembourse = credit.get_montant_rembourse()
            reste = credit.get_reste_a_rembourser()
            
            data_credits.append([
                str(i),
                credit.membre.get_full_name(),
                f"{credit.montant_accorde:,.2f}",
                f"{interet:,.2f}",
                f"{montant_total:,.2f}",
                f"{deja_rembourse:,.2f}",
                f"{reste:,.2f}"
            ])
            
            total_credits_montant += credit.montant_accorde
            total_interets += interet
            total_a_rembourser += montant_total
            total_rembourse += deja_rembourse
            total_reste += reste
        
        data_credits.append([
            '', 'TOTAL',
            f"{total_credits_montant:,.2f}",
            f"{total_interets:,.2f}",
            f"{total_a_rembourser:,.2f}",
            f"{total_rembourse:,.2f}",
            f"{total_reste:,.2f}"
        ])
        
        table_credits = Table(data_credits, colWidths=[1.5*cm, 4*cm, 3*cm, 3*cm, 3.5*cm, 3.5*cm, 3*cm])
        table_credits.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e74c3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#fadbd8')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table_credits)
    else:
        elements.append(Paragraph("<i>Aucun crédit en cours pour ce mois.</i>", styles['Normal']))
    
    elements.append(Spacer(1, 0.8*cm))
    
    # Section 3: Remboursements du mois
    elements.append(Paragraph("<b>3. REMBOURSEMENTS DU MOIS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    remboursements = Remboursement.objects.filter(
        date_remboursement__month=mois,
        date_remboursement__year=annee
    ).select_related('credit__membre')
    
    if remboursements.exists():
        data_remb = [['#', 'Nom Complet', 'Montant Remboursé', 'Intérêt Remboursé', 'Date', 'Mode']]
        
        total_montant_remb = Decimal('0')
        total_interet_remb = Decimal('0')
        
        for i, remb in enumerate(remboursements, 1):
            data_remb.append([
                str(i),
                remb.credit.membre.get_full_name(),
                f"{remb.montant_rembourse:,.2f}",
                f"{remb.interet_rembourse:,.2f}",
                remb.date_remboursement.strftime("%d/%m/%Y"),
                remb.get_mode_paiement_display()
            ])
            
            total_montant_remb += remb.montant_rembourse
            total_interet_remb += remb.interet_rembourse
        
        data_remb.append([
            '', 'TOTAL',
            f"{total_montant_remb:,.2f} FBU",
            f"{total_interet_remb:,.2f} FBU",
            '', ''
        ])
        
        table_remb = Table(data_remb, colWidths=[1.5*cm, 5*cm, 3.5*cm, 3.5*cm, 3*cm, 3.5*cm])
        table_remb.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#27ae60')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
            ('GRID', (0, 0), (-1, -2), 1, colors.black),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f4e6')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
        ]))
        
        elements.append(table_remb)
    else:
        elements.append(Paragraph("<i>Aucun remboursement enregistré pour ce mois.</i>", styles['Normal']))
    
    elements.append(Spacer(1, 1*cm))
    
    # Section 4: Résumé financier
    elements.append(Paragraph("<b>4. RÉSUMÉ FINANCIER</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    total_cotisations = cotisations.aggregate(Sum('montant'))['montant__sum'] or 0
    total_remboursements = remboursements.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0
    total_interets_percus = remboursements.aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or 0
    
    data_resume = [
        ['Total des cotisations du mois', f"{total_cotisations:,.2f} FBU"],
        ['Total des remboursements reçus', f"{total_remboursements:,.2f} FBU"],
        ['Total des intérêts perçus', f"{total_interets_percus:,.2f} FBU"],
        ['TOTAL DES ENTRÉES', f"{(total_cotisations + total_remboursements + total_interets_percus):,.2f} FBU"],
    ]
    
    table_resume = Table(data_resume, colWidths=[10*cm, 5*cm])
    table_resume.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -2), colors.lightgrey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#4a90e2')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    
    elements.append(table_resume)
    
    # Construire le PDF
    doc.build(elements)
    
    return response


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapport_annuel_pdf(request, annee):
    """Génère un rapport annuel en PDF"""
    
    # Créer le document PDF
    response = HttpResponse(content_type='application/pdf')
    filename = f"Rapport_Annuel_{annee}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Créer le document
    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
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
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Récupérer les informations de l'association
    association = Association.get_association()
    
    # Titre du rapport
    if association:
        elements.append(Paragraph(association.nom, title_style))
    else:
        elements.append(Paragraph("Association de Cotisation", title_style))
    
    elements.append(Paragraph(f"Rapport Annuel {annee}", subtitle_style))
    elements.append(Spacer(1, 0.5*cm))
    
    # Date de génération
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Section 1: Cotisations par mois
    elements.append(Paragraph("<b>1. COTISATIONS PAR MOIS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    data_cotisations_annuel = [['Mois', 'Nombre de cotisations', 'Total (FBU)']]
    
    total_annuel_cotisations = Decimal('0')
    total_nombre_cotisations = 0
    
    for mois in range(1, 13):
        cotisations_mois = Cotisation.objects.filter(mois=mois, annee=annee)
        nombre = cotisations_mois.count()
        total = cotisations_mois.aggregate(Sum('montant'))['montant__sum'] or 0
        
        data_cotisations_annuel.append([
            mois_noms[mois],
            str(nombre),
            f"{total:,.2f}"
        ])
        
        total_annuel_cotisations += total
        total_nombre_cotisations += nombre
    
    data_cotisations_annuel.append([
        'TOTAL ANNUEL',
        str(total_nombre_cotisations),
        f"{total_annuel_cotisations:,.2f} FBU"
    ])
    
    table_cotisations_annuel = Table(data_cotisations_annuel, colWidths=[6*cm, 5*cm, 5*cm])
    table_cotisations_annuel.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4a90e2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -2), colors.beige),
        ('GRID', (0, 0), (-1, -2), 1, colors.black),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
    ]))
    
    elements.append(table_cotisations_annuel)
    elements.append(Spacer(1, 0.8*cm))
    
    # Section 2: Statistiques des crédits
    elements.append(Paragraph("<b>2. STATISTIQUES DES CRÉDITS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    credits_annee = Credit.objects.filter(date_accord__year=annee)
    nombre_credits = credits_annee.count()
    total_credits_accordes = credits_annee.aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or 0
    
    # Calcul des intérêts totaux
    total_interets_annee = Decimal('0')
    for credit in credits_annee:
        total_interets_annee += credit.calculer_interet()
    
    # Remboursements de l'année
    remboursements_annee = Remboursement.objects.filter(date_remboursement__year=annee)
    total_remboursements_annee = remboursements_annee.aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or 0
    total_interets_percus_annee = remboursements_annee.aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or 0
    
    data_credits_stats = [
        ['Nombre de crédits accordés', str(nombre_credits)],
        ['Montant total des crédits', f"{total_credits_accordes:,.2f} FBU"],
        ['Intérêts générés', f"{total_interets_annee:,.2f} FBU"],
        ['Remboursements reçus', f"{total_remboursements_annee:,.2f} FBU"],
        ['Intérêts perçus', f"{total_interets_percus_annee:,.2f} FBU"],
    ]
    
    table_credits_stats = Table(data_credits_stats, colWidths=[10*cm, 5*cm])
    table_credits_stats.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    elements.append(table_credits_stats)
    elements.append(Spacer(1, 1*cm))
    
    # Section 3: Bilan financier
    elements.append(Paragraph("<b>3. BILAN FINANCIER ANNUEL</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    total_entrees = total_annuel_cotisations + total_remboursements_annee + total_interets_percus_annee
    
    data_bilan = [
        ['ENTRÉES', ''],
        ['Cotisations', f"{total_annuel_cotisations:,.2f} FBU"],
        ['Remboursements de crédits', f"{total_remboursements_annee:,.2f} FBU"],
        ['Intérêts perçus', f"{total_interets_percus_annee:,.2f} FBU"],
        ['TOTAL DES ENTRÉES', f"{total_entrees:,.2f} FBU"],
        ['', ''],
        ['SORTIES', ''],
        ['Crédits accordés', f"{total_credits_accordes:,.2f} FBU"],
        ['', ''],
        ['SOLDE NET', f"{(total_entrees - total_credits_accordes):,.2f} FBU"],
    ]
    
    table_bilan = Table(data_bilan, colWidths=[10*cm, 5*cm])
    table_bilan.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#4a90e2')),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#4a90e2')),
        ('BACKGROUND', (0, 6), (0, 6), colors.HexColor('#e74c3c')),
        ('BACKGROUND', (0, 9), (-1, 9), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.whitesmoke),
        ('TEXTCOLOR', (0, 4), (-1, 4), colors.whitesmoke),
        ('TEXTCOLOR', (0, 6), (0, 6), colors.whitesmoke),
        ('TEXTCOLOR', (0, 9), (-1, 9), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 4), (-1, 4), 'Helvetica-Bold'),
        ('FONTNAME', (0, 6), (0, 6), 'Helvetica-Bold'),
        ('FONTNAME', (0, 9), (-1, 9), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('LINEABOVE', (0, 4), (-1, 4), 2, colors.black),
        ('LINEABOVE', (0, 9), (-1, 9), 2, colors.black),
    ]))
    
    elements.append(table_bilan)
    
    # Construire le PDF
    doc.build(elements)
    
    return response
