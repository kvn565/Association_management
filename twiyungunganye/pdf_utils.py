from io import BytesIO
from django.http import HttpResponse


def make_pdf_response(filename, pagesize, build_elements_func, *args, **kwargs):
    """Génère un PDF en mémoire et le retourne en téléchargement (sans sauvegarde disque)."""
    buffer = BytesIO()
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=pagesize)
    elements = []

    build_elements_func(doc, elements, *args, **kwargs)

    doc.build(elements)

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def save_pdf_and_respond(buffer, filename):
    """Retourne le PDF en téléchargement (sans sauvegarde disque)."""
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
