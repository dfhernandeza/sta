from decimal import Decimal

from django.db import models
from django.db.models import Max
from django.utils import timezone
from apps.core.models import TimeStampedModel
from apps.core.validators import validar_rut


class Cliente(TimeStampedModel):
    rut = models.CharField(
        max_length=15, unique=True, validators=[validar_rut],
        verbose_name='RUT', help_text='Formato: XX.XXX.XXX-X'
    )
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social')
    giro = models.CharField(max_length=200, blank=True, verbose_name='Giro')
    direccion = models.CharField(max_length=300, blank=True, verbose_name='Dirección')
    comuna = models.CharField(max_length=100, blank=True, verbose_name='Comuna')
    ciudad = models.CharField(max_length=100, blank=True, verbose_name='Ciudad')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    contacto = models.CharField(max_length=100, blank=True, verbose_name='Nombre contacto')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas = models.TextField(blank=True, verbose_name='Notas')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['razon_social']

    def __str__(self):
        return f'{self.razon_social} ({self.rut})'


class FacturaEmitida(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('anulada', 'Anulada'),
    ]

    numero = models.CharField(max_length=20, unique=True, verbose_name='N° Factura')
    fecha_emision = models.DateField(verbose_name='Fecha de Emisión')
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name='Fecha Vencimiento')
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT,
        related_name='facturas', verbose_name='Cliente'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )
    neto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto Neto')
    iva = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='IVA (19%)')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    correlativo_libro_ventas = models.PositiveIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Correlativo Libro de Ventas'
    )
    periodo_libro_ventas_mes = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Mes Libro de Ventas'
    )
    periodo_libro_ventas_anio = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Año Libro de Ventas'
    )

    class Meta:
        verbose_name = 'Factura Emitida'
        verbose_name_plural = 'Facturas Emitidas'
        ordering = ['-fecha_emision', '-numero']
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'periodo_libro_ventas_anio',
                    'periodo_libro_ventas_mes',
                    'correlativo_libro_ventas',
                ],
                name='uniq_factura_emitida_correlativo_libro_ventas',
            ),
        ]

    def __str__(self):
        return f'Factura {self.numero} - {self.cliente.razon_social}'

    @property
    def indice_libro_ventas(self):
        if not self.correlativo_libro_ventas or not self.periodo_libro_ventas_mes:
            return '—'
        return f'{self.correlativo_libro_ventas}/{self.periodo_libro_ventas_mes}'

    def _asignar_correlativo_libro_ventas(self):
        if self.correlativo_libro_ventas:
            return

        fecha_ingreso = timezone.localdate()
        self.periodo_libro_ventas_mes = fecha_ingreso.month
        self.periodo_libro_ventas_anio = fecha_ingreso.year

        ultimo = FacturaEmitida.objects.filter(
            periodo_libro_ventas_anio=self.periodo_libro_ventas_anio,
            periodo_libro_ventas_mes=self.periodo_libro_ventas_mes,
        ).aggregate(maximo=Max('correlativo_libro_ventas'))['maximo'] or 0
        self.correlativo_libro_ventas = ultimo + 1

    def save(self, *args, **kwargs):
        self._asignar_correlativo_libro_ventas()
        if not self.iva:
            self.iva = round(self.neto * Decimal('0.19'), 2)
        if not self.total:
            self.total = self.neto + self.iva
        super().save(*args, **kwargs)


class DetalleFacturaEmitida(models.Model):
    factura = models.ForeignKey(
        FacturaEmitida, on_delete=models.CASCADE,
        related_name='detalles', verbose_name='Factura'
    )
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Precio Unitario')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Cuenta contable',
    )
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )

    class Meta:
        verbose_name = 'Detalle Factura Emitida'
        verbose_name_plural = 'Detalles Facturas Emitidas'

    def __str__(self):
        return f'{self.descripcion} x{self.cantidad}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class CuentaPorCobrar(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('incobrable', 'Incobrable'),
    ]
    MEDIO_COBRO_CHOICES = [
        ('transferencia', 'Transferencia bancaria'),
        ('cheque', 'Cheque'),
        ('efectivo', 'Efectivo'),
        ('deposito', 'Depósito'),
        ('otro', 'Otro'),
    ]

    factura = models.OneToOneField(
        FacturaEmitida, on_delete=models.CASCADE,
        related_name='cuenta_cobrar', verbose_name='Factura'
    )
    fecha_vencimiento = models.DateField(verbose_name='Fecha Vencimiento')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    monto_pagado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Monto Cobrado')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Cobro')
    medio_cobro = models.CharField(
        max_length=20, choices=MEDIO_COBRO_CHOICES, blank=True, verbose_name='Medio de Cobro'
    )
    numero_documento = models.CharField(
        max_length=100, blank=True, verbose_name='N° Documento / Referencia',
        help_text='N° transferencia, cheque, depósito, etc.'
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    movimiento_pago = models.ForeignKey(
        'tesoreria.MovimientoBancario', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cuentas_cobrar',
        verbose_name='Movimiento de Cobro',
    )

    class Meta:
        verbose_name = 'Cuenta por Cobrar'
        verbose_name_plural = 'Cuentas por Cobrar'
        ordering = ['fecha_vencimiento']

    def __str__(self):
        return f'CxC {self.factura.numero} - {self.factura.cliente.razon_social}'

    @property
    def saldo_pendiente(self):
        return self.monto - self.monto_pagado
