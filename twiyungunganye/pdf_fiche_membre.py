import io
import os
from datetime import datetime
from decimal import Decimal

import qrcode
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from .models import Membre, Association
from .pdf_utils import save_pdf_and_respond


def is_admin_or_gestionnaire(user):
    return user.is_authenticated and (user.is_admin or user.is_admin)


def get_tenant(request):
    return getattr(request, 'tenant', None)


def get_devise(request):
    tenant = get_tenant(request)
    assoc = Association.get_association(tenant)
    return assoc.devise if assoc and assoc.devise else 'FBU'


def _get_logo_path(association):
    if association and association.logo:
        path = association.logo.path
        if os.path.exists(path):
            return path
    return None


def _generate_qr_code(association, tenant):
    """Generate a QR code image with all association information."""
    if not tenant and not association:
        return None
    lines = []
    if association:
        lines.append(f"Association: {association.nom}")
        if association.sigle:
            lines.append(f"Sigle: {association.sigle}")
    if tenant:
        if tenant.nif:
            lines.append(f"NIF: {tenant.nif}")
        parts = []
        for f in ('province', 'commune', 'quartier', 'avenue', 'numero'):
            v = getattr(tenant, f, None)
            if v:
                parts.append(str(v))
        if parts:
            lines.append(f"Adresse: {', '.join(parts)}")
        if tenant.boite_postale:
            lines.append(f"B.P.: {tenant.boite_postale}")
        if tenant.telephone:
            lines.append(f"Tél.: {tenant.telephone}")
        if tenant.email:
            lines.append(f"Email: {tenant.email}")
    if not lines:
        return None
    content = '\n'.join(lines)
    try:
        img = qrcode.make(content, box_size=4, border=1)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf
    except Exception:
        return None


