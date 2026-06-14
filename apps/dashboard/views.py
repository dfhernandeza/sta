from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from django.utils import timezone
from apps.core.mixins import GestionMixin
from apps.clientes.models import FacturaEmitida, CuentaPorCobrar
from apps.proveedores.models import FacturaRecibida, CuentaPorPagar
from apps.tesoreria.models import CuentaBancaria
from apps.proyectos.models import Proyecto
from apps.tributario.models import FormularioF29, DeclaracionIVA
from apps.rrhh.models import Trabajador, Remuneracion
import json


class DashboardView(GestionMixin, TemplateView):
    template_name = 'admin/dashboard/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.now().date()
        mes_actual = hoy.month
        anio_actual = hoy.year

        # KPIs bancarios
        cuentas = CuentaBancaria.objects.filter(activa=True)
        ctx['saldo_total'] = sum(c.saldo_actual for c in cuentas)
        ctx['cuentas_bancarias'] = cuentas

        # Facturas del mes
        facturas_emitidas_mes = FacturaEmitida.objects.filter(
            fecha_emision__month=mes_actual, fecha_emision__year=anio_actual
        ).exclude(estado='anulada')
        ctx['ingresos_mes'] = facturas_emitidas_mes.aggregate(t=Sum('total'))['t'] or 0
        ctx['facturas_emitidas_mes'] = facturas_emitidas_mes.count()

        facturas_recibidas_mes = FacturaRecibida.objects.filter(
            fecha_emision__month=mes_actual, fecha_emision__year=anio_actual
        ).exclude(estado='anulada')
        ctx['egresos_mes'] = facturas_recibidas_mes.aggregate(t=Sum('total'))['t'] or 0

        ctx['utilidad_mes'] = ctx['ingresos_mes'] - ctx['egresos_mes']

        # Sueldos pagados el mes
        remuneraciones_pagadas_mes = Remuneracion.objects.filter(
            estado='pagado',
            fecha_pago__month=mes_actual,
            fecha_pago__year=anio_actual
        )
        ctx['sueldos_pagados_mes'] = remuneraciones_pagadas_mes.aggregate(t=Sum('liquido_pagar'))['t'] or 0

        # CxC vencidas
        ctx['cxc_vencidas'] = CuentaPorCobrar.objects.filter(
            estado__in=['pendiente', 'vencida'],
            fecha_vencimiento__lt=hoy
        ).select_related('factura__cliente').order_by('fecha_vencimiento')[:10]

        ctx['total_cxc_pendiente'] = CuentaPorCobrar.objects.filter(
            estado__in=['pendiente', 'vencida']
        ).aggregate(t=Sum('monto'))['t'] or 0

        # CxP pendientes
        ctx['total_cxp_pendiente'] = CuentaPorPagar.objects.filter(
            estado__in=['pendiente', 'vencida']
        ).aggregate(t=Sum('monto'))['t'] or 0

        # Proyectos activos
        ctx['proyectos_activos'] = Proyecto.objects.filter(
            estado='en_ejecucion'
        ).count()

        # F29 pendientes
        ctx['f29_pendientes'] = FormularioF29.objects.filter(
            estado='pendiente'
        ).order_by('-periodo_anio', '-periodo_mes')[:3]

        # Datos para gráfico de los últimos 6 meses
        meses_labels = []
        ingresos_data = []
        egresos_data = []
        for i in range(5, -1, -1):
            if mes_actual - i <= 0:
                m = mes_actual - i + 12
                a = anio_actual - 1
            else:
                m = mes_actual - i
                a = anio_actual
            meses_labels.append(f'{m:02d}/{a}')
            ing = FacturaEmitida.objects.filter(
                fecha_emision__month=m, fecha_emision__year=a
            ).exclude(estado='anulada').aggregate(t=Sum('total'))['t'] or 0
            egr = FacturaRecibida.objects.filter(
                fecha_emision__month=m, fecha_emision__year=a
            ).exclude(estado='anulada').aggregate(t=Sum('total'))['t'] or 0
            sueldos = Remuneracion.objects.filter(
                estado='pagado',
                fecha_pago__month=m,
                fecha_pago__year=a
            ).aggregate(t=Sum('liquido_pagar'))['t'] or 0

            egr += sueldos  # Incluir sueldos como parte de los egresos para el gráfico


            ingresos_data.append(float(ing))
            egresos_data.append(float(egr))

        ctx['chart_labels'] = json.dumps(meses_labels)
        ctx['chart_ingresos'] = json.dumps(ingresos_data)
        ctx['chart_egresos'] = json.dumps(egresos_data)

        return ctx
