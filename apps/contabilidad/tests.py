from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import (
    PlanCuentas,
    ConfiguracionContable,
    AsientoContable,
    LineaAsiento,
    CentroCosto,
)
from apps.contabilidad.utils import generar_asiento_movimiento_bancario
from apps.tesoreria.models import Banco, CuentaBancaria, MovimientoBancario


def make_cuenta(codigo, nombre, tipo='activo'):
    return PlanCuentas.objects.create(codigo=codigo, nombre=nombre, tipo=tipo, nivel=1)


def make_config(**kwargs):
    obj = ConfiguracionContable.get()
    for k, v in kwargs.items():
        setattr(obj, k, v)
    obj.save()
    return obj


def make_banco_y_cuenta(cuenta_contable=None):
    banco = Banco.objects.create(nombre='Banco Test', codigo='BT')
    return CuentaBancaria.objects.create(
        banco=banco, numero='000001', tipo='corriente',
        saldo_inicial=Decimal('10000000'),
        cuenta_contable=cuenta_contable,
    )


class AsientoMovimientoIngresoTest(TestCase):
    """generar_asiento_movimiento_bancario — tipo ingreso."""

    def setUp(self):
        self.user = CustomUser.objects.create_user('tester', password='x')
        self.cta_banco = make_cuenta('1.1.01', 'Banco Corriente')
        self.cta_cxc = make_cuenta('1.1.02', 'Clientes Nacionales')
        self.cuenta_bancaria = make_banco_y_cuenta(cuenta_contable=self.cta_banco)

    def _movimiento(self, cuenta_contable):
        return MovimientoBancario.objects.create(
            cuenta=self.cuenta_bancaria,
            fecha=timezone.now().date(),
            tipo='ingreso',
            monto=Decimal('119000'),
            descripcion='Cobro Factura 001',
            cuenta_contable=cuenta_contable,
        )

    def test_retorna_none_sin_cuenta_contable_banco(self):
        """Sin cuenta_contable en CuentaBancaria no genera asiento."""
        cb = CuentaBancaria.objects.create(
            banco=self.cuenta_bancaria.banco, numero='000002', tipo='corriente',
            saldo_inicial=0, cuenta_contable=None,
        )
        mov = MovimientoBancario.objects.create(
            cuenta=cb, fecha=timezone.now().date(), tipo='ingreso',
            monto=100, descripcion='test', cuenta_contable=self.cta_cxc,
        )
        self.assertIsNone(generar_asiento_movimiento_bancario(mov))

    def test_retorna_none_sin_cuenta_contable_contrapartida(self):
        mov = self._movimiento(cuenta_contable=None)
        self.assertIsNone(generar_asiento_movimiento_bancario(mov))

    def test_genera_asiento_ingreso(self):
        mov = self._movimiento(cuenta_contable=self.cta_cxc)
        asiento = generar_asiento_movimiento_bancario(mov, usuario=self.user)

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.estado, 'borrador')
        self.assertEqual(asiento.tipo, 'movimiento_banco')

        lineas = asiento.lineas.all()
        self.assertEqual(lineas.count(), 2)

        debe_linea = lineas.filter(debe__gt=0).first()
        haber_linea = lineas.filter(haber__gt=0).first()

        self.assertEqual(debe_linea.cuenta, self.cta_banco)
        self.assertEqual(debe_linea.debe, Decimal('119000'))
        self.assertEqual(haber_linea.cuenta, self.cta_cxc)
        self.assertEqual(haber_linea.haber, Decimal('119000'))

    def test_genera_asiento_egreso(self):
        cta_sueldos = make_cuenta('4.1.01', 'Sueldos', 'gasto')
        mov = MovimientoBancario.objects.create(
            cuenta=self.cuenta_bancaria,
            fecha=timezone.now().date(),
            tipo='egreso',
            monto=Decimal('500000'),
            descripcion='Pago remuneración',
            cuenta_contable=cta_sueldos,
        )
        asiento = generar_asiento_movimiento_bancario(mov, usuario=self.user)

        lineas = asiento.lineas.all()
        debe_linea = lineas.filter(debe__gt=0).first()
        haber_linea = lineas.filter(haber__gt=0).first()

        self.assertEqual(debe_linea.cuenta, cta_sueldos)
        self.assertEqual(haber_linea.cuenta, self.cta_banco)

    def test_cuadre_debe_igual_haber(self):
        mov = self._movimiento(cuenta_contable=self.cta_cxc)
        asiento = generar_asiento_movimiento_bancario(mov)
        total_debe = sum(l.debe for l in asiento.lineas.all())
        total_haber = sum(l.haber for l in asiento.lineas.all())
        self.assertEqual(total_debe, total_haber)


