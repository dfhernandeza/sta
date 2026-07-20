from django.db import models
from apps.core.models import TimeStampedModel


class ConfiguracionSitio(TimeStampedModel):
    nombre_sitio = models.CharField(max_length=150, default='STA Muebles y Terminaciones', verbose_name='Nombre del sitio')
    razon_social = models.CharField(
        max_length=200, default='SOLUCIONES TERMO ACUSTICAS SPA',
        verbose_name='Razón social',
    )
    rut_empresa = models.CharField(
        max_length=15, default='76.471.912-3', verbose_name='RUT empresa',
    )
    giro_empresa = models.CharField(
        max_length=250,
        default='Soluciones termoacústicas, muebles y terminaciones',
        verbose_name='Giro',
    )
    direccion_empresa = models.CharField(
        max_length=300, default='SIMPSON 46, CHILLÁN',
        verbose_name='Dirección empresa',
    )
    representante_legal = models.CharField(
        max_length=200, blank=True, verbose_name='Representante legal',
    )
    firma_representante_legal = models.ImageField(
        upload_to='web/empresa/firmas/', null=True, blank=True,
        verbose_name='Firma del representante legal',
        help_text='Se recomienda una imagen PNG con fondo transparente.',
    )
    meta_descripcion = models.TextField(
        blank=True,
        default='STA Muebles y Terminaciones - Calidad en cada detalle',
        verbose_name='Meta descripción global'
    )
    logo = models.ImageField(upload_to='web/logo/', null=True, blank=True, verbose_name='Logo')
    descripcion_footer = models.TextField(
        blank=True,
        default='Muebles y Terminaciones de calidad para proyectos residenciales y comerciales en Chile.',
        verbose_name='Descripción del footer'
    )
    telefono = models.CharField(max_length=50, blank=True, default='+56 X XXXX XXXX', verbose_name='Teléfono')
    email = models.EmailField(blank=True, default='contacto@stamuebles.cl', verbose_name='Email')
    ubicacion = models.CharField(max_length=200, blank=True, default='Chile', verbose_name='Ubicación')
    horario_atencion = models.CharField(max_length=150, blank=True, default='Lun-Vie: 8:30-18:00', verbose_name='Horario de atención')
    facebook = models.URLField(blank=True, verbose_name='Facebook')
    instagram = models.URLField(blank=True, verbose_name='Instagram')
    linkedin = models.URLField(blank=True, verbose_name='LinkedIn')
    whatsapp = models.CharField(max_length=50, blank=True, verbose_name='WhatsApp')

    class Meta:
        verbose_name = 'Configuración del Sitio'
        verbose_name_plural = 'Configuración del Sitio'

    def __str__(self):
        return self.nombre_sitio

    @classmethod
    def actual(cls):
        return cls.objects.order_by('id').first()


class PaginaWeb(TimeStampedModel):
    PAGINA_CHOICES = [
        ('inicio', 'Inicio'),
        ('proyectos', 'Proyectos'),
        ('servicios', 'Servicios'),
        ('nosotros', 'Nosotros'),
        ('contacto', 'Contacto'),
        ('contacto_gracias', 'Contacto - Gracias'),
    ]

    slug = models.CharField(max_length=50, choices=PAGINA_CHOICES, unique=True, verbose_name='Página')
    nombre_url = models.CharField(max_length=80, blank=True, help_text='Ej: web:index', verbose_name='Nombre URL')
    titulo_navegador = models.CharField(max_length=200, blank=True, verbose_name='Título del navegador')
    meta_descripcion = models.TextField(blank=True, verbose_name='Meta descripción')
    titulo_menu = models.CharField(max_length=80, blank=True, verbose_name='Texto de menú')
    titulo_encabezado = models.CharField(max_length=200, blank=True, verbose_name='Título de encabezado')
    subtitulo_encabezado = models.TextField(blank=True, verbose_name='Subtítulo de encabezado')
    imagen_encabezado = models.ImageField(upload_to='web/paginas/', null=True, blank=True, verbose_name='Imagen de encabezado')
    mostrar_en_menu = models.BooleanField(default=True, verbose_name='Mostrar en menú')
    mostrar_en_footer = models.BooleanField(default=True, verbose_name='Mostrar en footer')
    activo = models.BooleanField(default=True, verbose_name='Activa')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Página Web'
        verbose_name_plural = 'Páginas Web'
        ordering = ['orden', 'slug']

    def __str__(self):
        return self.titulo_menu or self.get_slug_display()


class SeccionWeb(TimeStampedModel):
    pagina = models.ForeignKey(PaginaWeb, related_name='secciones', on_delete=models.CASCADE, verbose_name='Página')
    clave = models.SlugField(
        max_length=80,
        help_text='Identificador usado por la plantilla. Ej: hero, estadisticas, cta',
        verbose_name='Clave'
    )
    titulo = models.CharField(max_length=200, blank=True, verbose_name='Título')
    subtitulo = models.TextField(blank=True, verbose_name='Subtítulo')
    contenido = models.TextField(blank=True, verbose_name='Contenido')
    imagen = models.ImageField(upload_to='web/secciones/', null=True, blank=True, verbose_name='Imagen')
    icono = models.CharField(max_length=50, blank=True, help_text='Ej: bi-tools', verbose_name='Icono Bootstrap')
    texto_boton = models.CharField(max_length=80, blank=True, verbose_name='Texto botón')
    url_boton = models.CharField(max_length=200, blank=True, help_text='Ej: /contacto/', verbose_name='URL botón')
    texto_boton_secundario = models.CharField(max_length=80, blank=True, verbose_name='Texto botón secundario')
    url_boton_secundario = models.CharField(max_length=200, blank=True, help_text='Ej: /proyectos/', verbose_name='URL botón secundario')
    activo = models.BooleanField(default=True, verbose_name='Activa')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Sección Web'
        verbose_name_plural = 'Secciones Web'
        ordering = ['pagina', 'orden', 'clave']
        unique_together = ('pagina', 'clave')

    def __str__(self):
        return f'{self.pagina} - {self.titulo or self.clave}'


