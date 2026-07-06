from django.db import migrations


def recalcular_indices_por_periodo(apps, schema_editor):
    RendicionGastos = apps.get_model('rendiciones', 'RendicionGastos')
    RendicionGastos.objects.update(
        correlativo_rendicion=None,
        periodo_rendicion_mes=None,
        periodo_rendicion_anio=None,
    )

    correlativos_por_periodo = {}
    for rendicion in RendicionGastos.objects.order_by('id').iterator():
        periodo = (rendicion.fecha.year, rendicion.fecha.month)
        indice = correlativos_por_periodo.get(periodo, 0) + 1
        correlativos_por_periodo[periodo] = indice
        RendicionGastos.objects.filter(pk=rendicion.pk).update(
            correlativo_rendicion=indice,
            periodo_rendicion_mes=periodo[1],
            periodo_rendicion_anio=periodo[0],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('rendiciones', '0005_recalcular_indice_por_orden_id'),
    ]

    operations = [
        migrations.RunPython(
            recalcular_indices_por_periodo,
            migrations.RunPython.noop,
        ),
    ]
