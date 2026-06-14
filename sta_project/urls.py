from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),
    # Sitio web público
    path('', include('apps.web.urls', namespace='web')),
    # Panel de gestión interno
    path('gestion/', include('apps.accounts.urls', namespace='accounts')),
    path('gestion/dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('gestion/contabilidad/', include('apps.contabilidad.urls', namespace='contabilidad')),
    path('gestion/tesoreria/', include('apps.tesoreria.urls', namespace='tesoreria')),
    path('gestion/clientes/', include('apps.clientes.urls', namespace='clientes')),
    path('gestion/proveedores/', include('apps.proveedores.urls', namespace='proveedores')),
    path('gestion/proyectos/', include('apps.proyectos.urls', namespace='proyectos')),
    path('gestion/rrhh/', include('apps.rrhh.urls', namespace='rrhh')),
    path('gestion/tributario/', include('apps.tributario.urls', namespace='tributario')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

