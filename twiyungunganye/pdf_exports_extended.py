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
    from django.db.models import Q

    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "RÉCAPITULATIF DES INTÉRÊTS PAR MEMBRE", "Interets_Par_Membre.pdf"
    )

    interets = qs_for_tenant(request, Interet.objects.all()).select_related(
        'credit__membre'
    ).order_by('credit__membre__nom', 'credit_id', 'annee', 'mois')

    # Filtres
    annee_filter = request.GET.get('annee', '')
    mois_filter = request.GET.get('mois', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')

    if annee_filter:
        interets = interets.filter(annee=annee_filter)
    if mois_filter:
        interets = interets.filter(mois=mois_filter)
    if date_debut:
        try:
            d = datetime.strptime(date_debut, '%Y-%m-%d').date()
            interets = interets.filter(
                Q(annee__gt=d.year) | Q(annee=d.year, mois__gte=d.month)
            )
        except ValueError:
            pass
    if date_fin:
        try:
            d = datetime.strptime(date_fin, '%Y-%m-%d').date()
            interets = interets.filter(
                Q(annee__lt=d.year) | Q(annee=d.year, mois__lte=d.month)
            )
        except ValueError:
            pass

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    header = ['Membre', 'Crédit #', 'Période', 'Mt Crédit', 'Taux%', 'Intérêt Ms', 'Payé', 'Reste', 'Total Membre']
    data = [header]
    span_cmds = []
    current_row = 1

    if interets.exists():
        from collections import OrderedDict
        membres_data = OrderedDict()

        for it in interets:
            membre = it.credit.membre
            mid = membre.id_membre
            if mid not in membres_data:
                membres_data[mid] = {
                    'membre': membre,
                    'lignes': [],
                    'total_interets': Decimal('0'),
                    'total_paye': Decimal('0'),
                }
            md = membres_data[mid]
            reste = max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))
            md['lignes'].append({
                'credit_id': it.credit.id_credit,
                'montant_accorde': it.credit.montant_accorde,
                'taux': it.credit.taux_interet,
                'periode': f"{mois_noms[it.mois]} {it.annee}",
                'interet_mensuel': it.interet_mensuel,
                'interet_rembourse': it.interet_rembourse,
                'reste': reste,
            })
            md['total_interets'] += it.interet_mensuel
            md['total_paye'] += it.interet_rembourse

        for mid, md in membres_data.items():
            reste_membre = md['total_interets'] - md['total_paye']
            est_solde = reste_membre <= 0
            membre_nom = md['membre'].get_full_name()
            if est_solde:
                membre_nom = f"✓ {membre_nom} (Soldé)"
            lignes = md['lignes']
            n = len(lignes)
            start_row = current_row

            for idx, ligne in enumerate(lignes):
                if idx == 0:
                    nom_cell = membre_nom
                    total_cell = f"{md['total_interets']:,.3f}"
                else:
                    nom_cell = ''
                    total_cell = ''

                reste_ligne = ligne['reste']
                reste_str = f"{reste_ligne:,.3f}" if reste_ligne > 0 else "Payé"

                data.append([
                    nom_cell,
                    str(ligne['credit_id']),
                    ligne['periode'],
                    f"{ligne['montant_accorde']:,.3f}",
                    f"{ligne['taux']}%",
                    f"{ligne['interet_mensuel']:,.3f}",
                    f"{ligne['interet_rembourse']:,.3f}",
                    reste_str,
                    total_cell,
                ])
                current_row += 1

            if n > 1:
                span_cmds.append(('SPAN', (0, start_row), (0, start_row + n - 1)))
                span_cmds.append(('SPAN', (8, start_row), (8, start_row + n - 1)))

        grand_total_interets = sum(md['total_interets'] for md in membres_data.values())
        grand_total_paye = sum(md['total_paye'] for md in membres_data.values())
        grand_total_reste = grand_total_interets - grand_total_paye
        data.append(['TOTAL GÉNÉRAL', '', '', '', '', f"{grand_total_interets:,.3f}", f"{grand_total_paye:,.3f}", f"{grand_total_reste:,.3f}", ''])

        col_widths = [3*cm, 1.5*cm, 2.5*cm, 2*cm, 1.2*cm, 2*cm, 2*cm, 2*cm, 2.5*cm]
        table = Table(data, colWidths=col_widths)

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 6.5),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f5e3')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            # Reste = "Payé" en vert
            ('TEXTCOLOR', (7, 1), (7, -2), colors.green),
        ]
        style_cmds.extend(span_cmds)

        # Alternance de couleurs par groupe de membre (vert si soldé)
        row_idx = 1
        color_idx = 0
        colors_bg = [colors.white, colors.HexColor('#f0faf0')]
        colors_bg_solde = [colors.HexColor('#e8f8e8'), colors.HexColor('#d0f0d0')]
        for mid, md in membres_data.items():
            reste_membre = md['total_interets'] - md['total_paye']
            n = len(md['lignes'])
            if reste_membre <= 0:
                bg = colors_bg_solde[color_idx % 2]
            else:
                bg = colors_bg[color_idx % 2]
            for r in range(row_idx, row_idx + n):
                if r < len(data) - 1:
                    style_cmds.append(('BACKGROUND', (0, r), (-1, r), bg))
            color_idx += 1
            row_idx += n

        table.setStyle(TableStyle(style_cmds))
        elements.append(table)
    else:
        elements.append(Paragraph("<i>Aucun intérêt trouvé.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Interets_Par_Membre.pdf")


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def export_interets_restants_pdf(request):
    from django.db.models import Q

    devise = get_devise(request)
    buffer, doc, elements, styles = _build_pdf_response(
        request, "INTÉRÊTS RESTANTS PAR MEMBRE", "Interets_Restants.pdf"
    )

    interets = qs_for_tenant(request, Interet.objects.all()).select_related(
        'credit__membre'
    ).order_by('credit__membre__nom', 'credit_id', 'annee', 'mois')

    annee_filter = request.GET.get('annee', '')
    mois_filter = request.GET.get('mois', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')

    if annee_filter:
        interets = interets.filter(annee=annee_filter)
    if mois_filter:
        interets = interets.filter(mois=mois_filter)
    if date_debut:
        try:
            d = datetime.strptime(date_debut, '%Y-%m-%d').date()
            interets = interets.filter(
                Q(annee__gt=d.year) | Q(annee=d.year, mois__gte=d.month)
            )
        except ValueError:
            pass
    if date_fin:
        try:
            d = datetime.strptime(date_fin, '%Y-%m-%d').date()
            interets = interets.filter(
                Q(annee__lt=d.year) | Q(annee=d.year, mois__lte=d.month)
            )
        except ValueError:
            pass

    mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']

    data = [['Membre', 'Crédit #', 'Date Demande', 'Période', 'Mt Crédit', 'Taux%', 'Intérêt Ms', 'Payé', 'Reste']]
    span_cmds = []
    current_row = 1

    if interets.exists():
        from collections import OrderedDict
        membres_data = OrderedDict()

        for it in interets:
            reste = max(it.interet_mensuel - it.interet_rembourse, Decimal('0'))
            if reste <= 0:
                continue
            membre = it.credit.membre
            mid = membre.id_membre
            if mid not in membres_data:
                membres_data[mid] = {
                    'membre': membre,
                    'lignes': [],
                    'total_interets': Decimal('0'),
                    'total_paye': Decimal('0'),
                }
            md = membres_data[mid]
            md['lignes'].append({
                'credit_id': it.credit.id_credit,
                'date_accord': it.credit.date_accord,
                'montant_accorde': it.credit.montant_accorde,
                'taux': it.credit.taux_interet,
                'periode': f"{mois_noms[it.mois]} {it.annee}",
                'interet_mensuel': it.interet_mensuel,
                'interet_rembourse': it.interet_rembourse,
                'reste': reste,
            })
            md['total_interets'] += it.interet_mensuel
            md['total_paye'] += it.interet_rembourse

        for mid, md in membres_data.items():
            reste_membre = md['total_interets'] - md['total_paye']
            if reste_membre <= 0:
                continue
            membre_nom = md['membre'].get_full_name()
            lignes = md['lignes']
            n = len(lignes)
            start_row = current_row

            for idx, ligne in enumerate(lignes):
                data.append([
                    membre_nom if idx == 0 else '',
                    str(ligne['credit_id']),
                    ligne['date_accord'].strftime('%d/%m/%Y') if ligne['date_accord'] else '',
                    ligne['periode'],
                    f"{ligne['montant_accorde']:,.3f}",
                    f"{ligne['taux']}%",
                    f"{ligne['interet_mensuel']:,.3f}",
                    f"{ligne['interet_rembourse']:,.3f}",
                    f"{ligne['reste']:,.3f}",
                ])
                current_row += 1

            if n > 1:
                span_cmds.append(('SPAN', (0, start_row), (0, start_row + n - 1)))

        if data:
            grand_total_interets = sum(md['total_interets'] for md in membres_data.values())
            grand_total_paye = sum(md['total_paye'] for md in membres_data.values())
            grand_total_reste = grand_total_interets - grand_total_paye
            data.append(['TOTAL GÉNÉRAL', '', '', '', '', '', f"{grand_total_interets:,.3f}", f"{grand_total_paye:,.3f}", f"{grand_total_reste:,.3f}"])

            col_widths = [3*cm, 1.5*cm, 2*cm, 2.5*cm, 2*cm, 1.2*cm, 2*cm, 2*cm, 2*cm]
            table = Table(data, colWidths=col_widths)

            style_cmds = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2ecc71')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 4),
                ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 6.5),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 1), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d5f5e3')),
                ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                ('LINEABOVE', (0, -1), (-1, -1), 2, colors.black),
            ]
            style_cmds.extend(span_cmds)

            row_idx = 1
            color_idx = 0
            colors_bg = [colors.white, colors.HexColor('#f0faf0')]
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
        else:
            elements.append(Paragraph("<i>Tous les intérêts sont soldés.</i>", styles['Normal']))
    else:
        elements.append(Paragraph("<i>Aucun intérêt trouvé.</i>", styles['Normal']))

    doc.build(elements)
    return save_pdf_and_respond(buffer, "Interets_Restants.pdf")
