from django.db import migrations


def recalcular_indices_por_periodo(apps, schema_editor):
    FacturaRecibida = apps.get_model('proveedores', 'FacturaRecibida')
    FacturaRecibida.objects.update(
        correlativo_libro_compras=None,
        periodo_libro_compras_mes=None,
        periodo_libro_compras_anio=None,
    )

    correlativos_por_periodo = {}
    for factura in FacturaRecibida.objects.order_by('id').iterator():
        periodo = (factura.fecha_emision.year, factura.fecha_emision.month)
        indice = correlativos_por_periodo.get(periodo, 0) + 1
        correlativos_por_periodo[periodo] = indice
        FacturaRecibida.objects.filter(pk=factura.pk).update(
            correlativo_libro_compras=indice,
            periodo_libro_compras_mes=periodo[1],
            periodo_libro_compras_anio=periodo[0],
        )


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0027_recalcular_indice_factura_por_orden_id'),
    ]

    operations = [
        migrations.RunPython(
            recalcular_indices_por_periodo,
            migrations.RunPython.noop,
        ),
    ]
