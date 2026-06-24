from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.db.models import Max
from django.utils import timezone

from apps.core.models import TimeStampedModel
from apps.core.validators import validar_rut
from apps.tesoreria.models import Banco, TIPO_CHOICES


TASA_RETENCION_HONORARIOS_2026 = Decimal('0.1525')


class PrestadorHonorarios(TimeStampedModel):
    rut = models.CharField(
        max_length=15, unique=True, validators=[validar_rut],
        verbose_name='RUT', help_text='Formato: XX.XXX.XXX-X'
    )
    nombre = models.CharField(max_length=200, verbose_name='Nombre / Razón Social')
    giro = models.CharField(max_length=200, blank=True, verbose_name='Giro')
    direccion = models.CharField(max_length=300, blank=True, verbose_name='Dirección')
    comuna = models.CharField(max_length=100, blank=True, verbose_name='Comuna')
    ciudad = models.CharField(max_length=100, blank=True, verbose_name='Ciudad')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    email = models.EmailField(blank=True, verbose_name='Email')
    banco = models.ForeignKey(Banco, null=True, blank=True, on_delete=models.SET_NULL, verbose_name='Banco')
    tipo_cuenta = models.CharField(max_length=50, choices=TIPO_CHOICES, blank=True, verbose_name='Tipo de cuenta')
    numero_cuenta = models.CharField(max_length=30, blank=True, verbose_name='N° Cuenta bancaria')
    activo = models.BooleanField(default=True, verbose_name='Activo')
    notas = models.TextField(blank=True, verbose_name='Notas')

    class Meta:
        verbose_name = 'Prestador de Honorarios'
        verbose_name_plural = 'Prestadores de Honorarios'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.rut})'


class BoletaHonorarios(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('pagada', 'Pagada'),
        ('anulada', 'Anulada'),
    ]

    numero = models.CharField(max_length=20, verbose_name='N° Boleta')
    fecha_emision = models.DateField(verbose_name='Fecha de Emisión')
    fecha_vencimiento = models.DateField(null=True, blank=True, verbose_name='Fecha Vencimiento')
    prestador = models.ForeignKey(
        PrestadorHonorarios, on_delete=models.PROTECT,
        related_name='boletas', verbose_name='Prestador'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta de gasto'
    )
    descripcion = models.CharField(max_length=300, verbose_name='Descripción del servicio')
    bruto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto Bruto')
    tasa_retencion = models.DecimalField(
        max_digits=6, decimal_places=4,
        default=TASA_RETENCION_HONORARIOS_2026,
        verbose_name='Tasa Retención'
    )
    retencion = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Retención')
    liquido = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Líquido a pagar')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    correlativo_honorarios = models.PositiveIntegerField(
        null=True, blank=True, editable=False, verbose_name='Correlativo Honorarios'
    )
    periodo_honorarios_mes = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False, verbose_name='Mes Honorarios'
    )
    periodo_honorarios_anio = models.PositiveSmallIntegerField(
        null=True, blank=True, editable=False, verbose_name='Año Honorarios'
    )

    class Meta:
        verbose_name = 'Boleta de Honorarios'
        verbose_name_plural = 'Boletas de Honorarios'
        ordering = ['-fecha_emision', '-numero']
        unique_together = ('prestador', 'numero')
        constraints = [
            models.UniqueConstraint(
                fields=['periodo_honorarios_anio', 'periodo_honorarios_mes', 'correlativo_honorarios'],
                name='uniq_boleta_honorarios_correlativo_mes',
            ),
        ]

    def __str__(self):
        return f'Boleta {self.numero} - {self.prestador.nombre}'

    @property
    def indice_honorarios(self):
        if not self.correlativo_honorarios or not self.periodo_honorarios_mes:
            return '—'
        return f'{self.correlativo_honorarios}/{self.periodo_honorarios_mes}'

    def _asignar_correlativo_honorarios(self):
        if self.correlativo_honorarios:
            return

        fecha_ingreso = timezone.localdate()
        self.periodo_honorarios_mes = fecha_ingreso.month
        self.periodo_honorarios_anio = fecha_ingreso.year
        ultimo = BoletaHonorarios.objects.filter(
            periodo_honorarios_anio=self.periodo_honorarios_anio,
            periodo_honorarios_mes=self.periodo_honorarios_mes,
        ).aggregate(maximo=Max('correlativo_honorarios'))['maximo'] or 0
        self.correlativo_honorarios = ultimo + 1

    def calcular_montos(self):
        bruto = self.bruto or Decimal('0')
        tasa = self.tasa_retencion or Decimal('0')
        self.retencion = (bruto * tasa).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        self.liquido = (bruto - self.retencion).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        self._asignar_correlativo_honorarios()
        self.calcular_montos()
        super().save(*args, **kwargs)
