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

from .models import Membre, Cotisation, Credit, Remboursement, Association


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_gestionnaire)


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
    
    # Construire la requête
    cotisations = Cotisation.objects.all().select_related('membre')
    
    titre_filtres = []
    
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
    response = HttpResponse(content_type='application/pdf')
    filename = 'Liste_Cotisations'
    if titre_filtres:
        filename += '_' + '_'.join(titre_filtres).replace(' ', '_')
    filename += '.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
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
    
    # En-tête
    association = Association.get_association()
    if association:
        elements.append(Paragraph(association.nom, title_style))
    
    elements.append(Paragraph("LISTE DES COTISATIONS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    # Tableau
    if cotisations.exists():
        data = [['#', 'Membre', 'Carte ID', 'Période', 'Montant (FBU)', 'Statut', 'Date']]
        
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        
        total = Decimal('0')
        
        for i, cot in enumerate(cotisations, 1):
            data.append([
                str(i),
                cot.membre.get_full_name(),
                cot.membre.carte_identite,
                f"{mois_noms[cot.mois]} {cot.annee}",
                f"{cot.montant:,.0f}",
                cot.get_statut_display(),
                cot.date_paiement.strftime("%d/%m/%Y") if cot.date_paiement else '-'
            ])
            if cot.statut == 'PAYE':
                total += cot.montant
        
        data.append(['', '', '', 'TOTAL PAYÉ', f"{total:,.0f} FBU", '', ''])
        
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
        stats = f"<b>Total :</b> {cotisations.count()} entrées | <b>Total payé :</b> {total:,.0f} FBU"
        elements.append(Paragraph(stats, styles['Normal']))
    else:
        elements.append(Paragraph("<i>Aucune cotisation trouvée.</i>", styles['Normal']))
    
    doc.build(elements)
    return response


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_liste_credits_pdf(request):
    """Exporter la liste des crédits en PDF"""
    
    statut = request.GET.get('statut')
    membre_id = request.GET.get('membre')
    
    credits = Credit.objects.all().select_related('membre')
    
    if statut:
        credits = credits.filter(statut=statut)
    if membre_id:
        credits = credits.filter(membre_id=int(membre_id))
    
    credits = credits.order_by('-date_demande')
    
    response = HttpResponse(content_type='application/pdf')
    filename = 'Liste_Credits.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
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
    
    association = Association.get_association()
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
                f"{credit.montant_demande:,.0f}",
                f"{credit.montant_accorde:,.0f}",
                f"{interet:,.0f}",
                f"{total_credit:,.0f}",
                f"{rembourse:,.0f}",
                f"{reste:,.0f}",
                credit.get_statut_display(),
                credit.date_demande.strftime("%d/%m/%Y")
            ])
            
            total_accorde += credit.montant_accorde
            total_interets += interet
            total_rembourse += rembourse
        
        data.append([
            '', 'TOTAL', '',
            f"{total_accorde:,.0f}",
            f"{total_interets:,.0f}",
            f"{(total_accorde + total_interets):,.0f}",
            f"{total_rembourse:,.0f}",
            f"{(total_accorde + total_interets - total_rembourse):,.0f}",
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
    return response


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_liste_remboursements_pdf(request):
    """Exporter la liste des remboursements en PDF"""
    
    credit_id = request.GET.get('credit')
    membre_id = request.GET.get('membre')
    
    remboursements = Remboursement.objects.all().select_related('credit__membre')
    
    if credit_id:
        remboursements = remboursements.filter(credit_id=int(credit_id))
    if membre_id:
        remboursements = remboursements.filter(credit__membre_id=int(membre_id))
    
    remboursements = remboursements.order_by('-date_remboursement')
    
    response = HttpResponse(content_type='application/pdf')
    filename = 'Liste_Remboursements.pdf'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    doc = SimpleDocTemplate(response, pagesize=landscape(A4))
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
    
    association = Association.get_association()
    if association:
        elements.append(Paragraph(association.nom, title_style))
    
    elements.append(Paragraph("LISTE DES REMBOURSEMENTS", title_style))
    elements.append(Spacer(1, 0.5*cm))
    
    date_generation = datetime.now().strftime("%d/%m/%Y à %H:%M")
    elements.append(Paragraph(f"<i>Généré le {date_generation}</i>", styles['Normal']))
    elements.append(Spacer(1, 0.5*cm))
    
    if remboursements.exists():
        data = [['#', 'Membre', 'Crédit #', 'Principal', 'Intérêt', 'Total', 'Reste', 'Mode', 'Date']]
        
        total_principal = Decimal('0')
        total_interets = Decimal('0')
        
        for i, remb in enumerate(remboursements, 1):
            total_remb = remb.montant_rembourse + remb.interet_rembourse
            
            data.append([
                str(i),
                remb.credit.membre.get_full_name(),
                str(remb.credit.id_credit),
                f"{remb.montant_rembourse:,.0f}",
                f"{remb.interet_rembourse:,.0f}",
                f"{total_remb:,.0f}",
                f"{remb.reste_a_rembourser:,.0f}",
                remb.get_mode_paiement_display(),
                remb.date_remboursement.strftime("%d/%m/%Y")
            ])
            
            total_principal += remb.montant_rembourse
            total_interets += remb.interet_rembourse
        
        data.append([
            '', 'TOTAL', '',
            f"{total_principal:,.0f}",
            f"{total_interets:,.0f}",
            f"{(total_principal + total_interets):,.0f}",
            '', '', ''
        ])
        
        table = Table(data, colWidths=[1*cm, 4*cm, 1.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm, 2.5*cm])
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
        stats = f"<b>Total :</b> {remboursements.count()} remboursements | <b>Montant total :</b> {(total_principal + total_interets):,.0f} FBU"
        elements.append(Paragraph(stats, styles['Normal']))
    else:
        elements.append(Paragraph("<i>Aucun remboursement trouvé.</i>", styles['Normal']))
    
    doc.build(elements)
    return response
