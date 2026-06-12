from .menu_permissions import MENU_PERMISSIONS, user_has_menu_access
from .models import Association


def menu_permissions_context(request):
    """Adds menu permission data to template context."""
    user = getattr(request, 'user', None)
    tenant = getattr(request, 'tenant', None)
    is_superadmin = getattr(request, 'is_superadmin', False)

    def can_access(code):
        if not user or not user.is_authenticated:
            return False
        return user_has_menu_access(user, code, tenant=tenant)

    # Devise dynamique depuis la configuration de l'association
    devise = "FBU"
    if tenant:
        assoc = Association.get_association(tenant)
        if assoc and assoc.devise:
            devise = assoc.devise

    return {
        'menu_permissions': MENU_PERMISSIONS,
        'can_access': can_access,
        'devise': devise,
    }
