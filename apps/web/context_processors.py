from django.db import OperationalError, ProgrammingError

from .models import ConfiguracionSitio, PaginaWeb, Servicio


def sitio_web(request):
    try:
        paginas = list(PaginaWeb.objects.filter(activo=True).order_by('orden', 'slug'))
        return {
            'site_config': ConfiguracionSitio.actual(),
            'paginas_menu': [p for p in paginas if p.mostrar_en_menu],
            'paginas_footer': [p for p in paginas if p.mostrar_en_footer],
            'servicios_footer': Servicio.objects.filter(activo=True).order_by('orden')[:5],
        }
    except (OperationalError, ProgrammingError):
        return {
            'site_config': None,
            'paginas_menu': [],
            'paginas_footer': [],
            'servicios_footer': [],
        }
