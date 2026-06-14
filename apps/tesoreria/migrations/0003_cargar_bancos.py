from django.db import migrations


BANCOS = [
    ("1", "Banco de Chile / A. Edwards / Citibank N.A."),
    ("9", "Banco Internacional"),
    ("11", "Dresdner Bank Leteinamerika"),
    ("12", "Banco del Estado de Chile"),
    ("14", "Scotiabank"),
    ("16", "Banco Crédito e Inversiones"),
    ("17", "Banco Do Brasil S.A."),
    ("27", "Corpbanca"),
    ("28", "Banco Bice"),
    ("31", "HSBC Bank Chile"),
    ("37", "Banco Santander - Santiago"),
    ("39", "Banco Itaú"),
    ("41", "JP Morgan Chase Bank"),
    ("43", "Banco de la Nación Argentina"),
    ("45", "The Bank of Tokyo – Mitsubishi"),
    ("46", "Abn Amro Bank (Chile)"),
    ("49", "Banco Security"),
    ("51", "Banco Falabella"),
    ("52", "Deutsche Bank (Chile)"),
    ("53", "Banco Ripley"),
    ("54", "HNS Banco"),
    ("55", "Banco Monex"),
    ("116", "MACH"),
    ("504", "BBVA Banco Bhif"),
    ("507", "Banco del Desarrollo"),
    ("734", "Banco Conosur"),
]


def cargar_bancos(apps, schema_editor):
    Banco = apps.get_model("tesoreria", "Banco")

    for codigo, nombre in BANCOS:
        Banco.objects.update_or_create(
            codigo=codigo,
            defaults={"nombre": nombre},
        )


def eliminar_bancos(apps, schema_editor):
    Banco = apps.get_model("tesoreria", "Banco")
    codigos = [codigo for codigo, _ in BANCOS]
    Banco.objects.filter(codigo__in=codigos).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tesoreria", "0002_libro_diario"),
    ]

    operations = [
        migrations.RunPython(cargar_bancos, eliminar_bancos),
    ]
