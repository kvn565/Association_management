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
from datetime import datetime, date
from decimal import Decimal

from .models import Membre, Cotisation, CotisationImprevu, Credit, Remboursement, Association, PenaliteCotisation, Interet
from .pdf_utils import save_pdf_and_respond


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


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and user.is_admin


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
        total_cotisations = cotisations.aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
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
    
    total_remb_interets = qs_for_tenant(request, Interet.objects.filter(
        date_remboursement__month=mois, date_remboursement__year=annee
    )).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0.000')
    
    # 2b. Pénalités payées du mois
    from .models import PenaliteCotisation
    total_penalites_payees = qs_for_tenant(request, PenaliteCotisation.objects.filter(
        date_paiement__month=mois, date_paiement__year=annee
    )).aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0.000')
    
    # 3. Crédits accordés dans le mois
    credits_approuves_mois = base_credits.filter(
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE'],
        date_accord__month=mois,
        date_accord__year=annee
    )
    total_credits_accordes = credits_approuves_mois.aggregate(
        Sum('montant_accorde')
    )['montant_accorde__sum'] or Decimal('0.000')
    
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
    ))
    total_depenses_mois = depenses_mois.aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')

    # 6. Assistances du mois
    from cas_assistance.models import CasAssistance
    total_assistances_mois = qs_for_tenant(request, CasAssistance.objects.filter(
        date_assistance__month=mois, date_assistance__year=annee
    )).aggregate(Sum('montant'))['montant__sum'] or Decimal('0.000')
    reste_imprevus_mois = total_imprevus_mois - total_assistances_mois

    # 7. SOLDE EN CAISSE
    entrees_totales = total_remb_principal + total_cotisations_mois + total_remb_interets + total_penalites_payees
    sorties_totales = total_depenses_mois + total_credits_accordes
    solde_caisse = entrees_totales - sorties_totales
    
    # ========== TABLEAU RÉCAPITULATIF ==========
    
    data_resume = [
        ['', ''],
        ['📥 ENTRÉES DU MOIS', ''],
        ['  Cotisations reçues', f"{total_cotisations_mois:,.3f} {devise}"],
        ['  Remboursements reçus (principal)', f"{total_remb_principal:,.3f} {devise}"],
        ['  Intérêts perçus', f"{total_remb_interets:,.3f} {devise}"],
        ['  Pénalités perçues', f"{total_penalites_payees:,.3f} {devise}"],
        ['  TOTAL ENTRÉES', f"{entrees_totales:,.3f} {devise}"],
        ['', ''],
        ['📤 SORTIES DU MOIS', ''],
        ['  Dépenses', f"{total_depenses_mois:,.3f} {devise}"],
        ['  Crédits accordés', f"{total_credits_accordes:,.3f} {devise}"],
        ['  TOTAL SORTIES', f"{sorties_totales:,.3f} {devise}"],
        ['', ''],
        ['📊 INFORMATIONS COMPLÉMENTAIRES', ''],
        ['  Cotisations imprévus reçues', f"{total_imprevus_mois:,.3f} {devise}"],
        ['  Assistances payées', f"{total_assistances_mois:,.3f} {devise}"],
        ['  Reste (Imprévus - Assistances)', f"{reste_imprevus_mois:,.3f} {devise}"],
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
        
        # Détails INFOS (lignes 12-16)
        ('BACKGROUND', (0, 12), (-1, 16), colors.HexColor('#fffef5')),
        
        # Ligne vide (ligne 20)
        ('BACKGROUND', (0, 20), (-1, 20), colors.white),
        ('GRID', (0, 20), (-1, 20), 0, colors.white),
        
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
    from .models import Interet
    
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
        total = cotisations_mois.aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        
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
    
    total_remb_interets = qs_for_tenant(request, Interet.objects.filter(
        date_remboursement__year=annee
    )).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0.000')
    
    total_remboursements_annee = total_remb_principal + total_remb_interets
    
    # 2b. Pénalités payées de l'année
    from .models import PenaliteCotisation
    total_penalites_payees_annee = qs_for_tenant(request, PenaliteCotisation.objects.filter(
        date_paiement__year=annee
    )).aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0.000')
    
    # 3. Dépenses de l'année
    from .models import Depense
    depenses_annee = qs_for_tenant(request, Depense.objects.filter(date_depense__year=annee))
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
    entrees_totales = (total_annuel_cotisations
                       + total_remb_principal + total_remb_interets + total_penalites_payees_annee)
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
        ['  Pénalités perçues', f"{total_penalites_payees_annee:,.3f} {devise}"],
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


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def rapport_periode_pdf(request, mois_debut, annee_debut, mois_fin, annee_fin):
    """Génère un PDF du rapport par période"""
    from dateutil.relativedelta import relativedelta
    from calendar import monthrange
    from datetime import date
    from decimal import Decimal
    from django.db.models import Sum

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    filename = f"Rapport_Periode_{mois_noms[mois_debut]}_{annee_debut}_a_{mois_noms[mois_fin]}_{annee_fin}.pdf"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=10, textColor=colors.grey, spaceAfter=12)

    date_generation = datetime.now().strftime('%d/%m/%Y %H:%M')
    devise = Association.objects.first().devise if Association.objects.first() else 'F'

    from cas_assistance.models import CasAssistance
    base_cotisations = qs_for_tenant(request, Cotisation.objects.all())
    base_imprevus = qs_for_tenant(request, CotisationImprevu.objects.all())
    base_assistances = qs_for_tenant(request, CasAssistance.objects.all())
    base_remboursements = qs_for_tenant(request, Remboursement.objects.all())
    base_credits = qs_for_tenant(request, Credit.objects.all())
    base_interets = qs_for_tenant(request, Interet.objects.all())
    base_penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False))
    from .models import Depense
    base_depenses = qs_for_tenant(request, Depense.objects.all())

    date_debut = date(annee_debut, mois_debut, 1)
    date_fin = date(annee_fin, mois_fin, monthrange(annee_fin, mois_fin)[1])

    # Collecter mois_list
    mois_list = []
    current = date_debut
    while current <= date_fin:
        mois_list.append((current.month, current.year))
        current += relativedelta(months=1)

    # Participants : tous les membres ayant effectué un paiement sur la période
    membres_ids = set()
    for m, a in mois_list:
        mids = base_cotisations.filter(mois=m, annee=a, statut='PAYE').values_list('membre_id', flat=True).distinct()
        membres_ids.update(mids)
        mids_imp = base_imprevus.filter(mois=m, annee=a, statut='PAYE').values_list('membre_id', flat=True).distinct()
        membres_ids.update(mids_imp)
    membres_ids.update(
        base_remboursements.filter(date_remboursement__range=(date_debut, date_fin)).values_list('credit__membre_id', flat=True).distinct()
    )
    membres_ids.update(
        base_interets.filter(date_remboursement__range=(date_debut, date_fin), interet_rembourse__gt=0).values_list('credit__membre_id', flat=True).distinct()
    )
    membres_ids.update(
        base_penalites.filter(date_paiement__range=(date_debut, date_fin)).values_list('membre_id', flat=True).distinct()
    )
    membres = Membre.objects.filter(pk__in=membres_ids).order_by('nom', 'prenom')

    # Récapitulatif par mois
    mois_data = []
    assist_data = []
    cumul = Decimal('0')
    for m, a in mois_list:
        cot_mois = base_cotisations.filter(mois=m, annee=a, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        imp_mois = base_imprevus.filter(mois=m, annee=a, statut='PAYE').aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        remb_mois = base_remboursements.filter(date_remboursement__month=m, date_remboursement__year=a).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0')
        int_mois = base_interets.filter(date_remboursement__month=m, date_remboursement__year=a).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0')
        cred_mois = base_credits.filter(date_accord__month=m, date_accord__year=a,
            statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or Decimal('0')
        pen_mois = base_penalites.filter(date_paiement__month=m, date_paiement__year=a).aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0')
        assistance_mois = base_assistances.filter(date_assistance__month=m, date_assistance__year=a).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        dep_mois = base_depenses.filter(date_depense__month=m, date_depense__year=a).aggregate(Sum('montant'))['montant__sum'] or Decimal('0')
        effectif = base_cotisations.filter(mois=m, annee=a, statut='PAYE').values('membre').distinct().count()
        reste_imprevus = imp_mois - assistance_mois
        entrees = cot_mois + remb_mois + int_mois + pen_mois
        sorties = cred_mois + dep_mois
        solde_mois = entrees - sorties
        cumul += solde_mois
        reste_caisse = max(solde_mois, Decimal('0'))
        mois_data.append((f"{mois_noms[m]} {a}", str(effectif),
                          f"{cot_mois:,.3f}", f"{imp_mois:,.3f}", f"{remb_mois:,.3f}",
                          f"{int_mois:,.3f}", f"{pen_mois:,.3f}", f"{cred_mois:,.3f}",
                          f"{dep_mois:,.3f}", f"{reste_caisse:,.3f}"))
        assist_data.append((f"{mois_noms[m]} {a}",
                            f"{imp_mois:,.3f}", f"{assistance_mois:,.3f}",
                            f"{reste_imprevus:,.3f}"))

    # ====== TITRE ======
    elements.append(Paragraph(f"Rapport par période", title_style))
    elements.append(Paragraph(
        f"Du {mois_noms[mois_debut]} {annee_debut} au {mois_noms[mois_fin]} {annee_fin} &nbsp;|&nbsp; Généré le {date_generation}",
        subtitle_style))
    elements.append(Spacer(1, 0.4*cm))

    # ====== TABLEAU PARTICIPANTS ======
    elements.append(Paragraph("<b>Participants aux cotisations</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.2*cm))

    part_header = ['Membre'] + [f"{mois_noms[m]}\n{a}" for m, a in mois_list]
    part_data = [part_header]
    for membre in membres:
        row = [membre.get_full_name()]
        for m, a in mois_list:
            cot = base_cotisations.filter(membre=membre, mois=m, annee=a, statut='PAYE').first()
            row.append('✓' if cot else '')
        part_data.append(row)

    # Largeurs de colonnes pour participants
    col_widths = [4*cm] + [1.5*cm] * len(mois_list)
    table_parts = Table(part_data, colWidths=col_widths, repeatRows=1)
    table_parts.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#38f9d7')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(table_parts)
    elements.append(Spacer(1, 0.6*cm))

    # ====== TABLEAU RÉCAPITULATIF ======
    elements.append(Paragraph("<b>Récapitulatif financier par mois</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.2*cm))

    rec_header = ['Période', 'Eff.', 'Cotisations', 'Imprévus',
                  'Rembours.' , 'Intérêts', 'Pénalités', 'Crédits',
                  'Dépenses', 'Solde en caisse']
    rec_data = [rec_header]
    for row in mois_data:
        rec_data.append(list(row))

    # Totaux
    tot_eff = max(int(r[1]) for r in mois_data)
    tot_cot = sum(Decimal(r[2].replace(',', '')) for r in mois_data)
    tot_imp = sum(Decimal(r[3].replace(',', '')) for r in mois_data)
    tot_remb = sum(Decimal(r[4].replace(',', '')) for r in mois_data)
    tot_int = sum(Decimal(r[5].replace(',', '')) for r in mois_data)
    tot_pen = sum(Decimal(r[6].replace(',', '')) for r in mois_data)
    tot_cred = sum(Decimal(r[7].replace(',', '')) for r in mois_data)
    tot_dep = sum(Decimal(r[8].replace(',', '')) for r in mois_data)
    rec_data.append(['TOTAL (Eff.=MAX)', str(tot_eff),
                     f"{tot_cot:,.3f}", f"{tot_imp:,.3f}", f"{tot_remb:,.3f}",
                     f"{tot_int:,.3f}", f"{tot_pen:,.3f}", f"{tot_cred:,.3f}",
                     f"{tot_dep:,.3f}", ''])

    rec_widths = [3.5*cm, 1*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.3*cm, 2.6*cm]
    table_rec = Table(rec_data, colWidths=rec_widths, repeatRows=1)
    table_rec.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -2), 7),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f0ff')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#38f9d7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#28a745')),
    ]))
    elements.append(table_rec)

    elements.append(Spacer(1, 0.6*cm))
    elements.append(Paragraph(
        f"<i>Légende : Eff. = effectif (nombre de membres ayant cotisé) | "
        f"Solde en caisse = Entrées (cotisations + remboursements + intérêts + pénalités) "
        f"- Sorties (dépenses + crédits accordés), minimum 0. "
        f"Imprévus et assistances : voir bilan ci-dessous.</i>",
        styles['Normal']))

    # ====== BILAN IMPREVUS / ASSISTANCES ======
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph("<b>Bilan Imprévus / Assistances</b>", styles['Heading2']))
    elements.append(Spacer(1, 0.2*cm))

    bil_header = ['Période', 'Imprévus', 'Assistances', 'Reste']
    bil_data = [bil_header]
    for row in assist_data:
        bil_data.append(list(row))
    tot_imp = sum(Decimal(r[1].replace(',', '')) for r in assist_data)
    tot_assist = sum(Decimal(r[2].replace(',', '')) for r in assist_data)
    tot_reste = tot_imp - tot_assist
    bil_data.append(['TOTAL', f"{tot_imp:,.3f}", f"{tot_assist:,.3f}", f"{tot_reste:,.3f}"])

    bil_widths = [3.5*cm, 3*cm, 3*cm, 3*cm]
    table_bil = Table(bil_data, colWidths=bil_widths, repeatRows=1)
    table_bil.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#43e97b')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 7),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0fff0')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#38f9d7')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#28a745')),
    ]))
    elements.append(table_bil)

    # ====== TABLEAU PAIEMENTS PAR MEMBRE ======
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("<b>Paiements par membre et par mois</b>", styles['Heading2']))
    elements.append(Paragraph(
        "<i>Légende : C = cotisation, IMP = imprévu, R = remboursement, I = intérêt, P = pénalité.</i>",
        styles['Normal']))
    elements.append(Spacer(1, 0.2*cm))

    pay_header = ['Membre'] + [f"{mois_noms[m]}\n{a}" for m, a in mois_list] + ['Total']
    pay_data = [pay_header]
    for membre in membres:
        row = [membre.get_full_name()]
        total_general = Decimal('0')
        for m, a in mois_list:
            cot_p = base_cotisations.filter(membre=membre, mois=m, annee=a, statut='PAYE').aggregate(
                Sum('montant'))['montant__sum'] or Decimal('0')
            imp_p = base_imprevus.filter(membre=membre, mois=m, annee=a, statut='PAYE').aggregate(
                Sum('montant'))['montant__sum'] or Decimal('0')
            remb_p = base_remboursements.filter(
                credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
            ).aggregate(Sum('montant_rembourse'))['montant_rembourse__sum'] or Decimal('0')
            inte_p = base_interets.filter(
                credit__membre=membre, date_remboursement__month=m, date_remboursement__year=a
            ).aggregate(Sum('interet_rembourse'))['interet_rembourse__sum'] or Decimal('0')
            pen_p = base_penalites.filter(
                membre=membre, date_paiement__month=m, date_paiement__year=a
            ).aggregate(Sum('montant_paye'))['montant_paye__sum'] or Decimal('0')
            total_general += cot_p + imp_p + remb_p + inte_p + pen_p
            lignes = []
            if cot_p:
                lignes.append(f"C:{cot_p:,.0f}")
            if imp_p:
                lignes.append(f"IMP:{imp_p:,.0f}")
            if remb_p:
                lignes.append(f"R:{remb_p:,.0f}")
            if inte_p:
                lignes.append(f"I:{inte_p:,.0f}")
            if pen_p:
                lignes.append(f"P:{pen_p:,.0f}")
            row.append("\n".join(lignes) if lignes else "-")
        row.append(f"{total_general:,.0f}")
        pay_data.append(row)

    pay_name_w = 3*cm
    pay_total_w = 1.8*cm
    pay_month_w = min(2.4*cm, (27.7*cm - pay_name_w - pay_total_w) / max(len(mois_list), 1))
    pay_widths = [pay_name_w] + [pay_month_w] * len(mois_list) + [pay_total_w]
    table_pay = Table(pay_data, colWidths=pay_widths, repeatRows=1)
    table_pay.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f5576c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 6.5),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fff5f7')]),
    ]))
    elements.append(table_pay)

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def penalites_pdf(request):
    """Génère un PDF récapitulatif du calcul des pénalités - 1 ligne par membre"""
    from dateutil.relativedelta import relativedelta
    from django.db.models import F
    from collections import defaultdict

    nom_mois = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    filename = f"Recapitulatif_Penalites_{datetime.now().strftime('%Y%m%d')}.pdf"
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), leftMargin=1*cm, rightMargin=1*cm, topMargin=1.5*cm, bottomMargin=1.5*cm)
    elements = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=16, spaceAfter=6)
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=9, textColor=colors.grey, spaceAfter=12)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=6.5, leading=8, alignment=1)

    today = datetime.now()
    date_generation = today.strftime('%d/%m/%Y %H:%M')
    devise = Association.objects.first().devise if Association.objects.first() else 'F'

    penalites = qs_for_tenant(request, PenaliteCotisation.objects.filter(exclu=False))
    penalites = penalites.filter(membre__est_actif=True).select_related('membre')
    tenant = get_tenant(request)

    # Appliquer les mêmes filtres que la liste
    annee_filter = request.GET.get('annee', '')
    mois_filter = request.GET.get('mois', '')
    statut_filter = request.GET.get('statut', '')
    if annee_filter:
        penalites = penalites.filter(annee=annee_filter)
    if mois_filter:
        penalites = penalites.filter(mois=mois_filter)
    if statut_filter == 'payee':
        penalites = penalites.filter(montant_paye__gte=F('penalite_cumulee'))
    elif statut_filter == 'impayee':
        penalites = penalites.filter(montant_paye__lt=F('penalite_cumulee'))

    penalites = penalites.order_by('-annee', '-mois', 'membre__nom')

    # Exclure les pénalités antérieures au début global du tenant (comme generer_toutes_penalites)
    premiere_cot_tenant = Cotisation.objects.filter(
        membre__tenant=tenant
    ).order_by('annee', 'mois').values('annee', 'mois').first()
    premiere_imp_tenant = CotisationImprevu.objects.filter(
        membre__tenant=tenant
    ).order_by('annee', 'mois').values('annee', 'mois').first()
    mois_debut_tenant = None
    if premiere_cot_tenant:
        md = premiere_cot_tenant['annee'] * 12 + premiere_cot_tenant['mois']
        mois_debut_tenant = md if mois_debut_tenant is None else min(mois_debut_tenant, md)
    if premiere_imp_tenant:
        md = premiere_imp_tenant['annee'] * 12 + premiere_imp_tenant['mois']
        mois_debut_tenant = md if mois_debut_tenant is None else min(mois_debut_tenant, md)
    if mois_debut_tenant is not None:
        ids_a_garder = []
        for p in penalites:
            if p.annee * 12 + p.mois >= mois_debut_tenant:
                ids_a_garder.append(p.pk)
        penalites = [p for p in penalites if p.pk in ids_a_garder]

    elements.append(Paragraph("Récapitulatif des pénalités par membre", title_style))
    elements.append(Paragraph(f"Généré le {date_generation}", subtitle_style))
    elements.append(Spacer(1, 0.3*cm))

    if not penalites:
        elements.append(Paragraph("Aucune pénalité enregistrée.", styles['Normal']))
        doc.build(elements)
        return save_pdf_and_respond(buffer, filename)

    # Agréger par membre : 1 ligne par membre
    membres_aggreg = defaultdict(lambda: {
        'membre': None,
        'periodes': [],
        'base_simple_total': Decimal('0'),
        'base_imprevu_total': Decimal('0'),
        'base_totale': Decimal('0'),
        'pen_mens_totale': Decimal('0'),
        'paye_total': Decimal('0'),
        'reste_total': Decimal('0'),
        'details_base': [],
    })

    for p in penalites:
        agg = membres_aggreg[p.membre_id]
        agg['membre'] = p.membre
        mnt_cot = p.montant_cotisation_base
        mnt_imp = p.montant_imprevu_base
        if mnt_cot == 0 and mnt_imp == 0 and p.montant_cotisation > 0:
            cotisation = Cotisation.objects.filter(membre=p.membre, mois=p.mois, annee=p.annee).first()
            cotisation_imp = CotisationImprevu.objects.filter(membre=p.membre, mois=p.mois, annee=p.annee).first()
            assoc = Association.objects.filter(tenant=p.tenant).first() if hasattr(p, 'tenant') and p.tenant else None
            if assoc is None:
                assoc = Association.objects.first()
            mnt_cot = cotisation.montant if cotisation else (assoc.montant_cotisation_mensuelle if assoc else 0)
            mnt_imp = cotisation_imp.montant if cotisation_imp else (assoc.montant_cotisation_imprevu_mensuelle if assoc else 0)

        base = mnt_cot + mnt_imp
        reste = max(p.penalite_mensuelle - p.montant_paye, Decimal('0'))

        periode_label = f"{nom_mois[p.mois]} {p.annee}"
        agg['periodes'].append(periode_label)
        agg['base_simple_total'] += mnt_cot
        agg['base_imprevu_total'] += mnt_imp
        agg['base_totale'] += base
        agg['pen_mens_totale'] += p.penalite_mensuelle
        agg['paye_total'] += p.montant_paye
        agg['reste_total'] += reste
        # Détail pour affichage : "Janv 2024: 5000+2000=7000"
        if mnt_cot > 0 or mnt_imp > 0:
            detail_str = f"{periode_label}: {mnt_cot:,.0f}"
            if mnt_imp > 0:
                detail_str += f"+{mnt_imp:,.0f}"
            detail_str += f"={base:,.0f}"
            agg['details_base'].append(detail_str)

    header = ['N°', 'Membre', 'Périodes', 'Base simple\n(somme)', 'Base imprévu\n(somme)', 'Base totale\n(somme)', 'Détail base\npar période',
              'Pénalité/mois\n(somme)', 'Payé', 'Reste à payer']

    data = [header]
    for idx, (mid, agg) in enumerate(membres_aggreg.items(), 1):
        periodes_str = ", ".join(agg['periodes'])
        details_base_str = "<br/>".join(agg['details_base']) if agg['details_base'] else "—"
        data.append([
            Paragraph(str(idx), small_style),
            Paragraph(agg['membre'].get_full_name(), small_style),
            Paragraph(periodes_str, ParagraphStyle('p_left', parent=small_style, alignment=0)),
            Paragraph(f"{agg['base_simple_total']:,.0f}", small_style),
            Paragraph(f"{agg['base_imprevu_total']:,.0f}", small_style),
            Paragraph(f"<b>{agg['base_totale']:,.0f}</b>", small_style),
            Paragraph(details_base_str, ParagraphStyle('p_left_small', parent=small_style, alignment=0, fontSize=6)),
            Paragraph(f"{agg['pen_mens_totale']:,.3f}", small_style),
            Paragraph(f"{agg['paye_total']:,.3f}", small_style),
            Paragraph(f"<b><font color='red'>{agg['reste_total']:,.3f}</font></b>", small_style),
        ])

    # Totaux globaux
    tot_base_simple = sum(agg['base_simple_total'] for agg in membres_aggreg.values())
    tot_base_imprevu = sum(agg['base_imprevu_total'] for agg in membres_aggreg.values())
    tot_base = sum(agg['base_totale'] for agg in membres_aggreg.values())
    tot_pen_mens = sum(agg['pen_mens_totale'] for agg in membres_aggreg.values())
    tot_paye = sum(agg['paye_total'] for agg in membres_aggreg.values())
    tot_reste = sum(agg['reste_total'] for agg in membres_aggreg.values())

    data.append([
        Paragraph('', small_style),
        Paragraph('<b>TOTAUX</b>', small_style),
        Paragraph('', small_style),
        Paragraph(f"<b>{tot_base_simple:,.0f}</b>", small_style),
        Paragraph(f"<b>{tot_base_imprevu:,.0f}</b>", small_style),
        Paragraph(f"<b>{tot_base:,.0f}</b>", small_style),
        Paragraph('', small_style),
        Paragraph(f"<b>{tot_pen_mens:,.3f}</b>", small_style),
        Paragraph(f"<b>{tot_paye:,.3f}</b>", small_style),
        Paragraph(f"<b><font color='red'>{tot_reste:,.3f}</font></b>", small_style),
    ])

    col_widths = [0.8*cm, 3.2*cm, 3.5*cm, 2*cm, 2*cm, 2*cm, 4.5*cm, 2.2*cm, 1.8*cm, 2*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc3545')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 7),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'LEFT'),
        ('ALIGN', (6, 0), (6, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.4, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#fff5f5')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ffd32a')),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(table)

    elements.append(Spacer(1, 0.5*cm))
    note = """
    <b>Lecture du tableau (1 ligne = 1 membre) :</b><br/>
    • <b>Périodes</b> = mois où le membre a des pénalités<br/>
    • <b>Base simple / Base imprévu / Base totale</b> = sommes sur tous les mois impayés<br/>
    • <b>Détail base par période</b> = "Mois: simple+imprévu=total" pour chaque période<br/>
    • <b>Pénalité/mois</b> = somme des pénalités mensuelles (Base × Taux/100)<br/>
    • <b>Payé / Reste</b> = totaux versés et dû restant (Reste en <font color='red'>rouge</font>)
    """
    elements.append(Paragraph(note, styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
