import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Updates AsientoContable.rendicion_gastos FK to point to rendiciones.RendicionGastos.

    Uses SeparateDatabaseAndState because the underlying DB column (rendicion_gastos_id)
    already points to the same physical table (proveedores_rendiciongastos, kept via
    db_table in the rendiciones model), so no DDL changes are needed.
    """

    dependencies = [
        ('contabilidad', '0014_add_centro_costo_to_linea_asiento'),
        ('rendiciones', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='asientocontable',
                    name='rendicion_gastos',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='asientos',
                        to='rendiciones.rendiciongastos',
                        verbose_name='Rendición de Gastos',
                    ),
                ),
            ],
            database_operations=[
                # The FK column already references the correct physical table.
            ],
        ),
    ]
