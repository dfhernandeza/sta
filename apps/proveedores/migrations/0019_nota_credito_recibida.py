import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contabilidad', '0015_update_rendicion_gastos_fk'),
        ('proveedores', '0018_move_rendicion_to_rendiciones_app'),
    ]

    operations = [
        migrations.CreateModel(
            name='NotaCreditoRecibida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('numero', models.CharField(max_length=20, verbose_name='N° Nota de Crédito')),
                ('fecha_emision', models.DateField(verbose_name='Fecha de Emisión')),
                ('neto', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='Monto Neto Afecto')),
                ('exento', models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name='Monto Exento')),
                ('iva', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='IVA (19%)')),
                ('total', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='Total')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('aplicada', 'Aplicada'), ('anulada', 'Anulada')], default='aplicada', max_length=15, verbose_name='Estado')),
                ('observaciones', models.TextField(blank=True, verbose_name='Observaciones')),
                ('factura', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notas_credito', to='proveedores.facturarecibida', verbose_name='Factura asociada')),
                ('proveedor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='notas_credito', to='proveedores.proveedor', verbose_name='Proveedor')),
            ],
            options={
                'verbose_name': 'Nota de Crédito Recibida',
                'verbose_name_plural': 'Notas de Crédito Recibidas',
                'ordering': ['-fecha_emision'],
                'unique_together': {('proveedor', 'numero')},
            },
        ),
        migrations.CreateModel(
            name='DetalleNotaCreditoRecibida',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('descripcion', models.CharField(max_length=300, verbose_name='Descripción')),
                ('cantidad', models.DecimalField(decimal_places=4, default=1, max_digits=10, verbose_name='Cantidad')),
                ('precio_unitario', models.DecimalField(decimal_places=4, max_digits=15, verbose_name='Precio Unitario')),
                ('exento_iva', models.BooleanField(default=False, verbose_name='Exento de IVA')),
                ('centro_costo', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contabilidad.centrocosto', verbose_name='Centro de Costo')),
                ('cuenta_contable', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='contabilidad.plancuentas', verbose_name='Cuenta contable')),
                ('nota_credito', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='detalles', to='proveedores.notacreditorecibida', verbose_name='Nota de Crédito')),
            ],
            options={
                'verbose_name': 'Detalle Nota de Crédito Recibida',
                'verbose_name_plural': 'Detalles Notas de Crédito Recibidas',
            },
        ),
    ]
