from django.db import models
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
    sueldo_base = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Sueldo Base')
    horas_extra = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Horas Extra')
    bono = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name='Bonos')
    sueldo_bruto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Sueldo Bruto')
    descuento_afp = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Descuento AFP')
    descuento_salud = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Descuento Salud')
    impuesto_unico = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Impuesto Único')
    otros_descuentos = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Otros Descuentos')
    anticipo_descontado = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name='Anticipo Descontado')
    liquido_pagar = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='Líquido a Pagar')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='borrador', verbose_name='Estado')
    fecha_pago = models.DateField(null=True, blank=True, verbose_name='Fecha de Pago')

    class Meta:
        verbose_name = 'Remuneración'
        verbose_name_plural = 'Remuneraciones'
        ordering = ['-periodo_anio', '-periodo_mes']
        unique_together = ('trabajador', 'periodo_mes', 'periodo_anio')

    def __str__(self):
        return f'{self.trabajador.nombre_completo} - {self.periodo_mes:02d}/{self.periodo_anio}'

    @property
    def descuentos(self):
        return (
            (self.descuento_afp or 0) +
            (self.descuento_salud or 0) +
            (self.impuesto_unico or 0) +
            (self.otros_descuentos or 0)
        )


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
        on_delete=models.SET_NULL, related_name='anticipo_laboral',
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
