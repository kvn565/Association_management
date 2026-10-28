from io import BytesIO
from django.db.models import Sum
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from .models import CasAssistance
from twiyungunganye.models import CotisationImprevu


def get_tenant(request=None):
    if request:
        return getattr(request, 'tenant', None)
    return None


def generer_rapport_assistance_pdf(mois, annee, tenant=None):

    # ===== Nom fichier =====
    nom_fichier = "rapport_assistance.pdf"

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # ===== Filtrage =====
    qs_cas = CasAssistance.objects.all()
    qs_imprevus = CotisationImprevu.objects.filter(statut='PAYE')
    if tenant:
        qs_cas = qs_cas.filter(tenant=tenant)
        qs_imprevus = qs_imprevus.filter(tenant=tenant)

    if mois == 0:
        assistances = qs_cas.filter(date_assistance__year=annee)
        titre = f"Rapport Assistance Annuel {annee}"
    else:
        assistances = qs_cas.filter(
            date_assistance__month=mois,
            date_assistance__year=annee
        )
        titre = f"Rapport Assistance {mois}/{annee}"

    # ===== Titre =====
    elements.append(Paragraph(titre, styles['Title']))

    # ===== Tableau =====
    data = [["Membre", "Montant", "Motif", "Date"]]

    for a in assistances:
        data.append([
            str(a.membre),
            str(a.montant),
            a.motif,
            a.date_assistance.strftime("%d/%m/%Y")
        ])

    table = Table(data)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 20))

    # ===== Totaux =====
    total_assistance = assistances.aggregate(
        Sum('montant')
    )['montant__sum'] or 0

    total_imprevus = qs_imprevus.aggregate(
        Sum('montant')
    )['montant__sum'] or 0

    solde = total_imprevus - total_assistance

    elements.append(Paragraph(f"Total Imprévus : {total_imprevus}", styles['Normal']))
    elements.append(Paragraph(f"Total Assistance : {total_assistance}", styles['Normal']))
    elements.append(Paragraph(f"Solde Restant : {solde}", styles['Normal']))

    doc.build(elements)

    return buffer
