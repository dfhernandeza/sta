from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.views.generic import TemplateView
from django.db.models import Q, Sum
from django.utils import timezone
from apps.core.mixins import AppPermisoMixin

class DashboardMixin(AppPermisoMixin):
    app_name = 'dashboard'

from apps.clientes.models import FacturaEmitida, CuentaPorCobrar
from apps.proveedores.models import FacturaRecibida
from apps.tesoreria.models import CuentaBancaria
from apps.proyectos.models import Proyecto
from apps.contabilidad.models import AsientoContable, ConfiguracionContable, LineaAsiento
from apps.rrhh.models import Remuneracion
import json


class DashboardView(DashboardMixin, TemplateView):
    template_name = 'admin/dashboard/index.html'
    CUENTAS_SALDO_DEUDOR = {'activo', 'costo', 'gasto'}

    def _saldo_cuenta(self, cuenta, desde=None, hasta=None):
        if not cuenta:
            return Decimal('0')

        lineas = LineaAsiento.objects.filter(
            asiento__estado='confirmado',
            cuenta=cuenta,
        )
        if desde:
            lineas = lineas.filter(asiento__fecha__gte=desde)
        if hasta:
            lineas = lineas.filter(asiento__fecha__lte=hasta)

        saldos = lineas.aggregate(
            debe=Sum('debe'),
            haber=Sum('haber'),
        )
        debe = saldos['debe'] or Decimal('0')
        haber = saldos['haber'] or Decimal('0')

        if cuenta.tipo in self.CUENTAS_SALDO_DEUDOR:
            return debe - haber
        return haber - debe

    def _saldo_config(self, config, *field_names, desde=None, hasta=None):
        total = Decimal('0')
        cuentas_usadas = set()
        for field_name in field_names:
            cuenta = getattr(config, field_name, None)
            if not cuenta or cuenta.pk in cuentas_usadas:
                continue
            cuentas_usadas.add(cuenta.pk)
            total += self._saldo_cuenta(cuenta, desde=desde, hasta=hasta)
        return total

    @staticmethod
    def _desplazar_mes(anio, mes, desplazamiento):
        indice = anio * 12 + mes - 1 + desplazamiento
        nuevo_anio, nuevo_mes_cero = divmod(indice, 12)
        return nuevo_anio, nuevo_mes_cero + 1

    def _obtener_periodo(self):
        hoy = timezone.localdate()
        periodo = self.request.GET.get('periodo', '')
        try:
            anio, mes = (int(valor) for valor in periodo.split('-', 1))
            if not 1 <= mes <= 12:
                raise ValueError
            return anio, mes
        except (TypeError, ValueError):
            return hoy.year, hoy.month

    @staticmethod
    def _saldo_bancario(cuenta, desde, hasta, incluir_saldo_inicial):
        movimientos = cuenta.movimientos.filter(fecha__lte=hasta)
        if desde:
            movimientos = movimientos.filter(fecha__gte=desde)
        totales = movimientos.values('tipo').annotate(total=Sum('monto'))
        por_tipo = {fila['tipo']: fila['total'] for fila in totales}
        saldo = cuenta.saldo_inicial if incluir_saldo_inicial else Decimal('0')
        return (
            saldo
            + (por_tipo.get('ingreso') or Decimal('0'))
            - (por_tipo.get('egreso') or Decimal('0'))
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        anio_actual, mes_actual = self._obtener_periodo()
        inicio_mes = date(anio_actual, mes_actual, 1)
        fin_mes = date(anio_actual, mes_actual, monthrange(anio_actual, mes_actual)[1])

        apertura = (
            AsientoContable.objects
            .filter(tipo='apertura')
            .exclude(estado='anulado')
            .order_by('fecha', 'id')
            .first()
        )
        fecha_inicio_sistema = apertura.fecha if apertura else None
        inicio_periodo_efectivo = max(
            fecha for fecha in (inicio_mes, fecha_inicio_sistema) if fecha
        )
        periodo_fuera_sistema = inicio_periodo_efectivo > fin_mes

        # KPIs bancarios
        cuentas = CuentaBancaria.objects.filter(activa=True).select_related('banco')
        incluir_saldo_inicial = (
            not fecha_inicio_sistema or fin_mes >= fecha_inicio_sistema
        )
        for cuenta in cuentas:
            cuenta.saldo_periodo = self._saldo_bancario(
                cuenta,
                desde=fecha_inicio_sistema,
                hasta=fin_mes,
                incluir_saldo_inicial=incluir_saldo_inicial,
            )
        ctx['saldo_total'] = sum(
            (c.saldo_periodo for c in cuentas),
            Decimal('0'),
        )
        ctx['cuentas_bancarias'] = cuentas

        # Facturas del mes
        facturas_emitidas_mes = FacturaEmitida.objects.none()
        facturas_recibidas_mes = FacturaRecibida.objects.none()
        remuneraciones_pagadas_mes = Remuneracion.objects.none()
        if not periodo_fuera_sistema:
            facturas_emitidas_mes = FacturaEmitida.objects.filter(
                fecha_emision__range=(inicio_periodo_efectivo, fin_mes),
            ).exclude(estado='anulada')
            facturas_recibidas_mes = FacturaRecibida.objects.filter(
                fecha_emision__range=(inicio_periodo_efectivo, fin_mes),
            ).exclude(estado='anulada')
            remuneraciones_pagadas_mes = Remuneracion.objects.filter(
                estado='pagado',
                fecha_pago__range=(inicio_periodo_efectivo, fin_mes),
            )

        ctx['ingresos_mes'] = facturas_emitidas_mes.aggregate(t=Sum('total'))['t'] or 0
        ctx['facturas_emitidas_mes'] = facturas_emitidas_mes.count()
        ctx['egresos_mes'] = facturas_recibidas_mes.aggregate(t=Sum('total'))['t'] or 0

        # Sueldos pagados el mes
        ctx['sueldos_pagados_mes'] = remuneraciones_pagadas_mes.aggregate(t=Sum('liquido_pagar'))['t'] or 0

        ctx['egresos_mes'] += ctx['sueldos_pagados_mes']
        ctx['utilidad_mes'] = ctx['ingresos_mes'] - ctx['egresos_mes']

        # CxC vencidas
        ctx['cxc_vencidas'] = CuentaPorCobrar.objects.filter(
            estado__in=['pendiente', 'vencida'],
            factura__fecha_emision__range=(inicio_periodo_efectivo, fin_mes),
            fecha_vencimiento__lte=fin_mes,
        ).select_related('factura__cliente').order_by('fecha_vencimiento')[:10]

        # Saldos del resumen rápido desde las cuentas configuradas
        config_contable = ConfiguracionContable.get()
        saldo_kwargs = {
            'desde': fecha_inicio_sistema,
            'hasta': fin_mes,
        }
        ctx['total_cxc_pendiente'] = self._saldo_config(
            config_contable, 'cuenta_cxc', **saldo_kwargs
        )
        ctx['total_cxp_pendiente'] = self._saldo_config(
            config_contable, 'cuenta_cxp', **saldo_kwargs
        )
        ctx['sueldos_por_pagar'] = self._saldo_config(
            config_contable, 'cuenta_sueldos_por_pagar', **saldo_kwargs
        )
        ctx['afp_por_pagar'] = self._saldo_config(
            config_contable, 'cuenta_afp_por_pagar', **saldo_kwargs
        )
        ctx['salud_por_pagar'] = self._saldo_config(
            config_contable, 'cuenta_salud_por_pagar', **saldo_kwargs
        )
        ctx['previred_por_pagar'] = self._saldo_config(
            config_contable,
            'cuenta_afp_por_pagar',
            'cuenta_salud_por_pagar',
            **saldo_kwargs,
        )
        ctx['impuestos_sii_por_pagar'] = self._saldo_config(
            config_contable,
            'cuenta_impuestos_sii',
            'cuenta_retenciones_honorarios',
            **saldo_kwargs,
        )

        # Proyectos activos
        if periodo_fuera_sistema:
            ctx['proyectos_activos'] = 0
        else:
            ctx['proyectos_activos'] = Proyecto.objects.filter(
                estado='en_ejecucion',
            ).filter(
                Q(fecha_inicio__isnull=True) | Q(fecha_inicio__lte=fin_mes),
                Q(fecha_termino__isnull=True) | Q(fecha_termino__gte=inicio_periodo_efectivo),
            ).count()

        # Datos para gráfico de los últimos 6 meses
        meses_labels = []
        ingresos_data = []
        egresos_data = []
        for i in range(5, -1, -1):
            a, m = self._desplazar_mes(anio_actual, mes_actual, -i)
            inicio_grafico = date(a, m, 1)
            fin_grafico = date(a, m, monthrange(a, m)[1])
            inicio_grafico_efectivo = max(
                fecha for fecha in (inicio_grafico, fecha_inicio_sistema) if fecha
            )
            meses_labels.append(f'{m:02d}/{a}')
            ing = Decimal('0')
            egr = Decimal('0')
            if inicio_grafico_efectivo <= fin_grafico:
                ing = FacturaEmitida.objects.filter(
                    fecha_emision__range=(inicio_grafico_efectivo, fin_grafico),
                ).exclude(estado='anulada').aggregate(t=Sum('total'))['t'] or Decimal('0')
                egr = FacturaRecibida.objects.filter(
                    fecha_emision__range=(inicio_grafico_efectivo, fin_grafico),
                ).exclude(estado='anulada').aggregate(t=Sum('total'))['t'] or Decimal('0')
                sueldos = Remuneracion.objects.filter(
                    estado='pagado',
                    fecha_pago__range=(inicio_grafico_efectivo, fin_grafico),
                ).aggregate(t=Sum('liquido_pagar'))['t'] or Decimal('0')
                egr += sueldos

            ingresos_data.append(float(ing))
            egresos_data.append(float(egr))

        nombres_meses = [
            '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
        ]
        ctx['periodo_seleccionado'] = f'{anio_actual:04d}-{mes_actual:02d}'
        ctx['periodo_label'] = f'{nombres_meses[mes_actual]} {anio_actual}'
        ctx['fecha_inicio_sistema'] = fecha_inicio_sistema
        ctx['periodo_fuera_sistema'] = periodo_fuera_sistema
        ctx['chart_labels'] = json.dumps(meses_labels)
        ctx['chart_ingresos'] = json.dumps(ingresos_data)
        ctx['chart_egresos'] = json.dumps(egresos_data)

        return ctx
