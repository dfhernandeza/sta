"""
Comando de backfill: puebla LineaAsiento.centro_costo desde los documentos de origen.

Estrategia por tipo de asiento:
  factura_venta            → lineas HABER de ingreso desde DetalleFacturaEmitida.centro_costo
                             (por posición: los detalles se crean en orden, las lineas
                              HABER en orden 10, 11, ... — la linea CxC y la de IVA
                              tienen debe > 0 o son la última, se omiten)
  factura_compra           → lineas DEBE de gasto/costo desde DetalleFacturaRecibida.centro_costo
                             (orden 1, 2, ... ; la linea IVA crédito y la CxP se omiten)
  rendicion_gastos         → lineas DEBE desde DetalleRendicion.centro_costo
  devengamiento_remuneracion / pago_remuneracion → primera linea DEBE (gasto sueldos)
                             desde trabajador.centro_costo

Solo actualiza líneas cuyo centro_costo es actualmente NULL.
Imprime un resumen al finalizar.

Uso:
    python manage.py backfill_centro_costo_asientos
    python manage.py backfill_centro_costo_asientos --dry-run
"""

from django.core.management.base import BaseCommand
from apps.contabilidad.models import AsientoContable, LineaAsiento


class Command(BaseCommand):
    help = 'Rellena LineaAsiento.centro_costo desde los documentos de origen.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra lo que se haría sin guardar nada.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        total_updated = 0
        total_skipped = 0

        asientos = (
            AsientoContable.objects
            .filter(tipo__in=[
                'factura_venta', 'factura_compra',
                'rendicion_gastos',
                'devengamiento_remuneracion', 'pago_remuneracion',
            ])
            .select_related(
                'factura_emitida',
                'factura_recibida',
                'rendicion_gastos',
                'remuneracion__trabajador__centro_costo',
            )
            .prefetch_related('lineas')
            .order_by('fecha', 'numero')
        )

        for asiento in asientos:
            updated = self._backfill(asiento, dry_run)
            total_updated += updated
            if updated == 0:
                total_skipped += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'[DRY RUN] Se actualizarían {total_updated} líneas. {total_skipped} asientos sin cambios.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Backfill completado: {total_updated} líneas actualizadas. {total_skipped} asientos sin cambios.'
            ))

    # ------------------------------------------------------------------
    def _backfill(self, asiento, dry_run):
        tipo = asiento.tipo
        updated = 0

        if tipo == 'factura_venta' and asiento.factura_emitida_id:
            updated = self._from_factura_emitida(asiento, dry_run)

        elif tipo == 'factura_compra' and asiento.factura_recibida_id:
            updated = self._from_factura_recibida(asiento, dry_run)

        elif tipo == 'rendicion_gastos' and asiento.rendicion_gastos_id:
            updated = self._from_rendicion(asiento, dry_run)

        elif tipo in ('devengamiento_remuneracion', 'pago_remuneracion') and asiento.remuneracion_id:
            updated = self._from_remuneracion(asiento, dry_run)

        return updated

    # ------------------------------------------------------------------
    def _from_factura_emitida(self, asiento, dry_run):
        """
        Las líneas HABER de ingreso se crearon en el mismo orden que los detalles
        (orden 10, 11, ...). Las líneas con debe > 0 (CxC) y la última HABER (IVA)
        no tienen CC.
        """
        from apps.clientes.models import DetalleFacturaEmitida
        detalles = list(
            DetalleFacturaEmitida.objects
            .filter(factura=asiento.factura_emitida)
            .select_related('centro_costo')
            .order_by('pk')
        )
        if not detalles:
            return 0

        # Las lineas HABER de ingreso son las que tienen haber > 0
        # y no son la línea de IVA (la de IVA no tiene CC).
        # Filtramos las que tienen CC nulo y haber > 0, ordenadas por orden.
        lineas_haber = list(
            asiento.lineas.filter(centro_costo__isnull=True, haber__gt=0)
            .order_by('orden', 'pk')
        )

        # Las primeras N lineas_haber corresponden a los N detalles; la última es IVA.
        # Si hay exactamente len(detalles)+1 lineas haber → la última es IVA → excluirla.
        if len(lineas_haber) == len(detalles) + 1:
            lineas_haber = lineas_haber[:-1]  # excluir IVA

        return self._zip_and_save(asiento, lineas_haber, detalles, dry_run)

    def _from_factura_recibida(self, asiento, dry_run):
        """
        Las líneas DEBE de gasto/costo se crearon en el mismo orden que los detalles
        (orden 1, 2, ...). IVA Crédito (DEBE) y CxP (HABER) no tienen CC.
        """
        from apps.proveedores.models import DetalleFacturaRecibida
        detalles = list(
            DetalleFacturaRecibida.objects
            .filter(factura=asiento.factura_recibida)
            .select_related('centro_costo')
            .order_by('pk')
        )
        if not detalles:
            return 0

        # Lineas DEBE con CC nulo, ordenadas — excluimos la de IVA Crédito
        # (que es la penúltima DEBE en el asiento generado).
        lineas_debe = list(
            asiento.lineas.filter(centro_costo__isnull=True, debe__gt=0)
            .order_by('orden', 'pk')
        )

        # Si hay exactamente len(detalles)+1 lineas DEBE → la última es IVA Crédito → excluirla.
        if len(lineas_debe) == len(detalles) + 1:
            lineas_debe = lineas_debe[:-1]

        return self._zip_and_save(asiento, lineas_debe, detalles, dry_run)

    def _from_rendicion(self, asiento, dry_run):
        from apps.proveedores.models import DetalleRendicion
        detalles = list(
            DetalleRendicion.objects
            .filter(rendicion=asiento.rendicion_gastos)
            .select_related('centro_costo')
            .order_by('pk')
        )
        if not detalles:
            return 0

        lineas_debe = list(
            asiento.lineas.filter(centro_costo__isnull=True, debe__gt=0)
            .order_by('orden', 'pk')
        )
        return self._zip_and_save(asiento, lineas_debe, detalles, dry_run)

    def _from_remuneracion(self, asiento, dry_run):
        """
        Solo la primera línea DEBE (gasto sueldos) recibe el CC del trabajador.
        """
        try:
            cc = asiento.remuneracion.trabajador.centro_costo
        except AttributeError:
            return 0

        if not cc:
            return 0

        linea = (
            asiento.lineas
            .filter(centro_costo__isnull=True, debe__gt=0)
            .order_by('orden', 'pk')
            .first()
        )
        if not linea:
            return 0

        if not dry_run:
            linea.centro_costo = cc
            linea.save(update_fields=['centro_costo'])

        self.stdout.write(
            f'  {asiento.numero}: linea pk={linea.pk} → {cc}'
        )
        return 1

    # ------------------------------------------------------------------
    @staticmethod
    def _zip_and_save(asiento, lineas, detalles, dry_run):
        updated = 0
        for linea, det in zip(lineas, detalles):
            cc = det.centro_costo
            if not cc:
                continue
            if not dry_run:
                linea.centro_costo = cc
                linea.save(update_fields=['centro_costo'])
            updated += 1
        return updated
