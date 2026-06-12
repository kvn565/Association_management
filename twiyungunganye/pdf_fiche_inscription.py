import io
import os
from datetime import datetime
from decimal import Decimal

import qrcode
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from .models import Membre, Association
from .pdf_utils import save_pdf_and_respond


def get_devise(request=None, tenant=None):
    from .views import get_tenant as gt
    if request:
        tenant = gt(request)
    assoc = Association.get_association(tenant)
    return assoc.devise if assoc and assoc.devise else 'FBU'


def fiche_inscription_pdf(request):
    """Génère une fiche d'inscription avec les informations de l'association sélectionnée."""
    from superadmin.models import Tenant, ConfigurationApp

    tenant_id = request.GET.get('tenant')
    tenant = None
    association = None

    if tenant_id:
        tenant = get_object_or_404(Tenant, pk=tenant_id, actif=True)
        association = Association.get_association(tenant)

    config = ConfigurationApp.objects.first()

    buffer = io.BytesIO()
    filename = "Fiche_Inscription.pdf"

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
    fiche_title = ParagraphStyle('FicheTitle', fontSize=11, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                  spaceBefore=3, spaceAfter=6,
                                  borderPadding=3, backColor=colors.HexColor('#eef4fa'))
    label_style = ParagraphStyle('Label', fontSize=9, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#333333'))
    value_style = ParagraphStyle('Value', fontSize=10, fontName='Helvetica',
                                  textColor=colors.HexColor('#111111'))
    field_empty = ParagraphStyle('Empty', fontSize=9, fontName='Helvetica',
                                  textColor=colors.HexColor('#999999'))
    info_label = ParagraphStyle('InfoLabel', fontSize=8, fontName='Helvetica',
                                 textColor=colors.HexColor('#555555'))
    info_value = ParagraphStyle('InfoValue', fontSize=8, fontName='Helvetica-Bold',
                                 textColor=colors.HexColor('#1a3a5c'))
    note_style = ParagraphStyle('Note', fontSize=7, fontName='Helvetica',
                                 textColor=colors.HexColor('#888888'), alignment=TA_CENTER)

    # -- En-tête --
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

    # -- Infos association --
    if tenant and association:
        assoc_info = [
            [Paragraph(f"<b>Association :</b> {association.nom}", info_value)],
        ]
        if association.adresse or tenant.quartier or tenant.commune or tenant.province:
            adr_parts = []
            if association.adresse:
                adr_parts.append(association.adresse)
            elif tenant.avenue:
                adr_parts.append(f"Avenue {tenant.avenue}")
            if tenant.quartier:
                adr_parts.append(f"Quartier {tenant.quartier}")
            if tenant.commune:
                adr_parts.append(f"Commune {tenant.commune}")
            if tenant.province:
                adr_parts.append(f"Province {tenant.province}")
            if adr_parts:
                assoc_info.append([Paragraph(f"<b>Adresse :</b> {', '.join(adr_parts)}", info_label)])
        if tenant.telephone:
            assoc_info.append([Paragraph(f"<b>Tél :</b> {tenant.telephone}", info_label)])
        if tenant.email:
            assoc_info.append([Paragraph(f"<b>Email :</b> {tenant.email}", info_label)])
        assoc_table = Table(assoc_info, colWidths=[W])
        assoc_table.setStyle(TableStyle([
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elements.append(assoc_table)
        elements.append(Spacer(1, 0.15*cm))

    elements.append(Paragraph("FICHE D'INSCRIPTION", fiche_title))
    elements.append(Spacer(1, 0.1*cm))

    elements.append(Paragraph(
        "Date : ______ / ______ / ______",
        ParagraphStyle('DateStyle', fontSize=9, fontName='Helvetica',
                        textColor=colors.HexColor('#333333'), alignment=TA_CENTER, spaceAfter=4)
    ))
    elements.append(Spacer(1, 0.15*cm))

    # -- Section photo --
    photo_placeholder = Table(
        [[Paragraph("PHOTO", ParagraphStyle('PhotoLabel', fontSize=7, fontName='Helvetica',
                      textColor=colors.HexColor('#999999'), alignment=TA_CENTER))]],
        colWidths=[3.5*cm]
    )
    photo_placeholder.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cccccc')),
        ('MINHEIGHT', (0, 0), (-1, -1), 3*cm),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))

    # -- Informations personnelles (champs vides) --
    empty_line = "___________________________________________"
    info_data = [
        [Paragraph("Nom :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Prénom :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Carte d'identité :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Date de naissance :", label_style), Paragraph("____ / ____ / ________", value_style)],
        [Paragraph("Téléphone :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Email :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Adresse :", label_style), Paragraph(empty_line, value_style)],
        [Paragraph("Profession :", label_style), Paragraph(empty_line, value_style)],
    ]

    info_table = Table(info_data, colWidths=[3.5*cm, W-3.5*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ]))

    combined = Table([[photo_placeholder, info_table]], colWidths=[3.5*cm, W-3.5*cm])
    combined.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 3),
        ('RIGHTPADDING', (0, 0), (0, 0), 5),
    ]))
    elements.append(combined)
    elements.append(Spacer(1, 0.2*cm))

    # -- Engagement --
    elements.append(Paragraph(
        "Engagement du membre",
        ParagraphStyle('EngTitle', fontSize=9, fontName='Helvetica-Bold',
                        textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                        spaceBefore=2, spaceAfter=4)
    ))
    engagement_text = (
        "Je soussigné(e) déclare avoir pris connaissance du règlement intérieur de l'association "
        "et m'engage à respecter les statuts, à payer mes cotisations mensuelles et à participer "
        "activement à la vie de l'association."
    )
    elements.append(Paragraph(engagement_text, ParagraphStyle('EngText', fontSize=8, fontName='Helvetica',
                                textColor=colors.HexColor('#333333'), alignment=TA_LEFT,
                                leading=12, spaceAfter=6)))
    elements.append(Spacer(1, 0.15*cm))

    # -- Signature --
    elements.append(Paragraph(
        "Fait à _________________, le ____ / ____ / ________",
        ParagraphStyle('SignLoc', fontSize=9, fontName='Helvetica',
                        textColor=colors.HexColor('#333333'), alignment=TA_CENTER, spaceAfter=4)
    ))
    elements.append(Spacer(1, 0.6*cm))

    sign_data = [
        [Paragraph("Signature du membre", note_style),
         Paragraph("Signature du président de l'association", note_style)],
    ]
    sign_table = Table([
        [Paragraph("", ParagraphStyle('SignLine', fontSize=9, spaceBefore=15)),
         Paragraph("", ParagraphStyle('SignLine', fontSize=9, spaceBefore=15))],
        [Paragraph("Signature du membre", note_style),
         Paragraph("Signature du président de l'association", note_style)],
    ], colWidths=[W/2, W/2])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(sign_table)

    # -- QR Code de l'association --
    if tenant:
        elements.append(Spacer(1, 0.2*cm))
        qr_data = tenant.nom
        if tenant.telephone:
            qr_data += f"\nTél: {tenant.telephone}"
        if tenant.email:
            qr_data += f"\nEmail: {tenant.email}"
        if tenant.sous_domaine:
            domain = getattr(settings, 'DOMAIN', 'example.com')
            qr_data += f"\nhttps://{tenant.sous_domaine}.{domain}"

        try:
            qr = qrcode.QRCode(box_size=2, border=1)
            qr.add_data(qr_data)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="#1a3a5c", back_color="white")
            buf = io.BytesIO()
            qr_img.save(buf, format='PNG')
            buf.seek(0)
            qr_pdf = Image(buf, width=2.5*cm, height=2.5*cm)

            qr_table = Table(
                [[qr_pdf]],
                colWidths=[W]
            )
            qr_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(qr_table)
            elements.append(Spacer(1, 0.1*cm))
            elements.append(Paragraph(
                f"Scannez pour plus d'informations sur {tenant.nom}",
                ParagraphStyle('QRLabel', fontSize=7, fontName='Helvetica',
                                textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
            ))
        except Exception:
            pass

    # -- Contact info --
    if config and (config.email_contact or config.telephone_contact):
        elements.append(Spacer(1, 0.2*cm))
        contact = []
        if config.email_contact:
            contact.append(f"Email : {config.email_contact}")
        if config.telephone_contact:
            contact.append(f"Tél : {config.telephone_contact}")
        elements.append(Paragraph(
            " | ".join(contact),
            ParagraphStyle('Contact', fontSize=7, fontName='Helvetica',
                            textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
        ))

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
