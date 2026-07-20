from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ConfiguracionSitio,
    ContactoMensaje,
    ItemSeccionWeb,
    MiembroEquipo,
    PaginaWeb,
    Portada,
    ProyectoImagen,
    ProyectoPortafolio,
    SeccionWeb,
    Servicio,
)


class ImagenPreviewMixin:
    @admin.display(description='Vista previa')
    def vista_previa(self, obj):
        imagen = (
            getattr(obj, 'imagen', None)
            or getattr(obj, 'foto', None)
            or getattr(obj, 'logo', None)
            or getattr(obj, 'imagen_principal', None)
            or getattr(obj, 'imagen_encabezado', None)
        )

        if not imagen:
            return '-'

        return format_html(
            '<img src="{}" style="height: 70px; width: 100px; object-fit: cover; border-radius: 4px;" />',
            imagen.url,
        )


class ItemSeccionWebInline(ImagenPreviewMixin, admin.TabularInline):
    model = ItemSeccionWeb
    extra = 1
    fields = (
        'vista_previa',
        'titulo',
        'subtitulo',
        'descripcion',
        'valor',
        'icono',
        'imagen',
        'enlace',
        'texto_enlace',
        'orden',
        'activo',
    )
    readonly_fields = ('vista_previa',)
    ordering = ('orden', 'id')


class SeccionWebInline(ImagenPreviewMixin, admin.StackedInline):
    model = SeccionWeb
    extra = 0
    fields = (
        'clave',
        'titulo',
        'subtitulo',
        'contenido',
        'vista_previa',
        'imagen',
        'icono',
        'texto_boton',
        'url_boton',
        'texto_boton_secundario',
        'url_boton_secundario',
        'orden',
        'activo',
    )
    readonly_fields = ('vista_previa',)
    ordering = ('orden', 'clave')