class Portada(SeccionWeb):
    class Meta:
        proxy = True
        verbose_name = 'Portada principal'
        verbose_name_plural = 'Portada principal'


class ItemSeccionWeb(TimeStampedModel):
    seccion = models.ForeignKey(SeccionWeb, related_name='items', on_delete=models.CASCADE, verbose_name='Sección')
    titulo = models.CharField(max_length=200, blank=True, verbose_name='Título')
    subtitulo = models.CharField(max_length=200, blank=True, verbose_name='Subtítulo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    valor = models.CharField(max_length=50, blank=True, verbose_name='Valor destacado')
    icono = models.CharField(max_length=50, blank=True, help_text='Ej: bi-award', verbose_name='Icono Bootstrap')
    imagen = models.ImageField(upload_to='web/items/', null=True, blank=True, verbose_name='Imagen')
    enlace = models.CharField(max_length=200, blank=True, verbose_name='Enlace')
    texto_enlace = models.CharField(max_length=80, blank=True, verbose_name='Texto enlace')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Ítem de Sección'
        verbose_name_plural = 'Ítems de Sección'
        ordering = ['seccion', 'orden', 'id']

    def __str__(self):
        return self.titulo or self.valor or f'Ítem #{self.pk}'


class ProyectoPortafolio(TimeStampedModel):
    CATEGORIA_CHOICES = [
        ('muebles', 'Muebles'),
        ('terminaciones', 'Terminaciones'),
        ('cocinas', 'Cocinas'),
        ('closets', 'Closets'),
        ('oficinas', 'Oficinas'),
        ('otro', 'Otro'),
    ]

    titulo = models.CharField(max_length=200, verbose_name='Título')
    descripcion = models.TextField(verbose_name='Descripción')
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='otro', verbose_name='Categoría')
    imagen_principal = models.ImageField(upload_to='portafolio/', verbose_name='Imagen Principal')
    destacado = models.BooleanField(default=False, verbose_name='Destacado en inicio')
    activo = models.BooleanField(default=True, verbose_name='Visible en sitio')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden de aparición')
    proyecto_interno = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto interno relacionado'
    )

    class Meta:
        verbose_name = 'Proyecto Portafolio'
        verbose_name_plural = 'Proyectos Portafolio'
        ordering = ['orden', '-creado_en']

    def __str__(self):
        return self.titulo


class ProyectoImagen(TimeStampedModel):
    proyecto = models.ForeignKey(
        ProyectoPortafolio,
        related_name='galeria',
        on_delete=models.CASCADE,
        verbose_name='Proyecto'
    )
    imagen = models.ImageField(upload_to='portafolio/galeria/', verbose_name='Imagen')
    titulo = models.CharField(max_length=150, blank=True, verbose_name='Título')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    activo = models.BooleanField(default=True, verbose_name='Visible en sitio')

    class Meta:
        verbose_name = 'Imagen de Proyecto'
        verbose_name_plural = 'Galería de Proyectos'
        ordering = ['orden', 'id']

    def __str__(self):
        return self.titulo or f'Imagen de {self.proyecto}'


class Servicio(TimeStampedModel):
    titulo = models.CharField(max_length=200, verbose_name='Título')
    descripcion = models.TextField(verbose_name='Descripción')
    icono = models.CharField(
        max_length=50, blank=True,
        verbose_name='Icono Bootstrap Icons',
        help_text='Ej: bi-tools, bi-house, bi-brush'
    )
    imagen = models.ImageField(upload_to='servicios/', null=True, blank=True, verbose_name='Imagen')
    activo = models.BooleanField(default=True, verbose_name='Visible en sitio')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Servicio'
        verbose_name_plural = 'Servicios'
        ordering = ['orden']

    def __str__(self):
        return self.titulo


class MiembroEquipo(TimeStampedModel):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    cargo = models.CharField(max_length=100, verbose_name='Cargo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción breve')
    foto = models.ImageField(upload_to='equipo/', null=True, blank=True, verbose_name='Foto')
    linkedin = models.URLField(blank=True, verbose_name='LinkedIn')
    activo = models.BooleanField(default=True, verbose_name='Visible en sitio')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')

    class Meta:
        verbose_name = 'Miembro del Equipo'
        verbose_name_plural = 'Equipo'
        ordering = ['orden']

    def __str__(self):
        return f'{self.nombre} - {self.cargo}'


class ContactoMensaje(TimeStampedModel):
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    empresa = models.CharField(max_length=200, blank=True, verbose_name='Empresa')
    email = models.EmailField(verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    mensaje = models.TextField(verbose_name='Mensaje')
    leido = models.BooleanField(default=False, verbose_name='Leído')
    respondido = models.BooleanField(default=False, verbose_name='Respondido')

    class Meta:
        verbose_name = 'Mensaje de Contacto'
        verbose_name_plural = 'Mensajes de Contacto'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nombre} ({self.email}) - {self.creado_en.strftime("%d/%m/%Y")}'
