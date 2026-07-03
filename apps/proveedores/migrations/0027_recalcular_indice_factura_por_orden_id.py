from django.db import migrations


def recalcular_indices_por_orden_id(apps, schema_editor):
    FacturaRecibida = apps.get_model('proveedores', 'FacturaRecibida')
    FacturaRecibida.objects.update(
        correlativo_libro_compras=None,
        periodo_libro_compras_mes=None,
        periodo_libro_compras_anio=None,
    )

    for indice, factura in enumerate(
        FacturaRecibida.objects.order_by('id').iterator(),
        start=1,
    ):
        FacturaRecibida.objects.filter(pk=factura.pk).update(
            correlativo_libro_compras=indice,
            periodo_libro_compras_mes=factura.fecha_emision.month,
            periodo_libro_compras_anio=factura.fecha_emision.year,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0026_anticipo_movimiento_pago'),
    ]

    operations = [
        migrations.RunPython(
            recalcular_indices_por_orden_id,
            migrations.RunPython.noop,
        ),
    ]
