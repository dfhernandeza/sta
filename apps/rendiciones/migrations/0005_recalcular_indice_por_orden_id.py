from django.db import migrations


def recalcular_indices_por_orden_id(apps, schema_editor):
    RendicionGastos = apps.get_model('rendiciones', 'RendicionGastos')
    RendicionGastos.objects.update(
        correlativo_rendicion=None,
        periodo_rendicion_mes=None,
        periodo_rendicion_anio=None,
    )

    for indice, rendicion in enumerate(
        RendicionGastos.objects.order_by('id').iterator(),
        start=1,
    ):
        RendicionGastos.objects.filter(pk=rendicion.pk).update(
            correlativo_rendicion=indice,
            periodo_rendicion_mes=rendicion.fecha.month,
            periodo_rendicion_anio=rendicion.fecha.year,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('rendiciones', '0004_recalcular_indice_segun_fecha'),
    ]

    operations = [
        migrations.RunPython(
            recalcular_indices_por_orden_id,
            migrations.RunPython.noop,
        ),
    ]
