from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from apps.core.models import TimeStampedModel


class PlanCuentas(TimeStampedModel):
    TIPO_CHOICES = [
        ('activo', 'Activo'),
        ('pasivo', 'Pasivo'),
        ('ingreso', 'Ingreso'),
        ('costo', 'Costo Operacional'),
        ('gasto', 'Gasto Administrativo'),
        ('socio', 'Socio / Gerencia'),
        ('patrimonio', 'Patrimonio / Resultados Acumulados'),
    ]
    NIVEL_CHOICES = [(i, f'Nivel {i}') for i in range(1, 5)]

    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo')
    nivel = models.PositiveSmallIntegerField(choices=NIVEL_CHOICES, verbose_name='Nivel')
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT,
        related_name='subcuentas', verbose_name='Cuenta padre'
    )
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    acepta_movimientos = models.BooleanField(
        default=True,
        verbose_name='Acepta movimientos',
        help_text='Solo las cuentas de nivel 3 y 4 deberían aceptar movimientos directos.'
    )

    class Meta:
        verbose_name = 'Cuenta Contable'
        verbose_name_plural = 'Plan de Cuentas'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    def get_ruta(self):
        partes = [self.nombre]
        cuenta = self
        while cuenta.parent:
            cuenta = cuenta.parent
            partes.insert(0, cuenta.nombre)
        return ' > '.join(partes)


# ---------------------------------------------------------------------------
# Centro de Costo
# ---------------------------------------------------------------------------

class CentroCosto(models.Model):
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código',
                              help_text='Ej: ADM, OPE, VEN')
    nombre = models.CharField(max_length=100, verbose_name='Nombre')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    presupuesto_mensual = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True,
        verbose_name='Presupuesto Mensual',
        help_text='Monto de referencia para comparar con costos reales por período.'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')

    class Meta:
        verbose_name = 'Centro de Costo'
        verbose_name_plural = 'Centros de Costo'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} — {self.nombre}'


# ---------------------------------------------------------------------------
# Configuración Contable (singleton)
# ---------------------------------------------------------------------------

class ConfiguracionContable(models.Model):
    cuenta_cxc = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta CxC (Clientes Nacionales)',
        help_text='Cuenta activo para registrar cuentas por cobrar (Debe en venta).'
    )
    cuenta_cxp = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta CxP (Facturas por Pagar)',
        help_text='Cuenta pasivo para registrar cuentas por pagar (Haber en compra).'
    )
    cuenta_documentos_por_pagar = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Documentos por Pagar',
        help_text='Cuenta pasivo para registrar documentos por pagar (Haber en compra).'
    )
    cuenta_iva_debito = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='IVA Débito Fiscal',
        help_text='Cuenta pasivo IVA en ventas.'
    )
    cuenta_iva_credito = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='IVA Crédito Fiscal',
        help_text='Cuenta activo IVA en compras.'
    )
    cuenta_ventas_default = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta Ingresos por Defecto',
        help_text='Se usa cuando el detalle de factura no tiene cuenta asignada.'
    )
    cuenta_compras_default = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta Costos/Compras por Defecto',
        help_text='Se usa cuando el detalle de factura recibida no tiene cuenta asignada.'
    )
    cuenta_sueldos_operacional = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Sueldos — Costo Operacional',
        help_text='Cuenta de costo para remuneraciones del personal operativo (DEBE en pago).'
    )
    cuenta_sueldos_administrativo = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Sueldos — Gasto Administrativo',
        help_text='Cuenta de gasto para remuneraciones del personal administrativo (DEBE en pago).'
    )
    cuenta_impuestos_sii = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta Impuestos SII (F29)',
        help_text='Cuenta pasivo para registrar obligaciones tributarias pagadas al SII (Debe en pago F29).'
    )
    cuenta_ppm = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='PPM por Recuperar',
        help_text='Cuenta activo para registrar los pagos provisionales mensuales entregados al SII.'
    )
    cuenta_afp_por_pagar = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='AFP por Pagar',
        help_text='Cuenta pasivo para el descuento AFP retenido al trabajador pendiente de enterar a la AFP.'
    )
    cuenta_salud_por_pagar = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Salud por Pagar (Isapre/FONASA)',
        help_text='Cuenta pasivo para el descuento de salud retenido al trabajador pendiente de enterar.'
    )
    cuenta_sueldos_por_pagar = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Sueldos por Pagar (otros descuentos)',
        help_text='Cuenta pasivo catch-all para otros descuentos y anticipos descontados en liquidación.'
    )
    cuenta_anticipos_trabajadores = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Anticipos a Trabajadores',
        help_text='Cuenta activo para registrar anticipos entregados a trabajadores pendientes de descontar en liquidación.'
    )
    cuenta_anticipos_proveedores = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Anticipos a Proveedores',
        help_text='Cuenta activo para registrar anticipos entregados a proveedores pendientes de aplicar contra factura.'
    )
    cuenta_patrimonio_apertura = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Patrimonio / Resultados Acumulados (Apertura)',
        help_text='Cuenta de patrimonio o resultados acumulados usada como contrapartida de cuadre en el asiento de apertura.'
    )
    cuenta_honorarios_default = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Cuenta Honorarios por Defecto',
        help_text='Cuenta de gasto/costo usada cuando una boleta de honorarios no tiene cuenta asignada.'
    )
    cuenta_retenciones_honorarios = models.ForeignKey(
        PlanCuentas, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='+', verbose_name='Retenciones Honorarios por Pagar',
        help_text='Cuenta pasivo para registrar la retención de boletas de honorarios pendiente de enterar al SII.'
    )

    class Meta:
        verbose_name = 'Configuración Contable'
        verbose_name_plural = 'Configuración Contable'

    def __str__(self):
        return 'Configuración Contable'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ---------------------------------------------------------------------------
