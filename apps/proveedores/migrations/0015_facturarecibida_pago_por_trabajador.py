from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('rrhh', '0006_remove_trabajador_foto'),
        ('proveedores', '0014_facturarecibida_exento'),
    ]

    operations = [
        migrations.AddField(
            model_name='facturarecibida',
            name='pago_por_trabajador',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='facturas_pagadas',
                to='rrhh.trabajador',
                verbose_name='Pagada por trabajador',
            ),
        ),
    ]
