from django.db import migrations


class Migration(migrations.Migration):
    """
    Aligns the migration state with TimeStampedModel field names.

    The rendiciones models reuse existing proveedores_* tables through db_table, so
    this must not issue DDL. It only fixes Django's migration state to avoid
    makemigrations detecting created_at/updated_at as pending renames.
    """

    dependencies = [
        ('rendiciones', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name='rendiciongastos',
                    old_name='created_at',
                    new_name='creado_en',
                ),
                migrations.RenameField(
                    model_name='rendiciongastos',
                    old_name='updated_at',
                    new_name='actualizado_en',
                ),
            ],
            database_operations=[],
        ),
    ]
