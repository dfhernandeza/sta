import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Removes RendicionGastos and DetalleRendicion from the proveedores app state
    (they now live in apps.rendiciones) and updates CuentaPorPagar.rendicion FK.

    Uses SeparateDatabaseAndState: the physical tables are retained unchanged
    (still named proveedores_rendiciongastos / proveedores_detallerendicion,
    preserved via db_table in the rendiciones models).
    """

    dependencies = [
        ('proveedores', '0017_alter_detalle_decimal_places'),
        ('rendiciones', '0001_initial'),
        ('contabilidad', '0015_update_rendicion_gastos_fk'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                # 1. Update CuentaPorPagar.rendicion FK to point to rendiciones app
                migrations.AlterField(
                    model_name='cuentaporpagar',
                    name='rendicion',
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='cuentas_pagar',
                        to='rendiciones.rendiciongastos',
                        verbose_name='Rendición de Gastos',
                    ),
                ),
                # 2. Remove DetalleRendicion first (FK dependency on RendicionGastos)
                migrations.DeleteModel(name='DetalleRendicion'),
                # 3. Remove RendicionGastos
                migrations.DeleteModel(name='RendicionGastos'),
            ],
            database_operations=[
                # No DDL needed: tables keep the same physical names via db_table.
            ],
        ),
    ]
