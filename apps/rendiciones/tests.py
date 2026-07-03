from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable, ConfiguracionContable, PlanCuentas
from apps.contabilidad.utils import generar_asiento_rendicion_gastos_recibida
from apps.proveedores.models import CuentaPorPagar
from apps.rrhh.models import Trabajador
from apps.tesoreria.models import Banco, CuentaBancaria

from .models import DetalleRendicion, RendicionGastos


class RendicionGastosIndiceTests(TestCase):
    def setUp(self):
        self.trabajador = Trabajador.objects.create(
            rut='22.222.222-2',
            nombres='Índice',
            apellidos='Rendición',
            fecha_ingreso=date(2025, 1, 1),
            sueldo_base=Decimal('500000.00'),
        )

    def crear_rendicion(self, fecha):
        return RendicionGastos.objects.create(
            trabajador=self.trabajador,
            fecha=fecha,
            motivo_del_gasto='Prueba de índice',
        )

    def test_indice_usa_mes_y_anio_de_fecha_rendicion(self):
        rendicion = self.crear_rendicion(date(2024, 3, 15))

        self.assertEqual(rendicion.periodo_rendicion_mes, 3)
        self.assertEqual(rendicion.periodo_rendicion_anio, 2024)
        self.assertEqual(rendicion.correlativo_rendicion, 1)
        self.assertEqual(rendicion.indice_rendicion, '1/3')

    def test_correlativo_no_se_reinicia_en_cada_periodo(self):
        primera_marzo = self.crear_rendicion(date(2024, 3, 10))
        segunda_marzo = self.crear_rendicion(date(2024, 3, 20))
        primera_abril = self.crear_rendicion(date(2024, 4, 1))

        self.assertEqual(primera_marzo.correlativo_rendicion, 1)
        self.assertEqual(segunda_marzo.correlativo_rendicion, 2)
        self.assertEqual(primera_abril.correlativo_rendicion, 3)
        self.assertEqual(primera_abril.indice_rendicion, '3/4')

    def test_cambiar_fecha_actualiza_mes_y_conserva_orden(self):
        rendicion = self.crear_rendicion(date(2024, 3, 15))
        self.crear_rendicion(date(2024, 4, 5))

        rendicion.fecha = date(2024, 4, 10)
        rendicion.save()

        self.assertEqual(rendicion.periodo_rendicion_mes, 4)
        self.assertEqual(rendicion.periodo_rendicion_anio, 2024)
        self.assertEqual(rendicion.correlativo_rendicion, 1)
        self.assertEqual(rendicion.indice_rendicion, '1/4')

    def test_ids_con_espacios_generan_indices_consecutivos(self):
        primera = self.crear_rendicion(date(2024, 3, 1))
        eliminada = self.crear_rendicion(date(2024, 3, 2))
        tercera = self.crear_rendicion(date(2024, 4, 3))
        self.assertEqual(tercera.indice_rendicion, '3/4')

        eliminada.delete()
        primera.refresh_from_db()
        tercera.refresh_from_db()

        self.assertGreater(tercera.pk, primera.pk + 1)
        self.assertEqual(primera.indice_rendicion, '1/3')
        self.assertEqual(tercera.indice_rendicion, '2/4')


class RendicionGastosDeleteViewTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='test-pass',
        )
        self.client.force_login(self.user)
        self.trabajador = Trabajador.objects.create(
            rut='11.111.111-1',
            nombres='Ana',
            apellidos='Prueba',
            fecha_ingreso=date(2025, 1, 1),
            sueldo_base=Decimal('500000.00'),
        )

    def crear_rendicion(self):
        rendicion = RendicionGastos.objects.create(
            trabajador=self.trabajador,
            fecha=date(2026, 6, 30),
            motivo_del_gasto='Gastos de prueba',
        )
        DetalleRendicion.objects.create(
            rendicion=rendicion,
            fecha_gasto=date(2026, 6, 29),
            n_boleta_factura='123',
            descripcion='Traslado',
            monto=Decimal('10000.00'),
        )
        CuentaPorPagar.objects.create(
            rendicion=rendicion,
            fecha_vencimiento=date(2026, 7, 3),
            monto=Decimal('10000.00'),
        )
        return rendicion

    def test_elimina_rendicion_cxp_pendiente_detalles_y_asiento_borrador(self):
        rendicion = self.crear_rendicion()
        rendicion_pk = rendicion.pk
        asiento = AsientoContable.objects.create(
            fecha=rendicion.fecha,
            descripcion='Rendición de prueba',
            tipo='rendicion_gastos',
            estado='borrador',
            rendicion_gastos=rendicion,
        )

        response = self.client.post(
            reverse('rendiciones:rendicion_delete', kwargs={'pk': rendicion.pk})
        )

        self.assertRedirects(response, reverse('rendiciones:rendicion_list'))
        self.assertFalse(RendicionGastos.objects.filter(pk=rendicion_pk).exists())
        self.assertFalse(CuentaPorPagar.objects.filter(rendicion_id=rendicion_pk).exists())
        self.assertFalse(DetalleRendicion.objects.filter(rendicion_id=rendicion_pk).exists())
        self.assertFalse(AsientoContable.objects.filter(pk=asiento.pk).exists())

    def test_bloquea_eliminacion_con_asiento_confirmado(self):
        rendicion = self.crear_rendicion()
        AsientoContable.objects.create(
            fecha=rendicion.fecha,
            descripcion='Rendición confirmada',
            tipo='rendicion_gastos',
            estado='confirmado',
            rendicion_gastos=rendicion,
        )

        response = self.client.post(
            reverse('rendiciones:rendicion_delete', kwargs={'pk': rendicion.pk})
        )

        self.assertRedirects(
            response,
            reverse('rendiciones:rendicion_detail', kwargs={'pk': rendicion.pk}),
        )
        self.assertTrue(RendicionGastos.objects.filter(pk=rendicion.pk).exists())

    def test_bloquea_eliminacion_con_pago_registrado(self):
        rendicion = self.crear_rendicion()
        cxp = rendicion.cuentas_pagar.get()
        cxp.monto_pagado = Decimal('1000.00')
        cxp.save(update_fields=['monto_pagado'])

        response = self.client.post(
            reverse('rendiciones:rendicion_delete', kwargs={'pk': rendicion.pk})
        )

        self.assertRedirects(
            response,
            reverse('rendiciones:rendicion_detail', kwargs={'pk': rendicion.pk}),
        )
        self.assertTrue(RendicionGastos.objects.filter(pk=rendicion.pk).exists())

    def test_bloquea_eliminacion_si_la_rendicion_esta_pagada(self):
        rendicion = self.crear_rendicion()
        rendicion.estado = 'pagada'
        rendicion.save(update_fields=['estado'])

        response = self.client.post(
            reverse('rendiciones:rendicion_delete', kwargs={'pk': rendicion.pk})
        )

        self.assertRedirects(
            response,
            reverse('rendiciones:rendicion_detail', kwargs={'pk': rendicion.pk}),
        )
        self.assertTrue(RendicionGastos.objects.filter(pk=rendicion.pk).exists())

    def test_pago_debita_documentos_por_pagar(self):
        rendicion = self.crear_rendicion()
        cxp = rendicion.cuentas_pagar.get()
        cuenta_banco = PlanCuentas.objects.create(
            codigo='TEST-BANCO',
            nombre='Banco',
            tipo='activo',
            nivel=4,
        )
        cuenta_cxp = PlanCuentas.objects.create(
            codigo='TEST-CXP',
            nombre='Cuentas por pagar',
            tipo='pasivo',
            nivel=4,
        )
        cuenta_documentos = PlanCuentas.objects.create(
            codigo='TEST-DOC',
            nombre='Documentos por pagar',
            tipo='pasivo',
            nivel=4,
        )
        config = ConfiguracionContable.get()
        config.cuenta_cxp = cuenta_cxp
        config.cuenta_documentos_por_pagar = cuenta_documentos
        config.save()
        banco = Banco.objects.create(nombre='Banco prueba', codigo='BPR')
        cuenta_bancaria = CuentaBancaria.objects.create(
            banco=banco,
            numero='123456',
            tipo='corriente',
            cuenta_contable=cuenta_banco,
        )

        response = self.client.post(
            reverse('proveedores:cxp_pagar', kwargs={'pk': cxp.pk}),
            {
                'fecha_pago': '2026-07-03',
                'monto_anticipo': '0',
                'monto_pagado': '10000.00',
                'cuenta_bancaria': cuenta_bancaria.pk,
                'medio_pago': 'transferencia',
                'numero_documento': 'TRX-001',
                'notas': '',
            },
        )

        self.assertRedirects(response, reverse('proveedores:cxp_list'))
        cxp.refresh_from_db()
        movimiento = cxp.movimiento_pago
        self.assertEqual(movimiento.cuenta_contable, cuenta_documentos)
        asiento = movimiento.asientos.get()
        self.assertTrue(
            asiento.lineas.filter(
                cuenta=cuenta_documentos,
                debe=Decimal('10000.00'),
            ).exists()
        )
        self.assertFalse(asiento.lineas.filter(cuenta=cuenta_cxp).exists())

    def test_asiento_de_rendicion_usa_fecha_de_la_rendicion(self):
        rendicion = self.crear_rendicion()
        cuenta_gasto = PlanCuentas.objects.create(
            codigo='TEST-GASTO-REND',
            nombre='Gasto rendición',
            tipo='gasto',
            nivel=4,
        )
        cuenta_documentos = PlanCuentas.objects.create(
            codigo='TEST-DOC-REND',
            nombre='Documentos por pagar',
            tipo='pasivo',
            nivel=4,
        )
        rendicion.detalles.update(cuenta_contable=cuenta_gasto)
        config = ConfiguracionContable.get()
        config.cuenta_documentos_por_pagar = cuenta_documentos
        config.save(update_fields=['cuenta_documentos_por_pagar'])

        asiento = generar_asiento_rendicion_gastos_recibida(
            rendicion,
            usuario=self.user,
        )

        self.assertIsNotNone(asiento)
        self.assertEqual(asiento.fecha, rendicion.fecha)
