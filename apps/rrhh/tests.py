from datetime import date
from decimal import Decimal
from django.db.models.deletion import ProtectedError
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable, PlanCuentas, ConfiguracionContable
from apps.tesoreria.models import Banco, CuentaBancaria
from .models import CargoTrabajador, Trabajador, Remuneracion, AnticipoLaboral


def _setup_contabilidad():
    cta_banco = PlanCuentas.objects.create(codigo='TEST.RRHH.BANCO', nombre='Banco', tipo='activo', nivel=1)
    cta_sueldos = PlanCuentas.objects.create(codigo='TEST.RRHH.SUELDOS', nombre='Sueldos', tipo='gasto', nivel=1)
    cta_anticipos = PlanCuentas.objects.create(
        codigo='TEST.RRHH.ANTICIPOS',
        nombre='Anticipos a Trabajadores',
        tipo='activo',
        nivel=1,
    )
    config = ConfiguracionContable.get()
    config.cuenta_sueldos_administrativo = cta_sueldos
    config.cuenta_sueldos_operacional = cta_sueldos
    config.cuenta_anticipos_trabajadores = cta_anticipos
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
    cargo, _ = CargoTrabajador.objects.get_or_create(nombre='Desarrollador')
    return Trabajador.objects.create(
        rut='12.345.678-9',
        nombres='Juan', apellidos='Pérez',
        cargo=cargo,
        fecha_ingreso=timezone.now().date(),
        sueldo_base=Decimal('1000000'),
    )


