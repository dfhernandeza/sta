from django.db import migrations


def recalcular_indices_segun_fecha(apps, schema_editor):
    RendicionGastos = apps.get_model('rendiciones', 'RendicionGastos')
    RendicionGastos.objects.update(
        correlativo_rendicion=None,
        periodo_rendicion_mes=None,
        periodo_rendicion_anio=None,
    )

    contadores = {}
    for rendicion in RendicionGastos.objects.order_by('fecha', 'id').iterator():
        periodo = (rendicion.fecha.year, rendicion.fecha.month)
        contadores[periodo] = contadores.get(periodo, 0) + 1
        RendicionGastos.objects.filter(pk=rendicion.pk).update(
            correlativo_rendicion=contadores[periodo],
            periodo_rendicion_mes=rendicion.fecha.month,
            periodo_rendicion_anio=rendicion.fecha.year,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('rendiciones', '0003_rendiciongastos_correlativo_rendicion_and_more'),
    ]

    operations = [
        migrations.RunPython(
            recalcular_indices_segun_fecha,
            migrations.RunPython.noop,
        ),
    ]
