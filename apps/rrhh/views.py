from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from decimal import Decimal
import json
from apps.core.mixins import GestionMixin, AppPermisoMixin

class RrhhMixin(AppPermisoMixin):
    app_name = 'rrhh'

from .models import Trabajador, Remuneracion, AnticipoLaboral, CargoTrabajador

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


class RemuneracionCreateView(RrhhMixin, CreateView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_form.html'
    fields = ['trabajador', 'periodo_mes', 'periodo_anio', 'sueldo_base', 'horas_extra',
              'bono', 'sueldo_bruto', 'descuento_afp', 'descuento_salud',
              'impuesto_unico', 'otros_descuentos', 'anticipo_descontado',
              'liquido_pagar', 'estado', 'fecha_pago']
    success_url = reverse_lazy('rrhh:remuneracion_list')

    def get_initial(self):
        initial = super().get_initial()
        now = timezone.now()
        try:
            initial['periodo_mes'] = int(self.request.GET.get('mes', now.month))
            initial['periodo_anio'] = int(self.request.GET.get('anio', now.year))
        except (ValueError, TypeError):
            initial['periodo_mes'] = now.month
            initial['periodo_anio'] = now.year
        trabajador_pk = self.request.GET.get('trabajador')
        if trabajador_pk:
            try:
                t = Trabajador.objects.get(pk=int(trabajador_pk))
                bruto = t.sueldo_base
                anticipo = AnticipoLaboral.objects.filter(
                    trabajador=t, estado='descontado'
                ).aggregate(s=Sum('monto'))['s'] or Decimal('0')
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
        response = super().form_valid(form)
        from apps.contabilidad.utils import generar_asiento_devengamiento_remuneracion
        asiento = generar_asiento_devengamiento_remuneracion(self.object, usuario=self.request.user)
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
        anticipo_pendiente = AnticipoLaboral.objects.filter(
            trabajador=t, estado='descontado'
        ).aggregate(s=Sum('monto'))['s'] or Decimal('0')
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
            'impuesto_unico': 0,
            'anticipo_pendiente': float(anticipo_pendiente),
            'exento_previsional': t.exento_previsional,
        })


class RemuneracionUpdateView(RrhhMixin, UpdateView):
    model = Remuneracion
    template_name = 'admin/rrhh/remuneracion_form.html'
    fields = ['trabajador', 'periodo_mes', 'periodo_anio', 'sueldo_base', 'horas_extra',
              'bono', 'sueldo_bruto', 'descuento_afp', 'descuento_salud',
              'impuesto_unico', 'otros_descuentos', 'anticipo_descontado',
              'liquido_pagar', 'estado', 'fecha_pago']

    def dispatch(self, request, *args, **kwargs):
        rem = self.get_object()
        if rem.estado == 'pagado':
            messages.error(
                request,
                'No se puede editar una liquidación que ya fue pagada.'
            )
            return redirect('rrhh:remuneracion_procesar_detalle', mes=rem.periodo_mes, anio=rem.periodo_anio)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'Liquidación actualizada.')
        return super().form_valid(form)

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

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Anticipos Laborales'
        return ctx


class AnticipoLaboralCreateView(RrhhMixin, CreateView):
    model = AnticipoLaboral
    template_name = 'admin/rrhh/anticipo_form.html'
    fields = ['trabajador', 'fecha', 'monto', 'descripcion', 'estado']
    success_url = reverse_lazy('rrhh:anticipo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Anticipo registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Anticipo Laboral'
        return ctx


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

    def get(self, request, pk):
        anticipo = get_object_or_404(AnticipoLaboral, pk=pk)
        if anticipo.estado == 'descontado':
            messages.info(request, 'Este anticipo ya fue descontado/pagado.')
            return redirect('rrhh:anticipo_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(request, self.template_name, {'anticipo': anticipo, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_pago_anticipo

        anticipo = get_object_or_404(AnticipoLaboral, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'anticipo': anticipo, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Marcar anticipo como pagado (estado 'descontado' indica ya fue entregado)
        anticipo.estado = 'descontado'
        anticipo.save()

        # 2. Crear MovimientoBancario (egreso)
        descripcion_mov = f'Anticipo {anticipo.trabajador.nombre_completo} - {anticipo.fecha}'
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='egreso',
            monto=anticipo.monto,
            descripcion=descripcion_mov,
            cuenta_contable=None,
        )

        # La cuenta_contable del movimiento apunta a la cuenta de sueldos del trabajador
        # (usada como fallback en el asiento si cuenta_anticipos_trabajadores no está configurada)
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if anticipo.trabajador.tipo_costo == 'operacional':
                cuenta_sueldos = config.cuenta_sueldos_operacional if config else None
            else:
                cuenta_sueldos = config.cuenta_sueldos_administrativo if config else None
            if cuenta_sueldos:
                movimiento.cuenta_contable = cuenta_sueldos
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # 3. Generar asiento: DEBE Anticipos a Trabajadores (activo) / HABER Banco
        #    Si cuenta_anticipos_trabajadores no está configurada, fallback a DEBE gasto / HABER banco
        asiento = generar_asiento_pago_anticipo(anticipo, movimiento, usuario=request.user)

        if asiento:
            messages.success(
                request,
                f'Anticipo registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
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
        if remuneracion.estado == 'pagado':
            messages.info(request, 'Esta remuneración ya fue pagada.')
            return redirect('rrhh:remuneracion_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(request, self.template_name, {'remuneracion': remuneracion, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_pago_remuneracion

        remuneracion = get_object_or_404(Remuneracion, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'remuneracion': remuneracion, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Actualizar Remuneración
        remuneracion.estado = 'pagado'
        remuneracion.fecha_pago = d['fecha_pago']
        remuneracion.save()

        # 2. Crear MovimientoBancario (egreso por el líquido transferido al trabajador)
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

        # Asignar cuenta_contable del movimiento según tipo_costo del trabajador
        # (usado por el asiento como cuenta DEBE de gasto de sueldos)
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

        # 3. Generar asiento compuesto: DEBE gasto_sueldos (bruto) /
        #    HABER banco (líquido) + AFP por Pagar + Salud por Pagar + Sueldos por Pagar (otros)
        asiento = generar_asiento_pago_remuneracion(remuneracion, movimiento, usuario=request.user)

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
