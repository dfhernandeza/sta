from datetime import date
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.clientes.models import Cliente, CuentaPorCobrar, FacturaEmitida
from apps.contabilidad.models import (
    AsientoContable,
    ConfiguracionContable,
    LineaAsiento,
    PlanCuentas,
)
from apps.proveedores.models import (
    CuentaPorPagar,
    FacturaRecibida,
    Proveedor,
)
from apps.tesoreria.models import Banco, CuentaBancaria, MovimientoBancario


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
        banco = Banco.objects.create(nombre='Banco Dashboard', codigo='BDASH')
        self.cuenta_bancaria = CuentaBancaria.objects.create(
            banco=banco,
            numero='123456',
            tipo='corriente',
            saldo_inicial=Decimal('0'),
            cuenta_contable=self.cuenta_cxc,
        )

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

    def crear_movimiento(self, fecha, tipo, monto, descripcion='Movimiento'):
        return MovimientoBancario.objects.create(
            cuenta=self.cuenta_bancaria,
            fecha=fecha,
            tipo=tipo,
            monto=monto,
            descripcion=descripcion,
        )

    def test_kpi_usa_movimientos_bancarios_del_periodo(self):
        self.crear_movimiento(date(2026, 5, 20), 'ingreso', Decimal('10000'))
        self.crear_movimiento(date(2026, 6, 10), 'ingreso', Decimal('20000'))
        self.crear_movimiento(date(2026, 6, 20), 'ingreso', Decimal('45000'))
        self.crear_movimiento(date(2026, 7, 1), 'ingreso', Decimal('40000'))

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['ingresos_mes'], Decimal('45000'))
        self.assertEqual(response.context['periodo_seleccionado'], '2026-06')

    def test_suma_ingresos_y_egresos_bancarios(self):
        self.crear_movimiento(
            date(2026, 6, 25), 'ingreso', Decimal('100000')
        )
        self.crear_movimiento(
            date(2026, 6, 25), 'egreso', Decimal('40000')
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(response.context['ingresos_mes'], Decimal('100000'))
        self.assertEqual(response.context['egresos_mes'], Decimal('40000'))
        self.assertEqual(response.context['utilidad_mes'], Decimal('60000'))

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

    def test_kpi_conciliacion_proyeccion_cxc_vencida_y_runway(self):
        ingreso = self.crear_movimiento(
            date(2026, 6, 20),
            'ingreso',
            Decimal('1000'),
        )
        ingreso.conciliado = True
        ingreso.fecha_conciliacion = date(2026, 6, 21)
        ingreso.save(update_fields=['conciliado', 'fecha_conciliacion'])
        self.crear_movimiento(
            date(2026, 6, 25),
            'egreso',
            Decimal('300'),
        )

        cliente = Cliente.objects.create(
            rut='11.111.111-1',
            razon_social='Cliente KPI',
        )
        factura_vencida = FacturaEmitida.objects.create(
            numero='KPI-VENTA-1',
            fecha_emision=date(2026, 6, 1),
            fecha_vencimiento=date(2026, 6, 10),
            cliente=cliente,
            neto=Decimal('500'),
            iva=Decimal('0'),
            total=Decimal('500'),
        )
        CuentaPorCobrar.objects.create(
            factura=factura_vencida,
            fecha_vencimiento=date(2026, 6, 10),
            monto=Decimal('500'),
            monto_pagado=Decimal('100'),
            estado='vencida',
        )
        factura_proxima = FacturaEmitida.objects.create(
            numero='KPI-VENTA-2',
            fecha_emision=date(2026, 6, 20),
            fecha_vencimiento=date(2026, 7, 15),
            cliente=cliente,
            neto=Decimal('200'),
            iva=Decimal('0'),
            total=Decimal('200'),
        )
        CuentaPorCobrar.objects.create(
            factura=factura_proxima,
            fecha_vencimiento=date(2026, 7, 15),
            monto=Decimal('200'),
            estado='pendiente',
        )

        proveedor = Proveedor.objects.create(
            rut='22.222.222-2',
            razon_social='Proveedor KPI',
        )
        factura_compra = FacturaRecibida.objects.create(
            numero='KPI-COMPRA-1',
            fecha_emision=date(2026, 6, 20),
            fecha_vencimiento=date(2026, 7, 10),
            proveedor=proveedor,
            neto=Decimal('250'),
            iva=Decimal('0'),
            total=Decimal('250'),
        )
        CuentaPorPagar.objects.create(
            factura=factura_compra,
            fecha_vencimiento=date(2026, 7, 10),
            monto=Decimal('250'),
            monto_pagado=Decimal('50'),
            estado='pendiente',
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-06'},
        )

        self.assertEqual(
            response.context['movimientos_sin_conciliar_count'],
            1,
        )
        self.assertEqual(
            response.context['movimientos_sin_conciliar_monto'],
            Decimal('300'),
        )
        self.assertEqual(
            response.context['total_cxc_vencida'],
            Decimal('400'),
        )
        self.assertEqual(
            response.context['proyeccion_caja_30_dias'],
            Decimal('1100'),
        )
        self.assertEqual(
            response.context['promedio_egresos_mensual'],
            Decimal('300'),
        )
        self.assertEqual(response.context['runway_meses'], Decimal('2.3'))

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
        self.crear_movimiento(
            date(2026, 5, 20), 'ingreso', Decimal('10000')
        )

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-05'},
        )

        self.assertTrue(response.context['periodo_fuera_sistema'])
        self.assertEqual(response.context['ingresos_mes'], 0)
        self.assertEqual(response.context['total_cxc_pendiente'], Decimal('0'))

# Create your tests here.
