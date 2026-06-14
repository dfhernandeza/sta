"""
Management command para eliminar todos los datos de prueba de la base de datos,
conservando únicamente el Plan de Cuentas (PlanCuentas) y los usuarios.

Uso:
    python manage.py reset_datos
    python manage.py reset_datos --confirmar      (sin prompt interactivo)
    python manage.py reset_datos --incluir-cuentas  (borra también el Plan de Cuentas)

Solo disponible con DEBUG=True para evitar ejecución accidental en producción.
"""

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction


class Command(BaseCommand):
    help = 'Elimina todos los datos excepto Plan de Cuentas (solo en DEBUG=True)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirmar',
            action='store_true',
            help='Ejecuta sin pedir confirmación interactiva.',
        )
        parser.add_argument(
            '--incluir-cuentas',
            action='store_true',
            help='Borra también el Plan de Cuentas y la Configuración Contable.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'Este comando solo puede ejecutarse con DEBUG=True. '
                'No se ejecutará en producción.'
            )

        incluir_cuentas = options['incluir_cuentas']

        self.stdout.write(self.style.WARNING(
            '\n⚠  ADVERTENCIA: Se eliminarán TODOS los datos de la base de datos.'
        ))
        if not incluir_cuentas:
            self.stdout.write('   El Plan de Cuentas y la Configuración Contable se conservarán.')
        else:
            self.stdout.write(self.style.ERROR(
                '   --incluir-cuentas: también se borrará el Plan de Cuentas.'
            ))

        if not options['confirmar']:
            respuesta = input('\n¿Continuar? Escribe "si" para confirmar: ')
            if respuesta.strip().lower() != 'si':
                self.stdout.write(self.style.NOTICE('Operación cancelada.'))
                return

        with transaction.atomic():
            self._borrar_contabilidad(incluir_cuentas)
            # RRHH usa FK protegida hacia Banco; borrar RRHH antes de Tesoreria.
            self._borrar_rrhh()
            self._borrar_tesoreria()
            self._borrar_clientes()
            self._borrar_proveedores()
            self._borrar_tributario()
            self._borrar_proyectos()
            self._borrar_web()

        self.stdout.write(self.style.SUCCESS('\n✓ Base de datos limpiada correctamente.'))
        if not incluir_cuentas:
            from apps.contabilidad.models import PlanCuentas
            n = PlanCuentas.objects.count()
            self.stdout.write(f'  Plan de Cuentas conservado: {n} cuentas.')
        self.stdout.write(
            self.style.NOTICE(
                '\n  Puedes cargar datos de prueba con:\n'
                '  python manage.py cargar_datos_prueba\n'
            )
        )

    # ------------------------------------------------------------------

    def _borrar_contabilidad(self, incluir_cuentas):
        from apps.contabilidad.models import (
            LineaAsiento, AsientoContable, ConfiguracionContable,
        )
        n_lineas = LineaAsiento.objects.count()
        n_asientos = AsientoContable.objects.count()
        LineaAsiento.objects.all().delete()
        AsientoContable.objects.all().delete()
        self.stdout.write(f'  Contabilidad: {n_asientos} asientos, {n_lineas} líneas eliminados.')

        if incluir_cuentas:
            from apps.contabilidad.models import PlanCuentas
            ConfiguracionContable.objects.all().delete()
            n = PlanCuentas.objects.count()
            # Borrar en orden inverso de jerarquía (hijos antes que padres)
            for nivel in [4, 3, 2, 1]:
                PlanCuentas.objects.filter(nivel=nivel).delete()
            self.stdout.write(f'  Plan de Cuentas: {n} cuentas eliminadas.')
            self.stdout.write('  Configuración Contable: eliminada.')
        else:
            ConfiguracionContable.objects.all().delete()
            # Recrear el singleton vacío
            ConfiguracionContable.objects.create(pk=1)
            self.stdout.write('  Configuración Contable: reiniciada (cuentas en blanco).')

    def _borrar_tesoreria(self):
        from apps.tesoreria.models import MovimientoBancario, CuentaBancaria, Banco
        n_mov = MovimientoBancario.objects.count()
        n_cta = CuentaBancaria.objects.count()
        n_ban = Banco.objects.count()
        MovimientoBancario.objects.all().delete()
        CuentaBancaria.objects.all().delete()
        Banco.objects.all().delete()
        self.stdout.write(
            f'  Tesorería: {n_ban} bancos, {n_cta} cuentas, {n_mov} movimientos eliminados.'
        )

    def _borrar_clientes(self):
        from apps.clientes.models import (
            CuentaPorCobrar, DetalleFacturaEmitida, FacturaEmitida, Cliente,
        )
        n_cxc = CuentaPorCobrar.objects.count()
        n_det = DetalleFacturaEmitida.objects.count()
        n_fac = FacturaEmitida.objects.count()
        n_cli = Cliente.objects.count()
        CuentaPorCobrar.objects.all().delete()
        DetalleFacturaEmitida.objects.all().delete()
        FacturaEmitida.objects.all().delete()
        Cliente.objects.all().delete()
        self.stdout.write(
            f'  Clientes: {n_cli} clientes, {n_fac} facturas, {n_cxc} CxC eliminados.'
        )

    def _borrar_proveedores(self):
        from apps.proveedores.models import (
            CuentaPorPagar, FacturaRecibida, Proveedor,
        )
        # Anticipo si existe
        try:
            from apps.proveedores.models import Anticipo
            Anticipo.objects.all().delete()
        except ImportError:
            pass

        n_cxp = CuentaPorPagar.objects.count()
        n_fac = FacturaRecibida.objects.count()
        n_pro = Proveedor.objects.count()

        # Detalles de factura recibida si el modelo existe
        try:
            from apps.proveedores.models import DetalleFacturaRecibida
            DetalleFacturaRecibida.objects.all().delete()
        except ImportError:
            pass

        CuentaPorPagar.objects.all().delete()
        FacturaRecibida.objects.all().delete()
        Proveedor.objects.all().delete()
        self.stdout.write(
            f'  Proveedores: {n_pro} proveedores, {n_fac} facturas, {n_cxp} CxP eliminados.'
        )

    def _borrar_rrhh(self):
        from apps.rrhh.models import AnticipoLaboral, Remuneracion, Trabajador
        n_rend = 0

        # RendicionGastos (proveedores) protege FK hacia Trabajador.
        # Debe eliminarse antes de borrar trabajadores.
        try:
            from apps.proveedores.models import DetalleRendicion, RendicionGastos
            DetalleRendicion.objects.all().delete()
            n_rend = RendicionGastos.objects.count()
            RendicionGastos.objects.all().delete()
        except ImportError:
            pass

        try:
            from apps.rrhh.models import HistorialLaboral
            HistorialLaboral.objects.all().delete()
        except ImportError:
            pass
        n_ant = AnticipoLaboral.objects.count()
        n_rem = Remuneracion.objects.count()
        n_tra = Trabajador.objects.count()
        AnticipoLaboral.objects.all().delete()
        Remuneracion.objects.all().delete()
        Trabajador.objects.all().delete()
        self.stdout.write(
            f'  RRHH: {n_tra} trabajadores, {n_rem} remuneraciones, '
            f'{n_ant} anticipos, {n_rend} rendiciones eliminados.'
        )

    def _borrar_tributario(self):
        from apps.tributario.models import (
            FormularioF29, PPM, DeclaracionIVA, RegistroVenta, RegistroCompra,
        )
        counts = {
            'compras': RegistroCompra.objects.count(),
            'ventas': RegistroVenta.objects.count(),
            'iva': DeclaracionIVA.objects.count(),
            'ppm': PPM.objects.count(),
            'f29': FormularioF29.objects.count(),
        }
        RegistroCompra.objects.all().delete()
        RegistroVenta.objects.all().delete()
        DeclaracionIVA.objects.all().delete()
        PPM.objects.all().delete()
        FormularioF29.objects.all().delete()
        self.stdout.write(
            f'  Tributario: {counts["f29"]} F29, {counts["ppm"]} PPM, '
            f'{counts["iva"]} IVA, {counts["compras"]+counts["ventas"]} registros eliminados.'
        )

    def _borrar_proyectos(self):
        try:
            from apps.proyectos.models import Proyecto
            n = Proyecto.objects.count()
            Proyecto.objects.all().delete()
            self.stdout.write(f'  Proyectos: {n} proyectos eliminados.')
        except Exception:
            pass

    def _borrar_web(self):
        try:
            from apps.web.models import Contacto
            n = Contacto.objects.count()
            Contacto.objects.all().delete()
            self.stdout.write(f'  Web: {n} contactos eliminados.')
        except Exception:
            pass
