from decimal import Decimal
from django.db import models
from apps.tesoreria.models import Banco, TIPO_CHOICES
from apps.core.models import TimeStampedModel
from apps.core.validators import validar_rut
from apps.contabilidad.models import PlanCuentas, CentroCosto


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
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    class Meta:
        verbose_name = 'Factura Recibida'
        verbose_name_plural = 'Facturas Recibidas'
        ordering = ['-fecha_emision']
        unique_together = ('proveedor', 'numero')

    def __str__(self):
        if self.pago_por_trabajador:
            return f'Factura {self.numero} - Reembolso {self.pago_por_trabajador.nombre_completo}'
        return f'Factura {self.numero} - {self.proveedor.razon_social}'

    def save(self, *args, **kwargs):
        if not self.iva:
            self.iva = round(self.neto * Decimal('0.19'), 2)
        if not self.total:
            self.total = self.neto + self.iva + (self.exento or Decimal('0'))
        super().save(*args, **kwargs)


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
    cantidad = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name='Cantidad')
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Precio Unitario')
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
        'RendicionGastos', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='cuentas_pagar', verbose_name='Rendición de Gastos'
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
        return f'CxP #{self.pk}'

    @property
    def saldo_pendiente(self):
        return self.monto - self.monto_pagado


class Anticipo(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aplicado', 'Aplicado'),
        ('devuelto', 'Devuelto'),
    ]

    proveedor = models.ForeignKey(
        Proveedor, on_delete=models.PROTECT,
        related_name='anticipos', verbose_name='Proveedor'
    )
    fecha = models.DateField(verbose_name='Fecha')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
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

class RendicionGastos(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('enviado', 'Enviado para revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
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

    class Meta:
        verbose_name = 'Rendición de Gastos'
        verbose_name_plural = 'Rendiciones de Gastos'
        ordering = ['-id']

    def __str__(self):
        return f'Rendición de {self.trabajador.nombre_completo} - {self.fecha}'

class DetalleRendicion(models.Model):
    rendicion = models.ForeignKey(
        RendicionGastos, on_delete=models.CASCADE,
        related_name='detalles', verbose_name='Rendición de Gastos'
    )
    fecha_gasto = models.DateField(verbose_name='Fecha del gasto')
    n_boleta_factura = models.CharField(max_length=100, verbose_name='N° Boleta o Factura')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción del gasto')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto del gasto')
    centro_costo = models.ForeignKey(CentroCosto, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Centro de Costo')
    cuenta_contable = models.ForeignKey(PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Cuenta contable')
    proveedor = models.ForeignKey('proveedores.Proveedor', null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Proveedor')
    class Meta:
        verbose_name = 'Detalle de Rendición'
        verbose_name_plural = 'Detalles de Rendiciones'

    def __str__(self):
        return f'{self.descripcion} - ${self.monto:,.0f}'

