from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.contabilidad.models import AsientoContable, ConfiguracionContable, PlanCuentas
from apps.tesoreria.models import Banco, CuentaBancaria, MovimientoBancario

from .models import (
    Anticipo,
    AplicacionAnticipoProveedor,
    CuentaPorPagar,
    DetalleNotaCreditoRecibida,
    FacturaRecibida,
    NotaCreditoRecibida,
    Proveedor,
)


class FacturaRecibidaIndiceTests(TestCase):
    def setUp(self):
        self.proveedor = Proveedor.objects.create(
            rut='33.333.333-3',
            razon_social='Proveedor Índices',
        )

    def crear_factura(self, numero, fecha_emision):
        return FacturaRecibida.objects.create(
            numero=numero,
            fecha_emision=fecha_emision,
            proveedor=self.proveedor,
            neto=Decimal('100000'),
            exento=Decimal('0'),
            iva=Decimal('19000'),
            total=Decimal('119000'),
        )

    def test_indice_usa_orden_id_y_mes_de_fecha_emision(self):
        factura = self.crear_factura('F-IND-1', date(2026, 6, 15))

        self.assertEqual(factura.indice_libro_compras, '1/6')
        self.assertEqual(factura.correlativo_libro_compras, 1)
        self.assertEqual(factura.periodo_libro_compras_mes, 6)
        self.assertEqual(factura.periodo_libro_compras_anio, 2026)

    def test_indice_se_reinicia_al_cambiar_de_mes(self):
        junio = self.crear_factura('F-IND-2', date(2026, 6, 30))
        julio = self.crear_factura('F-IND-3', date(2026, 7, 1))

        self.assertEqual(junio.indice_libro_compras, '1/6')
        self.assertEqual(julio.indice_libro_compras, '1/7')
        self.assertGreater(julio.pk, junio.pk)

    def test_cambiar_fecha_actualiza_mes_pero_conserva_orden(self):
        factura = self.crear_factura('F-IND-4', date(2026, 7, 1))

        factura.fecha_emision = date(2026, 6, 25)
        factura.save(update_fields=['fecha_emision'])
        factura.refresh_from_db()

        self.assertEqual(factura.indice_libro_compras, '1/6')
        self.assertEqual(factura.correlativo_libro_compras, 1)
        self.assertEqual(factura.periodo_libro_compras_mes, 6)

    def test_ids_con_espacios_generan_indices_consecutivos(self):
        primera = self.crear_factura('F-IND-5', date(2026, 6, 1))
        eliminada = self.crear_factura('F-IND-6', date(2026, 6, 2))
        tercera = self.crear_factura('F-IND-7', date(2026, 6, 3))
        self.assertEqual(tercera.indice_libro_compras, '3/6')

        eliminada.delete()
        primera.refresh_from_db()
        tercera.refresh_from_db()

        self.assertGreater(tercera.pk, primera.pk + 1)
        self.assertEqual(primera.indice_libro_compras, '1/6')
        self.assertEqual(tercera.indice_libro_compras, '2/6')

    def test_correlativo_se_reinicia_en_el_mismo_mes_de_otro_anio(self):
        anterior = self.crear_factura('F-IND-8', date(2025, 6, 1))
        actual = self.crear_factura('F-IND-9', date(2026, 6, 1))

        self.assertEqual(anterior.correlativo_libro_compras, 1)
        self.assertEqual(actual.correlativo_libro_compras, 1)

    def test_cambiar_fecha_reindexa_periodos_origen_y_destino(self):
        junio_primera = self.crear_factura('F-IND-10', date(2026, 6, 1))
        junio_segunda = self.crear_factura('F-IND-11', date(2026, 6, 2))
        julio = self.crear_factura('F-IND-12', date(2026, 7, 1))

        junio_primera.fecha_emision = date(2026, 7, 2)
        junio_primera.save(update_fields=['fecha_emision'])
        junio_segunda.refresh_from_db()
        julio.refresh_from_db()

        self.assertEqual(junio_segunda.indice_libro_compras, '1/6')
        self.assertEqual(junio_primera.indice_libro_compras, '1/7')
        self.assertEqual(julio.indice_libro_compras, '2/7')


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
        cuenta_cxp = PlanCuentas.objects.create(
            codigo='TEST.CXP',
            nombre='Cuentas por pagar',
            tipo='pasivo',
            nivel=4,
        )
        cuenta_anticipos = PlanCuentas.objects.create(
            codigo='TEST.ANT.PROV',
            nombre='Anticipos a proveedores',
            tipo='activo',
            nivel=4,
        )
        config = ConfiguracionContable.get()
        config.cuenta_cxp = cuenta_cxp
        config.cuenta_anticipos_proveedores = cuenta_anticipos
        config.save()

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

    def crear_factura_cxp(self, monto=Decimal('200000.00')):
        factura = FacturaRecibida.objects.create(
            numero=f'F-{FacturaRecibida.objects.count() + 1}',
            fecha_emision=date(2026, 7, 1),
            fecha_vencimiento=date(2026, 7, 10),
            proveedor=self.proveedor,
            neto=monto,
            exento=Decimal('0'),
            iva=Decimal('0'),
            total=monto,
        )
        cxp = CuentaPorPagar.objects.create(
            factura=factura,
            fecha_vencimiento=date(2026, 7, 10),
            monto=monto,
        )
        return factura, cxp

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

    @patch(
        'apps.contabilidad.utils.generar_asiento_aplicacion_anticipo_proveedor',
        return_value=None,
    )
    def test_aplica_varios_anticipos_en_orden_de_antiguedad(self, _generar_asiento):
        _, cxp = self.crear_factura_cxp()
        anticipo_antiguo = self.crear_anticipo(
            fecha=date(2026, 6, 1),
            monto=Decimal('80000.00'),
        )
        anticipo_nuevo = self.crear_anticipo(
            fecha=date(2026, 6, 15),
            monto=Decimal('70000.00'),
        )

        response = self.client_http.post(
            reverse('proveedores:cxp_pagar', args=[cxp.pk]),
            {
                'fecha_pago': '2026-07-02',
                'anticipos': [anticipo_nuevo.pk, anticipo_antiguo.pk],
                'monto_anticipo': '120000',
                'monto_pagado': '0',
                'cuenta_bancaria': '',
                'medio_pago': '',
                'numero_documento': '',
                'notas': 'Aplicación múltiple',
            },
        )

        self.assertRedirects(response, reverse('proveedores:cxp_list'))
        aplicaciones = list(
            AplicacionAnticipoProveedor.objects.filter(
                cuenta_pagar=cxp,
            ).order_by('anticipo__fecha')
        )
        self.assertEqual(len(aplicaciones), 2)
        self.assertEqual(aplicaciones[0].anticipo, anticipo_antiguo)
        self.assertEqual(aplicaciones[0].monto, Decimal('80000.00'))
        self.assertEqual(aplicaciones[1].anticipo, anticipo_nuevo)
        self.assertEqual(aplicaciones[1].monto, Decimal('40000.00'))

        anticipo_antiguo.refresh_from_db()
        anticipo_nuevo.refresh_from_db()
        cxp.refresh_from_db()
        self.assertEqual(anticipo_antiguo.estado, 'aplicado')
        self.assertEqual(anticipo_nuevo.estado, 'pendiente')
        self.assertEqual(anticipo_nuevo.saldo_disponible, Decimal('30000.00'))
        self.assertEqual(cxp.monto_pagado, Decimal('120000.00'))

    def test_bloquea_eliminar_nota_con_anticipo_parcialmente_aplicado(self):
        factura, cxp = self.crear_factura_cxp()
        nota = NotaCreditoRecibida.objects.create(
            numero='NC-1',
            fecha_emision=date(2026, 7, 2),
            factura=factura,
            proveedor=self.proveedor,
            neto=Decimal('50000.00'),
            exento=Decimal('0'),
            iva=Decimal('0'),
            total=Decimal('50000.00'),
        )
        anticipo = self.crear_anticipo(
            monto=Decimal('50000.00'),
            origen='nota_credito',
            nota_credito_origen=nota,
        )
        AplicacionAnticipoProveedor.objects.create(
            anticipo=anticipo,
            cuenta_pagar=cxp,
            fecha=date(2026, 7, 2),
            monto=Decimal('10000.00'),
        )

        response = self.client_http.post(
            reverse('proveedores:nota_credito_delete', args=[nota.pk])
        )

        self.assertRedirects(
            response,
            reverse('proveedores:nota_credito_detail', args=[nota.pk]),
        )
        self.assertTrue(NotaCreditoRecibida.objects.filter(pk=nota.pk).exists())
        self.assertTrue(Anticipo.objects.filter(pk=anticipo.pk).exists())

    def test_edita_nota_credito_y_sus_detalles(self):
        factura, _ = self.crear_factura_cxp()
        nota = NotaCreditoRecibida.objects.create(
            numero='NC-EDIT',
            fecha_emision=date(2026, 7, 2),
            factura=factura,
            proveedor=self.proveedor,
            neto=Decimal('10000.00'),
            exento=Decimal('0'),
            iva=Decimal('1900.00'),
            total=Decimal('11900.00'),
        )
        detalle = DetalleNotaCreditoRecibida.objects.create(
            nota_credito=nota,
            descripcion='Detalle original',
            cantidad=Decimal('1'),
            precio_unitario=Decimal('10000'),
        )

        response = self.client_http.post(
            reverse('proveedores:nota_credito_update', args=[nota.pk]),
            {
                'numero': 'NC-EDIT',
                'fecha_emision': '2026-07-03',
                'estado': 'anulada',
                'observaciones': 'Corregida',
                'detalles-TOTAL_FORMS': '1',
                'detalles-INITIAL_FORMS': '1',
                'detalles-MIN_NUM_FORMS': '0',
                'detalles-MAX_NUM_FORMS': '1000',
                'detalles-0-id': detalle.pk,
                'detalles-0-descripcion': 'Detalle corregido',
                'detalles-0-cuenta_contable': '',
                'detalles-0-centro_costo': '',
                'detalles-0-cantidad': '2',
                'detalles-0-precio_unitario': '6000',
            },
        )

        self.assertRedirects(
            response,
            reverse('proveedores:nota_credito_detail', args=[nota.pk]),
        )
        nota.refresh_from_db()
        detalle.refresh_from_db()
        self.assertEqual(nota.fecha_emision, date(2026, 7, 3))
        self.assertEqual(nota.estado, 'anulada')
        self.assertEqual(nota.total, Decimal('14280.00'))
        self.assertEqual(detalle.descripcion, 'Detalle corregido')
