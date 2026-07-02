from decimal import Decimal
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable, PlanCuentas, ConfiguracionContable
from apps.tesoreria.models import Banco, CuentaBancaria
from .models import FormularioF29, PPM, DeclaracionIVA


def _setup_contabilidad():
    cta_banco = PlanCuentas.objects.create(codigo='1.1.01', nombre='Banco', tipo='activo', nivel=1)
    cta_iva_credito = PlanCuentas.objects.create(
        codigo='1.1.02', nombre='IVA Crédito Fiscal', tipo='activo', nivel=1
    )
    cta_ppm = PlanCuentas.objects.create(
        codigo='1.1.03', nombre='PPM por Recuperar', tipo='activo', nivel=1
    )
    cta_iva_debito = PlanCuentas.objects.create(
        codigo='2.1.04', nombre='IVA Débito Fiscal', tipo='pasivo', nivel=1
    )
    cta_sii = PlanCuentas.objects.create(codigo='2.1.05', nombre='Impuestos SII', tipo='pasivo', nivel=1)
    config = ConfiguracionContable.get()
    config.cuenta_iva_credito = cta_iva_credito
    config.cuenta_iva_debito = cta_iva_debito
    config.cuenta_impuestos_sii = cta_sii
    config.cuenta_ppm = cta_ppm
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


