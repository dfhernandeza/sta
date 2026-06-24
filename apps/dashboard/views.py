from decimal import Decimal

from django.views.generic import TemplateView
from django.db.models import Sum
from django.utils import timezone
from apps.core.mixins import AppPermisoMixin

class DashboardMixin(AppPermisoMixin):
    app_name = 'dashboard'

from apps.clientes.models import FacturaEmitida, CuentaPorCobrar
from apps.proveedores.models import FacturaRecibida
from apps.tesoreria.models import CuentaBancaria
from apps.proyectos.models import Proyecto
from apps.contabilidad.models import ConfiguracionContable, LineaAsiento
from apps.rrhh.models import Remuneracion
import json


class DashboardView(DashboardMixin, TemplateView):
    template_name = 'admin/dashboard/index.html'
    CUENTAS_SALDO_DEUDOR = {'activo', 'costo', 'gasto'}

    def _saldo_cuenta(self, cuenta):
        if not cuenta:
            return Decimal('0')

        saldos = LineaAsiento.objects.filter(
            asiento__estado='confirmado',
            cuenta=cuenta,
        ).aggregate(
            debe=Sum('debe'),
            haber=Sum('haber'),
        )
        debe = saldos['debe'] or Decimal('0')
        haber = saldos['haber'] or Decimal('0')

        if cuenta.tipo in self.CUENTAS_SALDO_DEUDOR:
            return debe - haber
        return haber - debe

    def _saldo_config(self, config, *field_names):
        total = Decimal('0')
        cuentas_usadas = set()
        for field_name in field_names:
            cuenta = getattr(config, field_name, None)
            if not cuenta or cuenta.pk in cuentas_usadas:
                continue
            cuentas_usadas.add(cuenta.pk)
            total += self._saldo_cuenta(cuenta)
        return total

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

        # Sueldos pagados el mes
        remuneraciones_pagadas_mes = Remuneracion.objects.filter(
            estado='pagado',
            fecha_pago__month=mes_actual,
            fecha_pago__year=anio_actual
        )
        ctx['sueldos_pagados_mes'] = remuneraciones_pagadas_mes.aggregate(t=Sum('liquido_pagar'))['t'] or 0

        ctx['egresos_mes'] += ctx['sueldos_pagados_mes']
        ctx['utilidad_mes'] = ctx['ingresos_mes'] - ctx['egresos_mes']

        # CxC vencidas
        ctx['cxc_vencidas'] = CuentaPorCobrar.objects.filter(
            estado__in=['pendiente', 'vencida'],
            fecha_vencimiento__lt=hoy
        ).select_related('factura__cliente').order_by('fecha_vencimiento')[:10]

        # Saldos del resumen rápido desde las cuentas configuradas
        config_contable = ConfiguracionContable.get()
        ctx['total_cxc_pendiente'] = self._saldo_config(config_contable, 'cuenta_cxc')
        ctx['total_cxp_pendiente'] = self._saldo_config(config_contable, 'cuenta_cxp')
        ctx['sueldos_por_pagar'] = self._saldo_config(config_contable, 'cuenta_sueldos_por_pagar')
        ctx['afp_por_pagar'] = self._saldo_config(config_contable, 'cuenta_afp_por_pagar')
        ctx['salud_por_pagar'] = self._saldo_config(config_contable, 'cuenta_salud_por_pagar')
        ctx['previred_por_pagar'] = self._saldo_config(
            config_contable,
            'cuenta_afp_por_pagar',
            'cuenta_salud_por_pagar',
        )
        ctx['impuestos_sii_por_pagar'] = self._saldo_config(
            config_contable,
            'cuenta_impuestos_sii',
            'cuenta_retenciones_honorarios',
        )

        # Proyectos activos
        ctx['proyectos_activos'] = Proyecto.objects.filter(
            estado='en_ejecucion'
        ).count()

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
