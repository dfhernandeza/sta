import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('proveedores', '0019_nota_credito_recibida'),
        ('tributario', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='registrocompra',
            name='tipo_documento',
            field=models.CharField(choices=[('factura', 'Factura'), ('nota_credito', 'Nota de Crédito')], default='factura', max_length=20, verbose_name='Tipo de documento'),
        ),
        migrations.AlterField(
            model_name='registrocompra',
            name='factura',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='proveedores.facturarecibida', verbose_name='Factura'),
        ),
        migrations.AddField(
            model_name='registrocompra',
            name='nota_credito',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='proveedores.notacreditorecibida', verbose_name='Nota de Crédito'),
        ),
    ]
