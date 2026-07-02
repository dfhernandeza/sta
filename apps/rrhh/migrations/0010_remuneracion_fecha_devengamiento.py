from calendar import monthrange
from datetime import date

from django.db import migrations, models


def completar_fecha_devengamiento(apps, schema_editor):
    Remuneracion = apps.get_model('rrhh', 'Remuneracion')
    for remuneracion in Remuneracion.objects.filter(
        fecha_devengamiento__isnull=True
    ).iterator():
        ultimo_dia = monthrange(
            remuneracion.periodo_anio,
            remuneracion.periodo_mes,
        )[1]
        remuneracion.fecha_devengamiento = date(
            remuneracion.periodo_anio,
            remuneracion.periodo_mes,
            ultimo_dia,
        )
        remuneracion.save(update_fields=['fecha_devengamiento'])


class Migration(migrations.Migration):

    dependencies = [
        ('rrhh', '0009_anticipolaboral_movimiento_pago'),
    ]

    operations = [
        migrations.AddField(
            model_name='remuneracion',
            name='fecha_devengamiento',
            field=models.DateField(
                blank=True,
                null=True,
                verbose_name='Fecha de Devengamiento',
            ),
        ),
        migrations.RunPython(
            completar_fecha_devengamiento,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='remuneracion',
            name='fecha_devengamiento',
            field=models.DateField(verbose_name='Fecha de Devengamiento'),
        ),
    ]
