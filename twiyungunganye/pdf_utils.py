from io import BytesIO
from urllib.parse import quote
from django.http import HttpResponse


def dispo_fichier(nom_fichier):
    """En-tête Content-Disposition avec support des accents (RFC 5987)."""
    nom_ascii = nom_fichier.encode('ascii', 'ignore').decode('ascii') or 'fichier'
    return f"attachment; filename=\"{nom_ascii}\"; filename*=UTF-8''{quote(nom_fichier)}"


def make_pdf_response(filename, pagesize, build_elements_func, *args, **kwargs):
    """Génère un PDF en mémoire et le retourne en téléchargement (sans sauvegarde disque)."""
    buffer = BytesIO()
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=pagesize)
    elements = []

    build_elements_func(doc, elements, *args, **kwargs)

    doc.build(elements)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = dispo_fichier(filename)
    return response


def save_pdf_and_respond(buffer, filename):
    """Retourne le PDF en téléchargement (sans sauvegarde disque)."""
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = dispo_fichier(filename)
    return response
