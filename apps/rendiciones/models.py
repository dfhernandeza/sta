from django.db import models
from django.db.models import Max
from django.utils import timezone
from apps.core.models import TimeStampedModel
from apps.contabilidad.models import PlanCuentas, CentroCosto


class RendicionGastos(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado para revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('pagada', 'Pagada'),
    ]

    trabajador = models.ForeignKey(
        'rrhh.Trabajador', on_delete=models.PROTECT,
        related_name='rendiciones', verbose_name='Trabajador'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )
    fecha = models.DateField(verbose_name='Fecha de Rendición')
    motivo_del_gasto = models.CharField(max_length=300, verbose_name='Motivo del gasto')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado')
    correlativo_rendicion = models.PositiveIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Correlativo Rendición'
    )
    periodo_rendicion_mes = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Mes Rendición'
    )
    periodo_rendicion_anio = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Año Rendición'
    )

    class Meta:
        verbose_name = 'Rendición de Gastos'
        verbose_name_plural = 'Rendiciones de Gastos'
        ordering = ['-id']
        # Keep the existing DB table name to avoid data migration
        db_table = 'proveedores_rendiciongastos'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'periodo_rendicion_anio',
                    'periodo_rendicion_mes',
                    'correlativo_rendicion',
                ],
                name='uniq_rendicion_correlativo_mes',
            ),
        ]

    def __str__(self):
        return f'Rendición de {self.trabajador.nombre_completo} - {self.fecha}'

    @property
    def indice_rendicion(self):
        if not self.correlativo_rendicion or not self.periodo_rendicion_mes:
            return '—'
        return f'{self.correlativo_rendicion}/{self.periodo_rendicion_mes}'

    def _asignar_correlativo_rendicion(self):
        if self.correlativo_rendicion:
            return

        fecha_ingreso = timezone.localdate()
        self.periodo_rendicion_mes = fecha_ingreso.month
        self.periodo_rendicion_anio = fecha_ingreso.year

        ultimo = RendicionGastos.objects.filter(
            periodo_rendicion_anio=self.periodo_rendicion_anio,
            periodo_rendicion_mes=self.periodo_rendicion_mes,
        ).aggregate(maximo=Max('correlativo_rendicion'))['maximo'] or 0
        self.correlativo_rendicion = ultimo + 1

    def save(self, *args, **kwargs):
        self._asignar_correlativo_rendicion()
        super().save(*args, **kwargs)


class DetalleRendicion(models.Model):
    rendicion = models.ForeignKey(
        RendicionGastos, on_delete=models.CASCADE,
        related_name='detalles', verbose_name='Rendición de Gastos'
    )
    fecha_gasto = models.DateField(verbose_name='Fecha del gasto')
    n_boleta_factura = models.CharField(max_length=100, verbose_name='N° Boleta o Factura')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción del gasto')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto del gasto')
    centro_costo = models.ForeignKey(
        CentroCosto, null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )
    cuenta_contable = models.ForeignKey(
        PlanCuentas, null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta contable'
    )
    proveedor = models.ForeignKey(
        'proveedores.Proveedor', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proveedor'
    )

    class Meta:
        verbose_name = 'Detalle de Rendición'
        verbose_name_plural = 'Detalles de Rendiciones'
        # Keep the existing DB table name to avoid data migration
        db_table = 'proveedores_detallerendicion'

    def __str__(self):
        return f'{self.descripcion} - ${self.monto:,.0f}'