@login_required
@user_passes_test(is_admin_or_gestionnaire)
def fiche_membre_pdf(request, pk):
    membre = Membre.objects.select_related('tenant').get(pk=pk)
    tenant = get_tenant(request)
    if tenant and membre.tenant_id and membre.tenant_id != tenant.pk:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès refusé")

    association = Association.get_association(tenant)
    devise = get_devise(request)
    dirigeant = Membre.objects.filter(tenant=tenant, is_admin=True).first()

    buffer = io.BytesIO()
    filename = f"Fiche_Membre_{membre.nom}_{membre.prenom}.pdf"

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=2*cm, rightMargin=2*cm
    )
    elements = []

    W = 17*cm

    # ── Styles ──
    styles = getSampleStyleSheet()

    nom_assoc = association.nom if association else "Association"

    title_style = ParagraphStyle('TitleAssoc', fontSize=16, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                  spaceAfter=4)
    subtitle_style = ParagraphStyle('SubAssoc', fontSize=9, fontName='Helvetica',
                                     textColor=colors.HexColor('#555555'), alignment=TA_CENTER,
                                     spaceAfter=2)
    fiche_title = ParagraphStyle('FicheTitle', fontSize=13, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                  spaceBefore=6, spaceAfter=10,
                                  borderPadding=4,
                                  backColor=colors.HexColor('#eef4fa'))
    label_style = ParagraphStyle('Label', fontSize=9, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#333333'))
    value_style = ParagraphStyle('Value', fontSize=11, fontName='Helvetica',
                                  textColor=colors.HexColor('#111111'))
    field_label = ParagraphStyle('FieldLabel', fontSize=9, fontName='Helvetica-Bold',
                                  textColor=colors.HexColor('#555555'))
    empty_style = ParagraphStyle('Empty', fontSize=10, fontName='Helvetica',
                                  textColor=colors.HexColor('#999999'))
    note_style = ParagraphStyle('Note', fontSize=7.5, fontName='Helvetica',
                                 textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
    sign_style = ParagraphStyle('Sign', fontSize=9, fontName='Helvetica',
                                 textColor=colors.HexColor('#333333'))

    # ── En-tête : logo + nom association + QR code ──
    logo_path = _get_logo_path(association)

    # Texte au centre
    assoc_text = Paragraph(
        f"<b>{nom_assoc}</b><br/>"
        f"<font size='8'>{association.sigle or ''}</font>",
        title_style
    )

    # QR code
    qr_buf = _generate_qr_code(association, tenant)
    qr_cell = []
    if qr_buf:
        try:
            qr_img = Image(qr_buf, width=2.5*cm, height=2.5*cm)
            qr_cell = [qr_img]
        except Exception:
            qr_cell = [Paragraph("", title_style)]
    else:
        qr_cell = [Paragraph("", title_style)]

    if logo_path:
        try:
            logo_img = Image(logo_path, width=3*cm, height=3*cm)
            header_data = [[logo_img, assoc_text, qr_cell[0]]]
            col_widths = [3.5*cm, W-6*cm, 3.5*cm]
        except Exception:
            header_data = [[Paragraph(f"<b>{nom_assoc}</b>", title_style)]]
            col_widths = [W]
    else:
        header_data = [[Paragraph(f"<b>{nom_assoc}</b>", title_style)]]
        col_widths = [W]

    header_table = Table(header_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.3*cm))

    # ── Titre : FICHE DE MEMBRE ──
    elements.append(Paragraph("FICHE DE MEMBRE", fiche_title))
    elements.append(Spacer(1, 0.2*cm))

    # ── Date ──
    date_style = ParagraphStyle('DateStyle', fontSize=10, fontName='Helvetica',
                                 textColor=colors.HexColor('#333333'), alignment=TA_CENTER,
                                 spaceAfter=8)
    elements.append(Paragraph(
        "Date : ______ / ______ / ______",
        date_style
    ))
    elements.append(Spacer(1, 0.2*cm))

    # ── Informations personnelles avec photo ──
    info_style = TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#555555')),
        ('TEXTCOLOR', (1, 0), (1, -1), colors.HexColor('#111111')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
    ])

    # Photo du membre
    membre_photo_elem = None
    if membre.photo:
        try:
            photo_path = membre.photo.path
            if os.path.exists(photo_path):
                membre_photo_elem = Image(photo_path, width=3*cm, height=3*cm)
        except Exception:
            pass
    
    info_data = [
        [Paragraph("Nom & Prénom :", label_style), Paragraph(f"{membre.prenom} {membre.nom}", value_style)],
        [Paragraph("Carte d'identité :", label_style), Paragraph(str(membre.carte_identite), value_style)],
        [Paragraph("Téléphone :", label_style), Paragraph(membre.telephone or '__________________', value_style)],
        [Paragraph("Adresse :", label_style), Paragraph(membre.adresse or '__________________', value_style)],
        [Paragraph("Date d'inscription :", label_style), Paragraph(
            membre.date_inscription.strftime('%d/%m/%Y') if membre.date_inscription else '__________________', value_style)],
    ]

    info_table = Table(info_data, colWidths=[4*cm, W-8*cm])
    info_table.setStyle(info_style)

    if membre_photo_elem:
        photo_cell = [[membre_photo_elem]]
        photo_table = Table(photo_cell, colWidths=[4*cm])
        photo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        combined = Table([[photo_table, info_table]], colWidths=[4*cm, W-4*cm])
        combined.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 5),
            ('RIGHTPADDING', (0, 0), (0, 0), 10),
        ]))
        elements.append(combined)
    else:
        elements.append(info_table)

    # Filtrer les cotisations et crédits du mois courant
    now = datetime.now()
    mois_courant = now.month
    annee_courante = now.year
    cotisation_mois = membre.cotisations.filter(mois=mois_courant, annee=annee_courante, statut='PAYE').aggregate(
        Sum('montant'))['montant__sum'] or Decimal('0.000')
    social_mois = membre.cotisations_imprevus.filter(mois=mois_courant, annee=annee_courante, statut='PAYE').aggregate(
        Sum('montant'))['montant__sum'] or Decimal('0.000')
    credit_mois = membre.credits.filter(
        date_accord__month=mois_courant, date_accord__year=annee_courante,
        statut__in=['APPROUVE', 'EN_COURS', 'REMBOURSE']
    ).aggregate(Sum('montant_accorde'))['montant_accorde__sum'] or Decimal('0.000')

    elements.append(Spacer(1, 0.4*cm))

    # ── Section : Situation du mois ──
    elements.append(Paragraph(f"Situation du mois de {now.strftime('%B %Y').capitalize()}",
                              ParagraphStyle('MoisTitle', fontSize=11, fontName='Helvetica-Bold',
                                             textColor=colors.HexColor('#1a3a5c'), alignment=TA_CENTER,
                                             spaceBefore=4, spaceAfter=6,
                                             backColor=colors.HexColor('#eef4fa'))))
    elements.append(Spacer(1, 0.2*cm))

    border_color = colors.HexColor('#cccccc')
    fill_color = colors.HexColor('#f9fafb')

    situ_data = [
        [Paragraph("<b>Rubrique</b>", label_style),
         Paragraph(f"<b>Montant ({devise})</b>", label_style)],
        [Paragraph("Cotisation du mois", field_label),
         Paragraph(f"{cotisation_mois:,.3f}" if cotisation_mois > 0 else "_____________", value_style)],
        [Paragraph("Cotisation sociale (imprévu)", field_label),
         Paragraph(f"{social_mois:,.3f}" if social_mois > 0 else "_____________", value_style)],
        [Paragraph("Crédit reçu du mois", field_label),
         Paragraph(f"{credit_mois:,.3f}" if credit_mois > 0 else "_____________", value_style)],
    ]

    situ_table = Table(situ_data, colWidths=[8*cm, 5*cm])
    situ_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('BACKGROUND', (0, 1), (-1, -1), fill_color),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
    ]))
    elements.append(situ_table)

    elements.append(Spacer(1, 0.8*cm))

    # ── Signature ──
    sign_data = [
        [Paragraph("Fait à _________________, le {0}/{1}/{2}".format(
            now.day, now.month, now.year), note_style)],
    ]
    sign_table = Table(sign_data, colWidths=[W])
    sign_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(sign_table)
    elements.append(Spacer(1, 1.5*cm))

    sign_row = [
        [Paragraph("", sign_style),
         Paragraph("", sign_style)],
        [Paragraph("Signature du membre", note_style),
         Paragraph("Signature du président de l'association", note_style)],
    ]
    sign_table2 = Table(sign_row, colWidths=[W/2, W/2])
    sign_table2.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, colors.HexColor('#aaaaaa')),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(sign_table2)

    elements.append(Spacer(1, 0.3*cm))

    # ── Nom du dirigeant ──
    if dirigeant:
        elements.append(Paragraph(
            f"Nom du président de l'association : <b>{dirigeant.prenom} {dirigeant.nom}</b>",
            ParagraphStyle('DirName', fontSize=9, fontName='Helvetica',
                           textColor=colors.HexColor('#555555'), alignment=TA_CENTER))
        )

    doc.build(elements)
    return save_pdf_and_respond(buffer, filename)
