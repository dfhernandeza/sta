from django.contrib import admin

from .models import (
    AsientoContable,
    CentroCosto,
    ConfiguracionContable,
    LineaAsiento,
    PlanCuentas,
)


class LineaAsientoInline(admin.TabularInline):
    model = LineaAsiento
    fields = ('orden', 'cuenta', 'descripcion', 'centro_costo', 'debe', 'haber')
    autocomplete_fields = ('cuenta', 'centro_costo')
    extra = 1


@admin.register(PlanCuentas)
class PlanCuentasAdmin(admin.ModelAdmin):
    list_display = (
        'codigo',
        'nombre',
        'tipo',
        'nivel',
        'parent',
        'activa',
        'acepta_movimientos',
    )
    list_editable = ('activa', 'acepta_movimientos')
    list_filter = ('tipo', 'nivel', 'activa', 'acepta_movimientos')
    search_fields = ('codigo', 'nombre', 'descripcion', 'parent__codigo', 'parent__nombre')
    ordering = ('codigo',)
    autocomplete_fields = ('parent',)
    readonly_fields = ('creado_en', 'actualizado_en', 'ruta_completa')
    fieldsets = (
        ('Cuenta', {
            'fields': ('codigo', 'nombre', 'tipo', 'nivel', 'parent', 'descripcion'),
        }),
        ('Uso contable', {
            'fields': ('activa', 'acepta_movimientos', 'ruta_completa'),
        }),
        ('Auditoria', {
            'classes': ('collapse',),
            'fields': ('creado_en', 'actualizado_en'),
        }),
    )

    @admin.display(description='Ruta completa')
    def ruta_completa(self, obj):
        return obj.get_ruta() if obj.pk else ''


@admin.register(CentroCosto)
class CentroCostoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nombre', 'presupuesto_mensual', 'activo')
    list_editable = ('activo',)
    list_filter = ('activo',)
    search_fields = ('codigo', 'nombre', 'descripcion')
    ordering = ('codigo',)


@admin.register(ConfiguracionContable)
class ConfiguracionContableAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'cuentas_configuradas')
    autocomplete_fields = (
        'cuenta_cxc',
        'cuenta_cxp',
        'cuenta_documentos_por_pagar',
        'cuenta_iva_debito',
        'cuenta_iva_credito',
        'cuenta_ventas_default',
        'cuenta_compras_default',
        'cuenta_sueldos_operacional',
        'cuenta_sueldos_administrativo',
        'cuenta_impuestos_sii',
        'cuenta_ppm',
        'cuenta_afp_por_pagar',
        'cuenta_salud_por_pagar',
        'cuenta_seguro_cesantia_por_pagar',
        'cuenta_gasto_seguro_cesantia',
        'cuenta_sueldos_por_pagar',
        'cuenta_anticipos_trabajadores',
        'cuenta_anticipos_proveedores',
        'cuenta_patrimonio_apertura',
        'cuenta_honorarios_default',
        'cuenta_retenciones_honorarios',
    )
    fieldsets = (
        ('Clientes y proveedores', {
            'fields': (
                'cuenta_cxc',
                'cuenta_cxp',
                'cuenta_documentos_por_pagar',
                'cuenta_ventas_default',
                'cuenta_compras_default',
            ),
        }),
        ('Tributario', {
            'fields': (
                'cuenta_iva_debito',
                'cuenta_iva_credito',
                'cuenta_impuestos_sii',
                'cuenta_ppm',
            ),
        }),
        ('Remuneraciones y previsional', {
            'fields': (
                'cuenta_sueldos_operacional',
                'cuenta_sueldos_administrativo',
                'cuenta_afp_por_pagar',
                'cuenta_salud_por_pagar',
                'cuenta_seguro_cesantia_por_pagar',
                'cuenta_gasto_seguro_cesantia',
                'cuenta_sueldos_por_pagar',
            ),
        }),
        ('Anticipos y apertura', {
            'fields': (
                'cuenta_anticipos_trabajadores',
                'cuenta_anticipos_proveedores',
                'cuenta_patrimonio_apertura',
            ),
        }),
        ('Honorarios', {
            'fields': ('cuenta_honorarios_default', 'cuenta_retenciones_honorarios'),
        }),
    )

    @admin.display(description='Cuentas configuradas')
    def cuentas_configuradas(self, obj):
        total = len(self.autocomplete_fields)
        configuradas = sum(1 for field in self.autocomplete_fields if getattr(obj, field))
        return f'{configuradas}/{total}'

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not ConfiguracionContable.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AsientoContable)
class AsientoContableAdmin(admin.ModelAdmin):
    list_display = (
        'numero',
        'fecha',
        'descripcion',
        'tipo',
        'estado',
        'total_debe_admin',
        'total_haber_admin',
        'esta_cuadrado_admin',
    )
    list_filter = ('estado', 'tipo', 'fecha')
    search_fields = ('numero', 'descripcion')
    date_hierarchy = 'fecha'
    ordering = ('-fecha', '-numero')
    readonly_fields = (
        'numero',
        'total_debe_admin',
        'total_haber_admin',
        'esta_cuadrado_admin',
        'creado_en',
        'actualizado_en',
    )
    raw_id_fields = (
        'factura_emitida',
        'factura_recibida',
        'nota_credito_recibida',
        'boleta_honorarios',
        'movimiento_bancario',
        'rendicion_gastos',
        'remuneracion',
        'declaracion_previsional',
        'declaracion_iva',
        'formulario_f29',
        'ppm',
        'creado_por',
    )
    inlines = (LineaAsientoInline,)
    fieldsets = (
        ('Asiento', {
            'fields': ('numero', 'fecha', 'descripcion', 'tipo', 'estado', 'creado_por'),
        }),
        ('Totales', {
            'fields': ('total_debe_admin', 'total_haber_admin', 'esta_cuadrado_admin'),
        }),
        ('Documentos relacionados', {
            'classes': ('collapse',),
            'fields': (
                'factura_emitida',
                'factura_recibida',
                'nota_credito_recibida',
                'boleta_honorarios',
                'movimiento_bancario',
                'rendicion_gastos',
                'remuneracion',
                'declaracion_previsional',
                'declaracion_iva',
                'formulario_f29',
                'ppm',
            ),
        }),
        ('Auditoria', {
            'classes': ('collapse',),
            'fields': ('creado_en', 'actualizado_en'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('creado_por')

    @admin.display(description='Debe')
    def total_debe_admin(self, obj):
        return obj.total_debe

    @admin.display(description='Haber')
    def total_haber_admin(self, obj):
        return obj.total_haber

    @admin.display(boolean=True, description='Cuadrado')
    def esta_cuadrado_admin(self, obj):
        return obj.esta_cuadrado


@admin.register(LineaAsiento)
class LineaAsientoAdmin(admin.ModelAdmin):
    list_display = (
        'asiento',
        'fecha_asiento',
        'cuenta',
        'centro_costo',
        'descripcion',
        'debe',
        'haber',
        'orden',
    )
    list_filter = ('centro_costo', 'cuenta__tipo')
    search_fields = (
        'asiento__numero',
        'asiento__descripcion',
        'cuenta__codigo',
        'cuenta__nombre',
        'centro_costo__codigo',
        'centro_costo__nombre',
        'descripcion',
    )
    autocomplete_fields = ('asiento', 'cuenta', 'centro_costo')
    ordering = ('-asiento__fecha', 'asiento__numero', 'orden', 'pk')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('asiento', 'cuenta', 'centro_costo')

    @admin.display(ordering='asiento__fecha', description='Fecha')
    def fecha_asiento(self, obj):
        return obj.asiento.fecha
