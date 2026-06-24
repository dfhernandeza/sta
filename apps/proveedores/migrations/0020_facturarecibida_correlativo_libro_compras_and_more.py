from django.db import migrations, models
from django.utils import timezone


def asignar_correlativos_existentes(apps, schema_editor):
    FacturaRecibida = apps.get_model('proveedores', 'FacturaRecibida')
    contadores = {}

    facturas = FacturaRecibida.objects.order_by('creado_en', 'id')
    for factura in facturas:
        fecha_creacion = factura.creado_en
        if timezone.is_aware(fecha_creacion):
            fecha_ingreso = timezone.localtime(fecha_creacion).date()
        else:
            fecha_ingreso = fecha_creacion.date()
        periodo = (fecha_ingreso.year, fecha_ingreso.month)
        contadores[periodo] = contadores.get(periodo, 0) + 1

        factura.periodo_libro_compras_anio = fecha_ingreso.year
        factura.periodo_libro_compras_mes = fecha_ingreso.month
        factura.correlativo_libro_compras = contadores[periodo]
        factura.save(update_fields=[
            'periodo_libro_compras_anio',
            'periodo_libro_compras_mes',
            'correlativo_libro_compras',
        ])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0019_nota_credito_recibida'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturarecibida',
            name='correlativo_libro_compras',
            field=models.PositiveIntegerField(blank=True, editable=False, null=True, verbose_name='Correlativo Libro de Compras'),
        ),
        migrations.AddField(
            model_name='facturarecibida',
            name='periodo_libro_compras_anio',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Año Libro de Compras'),
        ),
        migrations.AddField(
            model_name='facturarecibida',
            name='periodo_libro_compras_mes',
            field=models.PositiveSmallIntegerField(blank=True, editable=False, null=True, verbose_name='Mes Libro de Compras'),
        ),
        migrations.RunPython(asignar_correlativos_existentes, noop),
        migrations.AddConstraint(
            model_name='facturarecibida',
            constraint=models.UniqueConstraint(fields=('periodo_libro_compras_anio', 'periodo_libro_compras_mes', 'correlativo_libro_compras'), name='uniq_factura_recibida_correlativo_libro_compras'),
        ),
    ]
