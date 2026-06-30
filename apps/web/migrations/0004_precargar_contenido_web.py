from django.db import migrations


def crear_contenido(apps, schema_editor):
    ConfiguracionSitio = apps.get_model('web', 'ConfiguracionSitio')
    PaginaWeb = apps.get_model('web', 'PaginaWeb')
    SeccionWeb = apps.get_model('web', 'SeccionWeb')
    ItemSeccionWeb = apps.get_model('web', 'ItemSeccionWeb')

    ConfiguracionSitio.objects.get_or_create(
        pk=1,
        defaults={
            'nombre_sitio': 'STA Muebles y Terminaciones',
            'meta_descripcion': 'STA Muebles y Terminaciones - Calidad en cada detalle',
            'descripcion_footer': 'Muebles y Terminaciones de calidad para proyectos residenciales y comerciales en Chile.',
            'telefono': '+56 X XXXX XXXX',
            'email': 'contacto@stamuebles.cl',
            'ubicacion': 'Chile',
            'horario_atencion': 'Lun-Vie: 8:30-18:00',
        },
    )

    paginas = {
        'inicio': {
            'nombre_url': 'web:index',
            'titulo_navegador': 'STA Muebles y Terminaciones - Inicio',
            'titulo_menu': 'Inicio',
            'orden': 1,
        },
        'proyectos': {
            'nombre_url': 'web:proyectos',
            'titulo_navegador': 'Proyectos | STA Muebles y Terminaciones',
            'titulo_menu': 'Proyectos',
            'titulo_encabezado': 'Nuestros Proyectos',
            'subtitulo_encabezado': 'Trabajos que reflejan nuestra pasión por la calidad y el detalle',
            'orden': 2,
        },
        'servicios': {
            'nombre_url': 'web:servicios',
            'titulo_navegador': 'Servicios | STA Muebles y Terminaciones',
            'titulo_menu': 'Servicios',
            'titulo_encabezado': 'Nuestros Servicios',
            'subtitulo_encabezado': 'Soluciones integrales en muebles y terminaciones para cada proyecto',
            'orden': 3,
        },
        'nosotros': {
            'nombre_url': 'web:nosotros',
            'titulo_navegador': 'Nosotros | STA Muebles y Terminaciones',
            'titulo_menu': 'Nosotros',
            'titulo_encabezado': 'Quiénes Somos',
            'subtitulo_encabezado': 'Más de 15 años fabricando muebles y terminaciones de calidad en Chile',
            'orden': 4,
        },
        'contacto': {
            'nombre_url': 'web:contacto',
            'titulo_navegador': 'Contacto | STA Muebles y Terminaciones',
            'titulo_menu': 'Cotizar',
            'titulo_encabezado': 'Contáctanos',
            'subtitulo_encabezado': 'Cuéntanos tu proyecto y te enviamos una cotización sin compromiso',
            'orden': 5,
        },
        'contacto_gracias': {
            'nombre_url': 'web:contacto_gracias',
            'titulo_navegador': 'Mensaje Enviado | STA Muebles y Terminaciones',
            'titulo_menu': 'Gracias',
            'mostrar_en_menu': False,
            'mostrar_en_footer': False,
            'orden': 6,
        },
    }

    paginas_creadas = {}
    for slug, defaults in paginas.items():
        pagina, _ = PaginaWeb.objects.get_or_create(slug=slug, defaults=defaults)
        paginas_creadas[slug] = pagina

    def seccion(slug_pagina, clave, **defaults):
        obj, _ = SeccionWeb.objects.get_or_create(
            pagina=paginas_creadas[slug_pagina],
            clave=clave,
            defaults=defaults,
        )
        return obj

    def item(sec, orden, **defaults):
        ItemSeccionWeb.objects.get_or_create(
            seccion=sec,
            orden=orden,
            titulo=defaults.get('titulo', ''),
            defaults=defaults,
        )

    hero = seccion(
        'inicio',
        'hero',
        titulo='Muebles y Terminaciones\nde alta calidad',
        subtitulo='Diseñamos y fabricamos muebles a medida, cocinas, closets y terminaciones para proyectos residenciales y comerciales en todo Chile.',
        texto_boton='Ver Proyectos',
        url_boton='/proyectos/',
        texto_boton_secundario='Cotizar ahora',
        url_boton_secundario='/contacto/',
        orden=1,
    )
    estadisticas = seccion('inicio', 'estadisticas', titulo='Estadísticas', orden=2)
    item(estadisticas, 1, titulo='Proyectos Realizados', valor='+500')
    item(estadisticas, 2, titulo='Años de Experiencia', valor='+15')
    item(estadisticas, 3, titulo='Clientes Satisfechos', valor='+300')
    item(estadisticas, 4, titulo='Comprometidos', valor='100%')
    seccion(
        'inicio',
        'servicios',
        titulo='Nuestros Servicios',
        subtitulo='Soluciones integrales en muebles y terminaciones',
        texto_boton='Ver todos los servicios',
        url_boton='/servicios/',
        orden=3,
    )
    seccion(
        'inicio',
        'proyectos_destacados',
        titulo='Proyectos Destacados',
        subtitulo='Una selección de nuestros mejores trabajos',
        texto_boton='Ver todos los proyectos',
        url_boton='/proyectos/',
        orden=4,
    )
    seccion(
        'inicio',
        'cta',
        titulo='¿Tienes un proyecto en mente?',
        subtitulo='Cuéntanos tu idea y te ayudamos a hacerla realidad con calidad y precisión.',
        texto_boton='Solicitar cotización gratis',
        url_boton='/contacto/',
        orden=5,
    )

    seccion(
        'proyectos',
        'cta',
        titulo='¿Te gustaría tener un proyecto como estos?',
        texto_boton='Contáctanos',
        url_boton='/contacto/',
        orden=1,
    )

    beneficios = seccion('servicios', 'beneficios', titulo='¿Por qué elegirnos?', orden=1)
    item(beneficios, 1, titulo='Calidad Superior', descripcion='Utilizamos materiales de primera calidad para garantizar durabilidad y estética en cada producto.', icono='bi-award')
    item(beneficios, 2, titulo='Medida Exacta', descripcion='Cada proyecto es diseñado y fabricado según las medidas y requerimientos específicos del cliente.', icono='bi-rulers')
    item(beneficios, 3, titulo='Soporte Total', descripcion='Acompañamos cada proyecto desde el diseño hasta la instalación y post-venta.', icono='bi-headset')
    seccion(
        'servicios',
        'cta',
        titulo='¿Listo para comenzar tu proyecto?',
        texto_boton='Solicitar cotización',
        url_boton='/contacto/',
        orden=2,
    )

    historia = seccion(
        'nosotros',
        'historia',
        titulo='Nuestra Historia',
        contenido='STA Muebles y Terminaciones nació con la misión de ofrecer soluciones de alta calidad en fabricación de muebles a medida y terminaciones de interiores para proyectos residenciales y comerciales en todo Chile.\n\nCon más de 15 años de experiencia, hemos consolidado un equipo de profesionales dedicados a transformar cada idea en un producto de excelencia, combinando diseño, funcionalidad y durabilidad.',
        orden=1,
    )
    item(historia, 1, titulo='Años de experiencia', valor='+15')
    item(historia, 2, titulo='Proyectos terminados', valor='+500')
    valores = seccion('nosotros', 'valores', titulo='Nuestros Valores', orden=2)
    item(valores, 1, titulo='Calidad', descripcion='Compromiso con la excelencia en cada producto y servicio.', icono='bi-patch-check')
    item(valores, 2, titulo='Puntualidad', descripcion='Cumplimos los plazos acordados con nuestros clientes.', icono='bi-clock-history')
    item(valores, 3, titulo='Innovación', descripcion='Incorporamos diseños modernos y técnicas actualizadas.', icono='bi-lightbulb')
    item(valores, 4, titulo='Confianza', descripcion='Relaciones transparentes y honestas con clientes y proveedores.', icono='bi-handshake')
    seccion('nosotros', 'equipo', titulo='Nuestro Equipo', subtitulo='Las personas detrás de cada proyecto', orden=3)
    seccion(
        'nosotros',
        'cta',
        titulo='¿Quieres trabajar con nosotros?',
        texto_boton='Contáctanos',
        url_boton='/contacto/',
        orden=4,
    )

    info_contacto = seccion('contacto', 'info_contacto', titulo='Información de contacto', orden=1)
    item(info_contacto, 1, titulo='Teléfono', descripcion='+56 X XXXX XXXX', icono='bi-telephone-fill')
    item(info_contacto, 2, titulo='Email', descripcion='contacto@stamuebles.cl', icono='bi-envelope-fill')
    item(info_contacto, 3, titulo='Ubicación', descripcion='Chile', icono='bi-geo-alt-fill')
    item(info_contacto, 4, titulo='Horario', descripcion='Lun-Vie: 8:30-18:00', icono='bi-clock-fill')
    seccion('contacto', 'formulario', titulo='Envíanos un mensaje', orden=2)

    seccion(
        'contacto_gracias',
        'mensaje',
        titulo='¡Mensaje enviado!',
        subtitulo='Gracias por contactarnos. Hemos recibido tu mensaje y nos pondremos en contacto contigo a la brevedad posible.',
        texto_boton='Inicio',
        url_boton='/',
        texto_boton_secundario='Ver proyectos',
        url_boton_secundario='/proyectos/',
        orden=1,
    )


def borrar_contenido(apps, schema_editor):
    ConfiguracionSitio = apps.get_model('web', 'ConfiguracionSitio')
    PaginaWeb = apps.get_model('web', 'PaginaWeb')
    ConfiguracionSitio.objects.filter(pk=1).delete()
    PaginaWeb.objects.filter(slug__in=[
        'inicio',
        'proyectos',
        'servicios',
        'nosotros',
        'contacto',
        'contacto_gracias',
    ]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('web', '0003_configuracionsitio_paginaweb_seccionweb_and_more'),
    ]

    operations = [
        migrations.RunPython(crear_contenido, borrar_contenido),
    ]
