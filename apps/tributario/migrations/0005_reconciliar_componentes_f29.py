from decimal import Decimal

from django.db import migrations
from django.db.models import Sum


def reconciliar_componentes(apps, schema_editor):
    FormularioF29 = apps.get_model('tributario', 'FormularioF29')
    BoletaHonorarios = apps.get_model('boletas', 'BoletaHonorarios')
    Remuneracion = apps.get_model('rrhh', 'Remuneracion')

    for f29 in FormularioF29.objects.all().iterator():
        retenciones_honorarios = (
            BoletaHonorarios.objects.filter(
                fecha_emision__month=f29.periodo_mes,
                fecha_emision__year=f29.periodo_anio,
            )
            .exclude(estado='anulada')
            .aggregate(total=Sum('retencion'))['total']
            or Decimal('0')
        )
        impuesto_unico = (
            Remuneracion.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado__in=['aprobado', 'pagado'],
            ).aggregate(total=Sum('impuesto_unico'))['total']
            or Decimal('0')
        )

        f29.retenciones = retenciones_honorarios
        f29.impuesto_unico = impuesto_unico
        f29.total_pagar = (
            (f29.iva_pagar or Decimal('0'))
            + (f29.ppm_pagar or Decimal('0'))
            + retenciones_honorarios
            + impuesto_unico
        )
        f29.save(update_fields=['retenciones', 'impuesto_unico', 'total_pagar'])


class Migration(migrations.Migration):
    dependencies = [
        ('boletas', '0001_initial'),
        ('tributario', '0004_formulariof29_impuesto_unico'),
    ]

    operations = [
        migrations.RunPython(reconciliar_componentes, migrations.RunPython.noop),
    ]
