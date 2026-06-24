import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0019_nota_credito_recibida'),
        ('contabilidad', '0015_update_rendicion_gastos_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='asientocontable',
            name='tipo',
            field=models.CharField(choices=[('apertura', 'Asiento de Apertura'), ('factura_venta', 'Factura de Venta'), ('factura_compra', 'Factura de Compra'), ('nota_credito_compra', 'Nota de Crédito de Compra'), ('pago_cxc', 'Cobro CxC'), ('pago_cxp', 'Pago CxP'), ('movimiento_banco', 'Movimiento Bancario'), ('devengamiento_remuneracion', 'Devengamiento de Remuneración'), ('pago_remuneracion', 'Pago de Remuneración'), ('pago_anticipo', 'Pago de Anticipo Laboral'), ('pago_anticipo_proveedor', 'Pago de Anticipo a Proveedor'), ('ajuste', 'Ajuste Contable'), ('rendicion_gastos', 'Rendición de Gastos'), ('otro', 'Otro')], default='otro', max_length=30, verbose_name='Tipo'),
        ),
        migrations.AddField(
            model_name='asientocontable',
            name='nota_credito_recibida',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asientos', to='proveedores.notacreditorecibida', verbose_name='Nota de Crédito Recibida'),
        ),
    ]
