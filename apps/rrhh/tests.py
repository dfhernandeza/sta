from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import PlanCuentas, ConfiguracionContable
from apps.tesoreria.models import Banco, CuentaBancaria
from .models import Trabajador, Remuneracion, AnticipoLaboral


def _setup_contabilidad():
    cta_banco = PlanCuentas.objects.create(codigo='1.1.01', nombre='Banco', tipo='activo', nivel=1)
    cta_sueldos = PlanCuentas.objects.create(codigo='4.1.01', nombre='Sueldos', tipo='gasto', nivel=1)
    config = ConfiguracionContable.get()
    config.cuenta_sueldos_administrativo = cta_sueldos
    config.cuenta_sueldos_operacional = cta_sueldos
    config.save()
    return cta_banco, cta_sueldos


def _make_cuenta_bancaria(cta_banco):
    banco = Banco.objects.create(nombre='BancoRRHH', codigo='BRH')
    return CuentaBancaria.objects.create(
        banco=banco, numero='22222', tipo='corriente',
        saldo_inicial=Decimal('10000000'),
        cuenta_contable=cta_banco,
    )


def _make_trabajador():
    return Trabajador.objects.create(
        rut='12.345.678-9',
        nombres='Juan', apellidos='Pérez',
        cargo='Desarrollador',
        fecha_ingreso=timezone.now().date(),
        sueldo_base=Decimal('1000000'),
    )


class RemuneracionPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('tester_rrhh', password='pass')
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)
        self.trabajador = _make_trabajador()

        self.rem = Remuneracion.objects.create(
            trabajador=self.trabajador,
            periodo_mes=1, periodo_anio=2026,
            sueldo_base=Decimal('1000000'),
            sueldo_bruto=Decimal('1000000'),
            liquido_pagar=Decimal('850000'),
            estado='borrador',
        )
        self.url = reverse('rrhh:remuneracion_pagar', args=[self.rem.pk])

    def test_get_muestra_formulario(self):
        resp = self.client_http.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Registrar Pago')

    def test_get_redirige_si_ya_pagado(self):
        self.rem.estado = 'pagado'
        self.rem.save()
        resp = self.client_http.get(self.url)
        self.assertRedirects(resp, reverse('rrhh:remuneracion_list'), fetch_redirect_response=False)

    def test_post_invalido_vuelve_al_form(self):
        resp = self.client_http.post(self.url, {})
        self.assertEqual(resp.status_code, 200)

    def test_post_valido_marca_pagado(self):
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.rem.refresh_from_db()
        self.assertEqual(self.rem.estado, 'pagado')
        self.assertEqual(self.rem.fecha_pago, timezone.now().date())

    def test_post_crea_movimiento_egreso(self):
        from apps.tesoreria.models import MovimientoBancario
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        mov = MovimientoBancario.objects.filter(tipo='egreso').last()
        self.assertIsNotNone(mov)
        self.assertEqual(mov.monto, Decimal('850000'))

    def test_post_genera_asiento(self):
        from apps.contabilidad.models import AsientoContable
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.assertTrue(AsientoContable.objects.filter(tipo='movimiento_banco').exists())


class AnticipoLaboralPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user('tester_ant', password='pass')
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)
        # Banco ya existe, reusar con número diferente
        self.cuenta_bancaria.numero = '33333'
        self.cuenta_bancaria.pk = None
        self.cuenta_bancaria.save()

        self.trabajador = Trabajador.objects.create(
            rut='98.765.432-1',
            nombres='Ana', apellidos='López',
            cargo='Contadora',
            fecha_ingreso=timezone.now().date(),
            sueldo_base=Decimal('900000'),
        )
        self.anticipo = AnticipoLaboral.objects.create(
            trabajador=self.trabajador,
            fecha=timezone.now().date(),
            monto=Decimal('200000'),
            estado='pendiente',
        )
        self.url = reverse('rrhh:anticipo_pagar', args=[self.anticipo.pk])

    def test_get_muestra_formulario(self):
        resp = self.client_http.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_get_redirige_si_ya_descontado(self):
        self.anticipo.estado = 'descontado'
        self.anticipo.save()
        resp = self.client_http.get(self.url)
        self.assertRedirects(resp, reverse('rrhh:anticipo_list'), fetch_redirect_response=False)

    def test_post_valido_marca_descontado(self):
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.anticipo.refresh_from_db()
        self.assertEqual(self.anticipo.estado, 'descontado')

    def test_post_crea_movimiento_egreso_por_monto_anticipo(self):
        from apps.tesoreria.models import MovimientoBancario
        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        mov = MovimientoBancario.objects.filter(tipo='egreso').last()
        self.assertEqual(mov.monto, Decimal('200000'))
