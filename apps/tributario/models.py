from django.db import models
from apps.core.models import TimeStampedModel


class RegistroCompra(TimeStampedModel):
    TIPO_DOCUMENTO_CHOICES = [
        ('factura', 'Factura'),
        ('nota_credito', 'Nota de Crédito'),
    ]

    tipo_documento = models.CharField(
        max_length=20, choices=TIPO_DOCUMENTO_CHOICES,
        default='factura', verbose_name='Tipo de documento'
    )
    proveedor = models.ForeignKey(
        'proveedores.Proveedor', on_delete=models.PROTECT,
        verbose_name='Proveedor'
    )
    factura = models.ForeignKey(
        'proveedores.FacturaRecibida', null=True, blank=True,
        on_delete=models.CASCADE, verbose_name='Factura'
    )
    nota_credito = models.ForeignKey(
        'proveedores.NotaCreditoRecibida', null=True, blank=True,
        on_delete=models.CASCADE, verbose_name='Nota de Crédito'
    )
    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    neto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Neto')
    iva_credito = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='IVA Crédito Fiscal')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')

    class Meta:
        verbose_name = 'Registro de Compra'
        verbose_name_plural = 'Registro de Compras'
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        documento = self.nota_credito or self.factura or 'Sin documento'
        return f'{self.get_tipo_documento_display()} {documento} - {self.periodo_mes:02d}/{self.periodo_anio}'


class RegistroVenta(TimeStampedModel):
    cliente = models.ForeignKey(
        'clientes.Cliente', on_delete=models.PROTECT,
        verbose_name='Cliente'
    )
    factura = models.ForeignKey(
        'clientes.FacturaEmitida', on_delete=models.CASCADE,
        verbose_name='Factura'
    )
    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    neto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Neto')
    iva_debito = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='IVA Débito Fiscal')
    total = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Total')

    class Meta:
        verbose_name = 'Registro de Venta'
        verbose_name_plural = 'Registro de Ventas'
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f'Venta {self.cliente.razon_social} - {self.periodo_mes:02d}/{self.periodo_anio}'


class DeclaracionIVA(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('presentado', 'Presentado'),
        ('pagado', 'Pagado'),
    ]

    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    iva_debito = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA Débito')
    iva_credito = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA Crédito')
    diferencia = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Diferencia (a pagar)')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado')
    fecha_presentacion = models.DateField(null=True, blank=True, verbose_name='Fecha de Presentación')

    class Meta:
        verbose_name = 'Declaración IVA'
        verbose_name_plural = 'Declaraciones IVA'
        unique_together = ('periodo_mes', 'periodo_anio')
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f'IVA {self.periodo_mes:02d}/{self.periodo_anio}'

    def save(self, *args, **kwargs):
        self.diferencia = max(self.iva_debito - self.iva_credito, 0)
        super().save(*args, **kwargs)


class PPM(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('presentado', 'Presentado'),
        ('pagado', 'Pagado'),
    ]

    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    base_imponible = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Base Imponible')
    tasa = models.DecimalField(max_digits=5, decimal_places=4, default=0.0025, verbose_name='Tasa PPM')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto PPM')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Pago')

    class Meta:
        verbose_name = 'PPM'
        verbose_name_plural = 'PPM'
        unique_together = ('periodo_mes', 'periodo_anio')
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f'PPM {self.periodo_mes:02d}/{self.periodo_anio} - ${self.monto:,.0f}'


class FormularioF29(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('presentado', 'Presentado'),
        ('pagado', 'Pagado'),
    ]

    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    iva_pagar = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA a Pagar')
    ppm_pagar = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='PPM a Pagar')
    retenciones = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Retenciones')
    impuesto_unico = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
        verbose_name='Impuesto Único de Segunda Categoría',
    )
    total_pagar = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Total a Pagar')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    fecha_presentacion = models.DateField(null=True, blank=True, verbose_name='Fecha de Presentación')
    folio = models.CharField(max_length=20, blank=True, verbose_name='N° Folio')

    class Meta:
        verbose_name = 'Formulario F29'
        verbose_name_plural = 'Formularios F29'
        unique_together = ('periodo_mes', 'periodo_anio')
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f'F29 {self.periodo_mes:02d}/{self.periodo_anio}'

    def save(self, *args, **kwargs):
        self.total_pagar = (
            self.iva_pagar
            + self.ppm_pagar
            + self.retenciones
            + self.impuesto_unico
        )
        super().save(*args, **kwargs)
