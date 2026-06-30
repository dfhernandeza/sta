from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable
from apps.proveedores.models import CuentaPorPagar
from apps.rrhh.models import Trabajador

from .models import DetalleRendicion, RendicionGastos


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