class ConfiguracionContableSingletonTest(TestCase):
    def test_pk_siempre_1(self):
        c1 = ConfiguracionContable.get()
        c1.save()
        self.assertEqual(ConfiguracionContable.objects.count(), 1)
        self.assertEqual(c1.pk, 1)

    def test_get_crea_si_no_existe(self):
        self.assertEqual(ConfiguracionContable.objects.count(), 0)
        obj = ConfiguracionContable.get()
        self.assertIsNotNone(obj)
        self.assertEqual(ConfiguracionContable.objects.count(), 1)


class InformeCentroCostoTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'informe-centro-costo',
            password='x',
        )
        self.client.force_login(self.user)
        self.centro = CentroCosto.objects.create(
            codigo='ADM',
            nombre='Administración',
            presupuesto_mensual=Decimal('1000.00'),
        )
        self.cuenta = make_cuenta('4.1.99', 'Gastos manuales', 'gasto')
        self.cuenta_ingreso = make_cuenta('3.1.99', 'Ingresos manuales', 'ingreso')

    def crear_linea(self, fecha, estado, debe=0, haber=0, cuenta=None):
        asiento = AsientoContable.objects.create(
            fecha=fecha,
            descripcion='Movimiento manual',
            tipo='otro',
            estado=estado,
        )
        return LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=cuenta or self.cuenta,
            centro_costo=self.centro,
            debe=Decimal(str(debe)),
            haber=Decimal(str(haber)),
        )

    def test_clasifica_ingresos_y_egresos_desde_asientos_confirmados(self):
        self.crear_linea('2026-06-10', 'confirmado', debe='500.00')
        self.crear_linea('2026-06-11', 'confirmado', haber='125.00')
        self.crear_linea(
            '2026-06-11',
            'confirmado',
            haber='800.00',
            cuenta=self.cuenta_ingreso,
        )
        self.crear_linea(
            '2026-06-11',
            'confirmado',
            debe='50.00',
            cuenta=self.cuenta_ingreso,
        )
        self.crear_linea('2026-06-12', 'borrador', debe='900.00')

        response = self.client.get(reverse('contabilidad:centro_reporte'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['informe']), 1)
        fila = response.context['informe'][0]
        self.assertEqual(fila['ingresos'], Decimal('750.00'))
        self.assertEqual(fila['egresos'], Decimal('375.00'))
        self.assertEqual(fila['resultado'], Decimal('375.00'))
        self.assertEqual(fila['diferencia'], Decimal('625.00'))

    def test_filtra_por_fecha_del_asiento(self):
        self.crear_linea('2026-05-31', 'confirmado', debe='100.00')
        self.crear_linea('2026-06-01', 'confirmado', debe='250.00')

        response = self.client.get(
            reverse('contabilidad:centro_reporte'),
            {'fecha_desde': '2026-06-01', 'fecha_hasta': '2026-06-30'},
        )

        self.assertEqual(response.context['total_egresos'], Decimal('250.00'))


class AsientoDetailViewTest(TestCase):
    def test_muestra_centro_costo_de_cada_linea(self):
        user = CustomUser.objects.create_superuser(
            'detalle-asiento',
            password='x',
        )
        self.client.force_login(user)
        cuenta = make_cuenta('4.1.98', 'Gasto con centro', 'gasto')
        centro = CentroCosto.objects.create(
            codigo='OPE',
            nombre='Operaciones',
        )
        asiento = AsientoContable.objects.create(
            fecha='2026-07-02',
            descripcion='Asiento con centro de costo',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=cuenta,
            centro_costo=centro,
            debe=Decimal('1000.00'),
        )

        response = self.client.get(
            reverse('contabilidad:asiento_detail', kwargs={'pk': asiento.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'OPE')
        self.assertContains(response, 'Operaciones')
