from decimal import Decimal

from django.db import migrations, models
from django.db.models import Sum


def separar_impuesto_unico(apps, schema_editor):
    FormularioF29 = apps.get_model('tributario', 'FormularioF29')
    Remuneracion = apps.get_model('rrhh', 'Remuneracion')

    for f29 in FormularioF29.objects.all().iterator():
        impuesto = (
            Remuneracion.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado__in=['aprobado', 'pagado'],
            ).aggregate(total=Sum('impuesto_unico'))['total']
            or Decimal('0')
        )
        # Hasta esta migración, retenciones almacenaba honorarios + impuesto único.
        impuesto = min(impuesto, f29.retenciones or Decimal('0'))
        f29.impuesto_unico = impuesto
        f29.retenciones = max((f29.retenciones or Decimal('0')) - impuesto, Decimal('0'))
        f29.total_pagar = (
            (f29.iva_pagar or Decimal('0'))
            + (f29.ppm_pagar or Decimal('0'))
            + f29.retenciones
            + f29.impuesto_unico
        )
        f29.save(update_fields=['impuesto_unico', 'retenciones', 'total_pagar'])


class Migration(migrations.Migration):
    dependencies = [
        ('rrhh', '0013_remuneracion_seguro_cesantia_empleador_and_more'),
        ('tributario', '0003_alter_ppm_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='formulariof29',
            name='impuesto_unico',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                verbose_name='Impuesto Único de Segunda Categoría',
            ),
        ),
        migrations.RunPython(separar_impuesto_unico, migrations.RunPython.noop),
    ]
