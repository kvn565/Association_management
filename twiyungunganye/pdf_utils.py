import os
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from reportlab.lib.pagesizes import A4, landscape


def make_pdf_response(filename, pagesize, build_elements_func, *args, **kwargs):
    """Génère un PDF, le sauvegarde sur le serveur (remplace l'ancien) et retourne une réponse.

    build_elements_func(doc, elements, *args, **kwargs) doit remplir la liste `elements`.
    """
    buffer = BytesIO()
    from reportlab.platypus import SimpleDocTemplate
    doc = SimpleDocTemplate(buffer, pagesize=pagesize)
    elements = []

    build_elements_func(doc, elements, *args, **kwargs)

    doc.build(elements)

    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'rapports')
    os.makedirs(pdf_dir, exist_ok=True)
    filepath = os.path.join(pdf_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(buffer.getvalue())

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def save_pdf_and_respond(buffer, filename):
    """Sauvegarde le contenu du buffer sur le serveur (remplace l'ancien) et retourne une réponse."""
    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'rapports')
    os.makedirs(pdf_dir, exist_ok=True)
    filepath = os.path.join(pdf_dir, filename)
    with open(filepath, 'wb') as f:
        f.write(buffer.getvalue())

    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