# Asiento Contable
# ---------------------------------------------------------------------------

class AsientoContableQuerySet(models.QuerySet):
    def delete(self):
        anios = {
            self.model._extraer_anio_numero(numero)
            for numero in self.values_list('numero', flat=True)
        }
        anios.discard(None)
        resultado = super().delete()
        for anio in anios:
            self.model.resetear_correlativo(anio=anio)
        return resultado


class AsientoContable(TimeStampedModel):
    NUMERO_PREFIJO = 'AJ'

    objects = AsientoContableQuerySet.as_manager()

    TIPO_CHOICES = [
        ('apertura', 'Asiento de Apertura'),
        ('factura_venta', 'Factura de Venta'),
        ('factura_compra', 'Factura de Compra'),
        ('nota_credito_compra', 'Nota de Crédito de Compra'),
        ('boleta_honorarios', 'Boleta de Honorarios'),
        ('pago_cxc', 'Cobro CxC'),
        ('pago_cxp', 'Pago CxP'),
        ('movimiento_banco', 'Movimiento Bancario'),
        ('devengamiento_remuneracion', 'Devengamiento de Remuneración'),
        ('pago_remuneracion', 'Pago de Remuneración'),
        ('pago_anticipo', 'Pago de Anticipo Laboral'),
        ('pago_anticipo_proveedor', 'Pago de Anticipo a Proveedor'),
        ('centralizacion_iva', 'Centralización de IVA'),
        ('devengamiento_ppm', 'Devengamiento de PPM'),
        ('pago_f29', 'Pago de F29'),
        ('ajuste', 'Ajuste Contable'),
        ('rendicion_gastos', 'Rendición de Gastos'),
        ('otro', 'Otro'),
    ]
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
        ('anulado', 'Anulado'),
    ]

    numero = models.CharField(max_length=20, unique=True, verbose_name='N° Asiento', editable=False)
    fecha = models.DateField(verbose_name='Fecha')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='otro', verbose_name='Tipo')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado')

    factura_emitida = models.ForeignKey(
        'clientes.FacturaEmitida', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Factura Emitida'
    )
    factura_recibida = models.ForeignKey(
        'proveedores.FacturaRecibida', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Factura Recibida'
    )
    nota_credito_recibida = models.ForeignKey(
        'proveedores.NotaCreditoRecibida', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Nota de Crédito Recibida'
    )
    boleta_honorarios = models.ForeignKey(
        'boletas.BoletaHonorarios', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Boleta de Honorarios'
    )
    movimiento_bancario = models.ForeignKey(
        'tesoreria.MovimientoBancario', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Movimiento Bancario'
    )
    rendicion_gastos = models.ForeignKey(
        'rendiciones.RendicionGastos', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Rendición de Gastos'
    )
    remuneracion = models.ForeignKey(
        'rrhh.Remuneracion', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Remuneración'
    )
    declaracion_iva = models.ForeignKey(
        'tributario.DeclaracionIVA', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Declaración IVA'
    )
    formulario_f29 = models.ForeignKey(
        'tributario.FormularioF29', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Formulario F29'
    )
    ppm = models.ForeignKey(
        'tributario.PPM', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='PPM'
    )
    creado_por = models.ForeignKey(
        'accounts.CustomUser', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='asientos', verbose_name='Creado por'
    )

    class Meta:
        verbose_name = 'Asiento Contable'
        verbose_name_plural = 'Asientos Contables'
        ordering = ['-fecha', '-numero']

    def __str__(self):
        return f'{self.numero} – {self.descripcion[:60]}'

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        anio = self._extraer_anio_numero(self.numero)
        resultado = super().delete(*args, **kwargs)
        if anio:
            self.resetear_correlativo(anio=anio)
        return resultado

    @classmethod
    def _extraer_anio_numero(cls, numero):
        partes = (numero or '').split('-')
        if len(partes) < 3 or partes[0] != cls.NUMERO_PREFIJO:
            return None
        try:
            return int(partes[1])
        except ValueError:
            return None

    @classmethod
    def _prefix_numero(cls, anio):
        return f'{cls.NUMERO_PREFIJO}-{anio}-'

    @classmethod
    def _generar_numero(cls):
        from django.utils import timezone
        year = timezone.now().year
        prefix = cls._prefix_numero(year)
        numeros = (
            cls.objects
            .filter(numero__startswith=prefix)
            .values_list('numero', flat=True)
        )

        usados = set()
        for numero in numeros:
            try:
                usados.add(int(numero.rsplit('-', 1)[-1]))
            except (ValueError, IndexError):
                continue

        seq = 1
        while seq in usados:
            seq += 1

        return f'{prefix}{seq:04d}'

    @classmethod
    def resetear_correlativo(cls, anio=None):
        """
        Renumera los asientos sin dejar vacíos.

        La renumeración se hace por año del número actual y respeta el orden de
        creación: primero `creado_en`, luego `id`. Para evitar choques con el
        campo único `numero`, primero mueve todos los asientos a números
        temporales y luego asigna el correlativo final.
        """
        if anio is None:
            anios = {
                cls._extraer_anio_numero(numero)
                for numero in cls.objects.values_list('numero', flat=True)
            }
            anios.discard(None)
            for anio_disponible in sorted(anios):
                cls.resetear_correlativo(anio=anio_disponible)
            return

        prefix = cls._prefix_numero(anio)
        asientos = list(
            cls.objects
            .filter(numero__startswith=prefix)
            .order_by('creado_en', 'id')
        )

        with transaction.atomic():
            for asiento in asientos:
                cls.objects.filter(pk=asiento.pk).update(numero=f'T{asiento.pk}')

            for seq, asiento in enumerate(asientos, start=1):
                cls.objects.filter(pk=asiento.pk).update(numero=f'{prefix}{seq:04d}')

    @property
    def total_debe(self):
        return self.lineas.aggregate(t=models.Sum('debe'))['t'] or Decimal('0.00')

    @property
    def total_haber(self):
        return self.lineas.aggregate(t=models.Sum('haber'))['t'] or Decimal('0.00')

    @property
    def esta_cuadrado(self):
        return self.total_debe == self.total_haber

    def clean(self):
        if self.estado == 'confirmado' and not self.esta_cuadrado:
            raise ValidationError('El asiento no está cuadrado (Debe ≠ Haber).')


# ---------------------------------------------------------------------------
# Línea de Asiento
# ---------------------------------------------------------------------------

class LineaAsiento(models.Model):
    asiento = models.ForeignKey(
        AsientoContable, on_delete=models.CASCADE,
        related_name='lineas', verbose_name='Asiento'
    )
    cuenta = models.ForeignKey(
        PlanCuentas, on_delete=models.PROTECT,
        verbose_name='Cuenta Contable'
    )
    descripcion = models.CharField(max_length=200, blank=True, verbose_name='Descripción')
    debe = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Debe')
    haber = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Haber')
    orden = models.PositiveSmallIntegerField(default=0, verbose_name='Orden')
    centro_costo = models.ForeignKey(
        CentroCosto, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='lineas_asiento', verbose_name='Centro de Costo'
    )

    class Meta:
        verbose_name = 'Línea de Asiento'
        verbose_name_plural = 'Líneas de Asiento'
        ordering = ['orden', 'pk']

    def __str__(self):
        return f'{self.cuenta} | D:{self.debe} H:{self.haber}'

    def clean(self):
        if self.debe > 0 and self.haber > 0:
            raise ValidationError('Una línea no puede tener Debe y Haber al mismo tiempo.')
