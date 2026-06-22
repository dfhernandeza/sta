import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Creates the RendicionGastos and DetalleRendicion models in the rendiciones app.

    Uses SeparateDatabaseAndState so that no DB changes happen — the tables already
    exist as proveedores_rendiciongastos and proveedores_detallerendicion and are
    preserved via Meta.db_table in each model.
    """

    initial = True

    dependencies = [
        ('contabilidad', '0001_initial'),
        ('proyectos', '0001_initial'),
        ('proveedores', '0017_alter_detalle_decimal_places'),
        ('rrhh', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='RendicionGastos',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('fecha', models.DateField(verbose_name='Fecha de Rendición')),
                        ('motivo_del_gasto', models.CharField(max_length=300, verbose_name='Motivo del gasto')),
                        ('estado', models.CharField(
                            choices=[
                                ('borrador', 'Borrador'),
                                ('enviado', 'Enviado para revisión'),
                                ('aprobado', 'Aprobado'),
                                ('rechazado', 'Rechazado'),
                                ('pagada', 'Pagada'),
                            ],
                            default='borrador', max_length=15, verbose_name='Estado'
                        )),
                        ('trabajador', models.ForeignKey(
                            on_delete=django.db.models.deletion.PROTECT,
                            related_name='rendiciones',
                            to='rrhh.trabajador',
                            verbose_name='Trabajador',
                        )),
                        ('proyecto', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            to='proyectos.proyecto',
                            verbose_name='Proyecto',
                        )),
                    ],
                    options={
                        'verbose_name': 'Rendición de Gastos',
                        'verbose_name_plural': 'Rendiciones de Gastos',
                        'ordering': ['-id'],
                        'db_table': 'proveedores_rendiciongastos',
                    },
                ),
                migrations.CreateModel(
                    name='DetalleRendicion',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('fecha_gasto', models.DateField(verbose_name='Fecha del gasto')),
                        ('n_boleta_factura', models.CharField(max_length=100, verbose_name='N° Boleta o Factura')),
                        ('descripcion', models.CharField(max_length=300, verbose_name='Descripción del gasto')),
                        ('monto', models.DecimalField(decimal_places=2, max_digits=15, verbose_name='Monto del gasto')),
                        ('rendicion', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='detalles',
                            to='rendiciones.rendiciongastos',
                            verbose_name='Rendición de Gastos',
                        )),
                        ('centro_costo', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            to='contabilidad.centrocosto',
                            verbose_name='Centro de Costo',
                        )),
                        ('cuenta_contable', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            to='contabilidad.plancuentas',
                            verbose_name='Cuenta contable',
                        )),
                        ('proveedor', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            to='proveedores.proveedor',
                            verbose_name='Proveedor',
                        )),
                    ],
                    options={
                        'verbose_name': 'Detalle de Rendición',
                        'verbose_name_plural': 'Detalles de Rendiciones',
                        'db_table': 'proveedores_detallerendicion',
                    },
                ),
            ],
            database_operations=[
                # Tables already exist in the DB; nothing to create.
            ],
        ),
    ]