@admin.register(ConfiguracionSitio)
class ConfiguracionSitioAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('nombre_sitio', 'email', 'telefono', 'actualizado_en')
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    fieldsets = (
        ('Identidad', {
            'fields': ('nombre_sitio', 'meta_descripcion', 'vista_previa', 'logo')
        }),
        ('Datos legales de la empresa', {
            'fields': ('razon_social', 'rut_empresa', 'giro_empresa', 'direccion_empresa')
        }),
        ('Contacto', {
            'fields': ('telefono', 'email', 'ubicacion', 'horario_atencion', 'whatsapp')
        }),
        ('Redes sociales', {
            'fields': ('facebook', 'instagram', 'linkedin')
        }),
        ('Footer', {
            'fields': ('descripcion_footer',)
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(PaginaWeb)
class PaginaWebAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('slug', 'titulo_menu', 'nombre_url', 'mostrar_en_menu', 'mostrar_en_footer', 'activo', 'orden')
    list_editable = ('mostrar_en_menu', 'mostrar_en_footer', 'activo', 'orden')
    list_filter = ('activo', 'mostrar_en_menu', 'mostrar_en_footer')
    search_fields = ('titulo_menu', 'titulo_encabezado', 'subtitulo_encabezado', 'nombre_url')
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('orden', 'slug')
    inlines = (SeccionWebInline,)
    fieldsets = (
        ('Página', {
            'fields': ('slug', 'nombre_url', 'activo', 'orden')
        }),
        ('SEO y menú', {
            'fields': ('titulo_navegador', 'meta_descripcion', 'titulo_menu', 'mostrar_en_menu', 'mostrar_en_footer')
        }),
        ('Encabezado', {
            'fields': ('titulo_encabezado', 'subtitulo_encabezado', 'vista_previa', 'imagen_encabezado')
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(SeccionWeb)
class SeccionWebAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('pagina', 'clave', 'titulo', 'activo', 'orden', 'actualizado_en')
    list_editable = ('activo', 'orden')
    list_filter = ('pagina', 'activo')
    search_fields = ('clave', 'titulo', 'subtitulo', 'contenido')
    autocomplete_fields = ('pagina',)
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('pagina', 'orden', 'clave')
    inlines = (ItemSeccionWebInline,)


@admin.register(Portada)
class PortadaAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    fieldsets = (
        ('Contenido principal', {
            'fields': ('titulo', 'subtitulo')
        }),
        ('Imagen grande de portada', {
            'fields': ('vista_previa_portada', 'imagen'),
            'description': (
                'Use una imagen horizontal de alta resolución. '
                'Recomendado: 1920 x 1080 px o superior.'
            ),
        }),
        ('Botones', {
            'fields': (
                'texto_boton',
                'url_boton',
                'texto_boton_secundario',
                'url_boton_secundario',
            )
        }),
        ('Publicación', {
            'fields': ('activo',)
        }),
    )
    readonly_fields = ('vista_previa_portada',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            pagina__slug='inicio',
            clave='hero',
        )

    @admin.display(description='Vista previa de portada')
    def vista_previa_portada(self, obj):
        if not obj or not obj.imagen:
            return 'Sin imagen. Se mostrará el fondo predeterminado.'

        return format_html(
            '<img src="{}" style="width: min(100%, 720px); height: 260px; '
            'object-fit: cover; border-radius: 4px;" />',
            obj.imagen.url,
        )

    def has_add_permission(self, request):
        return not SeccionWeb.objects.filter(
            pagina__slug='inicio',
            clave='hero',
        ).exists()

    def save_model(self, request, obj, form, change):
        pagina, _ = PaginaWeb.objects.get_or_create(
            slug='inicio',
            defaults={
                'nombre_url': 'web:index',
                'titulo_menu': 'Inicio',
                'titulo_navegador': 'STA Muebles y Terminaciones - Inicio',
                'orden': 0,
            },
        )
        obj.pagina = pagina
        obj.clave = 'hero'
        obj.orden = 0
        super().save_model(request, obj, form, change)


@admin.register(ItemSeccionWeb)
class ItemSeccionWebAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('seccion', 'titulo', 'valor', 'activo', 'orden', 'actualizado_en')
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'seccion__pagina', 'seccion')
    search_fields = ('titulo', 'subtitulo', 'descripcion', 'valor')
    autocomplete_fields = ('seccion',)
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('seccion', 'orden', 'id')


class ProyectoImagenInline(ImagenPreviewMixin, admin.TabularInline):
    model = ProyectoImagen
    extra = 1
    fields = ('vista_previa', 'imagen', 'titulo', 'descripcion', 'orden', 'activo')
    readonly_fields = ('vista_previa',)
    ordering = ('orden', 'id')


@admin.register(ProyectoPortafolio)
class ProyectoPortafolioAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = (
        'vista_previa',
        'titulo',
        'categoria',
        'destacado',
        'activo',
        'orden',
        'actualizado_en',
    )
    list_editable = ('destacado', 'activo', 'orden')
    list_filter = ('categoria', 'destacado', 'activo', 'creado_en')
    search_fields = ('titulo', 'descripcion', 'proyecto_interno__nombre')
    raw_id_fields = ('proyecto_interno',)
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('orden', '-creado_en')
    inlines = (ProyectoImagenInline,)
    fieldsets = (
        ('Contenido', {
            'fields': ('titulo', 'descripcion', 'categoria', 'proyecto_interno')
        }),
        ('Imágenes', {
            'fields': ('vista_previa', 'imagen_principal')
        }),
        ('Publicación', {
            'fields': ('destacado', 'activo', 'orden')
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ProyectoImagen)
class ProyectoImagenAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('vista_previa', 'proyecto', 'titulo', 'activo', 'orden', 'actualizado_en')
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'creado_en', 'proyecto__categoria')
    search_fields = ('titulo', 'descripcion', 'proyecto__titulo')
    autocomplete_fields = ('proyecto',)
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('proyecto', 'orden', 'id')


@admin.register(Servicio)
class ServicioAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('titulo', 'icono', 'activo', 'orden', 'actualizado_en')
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'creado_en')
    search_fields = ('titulo', 'descripcion', 'icono')
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('orden',)
    fieldsets = (
        ('Contenido', {
            'fields': ('titulo', 'descripcion', 'icono')
        }),
        ('Imagen', {
            'fields': ('vista_previa', 'imagen')
        }),
        ('Publicación', {
            'fields': ('activo', 'orden')
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(MiembroEquipo)
class MiembroEquipoAdmin(ImagenPreviewMixin, admin.ModelAdmin):
    list_display = ('vista_previa', 'nombre', 'cargo', 'activo', 'orden', 'actualizado_en')
    list_editable = ('activo', 'orden')
    list_filter = ('activo', 'creado_en')
    search_fields = ('nombre', 'cargo', 'descripcion')
    readonly_fields = ('vista_previa', 'creado_en', 'actualizado_en')
    ordering = ('orden',)
    fieldsets = (
        ('Contenido', {
            'fields': ('nombre', 'cargo', 'descripcion', 'linkedin')
        }),
        ('Foto', {
            'fields': ('vista_previa', 'foto')
        }),
        ('Publicación', {
            'fields': ('activo', 'orden')
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ContactoMensaje)
class ContactoMensajeAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'empresa', 'email', 'telefono', 'leido', 'respondido', 'creado_en')
    list_editable = ('leido', 'respondido')
    list_filter = ('leido', 'respondido', 'creado_en')
    search_fields = ('nombre', 'empresa', 'email', 'telefono', 'mensaje')
    readonly_fields = ('nombre', 'empresa', 'email', 'telefono', 'mensaje', 'creado_en', 'actualizado_en')
    ordering = ('-creado_en',)
    actions = ('marcar_como_leido', 'marcar_como_respondido')
    fieldsets = (
        ('Contacto', {
            'fields': ('nombre', 'empresa', 'email', 'telefono')
        }),
        ('Mensaje', {
            'fields': ('mensaje',)
        }),
        ('Seguimiento', {
            'fields': ('leido', 'respondido')
        }),
        ('Fechas', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    @admin.action(description='Marcar mensajes seleccionados como leídos')
    def marcar_como_leido(self, request, queryset):
        queryset.update(leido=True)

    @admin.action(description='Marcar mensajes seleccionados como respondidos')
    def marcar_como_respondido(self, request, queryset):
        queryset.update(leido=True, respondido=True)
