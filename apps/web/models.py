from django.db import models
from apps.core.models import TimeStampedModel


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
