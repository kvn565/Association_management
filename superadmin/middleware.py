import logging
from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone

logger = logging.getLogger('superadmin.multi_tenant')

SUPERADMIN_DOMAIN = getattr(settings, 'SUPERADMIN_DOMAIN', 'superadmin')


def _get_subdomain(request):
    host = request.get_host().split(':')[0]
    parts = host.split('.')
    if len(parts) >= 3:
        subdomain = parts[0]
        main_domain = '.'.join(parts[1:])
        return subdomain.lower(), main_domain
    if len(parts) == 2 and parts[0] not in ('www', 'localhost', 'superadmin'):
        subdomain = parts[0]
        return subdomain.lower(), parts[1]
    return None, host


def _get_client_ip(request):
    """Adresse IP du client.

    On ne fait pas confiance à X-Forwarded-For par défaut : l'application est
    servie en local par waitress, sans proxy de confiance. Le header n'est
    utilisé que si l'option DJANGO_TRUST_PROXY est explicitement activée.
    """
    if getattr(settings, 'TRUST_PROXY_HEADERS', False):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _is_exempt_path(path, prefixes):
    return any(path.startswith(p) for p in prefixes)


class TenantMiddleware(MiddlewareMixin):
    EXEMPT_PATHS = [
        '/superadmin/',
        '/admin/',
        '/static/',
        '/media/',
        '/favicon.ico',
    ]

    def process_request(self, request):
        request.tenant = None
        request.is_superadmin = False

        subdomain, domain = _get_subdomain(request)

        if subdomain is None or subdomain in ('www', SUPERADMIN_DOMAIN, ''):
            if request.user.is_authenticated and request.user.is_superuser:
                request.is_superadmin = True
            # Le flag is_superadmin sera affiné après la vérification du user.tenant
        else:
            from .models import Tenant
            try:
                tenant = Tenant.objects.get(sous_domaine=subdomain, actif=True)
                request.tenant = tenant
            except Tenant.DoesNotExist:
                pass

        # Fallback : si l'utilisateur connecté a un tenant, l'utiliser
        if request.tenant is None and request.user.is_authenticated:
            user_tenant = getattr(request.user, 'tenant', None)
            if user_tenant:
                request.tenant = user_tenant

        # Affiner is_superadmin après avoir défini le tenant
        if request.user.is_authenticated:
            if request.user.is_superuser:
                request.is_superadmin = True
            elif not request.is_superadmin:
                request.is_superadmin = False

        return None


class LicenceMiddleware(MiddlewareMixin):
    EXEMPT_PATHS = [
        '/superadmin/',
        '/accounts/',
        '/admin/',
        '/static/',
        '/media/',
        '/superadmin/licence-expiree/',
        '/logout/',
        '/setup/',
        '/favicon.ico',
    ]

    def process_request(self, request):
        if _is_exempt_path(request.path, self.EXEMPT_PATHS):
            return None

        if request.is_superadmin:
            return None

        if not request.user.is_authenticated:
            return None

        if request.user.is_superuser:
            return None

        tenant = getattr(request, 'tenant', None)
        if tenant is None:
            return redirect(settings.LOGIN_URL)

        try:
            cle_active = tenant.cle_active
            if cle_active is None:
                from .models import CleActivation
                n_cles = tenant.cles_activation.count()
                if n_cles == 0:
                    logger.warning(
                        f"[LICENCE] Tenant '{tenant.sous_domaine}' sans clé — "
                        f"création auto essai 14j"
                    )
                    cle_active = CleActivation.creer_essai(
                        tenant, cree_par='middleware-auto'
                    )
                    request.cle_active = cle_active
                    request.jours_restants = cle_active.jours_restants
                    request._licence_warning = (
                        f"Essai gratuit 14 jours démarré automatiquement. "
                        f"Expire le {cle_active.date_fin.strftime('%d/%m/%Y')}."
                    )
                    return None
                else:
                    request.session['licence_tenant'] = tenant.nom
                    cle = tenant.cles_activation.order_by('-date_fin').first()
                    request.session['licence_statut'] = cle.statut if cle else 'AUCUNE'
                    expired_url = getattr(settings, 'LICENCE_EXPIRED_URL', '/superadmin/licence-expiree/')
                    return redirect(expired_url)

            request.cle_active = cle_active
            request.jours_restants = cle_active.jours_restants

            if request.jours_restants <= 7:
                request._licence_warning = (
                    f"Votre licence expire dans {request.jours_restants} jour(s) "
                    f"(le {cle_active.date_fin.strftime('%d/%m/%Y')})."
                )

        except Exception as e:
            logger.error(f"[LICENCE] Erreur middleware: {e}", exc_info=True)

        return None