@override_settings(SECURE_SSL_REDIRECT=False)
class RemuneracionPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            'tester_rrhh',
            password='pass',
            app_permisos=['rrhh'],
        )
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
        self.assertTrue(AsientoContable.objects.filter(tipo='pago_remuneracion').exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class AnticipoLaboralPagarViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            'tester_ant',
            password='pass',
            app_permisos=['rrhh'],
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)

        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)
        # Banco ya existe, reusar con número diferente
        self.cuenta_bancaria.numero = '33333'
        self.cuenta_bancaria.pk = None
        self.cuenta_bancaria.save()

        cargo, _ = CargoTrabajador.objects.get_or_create(nombre='Contadora')
        self.trabajador = Trabajador.objects.create(
            rut='98.765.432-1',
            nombres='Ana', apellidos='López',
            cargo=cargo,
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

    def test_post_vincula_movimiento_y_evitar_pago_duplicado(self):
        from apps.tesoreria.models import MovimientoBancario

        data = {
            'fecha_pago': timezone.now().date().isoformat(),
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }
        self.client_http.post(self.url, data)
        self.client_http.post(self.url, data)

        self.anticipo.refresh_from_db()
        self.assertIsNotNone(self.anticipo.movimiento_pago_id)
        self.assertEqual(MovimientoBancario.objects.count(), 1)

    def test_reconstruye_pago_huerfano_que_respalda_remuneracion(self):
        Remuneracion.objects.create(
            trabajador=self.trabajador,
            periodo_mes=7,
            periodo_anio=2026,
            sueldo_base=Decimal('900000'),
            sueldo_bruto=Decimal('900000'),
            anticipo_descontado=self.anticipo.monto,
            liquido_pagar=Decimal('700000'),
            estado='pagado',
        )
        self.anticipo.estado = 'descontado'
        self.anticipo.save(update_fields=['estado'])

        response = self.client_http.post(
            self.url,
            {
                'fecha_pago': '2026-07-01',
                'cuenta_bancaria': self.cuenta_bancaria.pk,
                'notas': 'Recuperación por eliminación accidental',
            },
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.anticipo.refresh_from_db()
        self.assertIsNotNone(self.anticipo.movimiento_pago_id)
        movimiento = self.anticipo.movimiento_pago
        self.assertIn('Reconstrucción pago anticipo', movimiento.descripcion)
        asiento = movimiento.asientos.get(tipo='pago_anticipo')
        config = ConfiguracionContable.get()
        self.assertEqual(asiento.estado, 'borrador')
        self.assertIn('Reconstrucción', asiento.descripcion)
        self.assertEqual(
            asiento.lineas.get(
                cuenta=config.cuenta_anticipos_trabajadores,
            ).debe,
            self.anticipo.monto,
        )
        self.assertEqual(
            asiento.lineas.get(
                cuenta=self.cuenta_bancaria.cuenta_contable,
            ).haber,
            self.anticipo.monto,
        )

    def test_no_reconstruye_descontado_sin_descuento_en_remuneracion(self):
        self.anticipo.estado = 'descontado'
        self.anticipo.save(update_fields=['estado'])

        response = self.client_http.post(
            self.url,
            {
                'fecha_pago': '2026-07-01',
                'cuenta_bancaria': self.cuenta_bancaria.pk,
                'notas': '',
            },
        )

        self.assertRedirects(
            response,
            reverse('rrhh:anticipo_list'),
            fetch_redirect_response=False,
        )
        self.anticipo.refresh_from_db()
        self.assertIsNone(self.anticipo.movimiento_pago_id)


@override_settings(SECURE_SSL_REDIRECT=False)
class AnticipoLaboralUpdateDeleteViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'admin_ant_laboral',
            'admin-laboral@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        cta_banco, _ = _setup_contabilidad()
        self.cuenta_bancaria = _make_cuenta_bancaria(cta_banco)
        self.trabajador = _make_trabajador()
        self.anticipo = AnticipoLaboral.objects.create(
            trabajador=self.trabajador,
            fecha=date(2026, 7, 1),
            monto=Decimal('200000'),
            descripcion='Anticipo julio',
            estado='pendiente',
        )

    def pagar_anticipo(self):
        return self.client_http.post(
            reverse('rrhh:anticipo_pagar', args=[self.anticipo.pk]),
            {
                'fecha_pago': '2026-07-01',
                'cuenta_bancaria': self.cuenta_bancaria.pk,
                'notas': '',
            },
        )

    def test_edita_anticipo_pendiente(self):
        response = self.client_http.post(
            reverse('rrhh:anticipo_update', args=[self.anticipo.pk]),
            {
                'trabajador': self.trabajador.pk,
                'fecha': '2026-07-02',
                'monto': '250000',
                'descripcion': 'Anticipo corregido',
            },
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.anticipo.refresh_from_db()
        self.assertEqual(self.anticipo.monto, Decimal('250000'))
        self.assertEqual(self.anticipo.descripcion, 'Anticipo corregido')

    def test_formulario_edicion_renderiza_fecha_iso_para_flatpickr(self):
        response = self.client_http.get(
            reverse('rrhh:anticipo_update', args=[self.anticipo.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-07-01"')

    def test_elimina_anticipo_pagado_y_revierte_movimiento(self):
        from apps.tesoreria.models import MovimientoBancario

        self.pagar_anticipo()
        self.anticipo.refresh_from_db()
        movimiento_id = self.anticipo.movimiento_pago_id

        response = self.client_http.post(
            reverse('rrhh:anticipo_delete', args=[self.anticipo.pk])
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.assertFalse(AnticipoLaboral.objects.filter(pk=self.anticipo.pk).exists())
        self.assertFalse(MovimientoBancario.objects.filter(pk=movimiento_id).exists())

    def test_movimiento_vinculado_no_puede_eliminarse_directamente(self):
        self.pagar_anticipo()
        self.anticipo.refresh_from_db()

        with self.assertRaises(ProtectedError):
            self.anticipo.movimiento_pago.delete()

    def test_bloquea_eliminar_si_respalda_descuento_en_remuneracion(self):
        self.pagar_anticipo()
        Remuneracion.objects.create(
            trabajador=self.trabajador,
            periodo_mes=7,
            periodo_anio=2026,
            sueldo_base=Decimal('1000000'),
            sueldo_bruto=Decimal('1000000'),
            anticipo_descontado=Decimal('200000'),
            liquido_pagar=Decimal('800000'),
            estado='borrador',
        )

        response = self.client_http.post(
            reverse('rrhh:anticipo_delete', args=[self.anticipo.pk])
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.assertTrue(AnticipoLaboral.objects.filter(pk=self.anticipo.pk).exists())

    def test_elimina_estado_descontado_sin_movimiento_ni_liquidacion(self):
        self.anticipo.estado = 'descontado'
        self.anticipo.save(update_fields=['estado'])

        response = self.client_http.post(
            reverse('rrhh:anticipo_delete', args=[self.anticipo.pk])
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.assertFalse(AnticipoLaboral.objects.filter(pk=self.anticipo.pk).exists())

    def test_editar_estado_descontado_sin_movimiento_lo_regulariza_a_pendiente(self):
        self.anticipo.estado = 'descontado'
        self.anticipo.save(update_fields=['estado'])

        response = self.client_http.post(
            reverse('rrhh:anticipo_update', args=[self.anticipo.pk]),
            {
                'trabajador': self.trabajador.pk,
                'fecha': '2026-07-01',
                'monto': '200000',
                'descripcion': 'Anticipo regularizado',
            },
        )

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.anticipo.refresh_from_db()
        self.assertEqual(self.anticipo.estado, 'pendiente')


@override_settings(SECURE_SSL_REDIRECT=False)
class AnticipoLaboralCreateViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'admin_ant_create',
            'admin-anticipo@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        self.trabajador = _make_trabajador()

    def test_crea_anticipo_pendiente_aunque_se_envie_estado_descontado(self):
        response = self.client_http.post(reverse('rrhh:anticipo_create'), {
            'trabajador': self.trabajador.pk,
            'fecha': date(2026, 6, 15).isoformat(),
            'monto': '200000',
            'descripcion': 'Anticipo junio',
            'estado': 'descontado',
        })

        self.assertRedirects(response, reverse('rrhh:anticipo_list'))
        self.assertEqual(AnticipoLaboral.objects.get().estado, 'pendiente')


@override_settings(SECURE_SSL_REDIRECT=False)
class RemuneracionUpdateAnticipoTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'admin_rem_update',
            'admin@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        self.trabajador = _make_trabajador()
        self.rem = Remuneracion.objects.create(
            trabajador=self.trabajador,
            periodo_mes=6,
            periodo_anio=2026,
            sueldo_base=Decimal('1000000'),
            sueldo_bruto=Decimal('1000000'),
            descuento_afp=Decimal('100000'),
            descuento_salud=Decimal('70000'),
            anticipo_descontado=Decimal('0'),
            liquido_pagar=Decimal('830000'),
            estado='borrador',
        )
        self.url = reverse('rrhh:remuneracion_update', args=[self.rem.pk])

    def test_fecha_devengamiento_inferida_al_cierre_del_periodo(self):
        self.assertEqual(self.rem.fecha_devengamiento, date(2026, 6, 30))

    def test_asiento_devengamiento_usa_fecha_proporcionada(self):
        from apps.contabilidad.utils import generar_asiento_devengamiento_remuneracion

        _, cuenta_sueldos = _setup_contabilidad()
        config = ConfiguracionContable.get()
        config.cuenta_sueldos_por_pagar = cuenta_sueldos
        config.cuenta_afp_por_pagar = cuenta_sueldos
        config.cuenta_salud_por_pagar = cuenta_sueldos
        config.save()
        self.rem.fecha_devengamiento = date(2026, 7, 5)
        self.rem.save(update_fields=['fecha_devengamiento'])

        asiento = generar_asiento_devengamiento_remuneracion(
            self.rem,
            usuario=self.user,
        )

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.fecha, date(2026, 7, 5))


    def test_carga_anticipo_pagado_si_no_estaba_en_la_remuneracion(self):
        AnticipoLaboral.objects.create(
            trabajador=self.trabajador,
            fecha=date(2026, 6, 15),
            monto=Decimal('200000'),
            estado='descontado',
        )

        response = self.client_http.get(self.url)

        self.assertEqual(
            response.context['form']['anticipo_descontado'].value(),
            Decimal('200000'),
        )
        self.assertEqual(
            response.context['form']['liquido_pagar'].value(),
            Decimal('630000'),
        )

    def test_no_carga_anticipo_pagado_despues_del_periodo(self):
        AnticipoLaboral.objects.create(
            trabajador=self.trabajador,
            fecha=date(2026, 7, 1),
            monto=Decimal('200000'),
            estado='descontado',
        )

        response = self.client_http.get(self.url)

        self.assertEqual(
            response.context['form']['anticipo_descontado'].value(),
            Decimal('0'),
        )

    def test_conserva_anticipo_ya_cargado(self):
        self.rem.anticipo_descontado = Decimal('50000')
        self.rem.liquido_pagar = Decimal('780000')
        self.rem.save(update_fields=['anticipo_descontado', 'liquido_pagar'])
        AnticipoLaboral.objects.create(
            trabajador=self.trabajador,
            fecha=date(2026, 6, 15),
            monto=Decimal('200000'),
            estado='descontado',
        )

        response = self.client_http.get(self.url)

        self.assertEqual(
            response.context['form']['anticipo_descontado'].value(),
            Decimal('50000'),
        )


@override_settings(SECURE_SSL_REDIRECT=False)
class RemuneracionDeleteViewTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            'tester_delete_remuneracion',
            password='pass',
            app_permisos=['rrhh'],
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        self.remuneracion = Remuneracion.objects.create(
            trabajador=_make_trabajador(),
            periodo_mes=6,
            periodo_anio=2026,
            sueldo_base=Decimal('900000'),
            sueldo_bruto=Decimal('900000'),
            liquido_pagar=Decimal('700000'),
            estado='borrador',
        )
        self.url = reverse(
            'rrhh:remuneracion_delete',
            args=[self.remuneracion.pk],
        )
        self.success_url = reverse(
            'rrhh:remuneracion_procesar_detalle',
            kwargs={'mes': 6, 'anio': 2026},
        )

    def test_elimina_remuneracion_y_asiento_borrador(self):
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 6, 30),
            descripcion='Devengamiento de prueba',
            tipo='devengamiento_remuneracion',
            estado='borrador',
            remuneracion=self.remuneracion,
        )

        response = self.client_http.post(self.url)

        self.assertRedirects(response, self.success_url)
        self.assertFalse(
            Remuneracion.objects.filter(pk=self.remuneracion.pk).exists()
        )
        self.assertFalse(AsientoContable.objects.filter(pk=asiento.pk).exists())

    def test_bloquea_remuneracion_pagada(self):
        self.remuneracion.estado = 'pagado'
        self.remuneracion.save(update_fields=['estado'])

        response = self.client_http.post(self.url)

        self.assertRedirects(response, self.success_url)
        self.assertTrue(
            Remuneracion.objects.filter(pk=self.remuneracion.pk).exists()
        )

    def test_bloquea_remuneracion_con_asiento_confirmado(self):
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 6, 30),
            descripcion='Devengamiento confirmado',
            tipo='devengamiento_remuneracion',
            estado='confirmado',
            remuneracion=self.remuneracion,
        )

        response = self.client_http.post(self.url)

        self.assertRedirects(response, self.success_url)
        self.assertTrue(
            Remuneracion.objects.filter(pk=self.remuneracion.pk).exists()
        )
        self.assertTrue(AsientoContable.objects.filter(pk=asiento.pk).exists())
