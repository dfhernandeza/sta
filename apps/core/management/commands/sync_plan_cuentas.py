# management/commands/sync_plan_cuentas.py
from django.core.management.base import BaseCommand
from apps.contabilidad.models import PlanCuentas

NUEVAS_CUENTAS = [
    # (codigo, nombre, tipo, nivel, codigo_parent)
    ("7",          "PATRIMONIO",             "patrimonio", 1, None),
    ("7.01",       "Capital",                "patrimonio", 2, "7"),
    ("7.01.01",    "Capital Social",         "patrimonio", 3, "7.01"),
    ("7.01.01.01", "Capital Socios",         "patrimonio", 4, "7.01.01"),
    ("7.02",       "Resultados",             "patrimonio", 2, "7"),
    ("7.02.01",    "Resultados Acumulados",  "patrimonio", 3, "7.02"),
    ("7.02.01.01", "Utilidades Retenidas",   "patrimonio", 4, "7.02.01"),
    ("7.02.02",    "Resultado del Ejercicio","patrimonio", 3, "7.02"),
    ("7.02.02.01", "Utilidad o Perdida",     "patrimonio", 4, "7.02.02"),
    ("7.03",       "Reservas",               "patrimonio", 2, "7"),
    ("7.03.01",    "Reserva Legal",          "patrimonio", 3, "7.03"),
    ("7.03.01.01", "Reserva Legal 10%",      "patrimonio", 4, "7.03.01"),
]

class Command(BaseCommand):
    help = "Agrega cuentas faltantes sin duplicar"

    def handle(self, *args, **kwargs):
        for codigo, nombre, tipo, nivel, parent_codigo in NUEVAS_CUENTAS:
            parent = PlanCuentas.objects.filter(codigo=parent_codigo).first() if parent_codigo else None
            obj, created = PlanCuentas.objects.get_or_create(
                codigo=codigo,
                defaults={
                    "nombre": nombre,
                    "tipo": tipo,
                    "nivel": nivel,
                    "parent": parent,
                    "activa": True,
                    "acepta_movimientos": (nivel == 4),
                }
            )
            status = "creada" if created else "ya existe"
            self.stdout.write(f"{codigo} — {nombre}: {status}")