from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import PlanCuentas, ConfiguracionContable
from apps.tesoreria.models import Banco, CuentaBancaria
from .models import Cliente, FacturaEmitida, CuentaPorCobrar


def _setup_contabilidad():
    """Crea Plan de Cuentas + ConfiguracionContable mínimos."""
    cta_banco = PlanCuentas.objects.create(codigo='1.1.01', nombre='Banco', tipo='activo', nivel=1)
    cta_cxc = PlanCuentas.objects.create(codigo='1.1.02', nombre='Clientes Nacionales', tipo='activo', nivel=1)
    cta_ventas = PlanCuentas.objects.create(codigo='4.1.01', nombre='Ventas', tipo='ingreso', nivel=1)
    cta_iva = PlanCuentas.objects.create(codigo='2.1.01', nombre='IVA Débito', tipo='pasivo', nivel=1)
    config = ConfiguracionContable.get()
    config.cuenta_cxc = cta_cxc
    config.cuenta_iva_debito = cta_iva
    config.cuenta_ventas_default = cta_ventas
    config.save()
    return cta_banco, cta_cxc


def _make_cuenta_bancaria(cta_banco):
    banco = Banco.objects.create(nombre='Banco Chile', codigo='BC')
    return CuentaBancaria.objects.create(
        banco=banco, numero='11111', tipo='corriente',
        saldo_inicial=Decimal('5000000'),
        cuenta_contable=cta_banco,
    )


class FacturaEmitidaModelTest(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            rut='76.000.001-1', razon_social='Cliente Test',
        )

    def test_save_calcula_iva_y_total(self):
        f = FacturaEmitida(
            numero='F-001',
            fecha_emision=timezone.now().date(),
            fecha_vencimiento=timezone.now().date(),
            cliente=self.cliente,
            neto=Decimal('100000'),
            estado='pendiente',
        )
        f.save()
        self.assertEqual(f.iva, Decimal('19000.00'))
        self.assertEqual(f.total, Decimal('119000.00'))

    def test_save_redondea_centavos(self):
        f = FacturaEmitida(
            numero='F-002',
            fecha_emision=timezone.now().date(),
            fecha_vencimiento=timezone.now().date(),
            cliente=self.cliente,
            neto=Decimal('100001'),
            estado='pendiente',
        )
        f.save()
        self.assertEqual(f.iva, Decimal('19000.19'))
        self.assertEqual(f.total, f.neto + f.iva)


class CxCPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('tester', password='pass')
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, cta_cxc = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)

        self.cliente = Cliente.objects.create(
            rut='76.000.002-K', razon_social='Empresa ABC',
        )
        f = FacturaEmitida.objects.create(
            numero='F-100',
            fecha_emision=timezone.now().date(),
            fecha_vencimiento=timezone.now().date(),
            cliente=self.cliente,
            neto=Decimal('100000'),
            estado='pendiente',
        )
        self.cxc = CuentaPorCobrar.objects.create(
            factura=f,
            fecha_vencimiento=f.fecha_vencimiento,
            monto=f.total,
            estado='pendiente',
        )
        self.url = reverse('clientes:cxc_pagar', args=[self.cxc.pk])

    def test_get_muestra_formulario(self):
        resp = self.client_http.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Registrar Cobro')

    def test_get_redirige_si_ya_pagada(self):
        self.cxc.estado = 'pagada'
        self.cxc.save()
        resp = self.client_http.get(self.url)
        self.assertRedirects(resp, reverse('clientes:cxc_list'), fetch_redirect_response=False)

    def test_post_invalido_vuelve_al_form(self):
        resp = self.client_http.post(self.url, {})
        self.assertEqual(resp.status_code, 200)

    def test_post_valido_actualiza_cxc_y_factura(self):
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'monto_cobrado': '119000',
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'medio_cobro': 'transferencia',
            'numero_documento': 'TRF-001',
            'notas': '',
        }
        resp = self.client_http.post(self.url, data)
        self.assertRedirects(resp, reverse('clientes:cxc_list'), fetch_redirect_response=False)

        self.cxc.refresh_from_db()
        self.assertEqual(self.cxc.estado, 'pagada')
        self.assertEqual(self.cxc.medio_cobro, 'transferencia')
        self.assertEqual(self.cxc.numero_documento, 'TRF-001')

        self.cxc.factura.refresh_from_db()
        self.assertEqual(self.cxc.factura.estado, 'pagada')

    def test_post_crea_movimiento_bancario_ingreso(self):
        from apps.tesoreria.models import MovimientoBancario
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'monto_cobrado': '119000',
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'medio_cobro': 'transferencia',
            'numero_documento': '',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        mov = MovimientoBancario.objects.filter(tipo='ingreso').last()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.monto, Decimal('119000'))
        self.assertEqual(mov.cuenta, self.cuenta_bancaria)

    def test_post_genera_asiento_contable(self):
        from apps.contabilidad.models import AsientoContable
        # Asignar cuenta_contable de contrapartida (CxC) a config
        config = ConfiguracionContable.get()
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'monto_cobrado': '119000',
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'medio_cobro': 'efectivo',
            'numero_documento': '',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.assertTrue(AsientoContable.objects.filter(tipo='movimiento_banco').exists())

    def test_login_requerido(self):
        c = Client()
        resp = c.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('login', resp['Location'])
