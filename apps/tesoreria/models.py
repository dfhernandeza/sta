from django.db import models
from apps.core.models import TimeStampedModel
from apps.core.templatetags.custom_tags import moneda_chilena
from apps.core.validators import validar_rut


class Banco(TimeStampedModel):
    nombre = models.CharField(max_length=100, verbose_name='Nombre del Banco')
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Código banco')

    class Meta:
        verbose_name = 'Banco'
        verbose_name_plural = 'Bancos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

TIPO_CHOICES = [
        ('corriente', 'Cuenta Corriente'),
        ('ahorro', 'Cuenta de Ahorro'),
        ('vista', 'Cuenta Vista'),
        ('rut', 'Cuenta RUT'),
    ]

class CuentaBancaria(TimeStampedModel):

    banco = models.ForeignKey(Banco, on_delete=models.PROTECT, related_name='cuentas', verbose_name='Banco')
    numero = models.CharField(max_length=30, verbose_name='Número de cuenta')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='corriente', verbose_name='Tipo')
    descripcion = models.CharField(max_length=100, blank=True, verbose_name='Descripción')
    saldo_inicial = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Saldo inicial')
    activa = models.BooleanField(default=True, verbose_name='Activa')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta Contable',
        help_text='Cuenta del plan de cuentas que representa esta cuenta bancaria.'
    )

    class Meta:
        verbose_name = 'Cuenta Bancaria'
        verbose_name_plural = 'Cuentas Bancarias'
        unique_together = ('banco', 'numero')

    def __str__(self):
        return f'{self.banco} - {self.numero} ({self.get_tipo_display()}) - Saldo: {moneda_chilena(self.saldo_actual)}'

    @property
    def saldo_actual(self):
        from django.db.models import Sum
        ingresos = self.movimientos.filter(tipo='ingreso').aggregate(t=Sum('monto'))['t'] or 0
        egresos = self.movimientos.filter(tipo='egreso').aggregate(t=Sum('monto'))['t'] or 0
        return self.saldo_inicial + ingresos - egresos


class MovimientoBancario(TimeStampedModel):
    TIPO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('egreso', 'Egreso'),
    ]

    cuenta = models.ForeignKey(
        CuentaBancaria, on_delete=models.PROTECT,
        related_name='movimientos', verbose_name='Cuenta bancaria'
    )
    fecha = models.DateField(verbose_name='Fecha')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='Tipo')
    monto = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Monto')
    descripcion = models.CharField(max_length=300, verbose_name='Descripción')
    cuenta_contable = models.ForeignKey(
        'contabilidad.PlanCuentas', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Cuenta contable'
    )
    proyecto = models.ForeignKey(
        'proyectos.Proyecto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Proyecto'
    )
    documento = models.CharField(max_length=50, blank=True, verbose_name='N° Documento')
    conciliado = models.BooleanField(default=False, verbose_name='Conciliado')
    fecha_conciliacion = models.DateField(null=True, blank=True, verbose_name='Fecha de conciliación')
    conciliado_por = models.ForeignKey(
        'accounts.CustomUser', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='movimientos_conciliados',
        verbose_name='Conciliado por'
    )

    class Meta:
        verbose_name = 'Movimiento Bancario'
        verbose_name_plural = 'Movimientos Bancarios'
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f'{self.fecha} | {self.get_tipo_display()} | ${self.monto:,.0f} | {self.descripcion[:40]}'