@override_settings(SECURE_SSL_REDIRECT=False)
class DeclaracionIVAContabilizacionTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'iva_admin',
            'iva-admin@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        _, self.cuenta_sii = _setup_contabilidad()

    def _crear_presentada(self, debito='500000', credito='200000', mes='5'):
        return self.client_http.post(
            reverse('tributario:iva_create'),
            {
                'periodo_mes': mes,
                'periodo_anio': '2026',
                'iva_debito': debito,
                'iva_credito': credito,
                'estado': 'presentado',
                'fecha_presentacion': '',
            },
        )

    def test_crear_presentada_genera_centralizacion_borrador(self):
        response = self._crear_presentada()

        self.assertRedirects(response, reverse('tributario:iva_list'))
        declaracion = DeclaracionIVA.objects.get(periodo_mes=5, periodo_anio=2026)
        asiento = declaracion.asientos.get(tipo='centralizacion_iva')
        self.assertEqual(asiento.estado, 'borrador')
        self.assertEqual(asiento.total_debe, Decimal('500000.00'))
        self.assertEqual(asiento.total_haber, Decimal('500000.00'))
        self.assertEqual(
            asiento.lineas.get(cuenta=self.cuenta_sii).haber,
            Decimal('300000.00'),
        )

    def test_crear_borrador_no_genera_asiento(self):
        response = self.client_http.post(
            reverse('tributario:iva_create'),
            {
                'periodo_mes': '5',
                'periodo_anio': '2026',
                'iva_debito': '500000',
                'iva_credito': '200000',
                'estado': 'borrador',
                'fecha_presentacion': '',
            },
        )

        self.assertRedirects(response, reverse('tributario:iva_list'))
        self.assertFalse(
            AsientoContable.objects.filter(tipo='centralizacion_iva').exists()
        )

    def test_remanente_credito_no_genera_impuesto_por_pagar(self):
        self._crear_presentada(debito='100000', credito='300000')

        declaracion = DeclaracionIVA.objects.get(periodo_mes=5, periodo_anio=2026)
        asiento = declaracion.asientos.get(tipo='centralizacion_iva')
        self.assertEqual(asiento.total_debe, Decimal('100000.00'))
        self.assertEqual(asiento.total_haber, Decimal('100000.00'))
        self.assertFalse(asiento.lineas.filter(cuenta=self.cuenta_sii).exists())

    def test_dashboard_muestra_deuda_despues_de_confirmar(self):
        self._crear_presentada()
        asiento = AsientoContable.objects.get(tipo='centralizacion_iva')
        asiento.estado = 'confirmado'
        asiento.save(update_fields=['estado'])

        response = self.client_http.get(
            reverse('dashboard:index'),
            {'periodo': '2026-05'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['impuestos_sii_por_pagar'],
            Decimal('300000.00'),
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class PPMContabilizacionTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'ppm_contable',
            'ppm-contable@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        _setup_contabilidad()

    def _crear(self, estado):
        return self.client_http.post(
            reverse('tributario:ppm_create'),
            {
                'periodo_mes': '6',
                'periodo_anio': '2026',
                'base_imponible': '12000000',
                'tasa': '0.0025',
                'monto': '30000',
                'estado': estado,
            },
        )

    def test_crear_pendiente_no_genera_asiento(self):
        response = self._crear('pendiente')

        self.assertRedirects(response, reverse('tributario:ppm_list'))
        ppm = PPM.objects.get(periodo_mes=6, periodo_anio=2026)
        self.assertFalse(ppm.asientos.exists())

    def test_crear_presentado_genera_devengamiento_y_sincroniza_f29(self):
        f29 = FormularioF29.objects.create(
            periodo_mes=6,
            periodo_anio=2026,
            estado='pendiente',
        )

        response = self._crear('presentado')

        self.assertRedirects(response, reverse('tributario:ppm_list'))
        ppm = PPM.objects.get(periodo_mes=6, periodo_anio=2026)
        asiento = ppm.asientos.get(tipo='devengamiento_ppm')
        config = ConfiguracionContable.get()
        self.assertEqual(asiento.estado, 'borrador')
        self.assertEqual(
            asiento.lineas.get(cuenta=config.cuenta_ppm).debe,
            Decimal('30000.00'),
        )
        self.assertEqual(
            asiento.lineas.get(cuenta=config.cuenta_impuestos_sii).haber,
            Decimal('30000.00'),
        )
        f29.refresh_from_db()
        self.assertEqual(f29.ppm_pagar, Decimal('30000.00'))
        self.assertEqual(f29.total_pagar, Decimal('30000.00'))


class F29ModelTest(TestCase):
    def test_total_pagar_calculado(self):
        f = FormularioF29(
            periodo_mes=3, periodo_anio=2026,
            iva_pagar=Decimal('300000'),
            ppm_pagar=Decimal('50000'),
            retenciones=Decimal('10000'),
        )
        f.save()
        self.assertEqual(f.total_pagar, Decimal('360000'))


@override_settings(SECURE_SSL_REDIRECT=False)
class F29PagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'trib_user',
            'trib-user@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)

        self.f29 = FormularioF29.objects.create(
            periodo_mes=5, periodo_anio=2026,
            iva_pagar=Decimal('200000'),
            ppm_pagar=Decimal('30000'),
            retenciones=Decimal('0'),
            estado='presentado',
        )
        self.declaracion = DeclaracionIVA.objects.create(
            periodo_mes=5,
            periodo_anio=2026,
            iva_debito=Decimal('300000'),
            iva_credito=Decimal('100000'),
            estado='presentado',
        )
        self.ppm = PPM.objects.create(
            periodo_mes=5,
            periodo_anio=2026,
            base_imponible=Decimal('12000000'),
            tasa=Decimal('0.0025'),
            monto=Decimal('30000'),
            estado='presentado',
        )
        from apps.contabilidad.utils import (
            generar_asiento_declaracion_iva,
            generar_asiento_devengamiento_ppm,
        )
        for asiento in [
            generar_asiento_declaracion_iva(self.declaracion),
            generar_asiento_devengamiento_ppm(self.ppm),
        ]:
            asiento.estado = 'confirmado'
            asiento.save(update_fields=['estado'])
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
        self.declaracion.refresh_from_db()
        self.ppm.refresh_from_db()
        self.assertEqual(self.f29.estado, 'pagado')
        self.assertEqual(self.f29.folio, 'F29-001')
        self.assertEqual(self.declaracion.estado, 'pagado')
        self.assertEqual(self.ppm.estado, 'pagado')
        self.assertEqual(self.ppm.fecha_pago, timezone.now().date())

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
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'folio': '',
            'notas': '',
        }
        self.client_http.post(self.url, data)
        asiento = AsientoContable.objects.get(tipo='pago_f29')
        config = ConfiguracionContable.get()
        self.assertEqual(asiento.total_debe, Decimal('230000'))
        self.assertEqual(asiento.total_haber, Decimal('230000'))
        self.assertEqual(
            asiento.lineas.get(cuenta=config.cuenta_impuestos_sii).debe,
            Decimal('230000'),
        )
        self.assertEqual(
            self.ppm.asientos.get(
                tipo='devengamiento_ppm',
            ).lineas.get(cuenta=config.cuenta_ppm).debe,
            Decimal('30000'),
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class PPMPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'ppm_user',
            'ppm-user@example.com',
            'pass',
        )
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
            estado='presentado',
        )
        from apps.contabilidad.utils import generar_asiento_devengamiento_ppm
        asiento = generar_asiento_devengamiento_ppm(self.ppm)
        asiento.estado = 'confirmado'
        asiento.save(update_fields=['estado'])
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
        config = ConfiguracionContable.get()
        asiento = mov.asientos.get(tipo='movimiento_banco')
        self.assertEqual(
            asiento.lineas.get(cuenta=config.cuenta_impuestos_sii).debe,
            Decimal('5000'),
        )

    def test_bloquea_pago_separado_si_ppm_esta_incluido_en_f29(self):
        FormularioF29.objects.create(
            periodo_mes=self.ppm.periodo_mes,
            periodo_anio=self.ppm.periodo_anio,
            iva_pagar=Decimal('100000'),
            ppm_pagar=self.ppm.monto,
            retenciones=Decimal('0'),
            estado='presentado',
        )

        response = self.client_http.get(self.url)

        self.assertRedirects(
            response,
            reverse('tributario:f29_list'),
            fetch_redirect_response=False,
        )
        self.ppm.refresh_from_db()
        self.assertEqual(self.ppm.estado, 'presentado')
