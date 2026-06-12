from .models import Tenant, ConfigurationApp
from django.conf import settings


def tenant_context(request):
    ctx = {
        'tenant': getattr(request, 'tenant', None),
        'is_superadmin': getattr(request, 'is_superadmin', False),
        'cle_active': getattr(request, 'cle_active', None),
        'jours_restants': getattr(request, 'jours_restants', 0),
        'licence_warning': getattr(request, '_licence_warning', None),
        'site_domain': getattr(settings, 'SITE_DOMAIN', ''),
    }
    if ctx['tenant']:
        ctx['association'] = ctx['tenant']

    config = ConfigurationApp.objects.first()
    ctx['config_app'] = config

    return ctx
