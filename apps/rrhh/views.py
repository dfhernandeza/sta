from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.views import View
from django import forms
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from calendar import monthrange
from datetime import date
from decimal import Decimal
import json
from apps.core.mixins import GestionMixin, AppPermisoMixin

class RrhhMixin(AppPermisoMixin):
    app_name = 'rrhh'

from .models import (
    Trabajador, Remuneracion, AnticipoLaboral, CargoTrabajador,
    DeclaracionPrevisional,
)


class DeclaracionPrevisionalForm(forms.ModelForm):
    class Meta:
        model = DeclaracionPrevisional
        fields = ['periodo_mes', 'periodo_anio', 'folio', 'fecha_presentacion']
        widgets = {
            'periodo_mes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'periodo_anio': forms.NumberInput(attrs={'class': 'form-control', 'min': 2000}),
            'folio': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_presentacion': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

    def clean_periodo_mes(self):
        mes = self.cleaned_data['periodo_mes']
        if not 1 <= mes <= 12:
            raise forms.ValidationError('Ingrese un mes entre 1 y 12.')
        return mes

# Tasas AFP vigentes (cotización obligatoria empleado)
AFP_TASAS = {
    'capital':   Decimal('0.1144'),
    'cuprum':    Decimal('0.1144'),
    'habitat':   Decimal('0.1127'),
    'modelo':    Decimal('0.1058'),
    'planvital': Decimal('0.1116'),
    'provida':   Decimal('0.1144'),
    'uno':       Decimal('0.1049'),
}
TASA_SALUD_DEFAULT = Decimal('0.07')

MESES_NOMBRES = {
    1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
    5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
    9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre',
}


def _generar_periodos(n=15):
    now = timezone.now().date()
    year, month = now.year, now.month
    periods = []
    for _ in range(n):
        periods.append({'mes': month, 'anio': year, 'nombre': MESES_NOMBRES[month]})
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return periods


def _sincronizar_declaracion_previsional(declaracion):
    remuneraciones = Remuneracion.objects.filter(
        periodo_mes=declaracion.periodo_mes,
        periodo_anio=declaracion.periodo_anio,
    ).order_by('trabajador__apellidos', 'trabajador__nombres', 'pk')
    declaracion.remuneraciones.set(remuneraciones)
    declaracion.recalcular_totales()
    return remuneraciones


def _sincronizar_declaraciones_borrador(*periodos):
    periodos_validos = {(mes, anio) for mes, anio in periodos if mes and anio}
    for mes, anio in periodos_validos:
        for declaracion in DeclaracionPrevisional.objects.filter(
            periodo_mes=mes, periodo_anio=anio, estado='borrador',
        ):
            _sincronizar_declaracion_previsional(declaracion)


def _anticipo_disponible_para_liquidacion(
    trabajador,
    remuneracion=None,
    periodo_mes=None,
    periodo_anio=None,
):
    if remuneracion:
        periodo_mes = periodo_mes or remuneracion.periodo_mes
        periodo_anio = periodo_anio or remuneracion.periodo_anio

    anticipos = AnticipoLaboral.objects.filter(
        trabajador=trabajador,
        estado='descontado',
    )

    remuneraciones = Remuneracion.objects.filter(trabajador=trabajador)
    if remuneracion and remuneracion.pk:
        remuneraciones = remuneraciones.exclude(pk=remuneracion.pk)

    if periodo_mes and periodo_anio and 1 <= periodo_mes <= 12:
        ultimo_dia = monthrange(periodo_anio, periodo_mes)[1]
        cierre_periodo = date(periodo_anio, periodo_mes, ultimo_dia)
        anticipos = anticipos.filter(fecha__lte=cierre_periodo)
        remuneraciones = remuneraciones.filter(
            Q(periodo_anio__lt=periodo_anio)
            | Q(periodo_anio=periodo_anio, periodo_mes__lte=periodo_mes)
        )

    anticipos_pagados = anticipos.aggregate(s=Sum('monto'))['s'] or Decimal('0')
    ya_descontado = remuneraciones.aggregate(s=Sum('anticipo_descontado'))['s'] or Decimal('0')
    return max(anticipos_pagados - ya_descontado, Decimal('0'))


def _validar_anticipo_remuneracion(form, remuneracion=None):
    trabajador = form.cleaned_data.get('trabajador')
    anticipo_ingresado = form.cleaned_data.get('anticipo_descontado') or Decimal('0')
    try:
        periodo_mes = int(form.cleaned_data.get('periodo_mes'))
        periodo_anio = int(form.cleaned_data.get('periodo_anio'))
    except (TypeError, ValueError):
        return True

    if anticipo_ingresado < 0:
        form.add_error(
            'anticipo_descontado',
            'El anticipo descontado no puede ser negativo.',
        )
        return False
    if not trabajador:
        return True

    disponible = _anticipo_disponible_para_liquidacion(
        trabajador,
        remuneracion=remuneracion,
        periodo_mes=periodo_mes,
        periodo_anio=periodo_anio,
    )
    if anticipo_ingresado > disponible:
        disponible_formateado = f'{disponible:,.0f}'.replace(',', '.')
        form.add_error(
            'anticipo_descontado',
            f'El anticipo descontado no puede superar el saldo disponible '
            f'(${disponible_formateado}).',
        )
        return False
    return True


def _validar_montos_remuneracion(form):
    campos_no_negativos = [
        'sueldo_base', 'horas_extra', 'bono', 'sueldo_bruto',
        'descuento_afp', 'descuento_salud',
        'seguro_cesantia_trabajador', 'seguro_cesantia_empleador',
        'impuesto_unico', 'otros_descuentos', 'anticipo_descontado',
        'liquido_pagar',
    ]
    valido = True
    for campo in campos_no_negativos:
        monto = form.cleaned_data.get(campo)
        if monto is not None and monto < 0:
            form.add_error(campo, 'El monto no puede ser negativo.')
            valido = False

    if not valido:
        return False

    bruto = form.cleaned_data.get('sueldo_bruto') or Decimal('0')
    descuentos = sum(
        (form.cleaned_data.get(campo) or Decimal('0'))
        for campo in [
            'descuento_afp', 'descuento_salud',
            'seguro_cesantia_trabajador', 'impuesto_unico',
            'otros_descuentos', 'anticipo_descontado',
        ]
    )
    liquido_esperado = bruto - descuentos
    liquido = form.cleaned_data.get('liquido_pagar') or Decimal('0')
    if liquido_esperado < 0:
        form.add_error(None, 'Los descuentos no pueden superar el sueldo bruto.')
        return False
    if liquido != liquido_esperado:
        form.add_error(
            'liquido_pagar',
            f'El líquido debe ser {liquido_esperado:.2f} según los haberes y descuentos.',
        )
        return False
    return True


def _anticipo_laboral_respalda_descuentos(anticipo):
    anticipos_restantes = (
        AnticipoLaboral.objects.filter(
            trabajador_id=anticipo.trabajador_id,
            estado='descontado',
        )
        .exclude(pk=anticipo.pk)
        .aggregate(total=Sum('monto'))['total']
        or Decimal('0')
    )
    total_descontado = (
        Remuneracion.objects.filter(
            trabajador_id=anticipo.trabajador_id,
        ).aggregate(total=Sum('anticipo_descontado'))['total']
        or Decimal('0')
    )
    return total_descontado > anticipos_restantes


def _anticipo_laboral_requiere_reconstruccion(anticipo):
    return (
        anticipo.estado == 'descontado'
        and not anticipo.movimiento_pago_id
        and _anticipo_laboral_respalda_descuentos(anticipo)
    )


def _asignaciones_anticipos_remuneracion(remuneracion):
    """
    Reconstruye la aplicación histórica por antigüedad. El modelo actual guarda
    el total descontado en la remuneración, pero no una relación por anticipo.
    """
    remuneraciones = list(
        Remuneracion.objects.filter(
            trabajador_id=remuneracion.trabajador_id,
        ).filter(
            Q(periodo_anio__lt=remuneracion.periodo_anio)
            | Q(
                periodo_anio=remuneracion.periodo_anio,
                periodo_mes__lte=remuneracion.periodo_mes,
            )
        ).order_by('periodo_anio', 'periodo_mes', 'pk')
    )
    anticipos = list(
        AnticipoLaboral.objects.filter(
            trabajador_id=remuneracion.trabajador_id,
            estado='descontado',
        ).order_by('fecha', 'pk')
    )

    saldos = {anticipo.pk: anticipo.monto or Decimal('0') for anticipo in anticipos}
    disponibles = []
    indice_anticipo = 0

    for liquidacion in remuneraciones:
        ultimo_dia = monthrange(
            liquidacion.periodo_anio,
            liquidacion.periodo_mes,
        )[1]
        cierre_periodo = date(
            liquidacion.periodo_anio,
            liquidacion.periodo_mes,
            ultimo_dia,
        )
        while (
            indice_anticipo < len(anticipos)
            and anticipos[indice_anticipo].fecha <= cierre_periodo
        ):
            disponibles.append(anticipos[indice_anticipo])
            indice_anticipo += 1

        pendiente = liquidacion.anticipo_descontado or Decimal('0')
        asignaciones_actuales = []
        for anticipo in disponibles:
            saldo = saldos[anticipo.pk]
            if pendiente <= 0:
                break
            if saldo <= 0:
                continue
            aplicado = min(saldo, pendiente)
            saldos[anticipo.pk] -= aplicado
            pendiente -= aplicado
            if liquidacion.pk == remuneracion.pk:
                asignaciones_actuales.append({
                    'anticipo': anticipo,
                    'monto_aplicado': aplicado,
                    'aplicacion_parcial': aplicado < anticipo.monto,
                })

        if liquidacion.pk == remuneracion.pk:
            return asignaciones_actuales, pendiente

    return [], remuneracion.anticipo_descontado or Decimal('0')


class CargoTrabajadorListView(RrhhMixin, ListView):
    model = CargoTrabajador
    template_name = 'admin/rrhh/cargo_list.html'
    context_object_name = 'cargos'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Cargos de Trabajadores'
        return ctx

class CargoTrabajadorCreateView(RrhhMixin, CreateView):
    model = CargoTrabajador
    template_name = 'admin/rrhh/cargo_form.html'
    fields = ['nombre', 'descripcion']
    success_url = reverse_lazy('rrhh:cargo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cargo registrado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Cargo de Trabajador'
        return ctx
    
class CargoTrabajadorUpdateView(RrhhMixin, UpdateView):
    model = CargoTrabajador
    template_name = 'admin/rrhh/cargo_form.html'
    fields = ['nombre', 'descripcion']
    success_url = reverse_lazy('rrhh:cargo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cargo actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Cargo: {self.object.nombre}'
        return ctx

class CargoTrabajadorDetailView(RrhhMixin, DetailView):
    model = CargoTrabajador
    template_name = 'admin/rrhh/cargo_detail.html'
    context_object_name = 'cargo'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['trabajadores'] = self.object.trabajadores.all()
        return ctx


class TrabajadorListView(RrhhMixin, ListView):
    model = Trabajador
    template_name = 'admin/rrhh/trabajador_list.html'
    context_object_name = 'trabajadores'
    paginate_by = 20

    def get_queryset(self):
        qs = Trabajador.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(apellidos__icontains=q) | qs.filter(nombres__icontains=q) | qs.filter(rut__icontains=q)
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estados'] = Trabajador.ESTADO_CHOICES
        ctx['titulo'] = 'Trabajadores'
        return ctx


class TrabajadorCreateView(RrhhMixin, CreateView):
    model = Trabajador
    template_name = 'admin/rrhh/trabajador_form.html'
    fields = ['rut', 'nombres', 'apellidos', 'cargo', 'fecha_ingreso', 'fecha_termino', 'fecha_nacimiento', 'sueldo_base',
              'afp', 'isapre', 'banco', 'tipo_cuenta', 'numero_cuenta', 'email', 'telefono', 'direccion',
              'tipo_costo', 'centro_costo', 'estado', 'exento_previsional']
    success_url = reverse_lazy('rrhh:trabajador_list')

    def form_valid(self, form):
        messages.success(self.request, 'Trabajador registrado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Trabajador'
        return ctx


class TrabajadorUpdateView(RrhhMixin, UpdateView):
    model = Trabajador
    template_name = 'admin/rrhh/trabajador_form.html'
    fields = ['rut', 'nombres', 'apellidos', 'cargo', 'fecha_ingreso', 'fecha_termino', 'fecha_nacimiento',
              'sueldo_base', 'afp', 'isapre', 'banco', 'tipo_cuenta', 'numero_cuenta',
              'email', 'telefono', 'direccion', 'estado', 'tipo_costo', 'centro_costo', 'exento_previsional']
    success_url = reverse_lazy('rrhh:trabajador_list')

    def form_valid(self, form):
        messages.success(self.request, 'Trabajador actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Trabajador: {self.object.nombre_completo}'
        return ctx


class TrabajadorDetailView(RrhhMixin, DetailView):
    model = Trabajador
    template_name = 'admin/rrhh/trabajador_detail.html'
    context_object_name = 'trabajador'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['remuneraciones'] = self.object.remuneraciones.all()[:12]
        ctx['anticipos'] = self.object.anticipos.all()[:10]
        ctx['historial'] = self.object.historial.all()[:10]
        return ctx


class RemuneracionListView(RrhhMixin, ListView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_list.html'
    context_object_name = 'remuneraciones'
    paginate_by = 25

    def get_queryset(self):
        qs = Remuneracion.objects.select_related('trabajador')
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes:
            qs = qs.filter(periodo_mes=mes)
        if anio:
            qs = qs.filter(periodo_anio=anio)
        return qs.order_by('-periodo_anio', '-periodo_mes', 'trabajador__apellidos')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Remuneraciones'
        return ctx


class RemuneracionDetailView(RrhhMixin, DetailView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_detail.html'
    context_object_name = 'remuneracion'

    def get_queryset(self):
        return Remuneracion.objects.select_related(
            'trabajador',
            'trabajador__cargo',
            'trabajador__centro_costo',
        ).prefetch_related('asientos__lineas')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        asignaciones, monto_sin_respaldo = _asignaciones_anticipos_remuneracion(
            self.object
        )
        descuentos_previsionales = self.object.descuentos
        total_descuentos = (
            descuentos_previsionales
            + (self.object.anticipo_descontado or Decimal('0'))
        )
        ctx.update({
            'titulo': (
                f'Remuneración {self.object.periodo_mes:02d}/'
                f'{self.object.periodo_anio}'
            ),
            'asignaciones_anticipos': asignaciones,
            'monto_anticipo_sin_respaldo': monto_sin_respaldo,
            'descuentos_previsionales': descuentos_previsionales,
            'total_descuentos': total_descuentos,
            'diferencia_calculo': (
                (self.object.sueldo_bruto or Decimal('0'))
                - total_descuentos
                - (self.object.liquido_pagar or Decimal('0'))
            ),
            'asientos': self.object.asientos.order_by('fecha', 'numero'),
        })
        return ctx


class RemuneracionCreateView(RrhhMixin, CreateView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_form.html'
    fields = ['trabajador', 'periodo_mes', 'periodo_anio', 'sueldo_base', 'horas_extra',
              'bono', 'sueldo_bruto', 'descuento_afp', 'descuento_salud',
              'seguro_cesantia_trabajador', 'seguro_cesantia_empleador',
              'impuesto_unico', 'otros_descuentos', 'anticipo_descontado',
              'liquido_pagar', 'estado', 'fecha_devengamiento', 'fecha_pago']
    success_url = reverse_lazy('rrhh:remuneracion_list')

    def get_initial(self):
        initial = super().get_initial()
        now = timezone.now()
        try:
            initial['periodo_mes'] = int(self.request.GET.get('mes', now.month))
            initial['periodo_anio'] = int(self.request.GET.get('anio', now.year))
            if not 1 <= initial['periodo_mes'] <= 12 or initial['periodo_anio'] < 1:
                raise ValueError
        except (ValueError, TypeError):
            initial['periodo_mes'] = now.month
            initial['periodo_anio'] = now.year
        ultimo_dia = monthrange(initial['periodo_anio'], initial['periodo_mes'])[1]
        initial['fecha_devengamiento'] = date(
            initial['periodo_anio'],
            initial['periodo_mes'],
            ultimo_dia,
        )
        trabajador_pk = self.request.GET.get('trabajador')
        if trabajador_pk:
            try:
                t = Trabajador.objects.get(pk=int(trabajador_pk))
                bruto = t.sueldo_base
                anticipo = _anticipo_disponible_para_liquidacion(
                    t,
                    periodo_mes=initial['periodo_mes'],
                    periodo_anio=initial['periodo_anio'],
                )
                if t.exento_previsional:
                    afp = Decimal('0')
                    salud = Decimal('0')
                else:
                    tasa_afp = AFP_TASAS.get(t.afp, Decimal('0.1144'))
                    afp = round(bruto * tasa_afp)
                    salud = round(bruto * TASA_SALUD_DEFAULT)
                impuesto = Decimal('0')
                liquido = bruto - afp - salud - impuesto - anticipo
                initial.update({
                    'trabajador': t.pk,
                    'sueldo_base': t.sueldo_base,
                    'sueldo_bruto': bruto,
                    'descuento_afp': afp,
                    'descuento_salud': salud,
                    'impuesto_unico': impuesto,
                    'anticipo_descontado': anticipo,
                    'liquido_pagar': max(liquido, Decimal('0')),
                })
            except (Trabajador.DoesNotExist, ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        if (
            not _validar_montos_remuneracion(form)
            or not _validar_anticipo_remuneracion(form)
        ):
            return self.form_invalid(form)
        response = super().form_valid(form)
        from apps.contabilidad.utils import generar_asiento_devengamiento_remuneracion
        asiento = generar_asiento_devengamiento_remuneracion(self.object, usuario=self.request.user)
        _sincronizar_declaraciones_borrador(
            (self.object.periodo_mes, self.object.periodo_anio),
        )
        if asiento:
            messages.success(
                self.request,
                f'Liquidación registrada. Asiento de devengamiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(self.request, 'Liquidación registrada.')
            messages.warning(
                self.request,
                'No se pudo generar el asiento de devengamiento. '
                'Verifique que la Configuración Contable tenga todas las cuentas de remuneraciones asignadas.'
            )
        return response

    def get_success_url(self):
        from django.urls import reverse
        return reverse('rrhh:remuneracion_procesar_detalle', kwargs={
            'mes': self.object.periodo_mes,
            'anio': self.object.periodo_anio,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Liquidación de Remuneración'
        ctx['afp_tasas_json'] = json.dumps({k: float(v) for k, v in AFP_TASAS.items()})
        ctx['tasa_salud'] = float(TASA_SALUD_DEFAULT)
        return ctx


class RemuneracionDatosAPI(RrhhMixin, View):
    """Retorna datos del trabajador en JSON para auto-rellenar el formulario de remuneración."""
    def get(self, request, pk):
        t = get_object_or_404(Trabajador, pk=pk)
        remuneracion = None
        remuneracion_id = request.GET.get('remuneracion')
        if remuneracion_id:
            remuneracion = Remuneracion.objects.filter(pk=remuneracion_id, trabajador=t).first()
        try:
            periodo_mes = int(request.GET.get('mes') or 0) or None
            periodo_anio = int(request.GET.get('anio') or 0) or None
        except (TypeError, ValueError):
            periodo_mes = None
            periodo_anio = None
        anticipo_pendiente = _anticipo_disponible_para_liquidacion(
            t,
            remuneracion=remuneracion,
            periodo_mes=periodo_mes,
            periodo_anio=periodo_anio,
        )
        tasa_afp = AFP_TASAS.get(t.afp, Decimal('0.1144'))
        bruto = t.sueldo_base
        afp = round(bruto * tasa_afp)
        salud = round(bruto * TASA_SALUD_DEFAULT)
        return JsonResponse({
            'sueldo_base': float(t.sueldo_base),
            'afp': t.afp,
            'isapre': t.isapre,
            'tasa_afp': float(tasa_afp),
            'tasa_salud': float(TASA_SALUD_DEFAULT),
            'descuento_afp': float(afp),
            'descuento_salud': float(salud),
            'seguro_cesantia_trabajador': 0,
            'seguro_cesantia_empleador': 0,
            'impuesto_unico': 0,
            'anticipo_pendiente': float(anticipo_pendiente),
            'exento_previsional': t.exento_previsional,
        })


class RemuneracionUpdateView(RrhhMixin, UpdateView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_form.html'
    fields = ['trabajador', 'periodo_mes', 'periodo_anio', 'sueldo_base', 'horas_extra',
              'bono', 'sueldo_bruto', 'descuento_afp', 'descuento_salud',
              'seguro_cesantia_trabajador', 'seguro_cesantia_empleador',
              'impuesto_unico', 'otros_descuentos', 'anticipo_descontado',
              'liquido_pagar', 'estado', 'fecha_devengamiento', 'fecha_pago']

    def dispatch(self, request, *args, **kwargs):
        rem = self.get_object()
        if rem.estado == 'pagado':
            messages.error(
                request,
                'No se puede editar una liquidación que ya fue pagada.'
            )
            return redirect('rrhh:remuneracion_procesar_detalle', mes=rem.periodo_mes, anio=rem.periodo_anio)
        if rem.declaraciones_previsionales.exclude(estado='borrador').exists():
            messages.error(
                request,
                'No se puede editar: la remuneración pertenece a una declaración previsional presentada o pagada.'
            )
            return redirect('rrhh:remuneracion_detail', pk=rem.pk)
        if rem.asientos.filter(tipo='devengamiento_remuneracion', estado='confirmado').exists():
            messages.error(
                request,
                'No se puede editar la liquidación porque su asiento de devengamiento está confirmado. '
                'Anule o reverse el asiento antes de modificarla.'
            )
            return redirect('rrhh:remuneracion_procesar_detalle', mes=rem.periodo_mes, anio=rem.periodo_anio)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        if not (self.object.anticipo_descontado or Decimal('0')):
            anticipo = _anticipo_disponible_para_liquidacion(
                self.object.trabajador,
                remuneracion=self.object,
            )
            if anticipo > 0:
                initial['anticipo_descontado'] = anticipo
                initial['liquido_pagar'] = max(
                    (self.object.sueldo_bruto or Decimal('0'))
                    - (self.object.descuento_afp or Decimal('0'))
                    - (self.object.descuento_salud or Decimal('0'))
                    - (self.object.seguro_cesantia_trabajador or Decimal('0'))
                    - (self.object.impuesto_unico or Decimal('0'))
                    - (self.object.otros_descuentos or Decimal('0'))
                    - anticipo,
                    Decimal('0'),
                )
        return initial

    def form_valid(self, form):
        from apps.contabilidad.utils import generar_asiento_devengamiento_remuneracion

        if (
            not _validar_montos_remuneracion(form)
            or not _validar_anticipo_remuneracion(form, remuneracion=self.object)
        ):
            return self.form_invalid(form)

        periodo_anterior = (self.object.periodo_mes, self.object.periodo_anio)
        with transaction.atomic():
            response = super().form_valid(form)
            self.object.asientos.filter(
                tipo='devengamiento_remuneracion',
                estado='borrador',
            ).delete()
            asiento = generar_asiento_devengamiento_remuneracion(
                self.object,
                usuario=self.request.user,
            )
            _sincronizar_declaraciones_borrador(
                periodo_anterior,
                (self.object.periodo_mes, self.object.periodo_anio),
            )

        if asiento:
            messages.success(
                self.request,
                f'Liquidación actualizada. Asiento de devengamiento {asiento.numero} regenerado en borrador.'
            )
        else:
            messages.success(self.request, 'Liquidación actualizada.')
            messages.warning(
                self.request,
                'No se pudo regenerar el asiento de devengamiento. '
                'Revise la Configuración Contable de remuneraciones.'
            )
        return response

    def get_success_url(self):
        from django.urls import reverse
        return reverse('rrhh:remuneracion_procesar_detalle', kwargs={
            'mes': self.object.periodo_mes,
            'anio': self.object.periodo_anio,
        })

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Liquidación — {self.object.trabajador.nombre_completo}'
        ctx['afp_tasas_json'] = json.dumps({k: float(v) for k, v in AFP_TASAS.items()})
        ctx['tasa_salud'] = float(TASA_SALUD_DEFAULT)
        return ctx


class RemuneracionDeleteView(RrhhMixin, DeleteView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_confirm_delete.html'

    @staticmethod
    def _movimientos_pago(remuneracion):
        movimientos = []
        ids = set()
        if remuneracion.movimiento_pago_id:
            ids.add(remuneracion.movimiento_pago_id)
            movimientos.append(remuneracion.movimiento_pago)
        for asiento in remuneracion.asientos.filter(
            tipo='pago_remuneracion',
        ).select_related('movimiento_bancario'):
            movimiento = asiento.movimiento_bancario
            if movimiento and movimiento.pk not in ids:
                ids.add(movimiento.pk)
                movimientos.append(movimiento)
        return movimientos

    def _motivo_bloqueo(self, remuneracion):
        if remuneracion.declaraciones_previsionales.exclude(estado='borrador').exists():
            return (
                'No se puede eliminar la remuneración porque pertenece a una '
                'declaración previsional presentada o pagada.'
            )
        if remuneracion.asientos.filter(estado='confirmado').exists():
            return (
                'No se puede eliminar la remuneración porque tiene asientos confirmados. '
                'Anule primero los asientos de devengamiento y pago.'
            )
        movimientos_conciliados = [
            movimiento
            for movimiento in self._movimientos_pago(remuneracion)
            if movimiento.conciliado
        ]
        if movimientos_conciliados:
            return (
                'No se puede eliminar la remuneración porque su movimiento bancario '
                'está conciliado. Revierta primero la conciliación.'
            )
        return None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        motivo = self._motivo_bloqueo(self.object)
        if motivo:
            messages.error(request, motivo)
            return redirect(
                'rrhh:remuneracion_procesar_detalle',
                mes=self.object.periodo_mes,
                anio=self.object.periodo_anio,
            )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse(
            'rrhh:remuneracion_procesar_detalle',
            kwargs={
                'mes': self.object.periodo_mes,
                'anio': self.object.periodo_anio,
            },
        )
        ctx['asientos_borrador'] = self.object.asientos.filter(
            estado='borrador'
        ).count()
        ctx['movimientos_pago'] = self._movimientos_pago(self.object)
        ctx['es_pagada'] = self.object.estado == 'pagado'
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            remuneracion = Remuneracion.objects.select_for_update().get(
                pk=self.object.pk
            )
            motivo = self._motivo_bloqueo(remuneracion)
            if motivo:
                messages.error(self.request, motivo)
                return redirect(
                    'rrhh:remuneracion_procesar_detalle',
                    mes=remuneracion.periodo_mes,
                    anio=remuneracion.periodo_anio,
                )

            mes = remuneracion.periodo_mes
            anio = remuneracion.periodo_anio
            movimientos_pago = self._movimientos_pago(remuneracion)
            remuneracion.asientos.filter(estado='borrador').delete()
            if remuneracion.movimiento_pago_id:
                remuneracion.movimiento_pago = None
                remuneracion.save(update_fields=['movimiento_pago'])
            for movimiento in movimientos_pago:
                movimiento.delete()
            remuneracion.delete()
            _sincronizar_declaraciones_borrador((mes, anio))

        messages.success(
            self.request,
            'Remuneración eliminada. Puede crear nuevamente la liquidación.',
        )
        return redirect(
            'rrhh:remuneracion_procesar_detalle',
            mes=mes,
            anio=anio,
        )


class RemuneracionPeriodoView(RrhhMixin, View):
    """Paso 1: selección de período para procesar remuneraciones."""
    template_name = 'admin/rrhh/remuneracion_periodo.html'

    def get(self, request):
        mes = request.GET.get('mes')
        anio = request.GET.get('anio')
        if mes and anio:
            try:
                return redirect('rrhh:remuneracion_procesar_detalle', mes=int(mes), anio=int(anio))
            except (ValueError, TypeError):
                pass

        periodos = _generar_periodos(15)
        total_activos = Trabajador.objects.filter(estado='activo').count()
        stats = {
            (s['periodo_mes'], s['periodo_anio']): s['cnt']
            for s in Remuneracion.objects.filter(estado='pagado')
                .values('periodo_mes', 'periodo_anio').annotate(cnt=Count('pk'))
        }
        now = timezone.now()
        for p in periodos:
            p['total'] = total_activos
            p['pagados'] = stats.get((p['mes'], p['anio']), 0)
            p['pendientes'] = total_activos - p['pagados']

        anios = sorted(set(p['anio'] for p in periodos), reverse=True)
        return render(request, self.template_name, {
            'titulo': 'Procesar Remuneraciones',
            'periodos': periodos,
            'anios_disponibles': anios,
            'mes_actual': now.month,
            'anio_actual': now.year,
        })


class RemuneracionPeriodoDetalleView(RrhhMixin, View):
    """Paso 2: listado de trabajadores con estado de remuneración para el período."""
    template_name = 'admin/rrhh/remuneracion_periodo_detalle.html'

    def get(self, request, mes, anio):
        trabajadores = Trabajador.objects.filter(estado='activo').select_related('cargo').order_by('apellidos', 'nombres')
        rems = {r.trabajador_id: r for r in Remuneracion.objects.filter(periodo_mes=mes, periodo_anio=anio)}
        items = [
            {
                'trabajador': t,
                'remuneracion': rems.get(t.pk),
                'estado': rems[t.pk].estado if t.pk in rems else None,
            }
            for t in trabajadores
        ]
        total = len(items)
        pagados = sum(1 for i in items if i['estado'] == 'pagado')
        return render(request, self.template_name, {
            'titulo': f'Remuneraciones {mes:02d}/{anio}',
            'mes': mes,
            'anio': anio,
            'mes_nombre': MESES_NOMBRES.get(mes, ''),
            'items': items,
            'total': total,
            'pagados': pagados,
            'pendientes': total - pagados,
        })


class AnticipoLaboralListView(RrhhMixin, ListView):
    model = AnticipoLaboral
    template_name = 'admin/rrhh/anticipo_list.html'
    context_object_name = 'anticipos'
    paginate_by = 20

    def get_queryset(self):
        qs = AnticipoLaboral.objects.select_related(
            'trabajador',
            'movimiento_pago',
        )
        q = self.request.GET.get('q')
        estado = self.request.GET.get('estado')
        if q:
            qs = qs.filter(
                Q(trabajador__nombres__icontains=q)
                | Q(trabajador__apellidos__icontains=q)
                | Q(trabajador__rut__icontains=q)
            )
        if estado:
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Anticipos Laborales'
        for anticipo in ctx['anticipos']:
            anticipo.requiere_reconstruccion = (
                _anticipo_laboral_requiere_reconstruccion(anticipo)
            )
        return ctx


class AnticipoLaboralCreateView(RrhhMixin, CreateView):
    model = AnticipoLaboral
    template_name = 'admin/rrhh/anticipo_form.html'
    fields = ['trabajador', 'fecha', 'monto', 'descripcion']
    success_url = reverse_lazy('rrhh:anticipo_list')

    def get_form(self, form_class=None):
        from django.forms import DateInput

        form = super().get_form(form_class)
        form.fields['fecha'].input_formats = ['%Y-%m-%d']
        form.fields['fecha'].widget = DateInput(
            format='%Y-%m-%d',
            attrs={'class': 'form-control', 'type': 'text'},
        )
        return form

    def form_valid(self, form):
        form.instance.estado = 'pendiente'
        messages.success(self.request, 'Anticipo registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Anticipo Laboral'
        return ctx


class AnticipoLaboralUpdateView(RrhhMixin, UpdateView):
    model = AnticipoLaboral
    template_name = 'admin/rrhh/anticipo_form.html'
    fields = ['trabajador', 'fecha', 'monto', 'descripcion']
    success_url = reverse_lazy('rrhh:anticipo_list')

    def get_form(self, form_class=None):
        from django.forms import DateInput

        form = super().get_form(form_class)
        form.fields['fecha'].input_formats = ['%Y-%m-%d']
        form.fields['fecha'].widget = DateInput(
            format='%Y-%m-%d',
            attrs={'class': 'form-control', 'type': 'text'},
        )
        return form

    def dispatch(self, request, *args, **kwargs):
        anticipo = self.get_object()
        if anticipo.movimiento_pago_id:
            messages.error(
                request,
                'Solo se puede editar un anticipo antes de registrar su pago.'
            )
            return redirect('rrhh:anticipo_list')
        if (
            anticipo.estado == 'descontado'
            and _anticipo_laboral_respalda_descuentos(anticipo)
        ):
            messages.error(
                request,
                'No se puede editar el anticipo porque su monto respalda descuentos '
                'registrados en liquidaciones. Corrija primero esas remuneraciones.'
            )
            return redirect('rrhh:anticipo_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.estado = 'pendiente'
        messages.success(self.request, 'Anticipo laboral actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Editar Anticipo Laboral'
        return ctx


class AnticipoLaboralDeleteView(RrhhMixin, DeleteView):
    model = AnticipoLaboral
    template_name = 'admin/rrhh/anticipo_confirm_delete.html'
    success_url = reverse_lazy('rrhh:anticipo_list')

    def _motivo_bloqueo(self, anticipo):
        movimiento = anticipo.movimiento_pago
        if anticipo.estado == 'descontado' or movimiento:
            if _anticipo_laboral_respalda_descuentos(anticipo):
                return (
                    'No se puede eliminar el anticipo porque su monto ya respalda descuentos '
                    'registrados en liquidaciones. Corrija primero esas remuneraciones.'
                )

        if movimiento:
            if movimiento.conciliado:
                return (
                    'No se puede eliminar el anticipo porque su movimiento bancario está conciliado. '
                    'Revierta primero la conciliación.'
                )
            if movimiento.asientos.filter(estado='confirmado').exists():
                return (
                    'No se puede eliminar el anticipo porque su pago tiene un asiento confirmado. '
                    'Anule o reverse primero el asiento.'
                )
        return None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        motivo = self._motivo_bloqueo(self.object)
        if motivo:
            messages.error(request, motivo)
            return redirect('rrhh:anticipo_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse('rrhh:anticipo_list')
        ctx['movimiento_pago'] = self.object.movimiento_pago
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            # Bloquear solo el anticipo. Incluir movimiento_pago (nullable) mediante
            # select_related genera un LEFT JOIN incompatible con FOR UPDATE en PostgreSQL.
            anticipo = AnticipoLaboral.objects.select_for_update().get(pk=self.object.pk)
            motivo = self._motivo_bloqueo(anticipo)
            if motivo:
                messages.error(self.request, motivo)
                return redirect('rrhh:anticipo_list')

            movimiento = anticipo.movimiento_pago
            if movimiento:
                movimiento.asientos.filter(estado='borrador').delete()
                anticipo.movimiento_pago = None
                anticipo.save(update_fields=['movimiento_pago'])
                movimiento.delete()
            anticipo.delete()

        messages.success(self.request, 'Anticipo laboral eliminado correctamente.')
        return redirect(self.success_url)


# ---------------------------------------------------------------------------
# Pago de Anticipo Laboral con automatismo contable
# ---------------------------------------------------------------------------

class AnticipoLaboralPagarView(RrhhMixin, View):
    template_name = 'admin/rrhh/anticipo_pagar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoAnticipoForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El anticipo se descontará de esta cuenta.',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoAnticipoForm(data=data, initial=initial)

    @staticmethod
    def _es_pago_nuevo(anticipo):
        return anticipo.estado == 'pendiente' and not anticipo.movimiento_pago_id

    def _contexto(self, anticipo, form, reconstruccion=False):
        return {
            'anticipo': anticipo,
            'form': form,
            'reconstruccion': reconstruccion,
        }

    def get(self, request, pk):
        anticipo = get_object_or_404(AnticipoLaboral, pk=pk)
        reconstruccion = _anticipo_laboral_requiere_reconstruccion(anticipo)
        if not self._es_pago_nuevo(anticipo) and not reconstruccion:
            messages.info(request, 'Este anticipo ya fue descontado/pagado.')
            return redirect('rrhh:anticipo_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(
            request,
            self.template_name,
            self._contexto(anticipo, form, reconstruccion),
        )

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.models import ConfiguracionContable
        from apps.contabilidad.utils import generar_asiento_pago_anticipo

        anticipo = get_object_or_404(AnticipoLaboral, pk=pk)
        reconstruccion = _anticipo_laboral_requiere_reconstruccion(anticipo)
        if not self._es_pago_nuevo(anticipo) and not reconstruccion:
            messages.error(request, 'Este anticipo ya tiene un pago registrado.')
            return redirect('rrhh:anticipo_list')
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self._contexto(anticipo, form, reconstruccion),
            )

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']
        config = ConfiguracionContable.get()
        if not cuenta_bancaria.cuenta_contable_id:
            messages.error(
                request,
                'La cuenta bancaria no tiene una cuenta contable asociada.',
            )
            return render(
                request,
                self.template_name,
                self._contexto(anticipo, form, reconstruccion),
            )
        if not config.cuenta_anticipos_trabajadores_id:
            messages.error(
                request,
                'Configure la cuenta Anticipos a Trabajadores antes de registrar '
                'o reconstruir el pago.',
            )
            return render(
                request,
                self.template_name,
                self._contexto(anticipo, form, reconstruccion),
            )

        with transaction.atomic():
            anticipo = AnticipoLaboral.objects.select_for_update().select_related(
                'trabajador',
            ).get(pk=pk)
            reconstruccion = _anticipo_laboral_requiere_reconstruccion(anticipo)
            if not self._es_pago_nuevo(anticipo) and not reconstruccion:
                messages.error(request, 'Este anticipo ya tiene un pago registrado.')
                return redirect('rrhh:anticipo_list')

            prefijo = 'Reconstrucción pago anticipo' if reconstruccion else 'Anticipo'
            descripcion_mov = (
                f'{prefijo} {anticipo.trabajador.nombre_completo} - {anticipo.fecha}'
            )
            if d['notas']:
                descripcion_mov = f'{descripcion_mov} - {d["notas"]}'
            movimiento = MovimientoBancario.objects.create(
                cuenta=cuenta_bancaria,
                fecha=d['fecha_pago'],
                tipo='egreso',
                monto=anticipo.monto,
                descripcion=descripcion_mov[:300],
                cuenta_contable=config.cuenta_anticipos_trabajadores,
            )

            asiento = generar_asiento_pago_anticipo(
                anticipo,
                movimiento,
                usuario=request.user,
            )
            if reconstruccion and asiento:
                asiento.descripcion = f'Reconstrucción - {asiento.descripcion}'[:300]
                asiento.save(update_fields=['descripcion'])
            anticipo.estado = 'descontado'
            anticipo.movimiento_pago = movimiento
            anticipo.save(update_fields=['estado', 'movimiento_pago'])

        if asiento:
            accion = 'reconstruido' if reconstruccion else 'registrado'
            messages.success(
                request,
                f'Pago de anticipo {accion}. Movimiento bancario creado y asiento '
                f'{asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'Anticipo registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('rrhh:anticipo_list')

class RemuneracionPagarView(RrhhMixin, View):
    template_name = 'admin/rrhh/remuneracion_pagar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoRemuneracionForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El pago se descontará de esta cuenta.',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoRemuneracionForm(data=data, initial=initial)

    def get(self, request, pk):
        remuneracion = get_object_or_404(Remuneracion, pk=pk)
        if remuneracion.estado == 'pagado' or remuneracion.movimiento_pago_id:
            messages.info(request, 'Esta remuneración ya fue pagada.')
            return redirect('rrhh:remuneracion_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(request, self.template_name, {'remuneracion': remuneracion, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_pago_remuneracion

        remuneracion = get_object_or_404(Remuneracion, pk=pk)
        if remuneracion.estado == 'pagado' or remuneracion.movimiento_pago_id:
            messages.error(request, 'Esta remuneración ya tiene un pago registrado.')
            return redirect('rrhh:remuneracion_list')
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'remuneracion': remuneracion, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        with transaction.atomic():
            remuneracion = Remuneracion.objects.select_for_update().select_related(
                'trabajador',
            ).get(pk=pk)
            if remuneracion.estado == 'pagado' or remuneracion.movimiento_pago_id:
                messages.error(request, 'Esta remuneración ya tiene un pago registrado.')
                return redirect('rrhh:remuneracion_list')

            # 1. Crear movimiento bancario por el líquido transferido.
            descripcion_mov = (
                f'Rem. {remuneracion.trabajador.nombre_completo} '
                f'{remuneracion.periodo_mes:02d}/{remuneracion.periodo_anio}'
            )
            movimiento = MovimientoBancario.objects.create(
                cuenta=cuenta_bancaria,
                fecha=d['fecha_pago'],
                tipo='egreso',
                monto=remuneracion.liquido_pagar,
                descripcion=descripcion_mov,
                cuenta_contable=None,
            )

            # Contrapartida usada por liquidaciones antiguas sin devengamiento.
            try:
                from apps.contabilidad.models import ConfiguracionContable
                config = ConfiguracionContable.get()
                if remuneracion.trabajador.tipo_costo == 'operacional':
                    cuenta_sueldos = config.cuenta_sueldos_operacional if config else None
                else:
                    cuenta_sueldos = config.cuenta_sueldos_administrativo if config else None
                if cuenta_sueldos:
                    movimiento.cuenta_contable = cuenta_sueldos
                    movimiento.save(update_fields=['cuenta_contable'])
            except Exception:
                pass

            # 2. Generar asiento y vincular explícitamente el movimiento.
            asiento = generar_asiento_pago_remuneracion(
                remuneracion,
                movimiento,
                usuario=request.user,
            )
            remuneracion.estado = 'pagado'
            remuneracion.fecha_pago = d['fecha_pago']
            remuneracion.movimiento_pago = movimiento
            remuneracion.save(
                update_fields=['estado', 'fecha_pago', 'movimiento_pago']
            )

        if asiento:
            messages.success(
                request,
                f'Pago registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'Pago registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable automáticamente. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('rrhh:remuneracion_procesar_detalle', mes=remuneracion.periodo_mes, anio=remuneracion.periodo_anio)


class DeclaracionPrevisionalListView(RrhhMixin, ListView):
    model = DeclaracionPrevisional
    template_name = 'admin/rrhh/declaracion_previsional_list.html'
    context_object_name = 'declaraciones'
    paginate_by = 25

    def get_queryset(self):
        return (
            DeclaracionPrevisional.objects
            .annotate(cantidad_remuneraciones=Count('remuneraciones'))
            .select_related('movimiento_pago')
        )


class DeclaracionPrevisionalDetailView(RrhhMixin, DetailView):
    model = DeclaracionPrevisional
    template_name = 'admin/rrhh/declaracion_previsional_detail.html'
    context_object_name = 'declaracion'

    def get_queryset(self):
        return (
            DeclaracionPrevisional.objects
            .select_related('movimiento_pago')
            .prefetch_related(
                'remuneraciones__trabajador',
                'asientos__lineas',
            )
        )


class DeclaracionPrevisionalCreateView(RrhhMixin, CreateView):
    model = DeclaracionPrevisional
    form_class = DeclaracionPrevisionalForm
    template_name = 'admin/rrhh/declaracion_previsional_form.html'

    def get_initial(self):
        initial = super().get_initial()
        hoy = timezone.now().date()
        initial.update({'periodo_mes': hoy.month, 'periodo_anio': hoy.year})
        return initial

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            _sincronizar_declaracion_previsional(self.object)
        messages.success(
            self.request,
            'Declaración creada en borrador y sincronizada con las remuneraciones del período.',
        )
        return response

    def get_success_url(self):
        return reverse('rrhh:declaracion_previsional_detail', kwargs={'pk': self.object.pk})


class DeclaracionPrevisionalUpdateView(RrhhMixin, UpdateView):
    model = DeclaracionPrevisional
    form_class = DeclaracionPrevisionalForm
    template_name = 'admin/rrhh/declaracion_previsional_form.html'

    def dispatch(self, request, *args, **kwargs):
        declaracion = self.get_object()
        if declaracion.estado != 'borrador':
            messages.error(request, 'Solo se puede editar una declaración en borrador.')
            return redirect('rrhh:declaracion_previsional_detail', pk=declaracion.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            response = super().form_valid(form)
            _sincronizar_declaracion_previsional(self.object)
        messages.success(self.request, 'Declaración actualizada y totales recalculados.')
        return response

    def get_success_url(self):
        return reverse('rrhh:declaracion_previsional_detail', kwargs={'pk': self.object.pk})


class DeclaracionPrevisionalDeleteView(RrhhMixin, DeleteView):
    model = DeclaracionPrevisional
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('rrhh:declaracion_previsional_list')

    def dispatch(self, request, *args, **kwargs):
        declaracion = self.get_object()
        if (
            declaracion.estado != 'borrador'
            or declaracion.movimiento_pago_id
            or declaracion.asientos.exists()
        ):
            messages.error(
                request,
                'Solo puede eliminarse una declaración en borrador, sin pago ni asientos.',
            )
            return redirect('rrhh:declaracion_previsional_detail', pk=declaracion.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Declaración previsional eliminada.')
        return super().form_valid(form)


class DeclaracionPrevisionalPresentarView(RrhhMixin, View):
    def post(self, request, pk):
        with transaction.atomic():
            declaracion = DeclaracionPrevisional.objects.select_for_update().get(pk=pk)
            if declaracion.estado != 'borrador':
                messages.error(request, 'La declaración ya no está en borrador.')
                return redirect('rrhh:declaracion_previsional_detail', pk=pk)

            remuneraciones = _sincronizar_declaracion_previsional(declaracion)
            if not remuneraciones.exists():
                messages.error(request, 'No existen remuneraciones para el período seleccionado.')
                return redirect('rrhh:declaracion_previsional_detail', pk=pk)

            sin_devengamiento = remuneraciones.exclude(
                asientos__tipo='devengamiento_remuneracion',
                asientos__estado='confirmado',
            ).distinct()
            if sin_devengamiento.exists():
                nombres = ', '.join(
                    sin_devengamiento.values_list(
                        'trabajador__apellidos', flat=True
                    )[:5]
                )
                messages.error(
                    request,
                    'No se puede presentar: todas las remuneraciones deben tener '
                    f'su asiento de devengamiento confirmado. Pendientes: {nombres}.',
                )
                return redirect('rrhh:declaracion_previsional_detail', pk=pk)

            if declaracion.total_pagar <= 0:
                messages.error(request, 'La declaración no tiene cotizaciones por pagar.')
                return redirect('rrhh:declaracion_previsional_detail', pk=pk)

            declaracion.estado = 'presentada'
            declaracion.fecha_presentacion = (
                declaracion.fecha_presentacion or timezone.now().date()
            )
            declaracion.save(update_fields=['estado', 'fecha_presentacion', 'actualizado_en'])

        messages.success(
            request,
            'Declaración presentada. Sus remuneraciones y montos quedaron bloqueados.',
        )
        return redirect('rrhh:declaracion_previsional_detail', pk=pk)


class DeclaracionPrevisionalPagarView(RrhhMixin, View):
    template_name = 'admin/rrhh/declaracion_previsional_pagar.html'

    def _form(self, data=None):
        from apps.tesoreria.models import CuentaBancaria

        class PagoForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=CuentaBancaria.objects.filter(
                    activa=True, cuenta_contable__isnull=False,
                ).select_related('banco', 'cuenta_contable'),
                widget=forms.Select(attrs={'class': 'form-select'}),
            )
            referencia = forms.CharField(
                max_length=50, required=False,
                widget=forms.TextInput(attrs={'class': 'form-control'}),
            )

        return PagoForm(data=data)

    def get(self, request, pk):
        declaracion = get_object_or_404(DeclaracionPrevisional, pk=pk)
        if declaracion.estado != 'presentada' or declaracion.movimiento_pago_id:
            messages.error(request, 'Solo puede pagarse una declaración presentada y pendiente.')
            return redirect('rrhh:declaracion_previsional_detail', pk=pk)
        form = self._form()
        form.initial['fecha_pago'] = timezone.now().date()
        return render(request, self.template_name, {
            'declaracion': declaracion, 'form': form,
        })

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.models import ConfiguracionContable
        from apps.contabilidad.utils import generar_asiento_pago_previsional

        form = self._form(request.POST)
        declaracion = get_object_or_404(DeclaracionPrevisional, pk=pk)
        if not form.is_valid():
            return render(request, self.template_name, {
                'declaracion': declaracion, 'form': form,
            })

        config = ConfiguracionContable.get()
        requeridas = [
            (declaracion.total_afp, config.cuenta_afp_por_pagar),
            (declaracion.total_salud, config.cuenta_salud_por_pagar),
            (
                declaracion.total_cesantia_trabajador + declaracion.total_cesantia_empleador,
                config.cuenta_seguro_cesantia_por_pagar or config.cuenta_afp_por_pagar,
            ),
        ]
        if any(monto > 0 and cuenta is None for monto, cuenta in requeridas):
            messages.error(
                request,
                'Faltan cuentas AFP, salud o cesantía en la Configuración Contable.',
            )
            return render(request, self.template_name, {
                'declaracion': declaracion, 'form': form,
            })

        d = form.cleaned_data
        with transaction.atomic():
            declaracion = DeclaracionPrevisional.objects.select_for_update().get(pk=pk)
            if declaracion.estado != 'presentada' or declaracion.movimiento_pago_id:
                messages.error(request, 'La declaración ya fue pagada o cambió de estado.')
                return redirect('rrhh:declaracion_previsional_detail', pk=pk)

            movimiento = MovimientoBancario.objects.create(
                cuenta=d['cuenta_bancaria'],
                fecha=d['fecha_pago'],
                tipo='egreso',
                monto=declaracion.total_pagar,
                descripcion=f'Pago Previred {declaracion.periodo_mes:02d}/{declaracion.periodo_anio}',
                documento=d['referencia'],
            )
            asiento = generar_asiento_pago_previsional(
                declaracion, movimiento, usuario=request.user,
            )
            if asiento is None:
                raise ValueError(
                    'No fue posible generar el asiento previsional; revise la configuración contable.'
                )
            declaracion.estado = 'pagada'
            declaracion.fecha_pago = d['fecha_pago']
            declaracion.movimiento_pago = movimiento
            declaracion.save(update_fields=[
                'estado', 'fecha_pago', 'movimiento_pago', 'actualizado_en',
            ])

        messages.success(
            request,
            f'Pago registrado y asiento {asiento.numero} generado en borrador.',
        )
        return redirect('rrhh:declaracion_previsional_detail', pk=pk)
