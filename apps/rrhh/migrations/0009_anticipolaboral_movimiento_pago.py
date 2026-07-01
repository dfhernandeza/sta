from django.db import migrations, models
import django.db.models.deletion


def vincular_movimientos_legacy(apps, schema_editor):
    AnticipoLaboral = apps.get_model('rrhh', 'AnticipoLaboral')
    MovimientoBancario = apps.get_model('tesoreria', 'MovimientoBancario')

    usados = set()
    for anticipo in AnticipoLaboral.objects.filter(
        estado='descontado',
        movimiento_pago__isnull=True,
    ).select_related('trabajador'):
        nombre = f'{anticipo.trabajador.nombres} {anticipo.trabajador.apellidos}'
        descripcion = f'Anticipo {nombre} - {anticipo.fecha}'
        candidatos = list(
            MovimientoBancario.objects.filter(
                tipo='egreso',
                monto=anticipo.monto,
                descripcion=descripcion,
            ).exclude(pk__in=usados).values_list('pk', flat=True)[:2]
        )
        if len(candidatos) == 1:
            AnticipoLaboral.objects.filter(pk=anticipo.pk).update(
                movimiento_pago_id=candidatos[0],
            )
            usados.add(candidatos[0])


class Migration(migrations.Migration):

    dependencies = [
        ('rrhh', '0008_remuneracion_impuesto_unico'),
        ('tesoreria', '0004_movimientobancario_conciliado_por_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='anticipolaboral',
            name='movimiento_pago',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='anticipo_laboral',
                to='tesoreria.movimientobancario',
                verbose_name='Movimiento de pago',
            ),
        ),
        migrations.RunPython(
            vincular_movimientos_legacy,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
