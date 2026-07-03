from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.db.models.signals import post_delete
from django.dispatch import receiver
from apps.tesoreria.models import Banco, TIPO_CHOICES
from apps.core.models import TimeStampedModel
from apps.core.validators import validar_rut


class Proveedor(TimeStampedModel):
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
    banco = models.ForeignKey(Banco, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Banco')
    tipo_cuenta = models.CharField(max_length=50, choices=TIPO_CHOICES, blank=True, verbose_name='Tipo de cuenta')
    numero_cuenta = models.CharField(max_length=30, blank=True, verbose_name='N° Cuenta bancaria')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas = models.TextField(blank=True, verbose_name='Notas')

    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['razon_social']

    def __str__(self):
        return f'{self.razon_social} ({self.rut})'


class FacturaRecibida(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
        ('anulada', 'Anulada'),
    ]
    ORIGEN_CHOICES = [
        ('operacional', 'Operacional'),
        ('apertura', 'Saldo de apertura'),
    ]

    numero = models.CharField(max_length=20, verbose_name='N° Factura')
    fecha_emision = models.DateField(verbose_name='Fecha de Emisión')
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name='Fecha Vencimiento')
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        related_name='facturas', verbose_name='Proveedor'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )
    pago_por_trabajador = models.ForeignKey(
        'rrhh.Trabajador', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='facturas_pagadas',
        verbose_name='Pagada por trabajador'
    )

    neto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto Neto Afecto')
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Monto Exento')
    iva = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='IVA (19%)')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, default='operacional',
        verbose_name='Origen'
    )
    asiento_apertura = models.ForeignKey(
        'contabilidad.AsientoContable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='facturas_apertura',
        verbose_name='Asiento de apertura'
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    correlativo_libro_compras = models.PositiveIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Correlativo Libro de Compras'
    )
    periodo_libro_compras_mes = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Mes Libro de Compras'
    )
    periodo_libro_compras_anio = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False,
        verbose_name='Año Libro de Compras'
    )

    class Meta:
        verbose_name = 'Factura Recibida'
        verbose_name_plural = 'Facturas Recibidas'
        ordering = ['-fecha_emision']
        unique_together = ('proveedor', 'numero')
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'periodo_libro_compras_anio',
                    'periodo_libro_compras_mes',
                    'correlativo_libro_compras',
                ],
                name='uniq_factura_recibida_correlativo_libro_compras',
            ),
        ]

    def __str__(self):
        if self.pago_por_trabajador:
            return f'Factura {self.numero} - Reembolso {self.pago_por_trabajador.nombre_completo}'
        return f'Factura {self.numero} - {self.proveedor.razon_social}'

    @property
    def indice_libro_compras(self):
        if not self.correlativo_libro_compras or not self.fecha_emision:
            return '—'
        return f'{self.correlativo_libro_compras}/{self.fecha_emision.month}'

    def _asignar_correlativo_libro_compras(self):
        if not self.pk or not self.fecha_emision:
            return

        self.correlativo_libro_compras = FacturaRecibida.objects.filter(
            pk__lte=self.pk,
        ).count()
        self.periodo_libro_compras_mes = self.fecha_emision.month
        self.periodo_libro_compras_anio = self.fecha_emision.year

    @classmethod
    def reindexar_libro_compras(cls):
        cls.objects.update(
            correlativo_libro_compras=None,
            periodo_libro_compras_mes=None,
            periodo_libro_compras_anio=None,
        )
        for indice, factura in enumerate(
            cls.objects.order_by('pk').only('pk', 'fecha_emision').iterator(),
            start=1,
        ):
            cls.objects.filter(pk=factura.pk).update(
                correlativo_libro_compras=indice,
                periodo_libro_compras_mes=factura.fecha_emision.month,
                periodo_libro_compras_anio=factura.fecha_emision.year,
            )

    def save(self, *args, **kwargs):
        if not self.iva:
            self.iva = round(self.neto * Decimal('0.19'), 2)
        if not self.total:
            self.total = self.neto + self.iva + (self.exento or Decimal('0'))
        super().save(*args, **kwargs)
        valores_anteriores = (
            self.correlativo_libro_compras,
            self.periodo_libro_compras_mes,
            self.periodo_libro_compras_anio,
        )
        self._asignar_correlativo_libro_compras()
        valores_nuevos = (
            self.correlativo_libro_compras,
            self.periodo_libro_compras_mes,
            self.periodo_libro_compras_anio,
        )
        if valores_nuevos != valores_anteriores:
            FacturaRecibida.objects.filter(pk=self.pk).update(
                correlativo_libro_compras=self.correlativo_libro_compras,
                periodo_libro_compras_mes=self.periodo_libro_compras_mes,
                periodo_libro_compras_anio=self.periodo_libro_compras_anio,
            )


