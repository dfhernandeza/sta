from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import PlanCuentas, ConfiguracionContable
from apps.tesoreria.models import Banco, CuentaBancaria
from .models import FormularioF29, PPM, DeclaracionIVA


def _setup_contabilidad():
    cta_banco = PlanCuentas.objects.create(codigo='1.1.01', nombre='Banco', tipo='activo', nivel=1)
    cta_sii = PlanCuentas.objects.create(codigo='2.1.05', nombre='Impuestos SII', tipo='pasivo', nivel=1)
    config = ConfiguracionContable.get()
    config.cuenta_impuestos_sii = cta_sii
    config.save()
    return cta_banco, cta_sii


def _make_cuenta_bancaria(cta_banco):
    banco = Banco.objects.create(nombre='BancoTrib', codigo='BTR')
    return CuentaBancaria.objects.create(
        banco=banco, numero='44444', tipo='corriente',
        saldo_inicial=Decimal('20000000'),
        cuenta_contable=cta_banco,
    )


class DeclaracionIVAModelTest(TestCase):
    def test_diferencia_calculada_en_save(self):
        d = DeclaracionIVA(
            periodo_mes=3, periodo_anio=2026,
            iva_debito=Decimal('500000'),
            iva_credito=Decimal('200000'),
        )
        d.save()
        self.assertEqual(d.diferencia, Decimal('300000'))

    def test_diferencia_no_negativa(self):
        d = DeclaracionIVA(
            periodo_mes=4, periodo_anio=2026,
            iva_debito=Decimal('100000'),
            iva_credito=Decimal('300000'),
        )
        d.save()
        self.assertEqual(d.diferencia, Decimal('0'))


class F29ModelTest(TestCase):
    def test_total_pagar_calculado(self):
        f = FormularioF29(
            periodo_mes=3, periodo_anio=2026,
            iva_pagar=Decimal('300000'),
            ppm_pagar=Decimal('50000'),
            retenciones=Decimal('10000'),
        )
        f.save()
        self.assertEqual(f.total_pagar, Decimal('340000'))


@override_settings(SECURE_SSL_REDIRECT=False)
class F29PagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('trib_user', password='pass')
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)

        self.f29 = FormularioF29.objects.create(
            periodo_mes=5, periodo_anio=2026,
            iva_pagar=Decimal('200000'),
            ppm_pagar=Decimal('30000'),
            retenciones=Decimal('0'),
            estado='pendiente',
        )
        self.url = reverse('tributario:f29_pagar', args=[self.f29.pk])

    def test_get_muestra_formulario(self):
        resp = self.client_http.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'F29')

    def test_get_redirige_si_ya_pagado(self):
        self.f29.estado = 'pagado'
        self.f29.save()
        resp = self.client_http.get(self.url)
        self.assertRedirects(resp, reverse('tributario:f29_list'), fetch_redirect_response=False)

    def test_post_invalido_vuelve_al_form(self):
        resp = self.client_http.post(self.url, {})
        self.assertEqual(resp.status_code, 200)

    def test_post_valido_marca_pagado(self):
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'folio': 'F29-001',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.f29.refresh_from_db()
        self.assertEqual(self.f29.estado, 'pagado')
        self.assertEqual(self.f29.folio, 'F29-001')

    def test_post_crea_movimiento_por_total_pagar(self):
        from apps.tesoreria.models import MovimientoBancario
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'folio': '',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        mov = MovimientoBancario.objects.filter(tipo='egreso').last()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.monto, Decimal('230000'))  # 200000 + 30000

    def test_post_genera_asiento(self):
        from apps.contabilidad.models import AsientoContable
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'folio': '',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.assertTrue(AsientoContable.objects.filter(tipo='movimiento_banco').exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class PPMPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('ppm_user', password='pass')
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)
        # Crear con número distinto para evitar unique_together
        self.cuenta_bancaria.pk = None
        self.cuenta_bancaria.numero = '55555'
        self.cuenta_bancaria.save()

        self.ppm = PPM.objects.create(
            periodo_mes=5, periodo_anio=2026,
            base_imponible=Decimal('2000000'),
            tasa=Decimal('0.0025'),
            monto=Decimal('5000'),
            estado='pendiente',
        )
        self.url = reverse('tributario:ppm_pagar', args=[self.ppm.pk])

    def test_get_muestra_formulario(self):
        resp = self.client_http.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_redirige_si_ya_pagado(self):
        self.ppm.estado = 'pagado'
        self.ppm.save()
        resp = self.client_http.get(self.url)
        self.assertRedirects(resp, reverse('tributario:ppm_list'), fetch_redirect_response=False)

    def test_post_valido_marca_pagado(self):
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.ppm.refresh_from_db()
        self.assertEqual(self.ppm.estado, 'pagado')

    def test_post_crea_movimiento_por_monto_ppm(self):
        from apps.tesoreria.models import MovimientoBancario
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        mov = MovimientoBancario.objects.filter(tipo='egreso').last()
        self.assertEqual(mov.monto, Decimal('5000'))
