"""Central definition of menu permission codes.

Every menu item in the sidebar has a unique code. These codes are stored
in GroupeAcces.permissions to control which menus a group can access.

Usage:
    from .menu_permissions import MENU_PERMISSIONS, user_has_menu_access
"""

MENU_PERMISSIONS = {
    'dashboard': 'Tableau de bord',
    'notifications': 'Notifications',
    'membres': 'Membres (liste, ajout, modification)',
    'cotisations': 'Cotisations régulières',
    'cotisations_imprevus': 'Cotisations imprévus (gestion)',
    'mes_cotisations_imprevus': 'Mes cotisations imprévus',
    'credits': 'Crédits (liste, demande, approbation)',
    'remboursements': 'Remboursements',
    'interets': 'Intérêts (calcul mensuel)',
    'penalites': 'Pénalités cotisations impayées',
    'assistances': "Cas d'assistance",
    'suggestions': 'Suggestions',
    'rapports': 'Rapports & exports',
    'association': 'Mon association (profil)',
    'modifier_profil': 'Modifier mon profil',
    'licence': 'Licence',
    'reinitialiser': 'Réinitialiser la base',
    'gestion_groupes': "Gestion des groupes d'accès",
}


def user_has_menu_access(user, menu_code, tenant=None):
    """Returns True if user can access the given menu.

    If the user belongs to a GroupeAcces, the group's permissions are used.
    Otherwise, falls back to default role-based access (is_admin / is_gestionnaire).
    """
    if not user.is_authenticated:
        return False
    groupe = getattr(user, 'groupe_acces', None)
    if groupe is not None:
        return groupe.has_permission(menu_code)
    if user.is_superuser:
        return True
    if menu_code in ('licence', 'reinitialiser', 'gestion_groupes'):
        return bool(user.is_admin)
    if menu_code in ('membres', 'cotisations_imprevus', 'remboursements', 'rapports'):
        return bool(user.is_admin)
    return True
