from django.db import migrations, models
from django.utils import timezone


def asignar_correlativos_existentes(apps, schema_editor):
    FacturaEmitida = apps.get_model('clientes', 'FacturaEmitida')
    contadores = {}

    facturas = FacturaEmitida.objects.order_by('creado_en', 'id')
    for factura in facturas:
        fecha_creacion = factura.creado_en
        if timezone.is_aware(fecha_creacion):
            fecha_ingreso = timezone.localtime(fecha_creacion).date()
        else:
            fecha_ingreso = fecha_creacion.date()

        periodo = (fecha_ingreso.year, fecha_ingreso.month)
        contadores[periodo] = contadores.get(periodo, 0) + 1

        factura.periodo_libro_ventas_anio = fecha_ingreso.year
        factura.periodo_libro_ventas_mes = fecha_ingreso.month
        factura.correlativo_libro_ventas = contadores[periodo]
        factura.save(update_fields=[
            'periodo_libro_ventas_anio',
            'periodo_libro_ventas_mes',
            'correlativo_libro_ventas',
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('clientes', '0006_add_movimiento_pago_to_cxp_cxc'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturaemitida',
            name='correlativo_libro_ventas',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Correlativo Libro de Ventas'),
        ),
        migrations.AddField(
            model_name='facturaemitida',
            name='periodo_libro_ventas_anio',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Año Libro de Ventas'),
        ),
        migrations.AddField(
            model_name='facturaemitida',
            name='periodo_libro_ventas_mes',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Mes Libro de Ventas'),
        ),
        migrations.RunPython(asignar_correlativos_existentes, noop),
        migrations.AddConstraint(
            model_name='facturaemitida',
            constraint=models.UniqueConstraint(fields=('periodo_libro_ventas_anio', 'periodo_libro_ventas_mes', 'correlativo_libro_ventas'), name='uniq_factura_emitida_correlativo_libro_ventas'),
        ),
    ]
