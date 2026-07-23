from django.db import models
from calendar import monthrange
from datetime import date
from decimal import Decimal
from django.conf import settings
from apps.core.models import TimeStampedModel
from apps.core.validators import validar_rut
from apps.tesoreria.models import Banco, TIPO_CHOICES


class CargoTrabajador(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name='Nombre del Cargo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción del Cargo')

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Trabajador(TimeStampedModel):
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('inactivo', 'Inactivo'),
        ('licencia', 'Con Licencia'),
        ('vacaciones', 'En Vacaciones'),
    ]
    TIPO_COSTO_CHOICES = [
        ('operacional', 'Costo Operacional'),
        ('administrativo', 'Gasto Administrativo'),
    ]

    AFP_CHOICES = [
        ('capital', 'Capital'),
        ('cuprum', 'Cuprum'),
        ('habitat', 'Hábitat'),
        ('modelo', 'Modelo'),
        ('planvital', 'PlanVital'),
        ('provida', 'Provida'),
        ('uno', 'Uno'),
    ]

    ISAPRE_CHOICES = [
        ('colmena', 'Colmena'),
        ('consalud', 'Consalud'),
        ('cruz_blanca', 'Cruz Blanca'),
        ('fonsalud', 'FONASA'),
        ('fundacion', 'Fundación'),
        ('masvida', 'Masvida'),
        ('nueva_masvida', 'Nueva Masvida'),
        ('red_salud', 'Red Salud'),
        ('vida_chile', 'Vida Chile'),
    ]

    rut = models.CharField(
        max_length=15, unique=True, validators=[validar_rut],
        verbose_name='RUT', help_text='Formato: XX.XXX.XXX-X'
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='trabajador',
        verbose_name='Usuario del sistema',
        help_text='Usuario que podrá ver y crear las rendiciones de este trabajador.',
    )
    nombres = models.CharField(max_length=100, verbose_name='Nombres')
    apellidos = models.CharField(max_length=100, verbose_name='Apellidos')
    cargo = models.ForeignKey(
        CargoTrabajador, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='trabajadores', verbose_name='Cargo'
    )
    fecha_ingreso = models.DateField(verbose_name='Fecha de Ingreso')
    fecha_termino = models.DateField(null=True, blank=True, verbose_name='Fecha de Término')
    fecha_nacimiento = models.DateField(null=True, blank=True, verbose_name='Fecha de Nacimiento')
    sueldo_base = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Sueldo Base')
    afp = models.CharField(max_length=100, choices=AFP_CHOICES, blank=True, verbose_name='AFP')
    isapre = models.CharField(max_length=100, choices=ISAPRE_CHOICES, blank=True, verbose_name='Isapre/FONASA')
    banco = models.ForeignKey(Banco, on_delete=models.PROTECT, null=True, blank=True, verbose_name='Banco')
    tipo_cuenta = models.CharField(max_length=50, choices=TIPO_CHOICES, blank=True, verbose_name='Tipo de Cuenta')
    numero_cuenta = models.CharField(max_length=30, blank=True, verbose_name='N° Cuenta Bancaria')
    email = models.EmailField(blank=True, verbose_name='Email')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    direccion = models.CharField(max_length=300, blank=True, verbose_name='Dirección')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='activo', verbose_name='Estado')
    exento_previsional = models.BooleanField(
        default=False,
        verbose_name='Exento de AFP/Salud',
        help_text='Marcar si el trabajador no tiene contrato y solo se le paga el sueldo bruto sin descuentos previsionales.',
    )
    tipo_costo = models.CharField(
        max_length=15, choices=TIPO_COSTO_CHOICES, default='administrativo',
        verbose_name='Tipo de costo',
        help_text='Determina la cuenta contable usada al pagar remuneraciones y anticipos.'
    )
    centro_costo = models.ForeignKey(
        'contabilidad.CentroCosto', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Centro de Costo'
    )

    class Meta:
        verbose_name = 'Trabajador'
        verbose_name_plural = 'Trabajadores'
        ordering = ['apellidos', 'nombres']

    def __str__(self):
        return f'{self.apellidos} {self.nombres} ({self.rut})'

    @property
    def nombre_completo(self):
        return f'{self.nombres} {self.apellidos}'


class Remuneracion(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('aprobado', 'Aprobado'),
        ('pagado', 'Pagado'),
    ]

    trabajador = models.ForeignKey(
        Trabajador, on_delete=models.PROTECT,
        related_name='remuneraciones', verbose_name='Trabajador'
    )
    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    fecha_devengamiento = models.DateField(verbose_name='Fecha de Devengamiento')
    sueldo_base = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Sueldo Base')
    horas_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Horas Extra')
    bono = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Bonos')
    sueldo_bruto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Sueldo Bruto')
    descuento_afp = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Descuento AFP')
    descuento_salud = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Descuento Salud')
    seguro_cesantia_trabajador = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True,
        verbose_name='Seguro de Cesantía — Trabajador',
    )
    seguro_cesantia_empleador = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True,
        verbose_name='Seguro de Cesantía — Empleador',
    )
    impuesto_unico = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Impuesto Único')
    otros_descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Otros Descuentos')
    anticipo_descontado = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Anticipo Descontado')
    liquido_pagar = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Líquido a Pagar')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Pago')
    movimiento_pago = models.OneToOneField(
        'tesoreria.MovimientoBancario',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='remuneracion_pagada',
        verbose_name='Movimiento de pago',
    )

    class Meta:
        verbose_name = 'Remuneración'
        verbose_name_plural = 'Remuneraciones'
        ordering = ['-periodo_anio', '-periodo_mes']
        unique_together = ('trabajador', 'periodo_mes', 'periodo_anio')

    def __str__(self):
        return f'{self.trabajador.nombre_completo} - {self.periodo_mes:02d}/{self.periodo_anio}'

    def save(self, *args, **kwargs):
        if not self.fecha_devengamiento and self.periodo_mes and self.periodo_anio:
            ultimo_dia = monthrange(self.periodo_anio, self.periodo_mes)[1]
            self.fecha_devengamiento = date(
                self.periodo_anio,
                self.periodo_mes,
                ultimo_dia,
            )
        super().save(*args, **kwargs)

    @property
    def descuentos(self):
        return (
            (self.descuento_afp or 0) +
            (self.descuento_salud or 0) +
            (self.seguro_cesantia_trabajador or 0) +
            (self.impuesto_unico or 0) +
            (self.otros_descuentos or 0)
        )


