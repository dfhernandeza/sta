from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum, Max
from django.db.models.signals import post_delete, post_save
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


class OrdenCompra(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente_aprobacion', 'Pendiente de Aprobación'),
        ('aprobada', 'Aprobada'),
        ('enviada', 'Enviada'),
        ('recepcion_parcial', 'Recepción Parcial'),
        ('recepcion_completa', 'Recepción Completa'),
        ('facturada', 'Facturada'),
        ('pagada', 'Pagada'),
        ('anulada', 'Anulada'),
    ]
    TRANSICIONES = {
        'borrador': {'pendiente_aprobacion', 'anulada'},
        'pendiente_aprobacion': {'borrador', 'aprobada', 'anulada'},
        'aprobada': {'enviada', 'anulada'},
        'enviada': {'recepcion_parcial', 'recepcion_completa', 'anulada'},
        'recepcion_parcial': {'recepcion_completa', 'anulada'},
        'recepcion_completa': {'facturada', 'anulada'},
        'facturada': {'pagada', 'anulada'},
        'pagada': set(),
        'anulada': set(),
    }

    numero = models.CharField(max_length=20, unique=True, blank=True, editable=False, verbose_name='N° OC')
    fecha = models.DateField(verbose_name='Fecha')
    proyecto = models.ForeignKey('proyectos.Proyecto', null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name='ordenes_compra', verbose_name='Proyecto')
    centro_costo = models.ForeignKey('contabilidad.CentroCosto', null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='ordenes_compra', verbose_name='Centro de Costo')
    solicitante = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT,
                                    related_name='ordenes_compra_solicitadas', verbose_name='Solicitante')
    aprobado_por = models.ForeignKey('accounts.CustomUser', null=True, blank=True, on_delete=models.PROTECT,
                                     related_name='ordenes_compra_aprobadas', verbose_name='Aprobado por')
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name='ordenes_compra',
                                  verbose_name='Proveedor')
    proveedor_razon_social = models.CharField(max_length=200, blank=True)
    proveedor_rut = models.CharField(max_length=15, blank=True)
    proveedor_direccion = models.CharField(max_length=300, blank=True)
    proveedor_telefono = models.CharField(max_length=20, blank=True)
    proveedor_email = models.EmailField(blank=True)
    subtotal = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    neto = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    iva = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='IVA')
    total = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estado = models.CharField(max_length=25, choices=ESTADO_CHOICES, default='borrador')
    observaciones = models.TextField(blank=True)
    condiciones_comerciales = models.TextField(blank=True)
    firma_solicitante = models.ImageField(upload_to='ordenes_compra/firmas/', null=True, blank=True)
    firma_aprobador = models.ImageField(upload_to='ordenes_compra/firmas/', null=True, blank=True)
    fecha_solicitud_aprobacion = models.DateTimeField(null=True, blank=True, editable=False)
    fecha_aprobacion = models.DateTimeField(null=True, blank=True, editable=False)
    fecha_envio = models.DateTimeField(null=True, blank=True, editable=False)
    fecha_anulacion = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['-fecha', '-id']
        verbose_name = 'Orden de Compra'
        verbose_name_plural = 'Órdenes de Compra'

    def __str__(self):
        return f'{self.numero} - {self.proveedor_razon_social or self.proveedor.razon_social}'

    def save(self, *args, **kwargs):
        if self.proveedor_id and (not self.pk or not self.proveedor_razon_social):
            self.proveedor_razon_social = self.proveedor.razon_social
            self.proveedor_rut = self.proveedor.rut
            self.proveedor_direccion = self.proveedor.direccion
            self.proveedor_telefono = self.proveedor.telefono
            self.proveedor_email = self.proveedor.email
        if not self.numero:
            anio = self.fecha.year
            prefijo = f'OC-{anio}-'
            ultimo = OrdenCompra.objects.filter(numero__startswith=prefijo).aggregate(Max('numero'))['numero__max']
            secuencia = int(ultimo.rsplit('-', 1)[1]) + 1 if ultimo else 1
            self.numero = f'{prefijo}{secuencia:04d}'
        super().save(*args, **kwargs)

    def recalcular_totales(self):
        subtotal = self.detalles.aggregate(total=Sum(models.F('cantidad') * models.F('precio_unitario')))['total'] or Decimal('0')
        self.subtotal = subtotal.quantize(Decimal('0.01'))
        self.descuento = min(max(self.descuento or Decimal('0'), Decimal('0')), self.subtotal)
        self.neto = (self.subtotal - self.descuento).quantize(Decimal('0.01'))
        self.iva = (self.neto * Decimal('0.19')).quantize(Decimal('0.01'))
        self.total = self.neto + self.iva
        self.save(update_fields=['subtotal', 'descuento', 'neto', 'iva', 'total', 'actualizado_en'])

    def puede_transicionar(self, nuevo_estado):
        return nuevo_estado in self.TRANSICIONES.get(self.estado, set())

    def sincronizar_estado(self):
        if self.estado == 'anulada':
            return
        facturas = self.facturas.exclude(estado='anulada')
        monto_facturado = facturas.aggregate(total=Sum('total'))['total'] or Decimal('0')
        if facturas.exists() and monto_facturado >= self.total:
            if all(f.estado == 'pagada' for f in facturas):
                nuevo = 'pagada'
            else:
                nuevo = 'facturada'
        else:
            cantidades = list(self.detalles.values_list('cantidad', flat=True))
            recibidas = list(self.detalles.annotate(r=Sum('recepciones__cantidad_recibida')).values_list('r', flat=True))
            total_recibido = sum((r or Decimal('0')) for r in recibidas)
            if cantidades and all((r or Decimal('0')) >= c for r, c in zip(recibidas, cantidades)):
                nuevo = 'recepcion_completa'
            elif total_recibido > 0:
                nuevo = 'recepcion_parcial'
            else:
                return
        if self.estado != nuevo:
            self.estado = nuevo
            self.save(update_fields=['estado', 'actualizado_en'])

    @property
    def monto_facturado(self):
        return self.facturas.exclude(estado='anulada').aggregate(total=Sum('total'))['total'] or Decimal('0')

    @property
    def saldo_por_facturar(self):
        return max(self.total - self.monto_facturado, Decimal('0'))