def _parse_user_agent(user_agent):
    """Parse User-Agent string to extract device, brand, browser, OS"""
    if not user_agent:
        return {'appareil': 'Inconnu', 'marque': '', 'navigateur': '', 'systeme': ''}

    ua = user_agent.lower()
    result = {'appareil': 'Desktop', 'marque': '', 'navigateur': '', 'systeme': ''}

    # Appareil
    if 'mobile' in ua or 'android' in ua and 'mobile' in ua:
        result['appareil'] = 'Mobile'
    elif 'tablet' in ua or 'ipad' in ua or 'tab' in ua:
        result['appareil'] = 'Tablette'
    elif 'iphone' in ua or 'ipod' in ua:
        result['appareil'] = 'Mobile'
    elif 'android' in ua:
        result['appareil'] = 'Mobile'

    # Marque (pour mobiles)
    marques = [
        'samsung', 'huawei', 'xiaomi', 'tecno', 'infinix', 'itel',
        'nokia', 'lg', 'sony', 'oppo', 'vivo', 'realme', 'oneplus',
        'google', 'motorola', 'honor', 'asus', 'lenovo', 'hp',
        'dell', 'acer', 'apple', 'blackberry',
    ]
    for m in marques:
        if m in ua:
            result['marque'] = m.capitalize()
            if m == 'apple':
                if 'iphone' in ua:
                    result['marque'] = 'Apple (iPhone)'
                elif 'ipad' in ua:
                    result['marque'] = 'Apple (iPad)'
                elif 'macintosh' in ua:
                    result['marque'] = 'Apple (Mac)'
            break

    # Navigateur
    if 'edge' in ua or 'edg/' in ua:
        result['navigateur'] = 'Edge'
    elif 'opr/' in ua or 'opera' in ua:
        result['navigateur'] = 'Opera'
    elif 'chrome/' in ua and 'chromium' not in ua:
        result['navigateur'] = 'Chrome'
    elif 'firefox/' in ua:
        result['navigateur'] = 'Firefox'
    elif 'safari/' in ua and 'chrome' not in ua:
        result['navigateur'] = 'Safari'

    # Système d'exploitation
    if 'windows' in ua:
        result['systeme'] = 'Windows'
    elif 'mac os' in ua or 'macintosh' in ua:
        result['systeme'] = 'macOS'
    elif 'linux' in ua and 'android' not in ua:
        result['systeme'] = 'Linux'
    elif 'android' in ua:
        result['systeme'] = 'Android'
    elif 'iphone' in ua or 'ipad' in ua:
        result['systeme'] = 'iOS'

    return result


class ConnexionAuditMiddleware(MiddlewareMixin):
    """Enregistre la connexion des utilisateurs authentifiés (une fois par session)."""

    EXEMPT_PATHS = ['/static/', '/media/', '/favicon.ico']

    def process_request(self, request):
        if _is_exempt_path(request.path, self.EXEMPT_PATHS):
            return None

        if not request.user.is_authenticated:
            return None

        # Évite d'écrire une ligne en base à chaque requête HTTP.
        try:
            if request.session.get('connexion_auditee'):
                return None
        except AttributeError:
            return None

        try:
            from .models import ConnexionAudit

            ua_string = request.META.get('HTTP_USER_AGENT', '')
            info = _parse_user_agent(ua_string)

            ConnexionAudit.objects.create(
                utilisateur_nom=request.user.get_full_name() or str(request.user),
                utilisateur_carte=getattr(request.user, 'carte_identite', ''),
                tenant=getattr(request, 'tenant', None),
                ip_address=_get_client_ip(request),
                user_agent=ua_string[:500],
                appareil=info['appareil'],
                marque=info['marque'],
                navigateur=info['navigateur'],
                systeme=info['systeme'],
                chemin=request.path,
            )
            request.session['connexion_auditee'] = True
        except Exception as e:
            logger.error(f"[AUDIT] Erreur enregistrement connexion: {e}")
