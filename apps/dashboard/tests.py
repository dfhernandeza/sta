from datetime import date
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.clientes.models import Cliente, FacturaEmitida
from apps.contabilidad.models import (
    AsientoContable,
    ConfiguracionContable,
    LineaAsiento,
    PlanCuentas,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class DashboardPeriodoTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'admin_dashboard',
            'dashboard@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        self.cliente = Cliente.objects.create(
            rut='11.111.111-1',
            razon_social='Cliente Dashboard',
        )
        self.cuenta_cxc = PlanCuentas.objects.create(
            codigo='TEST.DASH.CXC',
            nombre='CxC Dashboard',
            tipo='activo',
            nivel=4,
        )
        self.cuenta_ingreso = PlanCuentas.objects.create(
            codigo='TEST.DASH.ING',
            nombre='Ingreso Dashboard',
            tipo='ingreso',
            nivel=4,
        )
        self.cuenta_gasto = PlanCuentas.objects.create(
            codigo='TEST.DASH.GAS',
            nombre='Gasto Dashboard',
            tipo='gasto',
            nivel=4,
        )
        self.cuenta_cxp = PlanCuentas.objects.create(
            codigo='TEST.DASH.CXP',
            nombre='CxP Dashboard',
            tipo='pasivo',
            nivel=4,
        )
        self.cuenta_documentos = PlanCuentas.objects.create(
            codigo='TEST.DASH.DOC',
            nombre='Documentos por pagar Dashboard',
            tipo='pasivo',
            nivel=4,
        )
        config = ConfiguracionContable.get()
        config.cuenta_cxc = self.cuenta_cxc
        config.cuenta_cxp = self.cuenta_cxp
        config.cuenta_documentos_por_pagar = self.cuenta_documentos
        config.save(update_fields=[
            'cuenta_cxc',
            'cuenta_cxp',
            'cuenta_documentos_por_pagar',
        ])

        self.apertura = AsientoContable.objects.create(
            fecha=date(2026, 6, 15),
            descripcion='Saldos de Apertura',
            tipo='apertura',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=self.apertura,
            cuenta=self.cuenta_cxc,
            debe=Decimal('100000'),
            haber=Decimal('0'),
            descripcion='Saldo de apertura',
            orden=1,
        )

    def crear_factura(self, numero, fecha_emision, total):
        neto = (total / Decimal('1.19')).quantize(Decimal('0.01'))
        return FacturaEmitida.objects.create(
            numero=numero,
            fecha_emision=fecha_emision,
            fecha_vencimiento=fecha_emision,
            cliente=self.cliente,
            neto=neto,
            iva=total - neto,
            total=total,
            estado='pendiente',
        )

    def test_kpi_usa_asientos_y_facturas_solo_para_contador(self):
        self.crear_factura('MAYO', date(2026, 5, 20), Decimal('10000'))
        self.crear_factura('JUNIO-ANTES', date(2026, 6, 10), Decimal('20000'))
        self.crear_factura('JUNIO-DESPUES', date(2026, 6, 20), Decimal('30000'))
        self.crear_factura('JULIO', date(2026, 7, 1), Decimal('40000'))
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 6, 20),
            descripcion='Ingreso manual',
            tipo='ajuste',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_ingreso,
            haber=Decimal('45000'),
        )
        asiento_borrador = AsientoContable.objects.create(
            fecha=date(2026, 6, 21),
            descripcion='Ingreso no confirmado',
            tipo='ajuste',
            estado='borrador',
        )
        LineaAsiento.objects.create(
            asiento=asiento_borrador,
            cuenta=self.cuenta_ingreso,
            haber=Decimal('90000'),
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ingresos_mes'], Decimal('45000'))
        self.assertEqual(response.context['facturas_emitidas_mes'], 1)
        self.assertEqual(response.context['periodo_seleccionado'], '2026-06')

    def test_incluye_ingresos_egresos_manuales_y_reversos(self):
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 6, 25),
            descripcion='Resultado manual',
            tipo='ajuste',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_ingreso,
            haber=Decimal('100000'),
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_ingreso,
            debe=Decimal('10000'),
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_gasto,
            debe=Decimal('40000'),
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_gasto,
            haber=Decimal('5000'),
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(response.context['ingresos_mes'], Decimal('90000'))
        self.assertEqual(response.context['egresos_mes'], Decimal('35000'))
        self.assertEqual(response.context['utilidad_mes'], Decimal('55000'))

    def test_cxp_incluye_cuenta_documentos_por_pagar(self):
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 6, 25),
            descripcion='Pasivos pendientes',
            tipo='ajuste',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_cxp,
            haber=Decimal('30000'),
        )
        LineaAsiento.objects.create(
            asiento=asiento,
            cuenta=self.cuenta_documentos,
            haber=Decimal('20000'),
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(
            response.context['total_cxp_pendiente'],
            Decimal('50000'),
        )

    def test_resumen_contable_se_calcula_al_cierre_del_mes(self):
        asiento_julio = AsientoContable.objects.create(
            fecha=date(2026, 7, 1),
            descripcion='Movimiento julio',
            tipo='ajuste',
            estado='confirmado',
        )
        LineaAsiento.objects.create(
            asiento=asiento_julio,
            cuenta=self.cuenta_cxc,
            debe=Decimal('50000'),
            haber=Decimal('0'),
            descripcion='Movimiento posterior',
            orden=1,
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(
            response.context['total_cxc_pendiente'],
            Decimal('100000'),
        )

    def test_periodo_anterior_a_apertura_no_muestra_datos(self):
        self.crear_factura('MAYO', date(2026, 5, 20), Decimal('10000'))

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-05'},
        )

        self.assertTrue(response.context['periodo_fuera_sistema'])
        self.assertEqual(response.context['ingresos_mes'], 0)
        self.assertEqual(response.context['total_cxc_pendiente'], Decimal('0'))

# Create your tests here.
