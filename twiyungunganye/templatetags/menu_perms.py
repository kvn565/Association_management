import json
from django import template
from django.conf import settings

register = template.Library()

MENU_PERMISSIONS = {
    'dashboard': 'Tableau de bord',
    'notifications': 'Notifications',
    'membres': 'Membres (liste, ajout, modification)',
    'cotisations': 'Cotisations régulières',
    'cotisations_imprevus': 'Cotisations imprévus (gestion)',
    'mes_cotisations_imprevus': 'Mes cotisations imprévus',
    'credits': 'Crédits (liste, demande, approbation)',
    'remboursements': 'Remboursements',
    'interets': 'Intérêts',
    'penalites': 'Pénalités',
    'assistances': "Cas d'assistance",
    'suggestions': 'Suggestions',
    'rapports': 'Rapports & exports',
    'association': 'Mon association (profil)',
    'modifier_profil': 'Modifier mon profil',
    'licence': 'Licence',
    'reinitialiser': 'Réinitialiser la base',
    'gestion_groupes': "Gestion des groupes d'accès",
}


def _can_access(user, menu_code):
    """Returns True if user can access the given menu."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return False

    groupe = getattr(user, 'groupe_acces', None)
    if groupe is not None:
        return groupe.has_permission(menu_code)

    if menu_code in ('licence', 'reinitialiser', 'gestion_groupes'):
        return bool(user.is_admin)
    if menu_code in ('membres', 'cotisations_imprevus', 'remboursements', 'interets', 'penalites', 'rapports'):
        return bool(user.is_admin)
    return True


@register.filter
def has_menu_perm(user, menu_code):
    return _can_access(user, menu_code)


@register.simple_tag(takes_context=True)
def menu_visible(context, menu_code):
    user = context.get('user')
    if not user or not user.is_authenticated:
        return False
    tenant = context.get('tenant')
    is_superadmin = context.get('is_superadmin', False)
    if is_superadmin and not tenant:
        return False
    return _can_access(user, menu_code)


@register.simple_tag
def get_menu_permission_label(menu_code):
    return MENU_PERMISSIONS.get(menu_code, menu_code)


@register.filter
def user_can_manage_access(user):
    return user.is_authenticated and user.is_admin


@register.filter
def replace_annee(value):
    """Remplace {annee} par l'année courante dans une chaîne."""
    from datetime import date
    if value:
        return value.replace('{annee}', str(date.today().year))
    return value

@register.filter
def get_slide_image(slide_num, config):
    """Retourne l'URL de l'image téléchargée pour un slide donné (1-indexé)."""
    if not config:
        return None
    field_name = f'slide_image_{slide_num}'
    img_field = getattr(config, field_name, None)
    if img_field:
        try:
            return img_field.url
        except Exception:
            pass
    return None

@register.filter
def json_parse(value):
    """Parse une chaîne JSON en liste Python."""
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []

@register.filter
def json_attr(obj, key):
    """Accède à une propriété d'un objet JSON/dict."""
    if isinstance(obj, dict):
        return obj.get(key, '')
    return ''
