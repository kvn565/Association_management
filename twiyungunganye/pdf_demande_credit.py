import io
import os
from datetime import datetime

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .models import Association
from .pdf_utils import save_pdf_and_respond


def demande_credit_pdf(request):
    """Génère un formulaire vierge de demande de crédit téléchargeable."""
    from superadmin.models import Tenant, ConfigurationApp

    tenant_id = request.GET.get('tenant')
    tenant = None
    association = None

    if tenant_id:
        tenant = get_object_or_404(Tenant, pk=tenant_id, actif=True)
        association = Association.get_association(tenant)

    config = ConfigurationApp.objects.first()

    buffer = io.BytesIO()
    filename = "Demande_Credit.pdf"

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1*cm, bottomMargin=1*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm
    )
    elements = []
    W = 18*cm

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle('Title', fontSize=14, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                  spaceAfter=2)
    subtitle_style = ParagraphStyle('Sub', fontSize=8, fontName='Helvetica',
                                     textColor=colors.HexColor('#555555'), alignment=TA_CENTER,
                                     spaceAfter=1)
    form_title = ParagraphStyle('FormTitle', fontSize=11, fontName='Helvetica-Bold',
                                 textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                 spaceBefore=3, spaceAfter=6,
                                 borderPadding=3, backColor=colors.HexColor('#eef4fa'))
    label_style = ParagraphStyle('Label', fontSize=9, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#333333'))
    value_style = ParagraphStyle('Value', fontSize=10, fontName='Helvetica',
                                  textColor=colors.HexColor('#111111'))
    info_label = ParagraphStyle('InfoLabel', fontSize=8, fontName='Helvetica',
                                 textColor=colors.HexColor('#555555'))
    info_value = ParagraphStyle('InfoValue', fontSize=8, fontName='Helvetica-Bold',
                                 textColor=colors.HexColor('#1a3a5c'))
    note_style = ParagraphStyle('Note', fontSize=7, fontName='Helvetica',
                                 textColor=colors.HexColor('#888888'), alignment=TA_CENTER)

    nom_app = config.nom_app if config else "Association"
    logo_path = None
    if config and config.logo:
        try:
            p = config.logo.path
            if os.path.exists(p):
                logo_path = p
        except Exception:
            pass

    if logo_path:
        try:
            logo_img = Image(logo_path, width=3*cm, height=3*cm)
            header_data = [[logo_img, Paragraph(f"<b>{nom_app}</b>", title_style)]]
            col_widths = [3.5*cm, W-3.5*cm]
        except Exception:
            header_data = [[Paragraph(f"<b>{nom_app}</b>", title_style)]]
            col_widths = [W]
    else:
        header_data = [[Paragraph(f"<b>{nom_app}</b>", title_style)]]
        col_widths = [W]

    header_table = Table(header_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.15*cm))

    if tenant and association:
        assoc_info = [
            [Paragraph(f"<b>Association :</b> {association.nom}", info_value)],
        ]
        if association.adresse or (tenant and (tenant.quartier or tenant.commune or tenant.province)):
            adr_parts = []
            if association.adresse:
                adr_parts.append(association.adresse)
            else:
                if tenant.avenue:
                    adr_parts.append(f"Avenue {tenant.avenue}")
                if tenant.quartier:
                    adr_parts.append(f"Quartier {tenant.quartier}")
                if tenant.commune:
                    adr_parts.append(f"Commune {tenant.commune}")
                if tenant.province:
                    adr_parts.append(f"Province {tenant.province}")
            if adr_parts:
                assoc_info.append([Paragraph(f"<b>Adresse :</b> {', '.join(adr_parts)}", info_label)])
        if tenant and tenant.telephone:
            assoc_info.append([Paragraph(f"<b>Tél :</b> {tenant.telephone}", info_label)])
        if tenant and tenant.email:
            assoc_info.append([Paragraph(f"<b>Email :</b> {tenant.email}", info_label)])
        assoc_table = Table(assoc_info, colWidths=[W])
        assoc_table.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(assoc_table)
        elements.append(Spacer(1, 0.15*cm))

    elements.append(Paragraph("DEMANDE DE CREDIT", form_title))
    elements.append(Spacer(1, 0.15*cm))

    empty_line = "___________________________________________"
    empty_line_short = "____________________"

    info_data = [
        [Paragraph("Nom :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Prénom :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Carte d'identité :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Téléphone :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Date de la demande :", label_style), Paragraph("____ / ____ / ________", value_style)],
    ]

    info_table = Table(info_data, colWidths=[4.5*cm, W-4.5*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.2*cm))

    # Section: Informations du crédit
    elements.append(Paragraph(
        "Informations du crédit demandé",
        ParagraphStyle('Section', fontSize=10, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#1a3a5c'), alignment=TA_LEFT,
                        spaceBefore=2, spaceAfter=4)
    ))

    credit_data = [
        [Paragraph("Montant demandé :", label_style), Paragraph(empty_line, value_style),
         Paragraph("Devise :", label_style), Paragraph(empty_line_short, value_style)],
    ]
    credit_table = Table(credit_data, colWidths=[3.5*cm, 5*cm, 2.5*cm, 5.5*cm])
    credit_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (2, 0), colors.HexColor('#555555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#dddddd')),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor('#dddddd')),
        ('LINEBELOW', (2, 0), (2, 0), 0.5, colors.HexColor('#dddddd')),
        ('LINEBELOW', (3, 0), (3, 0), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(credit_table)
    elements.append(Spacer(1, 0.15*cm))

    duree_data = [
        [Paragraph("Durée de remboursement souhaitée :", label_style),
         Paragraph(empty_line, value_style)],
    ]
    duree_table = Table(duree_data, colWidths=[6.5*cm, W-6.5*cm])
    duree_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.HexColor('#555555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (1, 0), 0.5, colors.HexColor('#dddddd')),
    ]))
    elements.append(duree_table)
    elements.append(Spacer(1, 0.15*cm))

    # Motif
    elements.append(Paragraph(
        "Motif de la demande :",
        ParagraphStyle('MotifLabel', fontSize=9, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#555555'), alignment=TA_LEFT,
                        spaceBefore=2, spaceAfter=2)
    ))
    motif_lines = [
        [Paragraph("_________________________________________________________________________________",
                   ParagraphStyle('ML', fontSize=9, textColor=colors.HexColor('#cccccc')))],
        [Paragraph("_________________________________________________________________________________",
                   ParagraphStyle('ML', fontSize=9, textColor=colors.HexColor('#cccccc')))],
        [Paragraph("_________________________________________________________________________________",
                   ParagraphStyle('ML', fontSize=9, textColor=colors.HexColor('#cccccc')))],
    ]
    motif_table = Table(motif_lines, colWidths=[W])
    motif_table.setStyle(TableStyle([
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(motif_table)
    elements.append(Spacer(1, 0.25*cm))

    # Engagement
    elements.append(Paragraph(
        "Engagement du membre",
        ParagraphStyle('EngTitle', fontSize=9, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                        spaceBefore=2, spaceAfter=4)
    ))
    engagement = (
        "Je soussigné(e) déclare avoir pris connaissance des conditions générales d'octroi de crédit "
        "de l'association et m'engage à rembourser le montant sollicité ainsi que les intérêts y afférents "
        "selon les modalités convenues."
    )
    elements.append(Paragraph(engagement, ParagraphStyle('EngText', fontSize=8, fontName='Helvetica',
                                textColor=colors.HexColor('#333333'), alignment=TA_LEFT,
                                leading=12, spaceAfter=6)))
    elements.append(Spacer(1, 0.15*cm))

    # Signatures
    elements.append(Paragraph(
        "Fait à _________________, le ____ / ____ / ________",
        ParagraphStyle('SignLoc', fontSize=9, fontName='Helvetica',
                        textColor=colors.HexColor('#333333'), alignment=TA_CENTER, spaceAfter=4)
    ))
    elements.append(Spacer(1, 0.4*cm))

    sign_data = [
        [Paragraph("Signature du membre", note_style),
         Paragraph("Le Président de l'association", note_style)],
    ]
    sign_table = Table([
        [Paragraph("", ParagraphStyle('SignLine', fontSize=9, spaceBefore=15)),
         Paragraph("", ParagraphStyle('SignLine', fontSize=9, spaceBefore=15))],
        [Paragraph("Signature du membre", note_style),
         Paragraph("Le Président de l'association", note_style)],
    ], colWidths=[W/2, W/2])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(sign_table)

    if tenant:
        elements.append(Spacer(1, 0.2*cm))
        contact = []
        if tenant.telephone:
            contact.append(f"Tél: {tenant.telephone}")
        if tenant.email:
            contact.append(f"Email: {tenant.email}")
        if contact:
            elements.append(Paragraph(
                " | ".join(contact),
                ParagraphStyle('Contact', fontSize=7, fontName='Helvetica',
                                textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
            ))

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
