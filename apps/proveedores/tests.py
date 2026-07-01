from datetime import date
from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable, PlanCuentas
from apps.tesoreria.models import Banco, CuentaBancaria, MovimientoBancario

from .models import (
    Anticipo,
    AplicacionAnticipoProveedor,
    CuentaPorPagar,
    Proveedor,
)


@override_settings(SECURE_SSL_REDIRECT=False)
class AnticipoProveedorViewsTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_superuser(
            'admin_anticipo_proveedor',
            'admin-proveedor@example.com',
            'pass',
        )
        self.client_http = Client()
        self.client_http.force_login(self.user)
        self.proveedor = Proveedor.objects.create(
            rut='11.111.111-1',
            razon_social='Proveedor Prueba',
        )
        cuenta_banco = PlanCuentas.objects.create(
            codigo='TEST.BANCO',
            nombre='Banco',
            tipo='activo',
            nivel=4,
        )
        banco = Banco.objects.create(nombre='Banco Prueba', codigo='BPR')
        self.cuenta_bancaria = CuentaBancaria.objects.create(
            banco=banco,
            numero='123456',
            tipo='corriente',
            cuenta_contable=cuenta_banco,
        )

    def crear_anticipo(self, **kwargs):
        defaults = {
            'proveedor': self.proveedor,
            'fecha': date(2026, 7, 1),
            'monto': Decimal('100000.00'),
            'descripcion': 'Anticipo de prueba',
            'estado': 'pendiente',
            'origen': 'operacional',
        }
        defaults.update(kwargs)
        return Anticipo.objects.create(**defaults)

    def test_edita_anticipo_no_pagado(self):
        anticipo = self.crear_anticipo()

        response = self.client_http.post(
            reverse('proveedores:anticipo_update', args=[anticipo.pk]),
            {
                'proveedor': self.proveedor.pk,
                'fecha': '2026-07-02',
                'monto': '120000',
                'descripcion': 'Anticipo corregido',
                'proyecto': '',
                'origen': 'operacional',
            },
        )

        self.assertRedirects(response, reverse('proveedores:anticipo_list'))
        anticipo.refresh_from_db()
        self.assertEqual(anticipo.monto, Decimal('120000.00'))
        self.assertEqual(anticipo.descripcion, 'Anticipo corregido')

    def test_pago_se_vincula_y_no_se_puede_duplicar(self):
        anticipo = self.crear_anticipo()
        url = reverse('proveedores:anticipo_pagar', args=[anticipo.pk])
        data = {
            'fecha_pago': '2026-07-01',
            'cuenta_bancaria': self.cuenta_bancaria.pk,
            'notas': '',
        }

        self.client_http.post(url, data)
        self.client_http.post(url, data)

        anticipo.refresh_from_db()
        self.assertIsNotNone(anticipo.movimiento_pago_id)
        self.assertEqual(MovimientoBancario.objects.count(), 1)

    def test_eliminar_revierte_movimiento_y_asiento_borrador(self):
        anticipo = self.crear_anticipo()
        movimiento = MovimientoBancario.objects.create(
            cuenta=self.cuenta_bancaria,
            fecha=date(2026, 7, 1),
            tipo='egreso',
            monto=anticipo.monto,
            descripcion='Pago anticipo',
        )
        asiento = AsientoContable.objects.create(
            fecha=date(2026, 7, 1),
            descripcion='Pago anticipo',
            tipo='pago_anticipo_proveedor',
            estado='borrador',
            movimiento_bancario=movimiento,
        )
        anticipo.movimiento_pago = movimiento
        anticipo.save(update_fields=['movimiento_pago'])

        response = self.client_http.post(
            reverse('proveedores:anticipo_delete', args=[anticipo.pk])
        )

        self.assertRedirects(response, reverse('proveedores:anticipo_list'))
        self.assertFalse(Anticipo.objects.filter(pk=anticipo.pk).exists())
        self.assertFalse(MovimientoBancario.objects.filter(pk=movimiento.pk).exists())
        self.assertFalse(AsientoContable.objects.filter(pk=asiento.pk).exists())

    def test_bloquea_eliminar_anticipo_aplicado(self):
        anticipo = self.crear_anticipo()
        cxp = CuentaPorPagar.objects.create(
            fecha_vencimiento=date(2026, 7, 10),
            monto=Decimal('100000.00'),
        )
        AplicacionAnticipoProveedor.objects.create(
            anticipo=anticipo,
            cuenta_pagar=cxp,
            fecha=date(2026, 7, 2),
            monto=Decimal('50000.00'),
        )

        response = self.client_http.post(
            reverse('proveedores:anticipo_delete', args=[anticipo.pk])
        )

        self.assertRedirects(response, reverse('proveedores:anticipo_list'))
        self.assertTrue(Anticipo.objects.filter(pk=anticipo.pk).exists())