@receiver(post_delete, sender=FacturaRecibida)
def reindexar_facturas_recibidas_despues_de_eliminar(**kwargs):
    FacturaRecibida.reindexar_libro_compras()


class DetalleFacturaRecibida(models.Model):
    factura = models.ForeignKey(
        FacturaRecibida, on_delete=models.CASCADE,
        related_name='detalles', verbose_name='Factura'
    )
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta contable'
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=4, default=1, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, verbose_name='Precio Unitario')
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )
    exento_iva = models.BooleanField(default=False, verbose_name='Exento de IVA')

    class Meta:
        verbose_name = 'Detalle Factura Recibida'
        verbose_name_plural = 'Detalles Facturas Recibidas'

    def __str__(self):
        return f'{self.descripcion} - {self.cantidad} x ${self.precio_unitario:,.0f}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class NotaCreditoRecibida(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aplicada', 'Aplicada'),
        ('anulada', 'Anulada'),
    ]

    numero = models.CharField(max_length=20, verbose_name='N° Nota de Crédito')
    fecha_emision = models.DateField(verbose_name='Fecha de Emisión')
    factura = models.ForeignKey(
        FacturaRecibida, on_delete=models.PROTECT,
        related_name='notas_credito', verbose_name='Factura asociada'
    )
    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        related_name='notas_credito', verbose_name='Proveedor'
    )
    neto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto Neto Afecto')
    exento = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Monto Exento')
    iva = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='IVA (19%)')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='aplicada', verbose_name='Estado')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Nota de Crédito Recibida'
        verbose_name_plural = 'Notas de Crédito Recibidas'
        ordering = ['-fecha_emision']
        unique_together = ('proveedor', 'numero')

    def __str__(self):
        return f'Nota de crédito {self.numero} - {self.proveedor.razon_social}'

    def save(self, *args, **kwargs):
        if not self.iva:
            self.iva = round(self.neto * Decimal('0.19'), 2)
        if not self.total:
            self.total = self.neto + self.iva + (self.exento or Decimal('0'))
        super().save(*args, **kwargs)


class DetalleNotaCreditoRecibida(models.Model):
    nota_credito = models.ForeignKey(
        NotaCreditoRecibida, on_delete=models.CASCADE,
        related_name='detalles', verbose_name='Nota de Crédito'
    )
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta contable'
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=4, default=1, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4, verbose_name='Precio Unitario')
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )
    exento_iva = models.BooleanField(default=False, verbose_name='Exento de IVA')

    class Meta:
        verbose_name = 'Detalle Nota de Crédito Recibida'
        verbose_name_plural = 'Detalles Notas de Crédito Recibidas'

    def __str__(self):
        return f'{self.descripcion} - {self.cantidad} x ${self.precio_unitario:,.0f}'

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario


