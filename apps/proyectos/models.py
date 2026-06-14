from django.db import models
from apps.core.models import TimeStampedModel


class Proyecto(TimeStampedModel):
    ESTADO_CHOICES = [
        ('negociacion', 'En Negociación'),
        ('adjudicado', 'Adjudicado'),
        ('en_ejecucion', 'En Ejecución'),
        ('terminado', 'Terminado'),
        ('cancelado', 'Cancelado'),
    ]

    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=300, verbose_name='Nombre del Proyecto')
    cliente = models.ForeignKey(
        'clientes.Cliente', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='proyectos', verbose_name='Cliente'
    )
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='negociacion', verbose_name='Estado')
    fecha_inicio = models.DateField(null=True, blank=True, verbose_name='Fecha de Inicio')
    fecha_termino = models.DateField(null=True, blank=True, verbose_name='Fecha de Término')
    monto_contrato = models.DecimalField(
        max_digits=15, decimal_places=2, default=0, verbose_name='Monto Contrato'
    )
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    direccion_obra = models.CharField(max_length=300, blank=True, verbose_name='Dirección de la Obra')
    destacado = models.BooleanField(default=False, verbose_name='Destacado en portafolio')
    mostrar_en_web = models.BooleanField(default=False, verbose_name='Mostrar en sitio web')

    class Meta:
        verbose_name = 'Proyecto'
        verbose_name_plural = 'Proyectos'
        ordering = ['-fecha_inicio', 'nombre']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    @property
    def total_costos(self):
        from django.db.models import Sum, F, ExpressionWrapper, DecimalField
        from apps.proveedores.models import DetalleFacturaRecibida
        result = DetalleFacturaRecibida.objects.filter(
            factura__proyecto=self
        ).exclude(
            factura__estado='anulada'
        ).annotate(
            subtotal=ExpressionWrapper(F('cantidad') * F('precio_unitario'), output_field=DecimalField(max_digits=15, decimal_places=2))
        ).aggregate(t=Sum('subtotal'))['t']
        return result or 0

    @property
    def rentabilidad(self):
        return self.monto_contrato - self.total_costos

    @property
    def porcentaje_rentabilidad(self):
        if self.monto_contrato:
            return round((self.rentabilidad / self.monto_contrato) * 100, 1)
        return 0


class CostoProyecto(TimeStampedModel):
    TIPO_CHOICES = [
        ('material', 'Material'),
        ('mano_obra', 'Mano de Obra'),
        ('subcontrato', 'Subcontrato'),
        ('equipo', 'Equipos/Herramientas'),
        ('transporte', 'Transporte'),
        ('otro', 'Otro'),
    ]

    proyecto = models.ForeignKey(
        Proyecto, on_delete=models.CASCADE,
        related_name='costos', verbose_name='Proyecto'
    )
    fecha = models.DateField(verbose_name='Fecha')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='otro', verbose_name='Tipo')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta contable'
    )
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )
    proveedor = models.ForeignKey(
        'proveedores.Proveedor', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proveedor'
    )
    factura = models.ForeignKey(
        'proveedores.FacturaRecibida', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Factura relacionada'
    )

    class Meta:
        verbose_name = 'Costo de Proyecto'
        verbose_name_plural = 'Costos de Proyectos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.proyecto.codigo} | {self.descripcion[:50]} - ${self.monto:,.0f}'


class Presupuesto(TimeStampedModel):
    proyecto = models.ForeignKey(
        Proyecto, on_delete=models.CASCADE,
        related_name='presupuestos', verbose_name='Proyecto'
    )
    item = models.CharField(max_length=200, verbose_name='Ítem')
    tipo = models.CharField(max_length=20, choices=CostoProyecto.TIPO_CHOICES, default='otro', verbose_name='Tipo')
    monto_presupuestado = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto Presupuestado')
    monto_real = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Monto Real')

    class Meta:
        verbose_name = 'Presupuesto'
        verbose_name_plural = 'Presupuestos'
        ordering = ['proyecto', 'item']

    def __str__(self):
        return f'{self.proyecto.codigo} | {self.item}'

    @property
    def variacion(self):
        return self.monto_real - self.monto_presupuestado