class DeclaracionPrevisional(TimeStampedModel):
    ESTADO_CHOICES = [
        ('borrador', 'Borrador'),
        ('presentada', 'Presentada'),
        ('pagada', 'Pagada'),
    ]

    periodo_mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    periodo_anio = models.PositiveSmallIntegerField(verbose_name='Año')
    remuneraciones = models.ManyToManyField(
        Remuneracion, related_name='declaraciones_previsionales',
        blank=True, verbose_name='Remuneraciones incluidas',
    )
    total_afp = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_salud = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cesantia_trabajador = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_cesantia_empleador = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pagar = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='borrador')
    fecha_presentacion = models.DateField(null=True, blank=True)
    folio = models.CharField(max_length=80, blank=True)
    fecha_pago = models.DateField(null=True, blank=True)
    movimiento_pago = models.OneToOneField(
        'tesoreria.MovimientoBancario', null=True, blank=True,
        on_delete=models.PROTECT, related_name='declaracion_previsional',
        verbose_name='Movimiento de pago',
    )

    class Meta:
        verbose_name = 'Declaración Previsional'
        verbose_name_plural = 'Declaraciones Previsionales'
        ordering = ['-periodo_anio', '-periodo_mes']
        constraints = [
            models.UniqueConstraint(
                fields=['periodo_mes', 'periodo_anio'],
                name='rrhh_declaracion_previsional_periodo_unico',
            ),
            models.CheckConstraint(
                check=models.Q(periodo_mes__gte=1, periodo_mes__lte=12),
                name='rrhh_declaracion_previsional_mes_valido',
            ),
        ]

    def __str__(self):
        return f'Previred {self.periodo_mes:02d}/{self.periodo_anio}'

    def recalcular_totales(self, guardar=True):
        totales = self.remuneraciones.aggregate(
            afp=models.Sum('descuento_afp'),
            salud=models.Sum('descuento_salud'),
            cesantia_trabajador=models.Sum('seguro_cesantia_trabajador'),
            cesantia_empleador=models.Sum('seguro_cesantia_empleador'),
        )
        self.total_afp = totales['afp'] or Decimal('0')
        self.total_salud = totales['salud'] or Decimal('0')
        self.total_cesantia_trabajador = totales['cesantia_trabajador'] or Decimal('0')
        self.total_cesantia_empleador = totales['cesantia_empleador'] or Decimal('0')
        self.total_pagar = (
            self.total_afp + self.total_salud
            + self.total_cesantia_trabajador + self.total_cesantia_empleador
        )
        if guardar:
            self.save(update_fields=[
                'total_afp', 'total_salud',
                'total_cesantia_trabajador', 'total_cesantia_empleador',
                'total_pagar', 'actualizado_en',
            ])
        return self.total_pagar


class AnticipoLaboral(TimeStampedModel):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('descontado', 'Descontado en liquidación'),
    ]

    trabajador = models.ForeignKey(
        Trabajador, on_delete=models.PROTECT,
        related_name='anticipos', verbose_name='Trabajador'
    )
    fecha = models.DateField(verbose_name='Fecha')
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Monto')
    descripcion = models.CharField(max_length=200, blank=True, verbose_name='Descripción')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='pendiente', verbose_name='Estado')
    movimiento_pago = models.OneToOneField(
        'tesoreria.MovimientoBancario', null=True, blank=True,
        on_delete=models.PROTECT, related_name='anticipo_laboral',
        verbose_name='Movimiento de pago',
    )

    class Meta:
        verbose_name = 'Anticipo Laboral'
        verbose_name_plural = 'Anticipos Laborales'
        ordering = ['-fecha']

    def __str__(self):
        return f'Anticipo {self.trabajador.nombre_completo} - ${self.monto:,.0f} ({self.fecha})'


class HistorialLaboral(TimeStampedModel):
    TIPO_CHOICES = [
        ('ingreso', 'Ingreso'),
        ('cambio_cargo', 'Cambio de Cargo'),
        ('cambio_sueldo', 'Cambio de Sueldo'),
        ('licencia', 'Licencia Médica'),
        ('vacaciones', 'Vacaciones'),
        ('amonestacion', 'Amonestación'),
        ('finiquito', 'Finiquito'),
        ('otro', 'Otro'),
    ]

    trabajador = models.ForeignKey(
        Trabajador, on_delete=models.CASCADE,
        related_name='historial', verbose_name='Trabajador'
    )
    fecha = models.DateField(verbose_name='Fecha')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, verbose_name='Tipo de Evento')
    descripcion = models.TextField(verbose_name='Descripción')

    class Meta:
        verbose_name = 'Historial Laboral'
        verbose_name_plural = 'Historial Laboral'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.trabajador.nombre_completo} | {self.get_tipo_display()} | {self.fecha}'
