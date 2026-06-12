from io import BytesIO
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

from .models import Membre, Cotisation, CotisationImprevu, Credit, Remboursement, Association
from .pdf_utils import save_pdf_and_respond


def get_tenant(request):
    return getattr(request, 'tenant', None)


def qs_for_tenant(request, qs, field='tenant'):
    tenant = get_tenant(request)
    if tenant and not getattr(request, 'is_superadmin', False):
        return qs.filter(**{field: tenant})
    return qs


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_admin)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapport_mensuel_pdf(request, mois, annee):
    """Génère un rapport mensuel en PDF"""
    
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    filename = f"Rapport_Mensuel_{mois_noms[mois]}_{annee}.pdf"
    
    # Créer le document en mémoire
    buffer = BytesIO()
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
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    tenant = get_tenant(request)
    
    # Récupérer les informations de l'association
    association = Association.get_association(tenant)
    devise = association.devise if association and association.devise else "FBU"
    
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
    
    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_remboursements = qs_for_tenant(request, Remboursement.objects.all())
    
    cotisations = base_cotisations.filter(mois=mois, annee=annee).select_related('membre')
    
    if cotisations.exists():
        data_cotisations = [['#', 'Nom Complet', 'N° Carte ID', 'Montant ({devise})', 'Statut', 'Date Paiement']]
        
        for i, cot in enumerate(cotisations, 1):
            data_cotisations.append([
                str(i),
                cot.membre.get_full_name(),
                cot.membre.carte_identite,
                f"{cot.montant:,.3f}",
                cot.get_statut_display(),
                cot.date_paiement.strftime("%d/%m/%Y")
            ])
        
        # Total des cotisations
        total_cotisations = cotisations.aggregate(Sum('montant'))['montant__sum'] or 0
        data_cotisations.append(['', '', 'TOTAL', f"{total_cotisations:,.3f} {devise}", '', ''])
        
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
    
    # Filtrer les crédits approuvés ou en cours (peu importe leur date d'accord)
    credits = base_credits.filter(
        statut__in=['APPROUVE', 'EN_COURS']
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
                f"{credit.montant_accorde:,.3f}",
                f"{interet:,.3f}",
                f"{montant_total:,.3f}",
                f"{deja_rembourse:,.3f}",
                f"{reste:,.3f}"
            ])
            
            total_credits_montant += credit.montant_accorde
            total_interets += interet
            total_a_rembourser += montant_total
            total_rembourse += deja_rembourse
            total_reste += reste
        
        data_credits.append([
            '', 'TOTAL',
            f"{total_credits_montant:,.3f}",
            f"{total_interets:,.3f}",
            f"{total_a_rembourser:,.3f}",
            f"{total_rembourse:,.3f}",
            f"{total_reste:,.3f}"
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
    
    # Section 3: Résumé financier mensuel COMPLET
    elements.append(Paragraph("<b>3. RÉSUMÉ FINANCIER DU MOIS</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    # ========== CALCULS DÉTAILLÉS ==========
    
    # 1. Cotisations du mois
    total_cotisations_mois = cotisations.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
    
    # 1b. Cotisations Imprévus du mois
    total_imprevus_mois = qs_for_tenant(request, CotisationImprevu.objects.all()).filter(
        mois=mois, annee=annee, statut='PAYE'
    ).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
    
    # 2. Remboursements du mois (principal + intérêts séparés)
    remboursements_mois = base_remboursements.filter(
        date_remboursement__month=mois,
        date_remboursement__year=annee
    )
    total_remb_principal = remboursements_mois.aggregate(
        Sum('montant_rembourse')
    )['montant_rembourse__sum'] or Decimal('0.000')
    
    total_remb_interets = remboursements_mois.aggregate(
        Sum('interet_rembourse')
    )['interet_rembourse__sum'] or Decimal('0.000')
    
    total_remboursements = total_remb_principal + total_remb_interets
    
    # 3. Crédits approuvés dans le mois
    credits_approuves_mois = base_credits.filter(
        statut='APPROUVE',
        date_accord__month=mois,
        date_accord__year=annee
    )
    total_credits_accordes = credits_approuves_mois.aggregate(
        Sum('montant_accorde')
    )['montant_accorde__sum'] or Decimal('0')
    
    # 4. Intérêts générés sur les crédits en cours (à percevoir)
    credits_en_cours = base_credits.filter(
        statut__in=['APPROUVE', 'EN_COURS']
    )
    total_interets_a_percevoir = Decimal('0')
    for credit in credits_en_cours:
        interets_credit = credit.calculer_interet()
        interets_deja_percus = credit.remboursements.aggregate(
            Sum('interet_rembourse')
        )['interet_rembourse__sum'] or Decimal('0')
        interets_restants = interets_credit - interets_deja_percus
        total_interets_a_percevoir += interets_restants
    
    # 5. Dépenses du mois
    from .models import Depense
    depenses_mois = qs_for_tenant(request, Depense.objects.filter(
        date_depense__month=mois, date_depense__year=annee
    )) if hasattr(request, 'tenant') else Depense.objects.none()
    total_depenses_mois = depenses_mois.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

    # 6. SOLDE EN CAISSE
    # = (Cotisations + Imprévus + Remboursements) - (Dépenses + Crédits accordés)
    entrees_totales = total_cotisations_mois + total_imprevus_mois + total_remboursements
    sorties_totales = total_depenses_mois + total_credits_accordes
    solde_caisse = entrees_totales - sorties_totales
    
    # ========== TABLEAU RÉCAPITULATIF ==========
    
    data_resume = [
        ['', ''],
        ['📥 ENTRÉES DU MOIS', ''],
        ['  Cotisations reçues', f"{total_cotisations_mois:,.3f} {devise}"],
        ['  Cotisations imprévus reçues', f"{total_imprevus_mois:,.3f} {devise}"],
        ['  Remboursements reçus (principal)', f"{total_remb_principal:,.3f} {devise}"],
        ['  Intérêts perçus', f"{total_remb_interets:,.3f} {devise}"],
        ['  TOTAL ENTRÉES', f"{entrees_totales:,.3f} {devise}"],
        ['', ''],
        ['📤 SORTIES DU MOIS', ''],
        ['  Dépenses', f"{total_depenses_mois:,.3f} {devise}"],
        ['  Crédits accordés', f"{total_credits_accordes:,.3f} {devise}"],
        ['  TOTAL SORTIES', f"{sorties_totales:,.3f} {devise}"],
        ['', ''],
        ['📊 INFORMATIONS COMPLÉMENTAIRES', ''],
        ['  Intérêts à percevoir (crédits en cours)', f"{total_interets_a_percevoir:,.3f} {devise}"],
        ['  Nombre de remboursements', f"{remboursements_mois.count()}"],
        ['  Nombre de crédits accordés', f"{credits_approuves_mois.count()}"],
        ['', ''],
        ['💰 SOLDE EN CAISSE', f"{solde_caisse:,.3f} {devise}"],
    ]
    
    table_resume = Table(data_resume, colWidths=[12*cm, 4*cm])
    table_resume.setStyle(TableStyle([
        # Ligne vide en haut (ligne 0)
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, 0), 0, colors.white),
        
        # En-tête ENTRÉES (ligne 1)
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
        ('SPAN', (0, 1), (-1, 1)),
        
        # Détails ENTRÉES (lignes 2-5)
        ('BACKGROUND', (0, 2), (-1, 5), colors.lightgrey),
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
        
        # Ligne vide (ligne 6)
        ('BACKGROUND', (0, 6), (-1, 6), colors.white),
        ('GRID', (0, 6), (-1, 6), 0, colors.white),
        
        # En-tête SORTIES (ligne 7)
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#ffe8e8')),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 7), (-1, 7), 11),
        ('SPAN', (0, 7), (-1, 7)),
        
        # Détails SORTIES (lignes 8-9)
        ('BACKGROUND', (0, 8), (-1, 9), colors.lightgrey),
        ('FONTNAME', (0, 9), (-1, 9), 'Helvetica-Bold'),
        
        # Ligne vide (ligne 10)
        ('BACKGROUND', (0, 10), (-1, 10), colors.white),
        ('GRID', (0, 10), (-1, 10), 0, colors.white),
        
        # En-tête INFOS COMPLÉMENTAIRES (ligne 11)
        ('BACKGROUND', (0, 11), (-1, 11), colors.HexColor('#fff8e8')),
        ('FONTNAME', (0, 11), (-1, 11), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 11), (-1, 11), 11),
        ('SPAN', (0, 11), (-1, 11)),
        
        # Détails INFOS (lignes 12-14)
        ('BACKGROUND', (0, 12), (-1, 14), colors.HexColor('#fffef5')),
        
        # Ligne vide (ligne 15)
        ('BACKGROUND', (0, 15), (-1, 15), colors.white),
        ('GRID', (0, 15), (-1, 15), 0, colors.white),
        
        # SOLDE EN CAISSE (ligne 16 - dernière ligne)
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 3, colors.black),
        
        # Alignement général
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 1), (-1, -2), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table_resume)
    
    # Note explicative détaillée
    elements.append(Spacer(1, 0.5*cm))
    note = """
    <b>Lecture du tableau :</b><br/>
    • <b>ENTRÉES</b> = Tout l'argent qui entre dans la caisse ce mois<br/>
    • <b>SORTIES</b> = Tout l'argent qui sort de la caisse ce mois<br/>
    • <b>Intérêts à percevoir</b> = Intérêts non encore remboursés sur les crédits en cours<br/>
    • <b>SOLDE EN CAISSE</b> = Argent disponible actuellement (Entrées - Sorties)
    """
    elements.append(Paragraph(note, styles['Normal']))
    
    # Construire le PDF
    doc.build(elements)
    
    return save_pdf_and_respond(buffer, filename)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapport_annuel_pdf(request, annee):
    """Génère un rapport annuel en PDF"""
    
    filename = f"Rapport_Annuel_{annee}.pdf"
    
    # Créer le document en mémoire
    buffer = BytesIO()
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
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#333333'),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    tenant = get_tenant(request)
    
    # Récupérer les informations de l'association
    association = Association.get_association(tenant)
    devise = association.devise if association and association.devise else "FBU"
    
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
    
    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_remboursements = qs_for_tenant(request, Remboursement.objects.all())
    
    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    data_cotisations_annuel = [['Mois', 'Nombre de cotisations', 'Total ({devise})']]
    
    total_annuel_cotisations = Decimal('0')
    total_nombre_cotisations = 0
    
    for mois in range(1, 13):
        cotisations_mois = base_cotisations.filter(mois=mois, annee=annee)
        nombre = cotisations_mois.count()
        total = cotisations_mois.aggregate(Sum('montant'))['montant__sum'] or 0
        
        data_cotisations_annuel.append([
            mois_noms[mois],
            str(nombre),
            f"{total:,.3f}"
        ])
        
        total_annuel_cotisations += total
        total_nombre_cotisations += nombre
    
    data_cotisations_annuel.append([
        'TOTAL ANNUEL',
        str(total_nombre_cotisations),
        f"{total_annuel_cotisations:,.3f} {devise}"
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
    
    credits_annee = base_credits.filter(date_accord__year=annee)
    nombre_credits = credits_annee.count()
    total_credits_accordes = credits_annee.aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or Decimal('0.000')
    
    data_credits_stats = [
        ['Nombre de crédits accordés', str(nombre_credits)],
        ['Montant total des crédits', f"{total_credits_accordes:,.3f} {devise}"],
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
    
    # Section 3: Bilan financier annuel COMPLET
    elements.append(Paragraph("<b>3. BILAN FINANCIER ANNUEL</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.3*cm))
    
    # ========== CALCULS DÉTAILLÉS ==========
    
    # 1. Cotisations de l'année (déjà calculé)
    # total_annuel_cotisations
    
    # 1b. Cotisations Imprévus de l'année
    total_imprevus_annee = qs_for_tenant(request, CotisationImprevu.objects.filter(statut='PAYE', annee=annee)).aggregate(
        Sum('montant')
    )['montant__sum'] or Decimal('0.000')
    
    # 2. Remboursements de l'année (principal + intérêts)
    remboursements_annee = base_remboursements.filter(date_remboursement__year=annee)
    total_remb_principal = remboursements_annee.aggregate(
        Sum('montant_rembourse')
    )['montant_rembourse__sum'] or Decimal('0.000')
    
    total_remb_interets = remboursements_annee.aggregate(
        Sum('interet_rembourse')
    )['interet_rembourse__sum'] or Decimal('0.000')
    
    total_remboursements_annee = total_remb_principal + total_remb_interets
    
    # 3. Dépenses de l'année
    from .models import Depense
    depenses_annee = qs_for_tenant(request, Depense.objects.filter(date_depense__year=annee)) if hasattr(request, 'tenant') else Depense.objects.none()
    total_depenses_annee = depenses_annee.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

    # 4. Crédits accordés dans l'année (déjà calculé)
    # total_credits_accordes
    
    # 5. Intérêts générés sur TOUS les crédits de l'année
    total_interets_generes = Decimal('0')
    for credit in credits_annee:
        total_interets_generes += credit.calculer_interet()
    
    # 6. Intérêts restants à percevoir
    interets_restants = total_interets_generes - total_remb_interets
    
    # 7. SOLDE EN CAISSE
    # = (Cotisations + Imprévus + Remboursements) - (Dépenses + Crédits accordés)
    entrees_totales = total_annuel_cotisations + total_imprevus_annee + total_remboursements_annee
    sorties_totales = total_depenses_annee + total_credits_accordes
    solde_caisse = entrees_totales - sorties_totales
    
    # ========== TABLEAU RÉCAPITULATIF ==========
    
    data_bilan = [
        ['', ''],
        ['📥 ENTRÉES DE L\'ANNÉE', ''],
        ['  Cotisations annuelles', f"{total_annuel_cotisations:,.3f} {devise}"],
        ['  Cotisations imprévus annuelles', f"{total_imprevus_annee:,.3f} {devise}"],
        ['  Remboursements reçus (principal)', f"{total_remb_principal:,.3f} {devise}"],
        ['  Intérêts perçus', f"{total_remb_interets:,.3f} {devise}"],
        ['  TOTAL ENTRÉES', f"{entrees_totales:,.3f} {devise}"],
        ['', ''],
        ['📤 SORTIES DE L\'ANNÉE', ''],
        ['  Dépenses', f"{total_depenses_annee:,.3f} {devise}"],
        ['  Crédits accordés', f"{total_credits_accordes:,.3f} {devise}"],
        ['  TOTAL SORTIES', f"{sorties_totales:,.3f} {devise}"],
        ['', ''],
        ['📊 INFORMATIONS COMPLÉMENTAIRES', ''],
        ['  Intérêts générés (total)', f"{total_interets_generes:,.3f} {devise}"],
        ['  Intérêts restants à percevoir', f"{interets_restants:,.3f} {devise}"],
        ['  Nombre de remboursements', f"{remboursements_annee.count()}"],
        ['  Nombre de crédits accordés', f"{nombre_credits}"],
        ['', ''],
        ['💰 SOLDE EN CAISSE', f"{solde_caisse:,.3f} {devise}"],
    ]
    
    table_bilan = Table(data_bilan, colWidths=[12*cm, 4*cm])
    table_bilan.setStyle(TableStyle([
        # Ligne vide en haut (ligne 0)
        ('BACKGROUND', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, 0), 0, colors.white),
        
        # En-tête ENTRÉES (ligne 1)
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e8f4f8')),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 11),
        ('SPAN', (0, 1), (-1, 1)),
        
        # Détails ENTRÉES (lignes 2-5)
        ('BACKGROUND', (0, 2), (-1, 5), colors.lightgrey),
        ('FONTNAME', (0, 5), (-1, 5), 'Helvetica-Bold'),
        
        # Ligne vide (ligne 6)
        ('BACKGROUND', (0, 6), (-1, 6), colors.white),
        ('GRID', (0, 6), (-1, 6), 0, colors.white),
        
        # En-tête SORTIES (ligne 7)
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#ffe8e8')),
        ('FONTNAME', (0, 7), (-1, 7), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 7), (-1, 7), 11),
        ('SPAN', (0, 7), (-1, 7)),
        
        # Détails SORTIES (lignes 8-9)
        ('BACKGROUND', (0, 8), (-1, 9), colors.lightgrey),
        ('FONTNAME', (0, 9), (-1, 9), 'Helvetica-Bold'),
        
        # Ligne vide (ligne 10)
        ('BACKGROUND', (0, 10), (-1, 10), colors.white),
        ('GRID', (0, 10), (-1, 10), 0, colors.white),
        
        # En-tête INFOS COMPLÉMENTAIRES (ligne 11)
        ('BACKGROUND', (0, 11), (-1, 11), colors.HexColor('#fff8e8')),
        ('FONTNAME', (0, 11), (-1, 11), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 11), (-1, 11), 11),
        ('SPAN', (0, 11), (-1, 11)),
        
        # Détails INFOS (lignes 12-15)
        ('BACKGROUND', (0, 12), (-1, 15), colors.HexColor('#fffef5')),
        
        # Ligne vide (ligne 16)
        ('BACKGROUND', (0, 16), (-1, 16), colors.white),
        ('GRID', (0, 16), (-1, 16), 0, colors.white),
        
        # SOLDE EN CAISSE (ligne 17 - dernière ligne)
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#27ae60')),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 14),
        ('LINEABOVE', (0, -1), (-1, -1), 3, colors.black),
        
        # Alignement général
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 1), (-1, -2), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table_bilan)
    
    # Note explicative
    elements.append(Spacer(1, 0.5*cm))
    note = """
    <b>Lecture du tableau :</b><br/>
    • <b>ENTRÉES</b> = Tout l'argent qui entre dans la caisse cette année<br/>
    • <b>SORTIES</b> = Tout l'argent qui sort de la caisse cette année<br/>
    • <b>Intérêts générés</b> = Total des intérêts sur tous les crédits de l'année<br/>
    • <b>Intérêts restants à percevoir</b> = Intérêts non encore remboursés<br/>
    • <b>SOLDE EN CAISSE</b> = Argent disponible actuellement (Entrées - Sorties)
    """
    elements.append(Paragraph(note, styles['Normal']))
    
    # Construire le PDF
    doc.build(elements)
    
    return save_pdf_and_respond(buffer, filename)
