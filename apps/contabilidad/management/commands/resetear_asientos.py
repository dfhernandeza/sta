from django.core.management.base import BaseCommand

from apps.contabilidad.models import AsientoContable


class Command(BaseCommand):
    help = 'Renumera los asientos contables sin dejar vacios en el correlativo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--anio',
            type=int,
            help='Anio del correlativo que se desea renumerar. Si se omite, renumera todos los anios.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra los cambios sin modificar la base de datos.',
        )

    def handle(self, *args, **options):
        anio = options.get('anio')
        dry_run = options.get('dry_run')

        anios = [anio] if anio else self._anios_disponibles()
        if not anios:
            self.stdout.write(self.style.WARNING('No hay asientos para renumerar.'))
            return

        if dry_run:
            total_cambios = 0
            for anio_actual in anios:
                total_cambios += self._mostrar_plan(anio_actual)
            if total_cambios == 0:
                self.stdout.write(self.style.SUCCESS('No se detectaron cambios necesarios.'))
            return

        for anio_actual in anios:
            AsientoContable.resetear_correlativo(anio=anio_actual)
            self.stdout.write(self.style.SUCCESS(f'Correlativo {anio_actual} renumerado.'))

    def _anios_disponibles(self):
        anios = {
            AsientoContable._extraer_anio_numero(numero)
            for numero in AsientoContable.objects.values_list('numero', flat=True)
        }
        anios.discard(None)
        return sorted(anios)

    def _mostrar_plan(self, anio):
        prefix = AsientoContable._prefix_numero(anio)
        asientos = (
            AsientoContable.objects
            .filter(numero__startswith=prefix)
            .order_by('creado_en', 'id')
        )

        cambios = 0
        for seq, asiento in enumerate(asientos, start=1):
            numero_esperado = f'{prefix}{seq:04d}'
            if asiento.numero != numero_esperado:
                cambios += 1
                self.stdout.write(f'{asiento.numero} -> {numero_esperado} | pk={asiento.pk}')

        if cambios == 0:
            self.stdout.write(f'{anio}: sin cambios.')
        return cambios
