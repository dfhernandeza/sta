"""
Management command para cargar datos de prueba en todos los módulos.
Uso: python manage.py cargar_datos_prueba
Es idempotente: usa get_or_create para no duplicar datos.
"""

import calendar
import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Carga datos de prueba para todos los módulos del sistema'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Cargando datos de prueba ===\n'))
        self._crear_tesoreria()
        self._crear_clientes()
        self._crear_proveedores()
        self._crear_proyectos()
        self._crear_rrhh()
        self._crear_movimientos()
        self._crear_tributario()
        self._crear_web()
        self.stdout.write(self.style.SUCCESS('\n✔ Datos de prueba cargados correctamente.\n'))

    # ------------------------------------------------------------------
    # TESORERÍA
    # ------------------------------------------------------------------
    def _crear_tesoreria(self):
        from apps.tesoreria.models import Banco, CuentaBancaria

        self.stdout.write('  → Tesorería...')

        banco_stgo, _ = Banco.objects.get_or_create(codigo='SANT', defaults={'nombre': 'Banco Santander'})
        banco_bci, _ = Banco.objects.get_or_create(codigo='BCI', defaults={'nombre': 'Banco BCI'})

        CuentaBancaria.objects.get_or_create(
            banco=banco_stgo, numero='00-123-45678-09',
            defaults={
                'tipo': 'corriente',
                'descripcion': 'Cuenta operaciones principales',
                'saldo_inicial': Decimal('5000000'),
                'activa': True,
            }
        )
        CuentaBancaria.objects.get_or_create(
            banco=banco_bci, numero='012-34567-89',
            defaults={
                'tipo': 'corriente',
                'descripcion': 'Cuenta secundaria',
                'saldo_inicial': Decimal('2000000'),
                'activa': True,
            }
        )
        self.stdout.write(self.style.SUCCESS('    Bancos y cuentas OK'))

    # ------------------------------------------------------------------
    # CLIENTES
    # ------------------------------------------------------------------
    def _crear_clientes(self):
        from apps.clientes.models import Cliente, FacturaEmitida, DetalleFacturaEmitida, CuentaPorCobrar

        self.stdout.write('  → Clientes...')

        cliente1, _ = Cliente.objects.get_or_create(
            rut='76.354.771-K',
            defaults={
                'razon_social': 'Constructora Los Andes SpA',
                'giro': 'Construcción de edificios',
                'direccion': 'Av. Apoquindo 4500',
                'comuna': 'Las Condes',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2345 6789',
                'email': 'contacto@losandes.cl',
                'contacto': 'Carlos Fuentes',
                'activo': True,
            }
        )
        cliente2, _ = Cliente.objects.get_or_create(
            rut='12.345.678-5',
            defaults={
                'razon_social': 'Municipalidad de Santiago',
                'giro': 'Administración pública',
                'direccion': 'Plaza de Armas s/n',
                'comuna': 'Santiago',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2800 0000',
                'email': 'obras@municipalidadsantiago.cl',
                'contacto': 'Ana González',
                'activo': True,
            }
        )
        cliente3, _ = Cliente.objects.get_or_create(
            rut='96.543.210-8',
            defaults={
                'razon_social': 'Clínica Las Condes SA',
                'giro': 'Servicios de salud',
                'direccion': 'Lo Fontecilla 441',
                'comuna': 'Las Condes',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2610 8000',
                'email': 'licitaciones@clc.cl',
                'contacto': 'Patricio Rojas',
                'activo': True,
            }
        )

        # Facturas emitidas
        hoy = datetime.date.today()
        fac1, created1 = FacturaEmitida.objects.get_or_create(
            numero='F-0001',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=60),
                'fecha_vencimiento': hoy - datetime.timedelta(days=30),
                'cliente': cliente1,
                'neto': Decimal('8400000'),
                'iva': Decimal('1596000'),
                'total': Decimal('9996000'),
                'estado': 'pagada',
                'observaciones': 'Proyecto muebles comedor ejecutivo - saldo final',
            }
        )
        if created1:
            DetalleFacturaEmitida.objects.create(
                factura=fac1, descripcion='Muebles de cocina modular', cantidad=Decimal('1'), precio_unitario=Decimal('5200000')
            )
            DetalleFacturaEmitida.objects.create(
                factura=fac1, descripcion='Closets habitaciones x4', cantidad=Decimal('4'), precio_unitario=Decimal('800000')
            )
            CuentaPorCobrar.objects.get_or_create(
                factura=fac1,
                defaults={
                    'fecha_vencimiento': hoy - datetime.timedelta(days=30),
                    'monto': Decimal('9996000'),
                    'monto_pagado': Decimal('9996000'),
                    'estado': 'pagada',
                    'fecha_pago': hoy - datetime.timedelta(days=25),
                }
            )

        fac2, created2 = FacturaEmitida.objects.get_or_create(
            numero='F-0002',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=30),
                'fecha_vencimiento': hoy + datetime.timedelta(days=30),
                'cliente': cliente2,
                'neto': Decimal('12600000'),
                'iva': Decimal('2394000'),
                'total': Decimal('14994000'),
                'estado': 'pendiente',
                'observaciones': 'Mobiliario oficinas municipales - 50% avance',
            }
        )
        if created2:
            DetalleFacturaEmitida.objects.create(
                factura=fac2, descripcion='Escritorios modulares', cantidad=Decimal('20'), precio_unitario=Decimal('420000')
            )
            DetalleFacturaEmitida.objects.create(
                factura=fac2, descripcion='Sillas ejecutivas', cantidad=Decimal('20'), precio_unitario=Decimal('210000')
            )
            CuentaPorCobrar.objects.get_or_create(
                factura=fac2,
                defaults={
                    'fecha_vencimiento': hoy + datetime.timedelta(days=30),
                    'monto': Decimal('14994000'),
                    'monto_pagado': Decimal('0'),
                    'estado': 'pendiente',
                }
            )

        fac3, created3 = FacturaEmitida.objects.get_or_create(
            numero='F-0003',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=90),
                'fecha_vencimiento': hoy - datetime.timedelta(days=60),
                'cliente': cliente3,
                'neto': Decimal('6300000'),
                'iva': Decimal('1197000'),
                'total': Decimal('7497000'),
                'estado': 'vencida',
                'observaciones': 'Terminaciones box y mesones clínica',
            }
        )
        if created3:
            DetalleFacturaEmitida.objects.create(
                factura=fac3, descripcion='Mesones Corian box consultas', cantidad=Decimal('6'), precio_unitario=Decimal('850000')
            )
            DetalleFacturaEmitida.objects.create(
                factura=fac3, descripcion='Instalación y terminaciones', cantidad=Decimal('1'), precio_unitario=Decimal('1200000')
            )
            CuentaPorCobrar.objects.get_or_create(
                factura=fac3,
                defaults={
                    'fecha_vencimiento': hoy - datetime.timedelta(days=60),
                    'monto': Decimal('7497000'),
                    'monto_pagado': Decimal('0'),
                    'estado': 'vencida',
                }
            )

        self.stdout.write(self.style.SUCCESS('    Clientes y facturas OK'))

    # ------------------------------------------------------------------
    # PROVEEDORES
    # ------------------------------------------------------------------
    def _crear_proveedores(self):
        from apps.proveedores.models import Proveedor, FacturaRecibida, DetalleFacturaRecibida, CuentaPorPagar, Anticipo
        from apps.contabilidad.models import PlanCuentas

        self.stdout.write('  → Proveedores...')

        prov1, _ = Proveedor.objects.get_or_create(
            rut='78.901.234-2',
            defaults={
                'razon_social': 'Distribuidora Maderera del Sur Ltda',
                'giro': 'Venta de tableros y maderas',
                'direccion': 'Av. Industrial 890',
                'comuna': 'Pudahuel',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2456 7890',
                'email': 'ventas@maderadelasur.cl',
                'contacto': 'Roberto Muñoz',
                'banco': 'Banco BCI',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '087-654321',
                'activo': True,
            }
        )
        prov2, _ = Proveedor.objects.get_or_create(
            rut='99.887.766-0',
            defaults={
                'razon_social': 'Ferretería Industrial Pro SpA',
                'giro': 'Venta de herrajes e insumos',
                'direccion': 'Costanera Norte 1200',
                'comuna': 'Conchalí',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2567 8901',
                'email': 'pedidos@ferreindustrialpro.cl',
                'contacto': 'Silvia Araya',
                'banco': 'Banco Santander',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '000-112233',
                'activo': True,
            }
        )
        prov3, _ = Proveedor.objects.get_or_create(
            rut='76.543.210-3',
            defaults={
                'razon_social': 'Herrajes & Accesorios SpA',
                'giro': 'Importación y venta de herrajes',
                'direccion': 'Parque Industrial Quilicura 45',
                'comuna': 'Quilicura',
                'ciudad': 'Santiago',
                'telefono': '+56 2 2678 9012',
                'email': 'info@herrajess.cl',
                'contacto': 'Marco Soto',
                'banco': 'Banco BCI',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '010-987654',
                'activo': True,
            }
        )

        hoy = datetime.date.today()
        # Cuentas contables para detalles
        cta_tableros = PlanCuentas.objects.filter(nombre='Melamina').first()
        cta_herrajes = PlanCuentas.objects.filter(nombre='Bisagras').first()

        # Facturas recibidas
        frec1, created_fr1 = FacturaRecibida.objects.get_or_create(
            proveedor=prov1, numero='15234',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=45),
                'fecha_vencimiento': hoy - datetime.timedelta(days=15),
                'neto': Decimal('3200000'),
                'iva': Decimal('608000'),
                'total': Decimal('3808000'),
                'estado': 'pagada',
                'observaciones': 'Melaminas y MDF proyecto F-0001',
            }
        )
        if created_fr1:
            DetalleFacturaRecibida.objects.create(
                factura=frec1,
                descripcion='Melamina blanca 18mm (100 planchas)',
                cuenta_contable=cta_tableros,
                monto=Decimal('2000000'),
            )
            DetalleFacturaRecibida.objects.create(
                factura=frec1,
                descripcion='MDF 15mm (50 planchas)',
                cuenta_contable=cta_tableros,
                monto=Decimal('1200000'),
            )
            CuentaPorPagar.objects.get_or_create(
                factura=frec1,
                defaults={
                    'fecha_vencimiento': hoy - datetime.timedelta(days=15),
                    'monto': Decimal('3808000'),
                    'monto_pagado': Decimal('3808000'),
                    'estado': 'pagada',
                    'fecha_pago': hoy - datetime.timedelta(days=10),
                }
            )

        frec2, created_fr2 = FacturaRecibida.objects.get_or_create(
            proveedor=prov2, numero='98001',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=20),
                'fecha_vencimiento': hoy + datetime.timedelta(days=40),
                'neto': Decimal('1540000'),
                'iva': Decimal('292600'),
                'total': Decimal('1832600'),
                'estado': 'pendiente',
                'observaciones': 'Herrajes proyecto F-0002',
            }
        )
        if created_fr2:
            DetalleFacturaRecibida.objects.create(
                factura=frec2,
                descripcion='Bisagras Blum (200 unidades)',
                cuenta_contable=cta_herrajes,
                monto=Decimal('840000'),
            )
            DetalleFacturaRecibida.objects.create(
                factura=frec2,
                descripcion='Correderas Hettich (80 pares)',
                cuenta_contable=cta_herrajes,
                monto=Decimal('700000'),
            )
            CuentaPorPagar.objects.get_or_create(
                factura=frec2,
                defaults={
                    'fecha_vencimiento': hoy + datetime.timedelta(days=40),
                    'monto': Decimal('1832600'),
                    'monto_pagado': Decimal('0'),
                    'estado': 'pendiente',
                }
            )

        frec3, created_fr3 = FacturaRecibida.objects.get_or_create(
            proveedor=prov3, numero='7654',
            defaults={
                'fecha_emision': hoy - datetime.timedelta(days=10),
                'fecha_vencimiento': hoy + datetime.timedelta(days=20),
                'neto': Decimal('980000'),
                'iva': Decimal('186200'),
                'total': Decimal('1166200'),
                'estado': 'pendiente',
            }
        )
        if created_fr3:
            CuentaPorPagar.objects.get_or_create(
                factura=frec3,
                defaults={
                    'fecha_vencimiento': hoy + datetime.timedelta(days=20),
                    'monto': Decimal('1166200'),
                    'monto_pagado': Decimal('0'),
                    'estado': 'pendiente',
                }
            )

        # Anticipo a proveedor
        Anticipo.objects.get_or_create(
            proveedor=prov1,
            fecha=hoy - datetime.timedelta(days=60),
            defaults={
                'monto': Decimal('1000000'),
                'descripcion': 'Anticipo pedido especial melaminas',
                'estado': 'aplicado',
            }
        )

        self.stdout.write(self.style.SUCCESS('    Proveedores y facturas OK'))

    # ------------------------------------------------------------------
    # PROYECTOS
    # ------------------------------------------------------------------
    def _crear_proyectos(self):
        from apps.proyectos.models import Proyecto, CostoProyecto, Presupuesto
        from apps.clientes.models import Cliente
        from apps.proveedores.models import Proveedor, FacturaRecibida
        from apps.contabilidad.models import PlanCuentas

        self.stdout.write('  → Proyectos...')

        hoy = datetime.date.today()
        cliente1 = Cliente.objects.filter(rut='76.354.771-K').first()
        cliente2 = Cliente.objects.filter(rut='12.345.678-5').first()
        cliente3 = Cliente.objects.filter(rut='96.543.210-8').first()
        prov1 = Proveedor.objects.filter(rut='78.901.234-2').first()
        cta_mat = PlanCuentas.objects.filter(nombre='Melamina').first()
        cta_mo = PlanCuentas.objects.filter(nombre='Operarios').first()

        proy1, created_p1 = Proyecto.objects.get_or_create(
            codigo='PRY-2026-001',
            defaults={
                'nombre': 'Mobiliario Comedor Ejecutivo Los Andes',
                'cliente': cliente1,
                'estado': 'terminado',
                'fecha_inicio': hoy - datetime.timedelta(days=90),
                'fecha_termino': hoy - datetime.timedelta(days=20),
                'monto_contrato': Decimal('9996000'),
                'descripcion': 'Fabricación e instalación de muebles de cocina y closets para comedor ejecutivo.',
                'direccion_obra': 'Av. Apoquindo 4500, Las Condes',
                'destacado': True,
                'mostrar_en_web': True,
            }
        )
        if created_p1:
            CostoProyecto.objects.create(
                proyecto=proy1, fecha=hoy - datetime.timedelta(days=80),
                descripcion='Melaminas y materiales tableros',
                tipo='material', cuenta_contable=cta_mat,
                monto=Decimal('2000000'), proveedor=prov1,
            )
            CostoProyecto.objects.create(
                proyecto=proy1, fecha=hoy - datetime.timedelta(days=50),
                descripcion='Mano de obra fabricación e instalación',
                tipo='mano_obra', cuenta_contable=cta_mo,
                monto=Decimal('1800000'),
            )
            CostoProyecto.objects.create(
                proyecto=proy1, fecha=hoy - datetime.timedelta(days=30),
                descripcion='Herrajes y accesorios',
                tipo='material', monto=Decimal('840000'),
            )
            for item, tipo, monto in [
                ('Materiales tableros', 'material', Decimal('2200000')),
                ('Mano de obra', 'mano_obra', Decimal('2000000')),
                ('Herrajes', 'material', Decimal('900000')),
                ('Subcontratos', 'subcontrato', Decimal('500000')),
            ]:
                Presupuesto.objects.get_or_create(
                    proyecto=proy1, item=item,
                    defaults={'tipo': tipo, 'monto_presupuestado': monto, 'monto_real': monto * Decimal('0.95')}
                )

        proy2, created_p2 = Proyecto.objects.get_or_create(
            codigo='PRY-2026-002',
            defaults={
                'nombre': 'Mobiliario Oficinas Municipales Santiago',
                'cliente': cliente2,
                'estado': 'en_ejecucion',
                'fecha_inicio': hoy - datetime.timedelta(days=30),
                'fecha_termino': hoy + datetime.timedelta(days=60),
                'monto_contrato': Decimal('14994000'),
                'descripcion': 'Fabricación y montaje de escritorios y sillas para 20 oficinas.',
                'direccion_obra': 'Plaza de Armas s/n, Santiago',
                'destacado': False,
                'mostrar_en_web': False,
            }
        )
        if created_p2:
            CostoProyecto.objects.create(
                proyecto=proy2, fecha=hoy - datetime.timedelta(days=15),
                descripcion='Materiales tableros y perfilería',
                tipo='material', cuenta_contable=cta_mat,
                monto=Decimal('3200000'), proveedor=prov1,
            )
            for item, tipo, monto in [
                ('Tableros y materiales', 'material', Decimal('3500000')),
                ('Mano de obra', 'mano_obra', Decimal('3000000')),
                ('Herrajes', 'material', Decimal('1500000')),
                ('Transporte e instalación', 'transporte', Decimal('800000')),
            ]:
                Presupuesto.objects.get_or_create(
                    proyecto=proy2, item=item,
                    defaults={'tipo': tipo, 'monto_presupuestado': monto, 'monto_real': Decimal('0')}
                )

        proy3, _ = Proyecto.objects.get_or_create(
            codigo='PRY-2025-015',
            defaults={
                'nombre': 'Terminaciones Box Clínica Las Condes',
                'cliente': cliente3,
                'estado': 'terminado',
                'fecha_inicio': hoy - datetime.timedelta(days=150),
                'fecha_termino': hoy - datetime.timedelta(days=80),
                'monto_contrato': Decimal('7497000'),
                'descripcion': 'Mesones Corian y terminaciones para boxes de consulta médica.',
                'direccion_obra': 'Lo Fontecilla 441, Las Condes',
                'destacado': True,
                'mostrar_en_web': True,
            }
        )

        self.stdout.write(self.style.SUCCESS('    Proyectos y costos OK'))

    # ------------------------------------------------------------------
    # RRHH
    # ------------------------------------------------------------------
    def _crear_rrhh(self):
        from apps.rrhh.models import Trabajador, Remuneracion, AnticipoLaboral, HistorialLaboral

        self.stdout.write('  → RRHH...')

        hoy = datetime.date.today()

        trab1, created_t1 = Trabajador.objects.get_or_create(
            rut='15.423.698-8',
            defaults={
                'nombres': 'Juan Carlos',
                'apellidos': 'Pérez Molina',
                'cargo': 'Maestro Mueblista',
                'fecha_ingreso': datetime.date(2022, 3, 1),
                'sueldo_base': Decimal('850000'),
                'afp': 'Capital',
                'isapre': 'FONASA',
                'banco': 'Banco Estado',
                'tipo_cuenta': 'Cuenta RUT',
                'numero_cuenta': '15423698',
                'email': 'jcperez@gmail.com',
                'telefono': '+56 9 8765 4321',
                'estado': 'activo',
            }
        )
        trab2, created_t2 = Trabajador.objects.get_or_create(
            rut='16.789.456-9',
            defaults={
                'nombres': 'María Fernanda',
                'apellidos': 'López Contreras',
                'cargo': 'Instaladora',
                'fecha_ingreso': datetime.date(2023, 6, 15),
                'sueldo_base': Decimal('720000'),
                'afp': 'Habitat',
                'isapre': 'Cruz Blanca',
                'banco': 'Banco BCI',
                'tipo_cuenta': 'Cuenta Corriente',
                'numero_cuenta': '045-987654',
                'email': 'mflopez@gmail.com',
                'telefono': '+56 9 7654 3210',
                'estado': 'activo',
            }
        )
        trab3, _ = Trabajador.objects.get_or_create(
            rut='14.256.780-6',
            defaults={
                'nombres': 'Diego Andrés',
                'apellidos': 'Ramírez Torres',
                'cargo': 'Operario de Producción',
                'fecha_ingreso': datetime.date(2024, 1, 8),
                'sueldo_base': Decimal('580000'),
                'afp': 'PlanVital',
                'isapre': 'FONASA',
                'banco': 'Banco Estado',
                'tipo_cuenta': 'Cuenta RUT',
                'numero_cuenta': '14256780',
                'telefono': '+56 9 6543 2109',
                'estado': 'activo',
            }
        )

        # Remuneraciones (mes anterior)
        mes = hoy.month - 1 if hoy.month > 1 else 12
        anio = hoy.year if hoy.month > 1 else hoy.year - 1

        for trab, base in [(trab1, Decimal('850000')), (trab2, Decimal('720000')), (trab3, Decimal('580000'))]:
            bruto = base + Decimal('50000')
            afp = round(bruto * Decimal('0.1145'), 2)
            salud = round(bruto * Decimal('0.07'), 2)
            liquido = bruto - afp - salud
            Remuneracion.objects.get_or_create(
                trabajador=trab, periodo_mes=mes, periodo_anio=anio,
                defaults={
                    'sueldo_base': base,
                    'horas_extra': Decimal('0'),
                    'bono': Decimal('50000'),
                    'sueldo_bruto': bruto,
                    'descuento_afp': afp,
                    'descuento_salud': salud,
                    'otros_descuentos': Decimal('0'),
                    'anticipo_descontado': Decimal('0'),
                    'liquido_pagar': liquido,
                    'estado': 'pagado',
                    'fecha_devengamiento': datetime.date(
                        anio,
                        mes,
                        calendar.monthrange(anio, mes)[1],
                    ),
                    'fecha_pago': hoy.replace(day=5),
                }
            )

        if created_t1:
            AnticipoLaboral.objects.create(
                trabajador=trab1, fecha=hoy - datetime.timedelta(days=20),
                monto=Decimal('150000'), descripcion='Anticipo gastos médicos', estado='pendiente'
            )
            HistorialLaboral.objects.create(
                trabajador=trab1, fecha=datetime.date(2022, 3, 1),
                tipo='ingreso', descripcion='Ingreso como Maestro Mueblista.'
            )
            HistorialLaboral.objects.create(
                trabajador=trab1, fecha=datetime.date(2024, 1, 1),
                tipo='cambio_sueldo', descripcion='Ajuste sueldo base a $850.000.'
            )
        if created_t2:
            HistorialLaboral.objects.create(
                trabajador=trab2, fecha=datetime.date(2023, 6, 15),
                tipo='ingreso', descripcion='Ingreso como Instaladora.'
            )

        self.stdout.write(self.style.SUCCESS('    Trabajadores y remuneraciones OK'))

    # ------------------------------------------------------------------
    # MOVIMIENTOS BANCARIOS
    # ------------------------------------------------------------------
    def _crear_movimientos(self):
        from apps.tesoreria.models import CuentaBancaria, MovimientoBancario
        from apps.contabilidad.models import PlanCuentas
        from apps.proyectos.models import Proyecto

        self.stdout.write('  → Movimientos bancarios...')

        hoy = datetime.date.today()
        cuenta = CuentaBancaria.objects.first()
        if not cuenta:
            return

        proy1 = Proyecto.objects.filter(codigo='PRY-2026-001').first()
        proy2 = Proyecto.objects.filter(codigo='PRY-2026-002').first()
        cta_banco = PlanCuentas.objects.filter(nombre='Banco Santander').first()
        cta_ventas = PlanCuentas.objects.filter(nombre='Constructora X').first()
        cta_prov = PlanCuentas.objects.filter(nombre='Facturas por Pagar').first()
        cta_rem = PlanCuentas.objects.filter(nombre='Sueldos por Pagar').first()

        movimientos = [
            {
                'fecha': hoy - datetime.timedelta(days=55),
                'tipo': 'ingreso',
                'monto': Decimal('9996000'),
                'descripcion': 'Pago factura F-0001 Constructora Los Andes',
                'cuenta_contable': cta_ventas,
                'proyecto': proy1,
                'documento': 'F-0001',
                'conciliado': True,
            },
            {
                'fecha': hoy - datetime.timedelta(days=45),
                'tipo': 'egreso',
                'monto': Decimal('3808000'),
                'descripcion': 'Pago factura Maderera del Sur #15234',
                'cuenta_contable': cta_prov,
                'proyecto': proy1,
                'documento': '15234',
                'conciliado': True,
            },
            {
                'fecha': hoy.replace(day=5) if hoy.day >= 5 else hoy - datetime.timedelta(days=hoy.day - 1),
                'tipo': 'egreso',
                'monto': Decimal('2150000'),
                'descripcion': 'Pago remuneraciones mes anterior',
                'cuenta_contable': cta_rem,
                'documento': 'REM-' + str(hoy.month - 1 if hoy.month > 1 else 12),
                'conciliado': True,
            },
            {
                'fecha': hoy - datetime.timedelta(days=15),
                'tipo': 'egreso',
                'monto': Decimal('3200000'),
                'descripcion': 'Pago materiales proyecto F-0002',
                'cuenta_contable': cta_prov,
                'proyecto': proy2,
                'documento': 'TRANS-001',
                'conciliado': False,
            },
        ]

        for mov in movimientos:
            MovimientoBancario.objects.get_or_create(
                cuenta=cuenta,
                fecha=mov['fecha'],
                descripcion=mov['descripcion'],
                defaults={
                    'tipo': mov['tipo'],
                    'monto': mov['monto'],
                    'cuenta_contable': mov.get('cuenta_contable'),
                    'proyecto': mov.get('proyecto'),
                    'documento': mov.get('documento', ''),
                    'conciliado': mov.get('conciliado', False),
                }
            )

        self.stdout.write(self.style.SUCCESS('    Movimientos bancarios OK'))

    # ------------------------------------------------------------------
    # TRIBUTARIO
    # ------------------------------------------------------------------
    def _crear_tributario(self):
        from apps.tributario.models import RegistroCompra, RegistroVenta, DeclaracionIVA, PPM, FormularioF29
        from apps.clientes.models import Cliente, FacturaEmitida
        from apps.proveedores.models import Proveedor, FacturaRecibida

        self.stdout.write('  → Tributario...')

        hoy = datetime.date.today()
        mes = hoy.month - 1 if hoy.month > 1 else 12
        anio = hoy.year if hoy.month > 1 else hoy.year - 1

        cli1 = Cliente.objects.filter(rut='76.354.771-K').first()
        fac1 = FacturaEmitida.objects.filter(numero='F-0001').first()
        prov1 = Proveedor.objects.filter(rut='78.901.234-2').first()
        frec1 = FacturaRecibida.objects.filter(numero='15234').first()

        if cli1 and fac1:
            RegistroVenta.objects.get_or_create(
                cliente=cli1, factura=fac1,
                defaults={
                    'periodo_mes': mes,
                    'periodo_anio': anio,
                    'neto': fac1.neto,
                    'iva_debito': fac1.iva,
                    'total': fac1.total,
                }
            )

        if prov1 and frec1:
            RegistroCompra.objects.get_or_create(
                proveedor=prov1, factura=frec1,
                defaults={
                    'periodo_mes': mes,
                    'periodo_anio': anio,
                    'neto': frec1.neto,
                    'iva_credito': frec1.iva,
                    'total': frec1.total,
                }
            )

        # IVA del periodo anterior
        iva_debito = Decimal('1596000')
        iva_credito = Decimal('608000')
        diferencia = max(iva_debito - iva_credito, Decimal('0'))

        DeclaracionIVA.objects.get_or_create(
            periodo_mes=mes, periodo_anio=anio,
            defaults={
                'iva_debito': iva_debito,
                'iva_credito': iva_credito,
                'diferencia': diferencia,
                'estado': 'pagado',
                'fecha_presentacion': datetime.date(anio, mes, 20),
            }
        )

        base_ppm = Decimal('8400000')
        monto_ppm = round(base_ppm * Decimal('0.0025'), 2)
        PPM.objects.get_or_create(
            periodo_mes=mes, periodo_anio=anio,
            defaults={
                'base_imponible': base_ppm,
                'tasa': Decimal('0.0025'),
                'monto': monto_ppm,
                'estado': 'pagado',
                'fecha_pago': datetime.date(anio, mes, 20),
            }
        )

        FormularioF29.objects.get_or_create(
            periodo_mes=mes, periodo_anio=anio,
            defaults={
                'iva_pagar': diferencia,
                'ppm_pagar': monto_ppm,
                'retenciones': Decimal('0'),
                'total_pagar': diferencia + monto_ppm,
                'estado': 'pagado',
                'fecha_presentacion': datetime.date(anio, mes, 20),
                'folio': f'F29-{anio}{mes:02d}',
            }
        )

        self.stdout.write(self.style.SUCCESS('    Tributario OK'))

    # ------------------------------------------------------------------
    # WEB (portafolio, servicios, equipo)
    # ------------------------------------------------------------------
    def _crear_web(self):
        from apps.web.models import Servicio, MiembroEquipo, ContactoMensaje
        from apps.proyectos.models import Proyecto

        self.stdout.write('  → Web...')

        servicios = [
            ('Muebles a Medida', 'Diseñamos y fabricamos muebles de cocina, dormitorio, living y oficina completamente a medida, adaptados a cada espacio y estilo.', 'bi-tools', 1),
            ('Terminaciones en Corian', 'Instalación de mesones y revestimientos en Corian y piedra natural para cocinas, baños y espacios comerciales.', 'bi-grid-3x3', 2),
            ('Proyectos Corporativos', 'Soluciones integrales para hospitales, clínicas, oficinas y edificios públicos. Experiencia en licitaciones y grandes superficies.', 'bi-building', 3),
            ('Closets y Vestidores', 'Sistemas modulares de closets y vestidores con herrajes europeos, maximizando el almacenamiento y el diseño interior.', 'bi-box-seam', 4),
            ('Remodelaciones', 'Coordinamos remodelaciones completas integrando carpintería, terminaciones y acabados en un solo servicio.', 'bi-hammer', 5),
            ('Instalación y Post-Venta', 'Equipo propio de instaladores certificados con servicio post-venta y garantía en todos nuestros trabajos.', 'bi-patch-check', 6),
        ]
        for titulo, desc, icono, orden in servicios:
            Servicio.objects.get_or_create(
                titulo=titulo,
                defaults={'descripcion': desc, 'icono': icono, 'activo': True, 'orden': orden}
            )

        equipo = [
            ('Rodrigo Tapia', 'Gerente General', 'Ingeniero civil industrial con 20 años de experiencia en la industria del mueble y terminaciones.', 1),
            ('Claudia Espinoza', 'Jefa de Diseño', 'Diseñadora de interiores especializada en espacios funcionales y corporativos.', 2),
            ('Felipe Núñez', 'Jefe de Taller', 'Maestro mueblista con más de 15 años de experiencia en fabricación de alta calidad.', 3),
        ]
        for nombre, cargo, desc, orden in equipo:
            MiembroEquipo.objects.get_or_create(
                nombre=nombre,
                defaults={'cargo': cargo, 'descripcion': desc, 'activo': True, 'orden': orden}
            )

        # Mensajes de contacto de ejemplo
        mensajes = [
            ('Beatriz Salgado', 'Inmobiliaria Norte SpA', 'bsalgado@inmobinartenorte.cl', '+56 9 5544 3322',
             'Necesitamos cotización para mobiliario de 30 departamentos. ¿Cuándo podemos reunirnos?'),
            ('Tomás Herrera', '', 'tomasherrera@gmail.com', '',
             'Quisiera cotizar una cocina y closets para mi casa en Vitacura. Midan aprox. 15m².'),
        ]
        for nombre, empresa, email, tel, msj in mensajes:
            ContactoMensaje.objects.get_or_create(
                email=email,
                defaults={
                    'nombre': nombre, 'empresa': empresa,
                    'telefono': tel, 'mensaje': msj,
                    'leido': False, 'respondido': False,
                }
            )

        self.stdout.write(self.style.SUCCESS('    Contenido web OK'))
