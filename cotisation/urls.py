"""
URL configuration for cotisation project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from superadmin import views as superadmin_views

# L'interface d'administration Django est réservée aux superutilisateurs
# (les comptes `is_staff` non superusers n'y ont plus accès).
admin.site.has_permission = lambda request: (
    request.user.is_active and request.user.is_superuser
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path(f'{settings.SUPERADMIN_LOGIN_PATH}/', superadmin_views.superadmin_login, name='superadmin_login'),
    path('superadmin/', include('superadmin.urls', namespace='superadmin')),
    path('setup/', superadmin_views.inscription_chef, name='inscription_chef'),
    path('', include('twiyungunganye.urls')),
    path('cas-assistance/', include('cas_assistance.urls', namespace='cas_assistance')),
]

# L'application est servie en local (waitress) sans serveur web externe :
# les médias doivent rester accessibles même avec DEBUG=False.
urlpatterns += [
    re_path(
        r'^%s(?P<path>.*)$' % settings.MEDIA_URL.lstrip('/'),
        serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]

# Les fichiers statiques sont servis par WhiteNoise ; on garde le fallback
# Django uniquement en mode DEBUG.
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