class CuentaPorPagar(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('vencida', 'Vencida'),
    ]
    MEDIO_PAGO_CHOICES = [
        ('transferencia', 'Transferencia bancaria'),
        ('cheque', 'Cheque'),
        ('efectivo', 'Efectivo'),
        ('debito', 'Débito automático'),
        ('otro', 'Otro'),
    ]

    factura = models.OneToOneField(
        FacturaRecibida, on_delete=models.CASCADE,
        related_name='cuenta_pagar', verbose_name='Factura', null=True, blank=True
    )
    rendicion = models.ForeignKey(
        'rendiciones.RendicionGastos', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cuentas_pagar', verbose_name='Rendición de Gastos'
    )
    boleta_honorarios = models.OneToOneField(
        'boletas.BoletaHonorarios', on_delete=models.CASCADE,
        related_name='cuenta_pagar', verbose_name='Boleta de Honorarios', null=True, blank=True
    )
    fecha_vencimiento = models.DateField(verbose_name='Fecha Vencimiento')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    monto_pagado = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Monto Pagado')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Pago')
    medio_pago = models.CharField(
        max_length=20, choices=MEDIO_PAGO_CHOICES, blank=True, verbose_name='Medio de Pago'
    )
    numero_documento = models.CharField(
        max_length=100, blank=True, verbose_name='Nº Documento / Referencia',
        help_text='Número de cheque, folio transferencia, etc.'
    )
    notas = models.TextField(blank=True, verbose_name='Notas')
    movimiento_pago = models.ForeignKey(
        'tesoreria.MovimientoBancario', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='cuentas_pagar',
        verbose_name='Movimiento de Pago',
    )

    class Meta:
        verbose_name = 'Cuenta por Pagar'
        verbose_name_plural = 'Cuentas por Pagar'
        ordering = ['fecha_vencimiento']

    def __str__(self):
        if self.factura:
            if self.factura.pago_por_trabajador:
                return f'CxP Factura {self.factura.numero} - Reembolso {self.factura.pago_por_trabajador.nombre_completo}'
            return f'CxP {self.factura.numero} - {self.factura.proveedor.razon_social}'
        if self.rendicion:
            return f'CxP Rendición #{self.rendicion.id} - {self.rendicion.trabajador.nombre_completo}'
        if self.boleta_honorarios:
            return f'CxP Boleta {self.boleta_honorarios.numero} - {self.boleta_honorarios.prestador.nombre}'
        return f'CxP #{self.pk}'

    @property
    def saldo_pendiente(self):
        return max(self.monto - self.monto_pagado, Decimal('0'))


class Anticipo(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aplicado', 'Aplicado'),
        ('devuelto', 'Devuelto'),
    ]
    ORIGEN_CHOICES = [
        ('operacional', 'Operacional'),
        ('apertura', 'Saldo de apertura'),
        ('nota_credito', 'Nota de crédito'),
    ]

    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        related_name='anticipos', verbose_name='Proveedor'
    )
    fecha = models.DateField(verbose_name='Fecha')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    origen = models.CharField(
        max_length=20, choices=ORIGEN_CHOICES, default='operacional',
        verbose_name='Origen'
    )
    asiento_apertura = models.ForeignKey(
        'contabilidad.AsientoContable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='anticipos_proveedores_apertura',
        verbose_name='Asiento de apertura'
    )
    movimiento_pago = models.OneToOneField(
        'tesoreria.MovimientoBancario', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='anticipo_proveedor',
        verbose_name='Movimiento de pago',
    )
    nota_credito_origen = models.OneToOneField(
        NotaCreditoRecibida, null=True, blank=True,
        on_delete=models.CASCADE, related_name='anticipo_generado',
        verbose_name='Nota de crédito de origen'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )

    class Meta:
        verbose_name = 'Anticipo a Proveedor'
        verbose_name_plural = 'Anticipos a Proveedores'
        ordering = ['-fecha']

    def __str__(self):
        return f'Anticipo {self.proveedor.razon_social} - ${self.monto:,.0f}'

    @property
    def monto_aplicado(self):
        return self.aplicaciones.aggregate(total=Sum('monto'))['total'] or Decimal('0')

    @property
    def saldo_disponible(self):
        return max(self.monto - self.monto_aplicado, Decimal('0'))


class AplicacionAnticipoProveedor(TimeStampedModel):
    anticipo = models.ForeignKey(
        Anticipo, on_delete=models.PROTECT,
        related_name='aplicaciones', verbose_name='Anticipo'
    )
    cuenta_pagar = models.ForeignKey(
        CuentaPorPagar, on_delete=models.CASCADE,
        related_name='aplicaciones_anticipos', verbose_name='Cuenta por pagar'
    )
    fecha = models.DateField(verbose_name='Fecha de aplicación')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto aplicado')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    asiento = models.ForeignKey(
        'contabilidad.AsientoContable', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='aplicaciones_anticipos_proveedor',
        verbose_name='Asiento contable'
    )

    class Meta:
        verbose_name = 'Aplicación de Anticipo a Proveedor'
        verbose_name_plural = 'Aplicaciones de Anticipos a Proveedores'
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f'Aplicación {self.anticipo.proveedor.razon_social} - ${self.monto:,.0f}'

