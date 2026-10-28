from django import template

register = template.Library()


@register.filter
def dictkey(d, key):
    """Accède à une clé de dictionnaire avec une variable comme clé"""
    if isinstance(d, dict):
        return d.get(key)
    try:
        return d[int(key)]
    except (ValueError, TypeError, IndexError, KeyError):
        return None


@register.filter
def make_key(mois, annee):
    """Construit une clé 'mois-annee' pour lookup dans les dictionnaires participants"""
    return f'{mois}-{annee}'