class DetalleOrdenCompra(models.Model):
    UNIDAD_CHOICES = [('un', 'Unidad'), ('kg', 'Kilogramo'), ('m', 'Metro'), ('m2', 'Metro cuadrado'),
                      ('m3', 'Metro cúbico'), ('lt', 'Litro'), ('hr', 'Hora'), ('serv', 'Servicio'), ('gl', 'Global')]
    orden = models.ForeignKey(OrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    codigo = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=300)
    cantidad = models.DecimalField(max_digits=12, decimal_places=4)
    unidad_medida = models.CharField(max_length=10, choices=UNIDAD_CHOICES, default='un')
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=4)

    @property
    def total(self):
        return self.cantidad * self.precio_unitario

    @property
    def cantidad_recibida(self):
        return self.recepciones.aggregate(total=Sum('cantidad_recibida'))['total'] or Decimal('0')


class RecepcionOrdenCompra(TimeStampedModel):
    orden = models.ForeignKey(OrdenCompra, on_delete=models.PROTECT, related_name='recepciones')
    fecha = models.DateField()
    recibido_por = models.ForeignKey('accounts.CustomUser', on_delete=models.PROTECT, related_name='recepciones_oc')
    observaciones = models.TextField(blank=True)


class DetalleRecepcionOrdenCompra(models.Model):
    recepcion = models.ForeignKey(RecepcionOrdenCompra, on_delete=models.CASCADE, related_name='detalles')
    detalle_orden = models.ForeignKey(DetalleOrdenCompra, on_delete=models.PROTECT, related_name='recepciones')
    cantidad_recibida = models.DecimalField(max_digits=12, decimal_places=4)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['recepcion', 'detalle_orden'], name='uniq_recepcion_detalle_oc')]


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
    orden_compra = models.ForeignKey(
        OrdenCompra, null=True, blank=True, on_delete=models.PROTECT,
        related_name='facturas', verbose_name='Orden de Compra'
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
        null=True, blank=True,
        verbose_name='Mes Libro de Compras'
    )
    periodo_libro_compras_anio = models.PositiveSmallIntegerField(
        null=True, blank=True,
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

    def clean(self):
        super().clean()
        if self.orden_compra_id and self.proveedor_id != self.orden_compra.proveedor_id:
            raise ValidationError({'orden_compra': 'La orden de compra debe pertenecer al mismo proveedor.'})
        if self.orden_compra_id and self.orden_compra.estado in ('borrador', 'pendiente_aprobacion', 'anulada'):
            raise ValidationError({'orden_compra': 'Solo se pueden asociar órdenes aprobadas y vigentes.'})

    @property
    def indice_libro_compras(self):
        if not self.correlativo_libro_compras or not self.periodo_libro_compras_mes:
            return '—'
        return f'{self.correlativo_libro_compras}/{self.periodo_libro_compras_mes}'

    def _asignar_correlativo_libro_compras(self):
        if not self.pk or not self.fecha_emision:
            return
        if not self.periodo_libro_compras_mes:
            self.periodo_libro_compras_mes = self.fecha_emision.month
        if not self.periodo_libro_compras_anio:
            self.periodo_libro_compras_anio = self.fecha_emision.year

        self.correlativo_libro_compras = FacturaRecibida.objects.filter(
            pk__lte=self.pk,
            periodo_libro_compras_anio=self.periodo_libro_compras_anio,
            periodo_libro_compras_mes=self.periodo_libro_compras_mes,
        ).count()

    @classmethod
    def reindexar_libro_compras(cls):
        cls.objects.update(
            correlativo_libro_compras=None,
        )
        correlativos_por_periodo = {}
        for factura in cls.objects.order_by('pk').only(
            'pk',
            'fecha_emision',
            'periodo_libro_compras_mes',
            'periodo_libro_compras_anio',
        ).iterator():
            periodo_mes = factura.periodo_libro_compras_mes or factura.fecha_emision.month
            periodo_anio = factura.periodo_libro_compras_anio or factura.fecha_emision.year
            periodo = (periodo_anio, periodo_mes)
            indice = correlativos_por_periodo.get(periodo, 0) + 1
            correlativos_por_periodo[periodo] = indice
            cls.objects.filter(pk=factura.pk).update(
                correlativo_libro_compras=indice,
                periodo_libro_compras_mes=periodo_mes,
                periodo_libro_compras_anio=periodo_anio,
            )

    def save(self, *args, **kwargs):
        periodo_anterior = None
        if self.pk:
            periodo_anterior = FacturaRecibida.objects.filter(
                pk=self.pk,
            ).values_list(
                'periodo_libro_compras_anio',
                'periodo_libro_compras_mes',
            ).first()

        if not self.iva:
            self.iva = round(self.neto * Decimal('0.19'), 2)
        if not self.total:
            self.total = self.neto + self.iva + (self.exento or Decimal('0'))
        if self.fecha_emision:
            if not self.periodo_libro_compras_mes:
                self.periodo_libro_compras_mes = self.fecha_emision.month
            if not self.periodo_libro_compras_anio:
                self.periodo_libro_compras_anio = self.fecha_emision.year
        periodo_actual = (
            self.periodo_libro_compras_anio,
            self.periodo_libro_compras_mes,
        )
        if periodo_anterior and periodo_anterior != periodo_actual:
            self.correlativo_libro_compras = None
            update_fields = kwargs.get('update_fields')
            if update_fields:
                kwargs['update_fields'] = set(update_fields) | {'correlativo_libro_compras'}

        super().save(*args, **kwargs)

        if periodo_anterior and periodo_anterior != periodo_actual:
            FacturaRecibida.reindexar_libro_compras()
            self.refresh_from_db(fields=[
                'correlativo_libro_compras',
                'periodo_libro_compras_mes',
                'periodo_libro_compras_anio',
            ])
            return

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


@receiver(post_save, sender=FacturaRecibida)
def sincronizar_oc_despues_de_guardar_factura(sender, instance, **kwargs):
    if instance.orden_compra_id:
        instance.orden_compra.sincronizar_estado()


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
    periodo_libro_compras_mes = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Mes Libro de Compras'
    )
    periodo_libro_compras_anio = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Año Libro de Compras'
    )

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
        if self.fecha_emision:
            if not self.periodo_libro_compras_mes:
                self.periodo_libro_compras_mes = self.fecha_emision.month
            if not self.periodo_libro_compras_anio:
                self.periodo_libro_compras_anio = self.fecha_emision.year
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

