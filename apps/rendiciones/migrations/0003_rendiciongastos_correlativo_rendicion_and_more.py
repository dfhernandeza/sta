from django.db import migrations, models
from django.utils import timezone


def asignar_correlativos_existentes(apps, schema_editor):
    RendicionGastos = apps.get_model('rendiciones', 'RendicionGastos')
    contadores = {}

    rendiciones = RendicionGastos.objects.order_by('creado_en', 'id')
    for rendicion in rendiciones:
        fecha_creacion = rendicion.creado_en
        if timezone.is_aware(fecha_creacion):
            fecha_ingreso = timezone.localtime(fecha_creacion).date()
        else:
            fecha_ingreso = fecha_creacion.date()

        periodo = (fecha_ingreso.year, fecha_ingreso.month)
        contadores[periodo] = contadores.get(periodo, 0) + 1

        rendicion.periodo_rendicion_anio = fecha_ingreso.year
        rendicion.periodo_rendicion_mes = fecha_ingreso.month
        rendicion.correlativo_rendicion = contadores[periodo]
        rendicion.save(update_fields=[
            'periodo_rendicion_anio',
            'periodo_rendicion_mes',
            'correlativo_rendicion',
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('rendiciones', '0002_align_timestamp_field_names'),
    ]

    operations = [
        migrations.AddField(
            model_name='rendiciongastos',
            name='correlativo_rendicion',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Correlativo Rendición'),
        ),
        migrations.AddField(
            model_name='rendiciongastos',
            name='periodo_rendicion_anio',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Año Rendición'),
        ),
        migrations.AddField(
            model_name='rendiciongastos',
            name='periodo_rendicion_mes',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Mes Rendición'),
        ),
        migrations.RunPython(asignar_correlativos_existentes, noop),
        migrations.AddConstraint(
            model_name='rendiciongastos',
            constraint=models.UniqueConstraint(fields=('periodo_rendicion_anio', 'periodo_rendicion_mes', 'correlativo_rendicion'), name='uniq_rendicion_correlativo_mes'),
        ),
    ]
