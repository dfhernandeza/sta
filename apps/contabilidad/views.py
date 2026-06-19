from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date
from apps.core.mixins import GestionMixin
from .models import PlanCuentas, AsientoContable, LineaAsiento, ConfiguracionContable, CentroCosto


# ---------------------------------------------------------------------------
# Plan de Cuentas
# ---------------------------------------------------------------------------

class PlanCuentasListView(GestionMixin, ListView):
    model = PlanCuentas
    template_name = 'admin/contabilidad/plan_list.html'
    context_object_name = 'cuentas'
    paginate_by = 50

    def get_queryset(self):
        qs = PlanCuentas.objects.select_related('parent')
        q = self.request.GET.get('q')
        nivel = self.request.GET.get('nivel')
        if nivel:
            qs = qs.filter(nivel=nivel)
        if q:
            qs = qs.filter(codigo__icontains=q) | qs.filter(nombre__icontains=q)
        tipo = self.request.GET.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)
        return qs
        


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['tipos'] = PlanCuentas.TIPO_CHOICES
        ctx['titulo'] = 'Plan de Cuentas'
        return ctx


class PlanCuentasCreateView(GestionMixin, CreateView):
    model = PlanCuentas
    template_name = 'admin/contabilidad/plan_form.html'
    fields = ['codigo', 'nombre', 'tipo', 'nivel', 'parent', 'descripcion', 'acepta_movimientos', 'activa']
    success_url = reverse_lazy('contabilidad:plan_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cuenta creada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Cuenta Contable'
        return ctx


class PlanCuentasUpdateView(GestionMixin, UpdateView):
    model = PlanCuentas
    template_name = 'admin/contabilidad/plan_form.html'
    fields = ['codigo', 'nombre', 'tipo', 'nivel', 'parent', 'descripcion', 'acepta_movimientos', 'activa']
    success_url = reverse_lazy('contabilidad:plan_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cuenta actualizada exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Cuenta: {self.object}'
        return ctx


class PlanCuentasDeleteView(GestionMixin, DeleteView):
    model = PlanCuentas
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('contabilidad:plan_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cuenta eliminada.')
        return super().form_valid(form)



# ---------------------------------------------------------------------------
# Configuración Contable (singleton)
# ---------------------------------------------------------------------------



class ConfiguracionContableView(GestionMixin, View):
    template_name = 'admin/contabilidad/configuracion_form.html'

    def _get_form_class(self):
        from django import forms

        class ConfigForm(forms.ModelForm):
            class Meta:
                model = ConfiguracionContable
                fields = [
                    'cuenta_cxc', 'cuenta_cxp',
                    'cuenta_iva_debito', 'cuenta_iva_credito',
                    'cuenta_ventas_default', 'cuenta_compras_default',
                    'cuenta_sueldos_operacional', 'cuenta_sueldos_administrativo',
                    'cuenta_impuestos_sii',
                    'cuenta_afp_por_pagar', 'cuenta_salud_por_pagar',
                    'cuenta_sueldos_por_pagar',
                    'cuenta_anticipos_trabajadores', 'cuenta_anticipos_proveedores',
                    'cuenta_patrimonio_apertura',
                ]
            # Editamos el init para limitar las opciones de cuentas a solo aquellas que son de nivel 4 y si son de gastos o ingresos según corresponda
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                cuentas = PlanCuentas.objects.filter(activa=True, nivel=4).order_by('codigo')
                self.fields['cuenta_cxc'].queryset = cuentas.filter(tipo='activo')
                self.fields['cuenta_cxp'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_iva_debito'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_iva_credito'].queryset = cuentas.filter(tipo='activo')
                self.fields['cuenta_ventas_default'].queryset = cuentas.filter(tipo='ingreso')
                self.fields['cuenta_compras_default'].queryset = cuentas.filter(tipo='gasto')
                self.fields['cuenta_sueldos_operacional'].queryset = cuentas.filter(tipo='costo')
                self.fields['cuenta_sueldos_administrativo'].queryset = cuentas.filter(tipo='gasto')
                self.fields['cuenta_impuestos_sii'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_afp_por_pagar'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_salud_por_pagar'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_sueldos_por_pagar'].queryset = cuentas.filter(tipo='pasivo')
                self.fields['cuenta_anticipos_trabajadores'].queryset = cuentas.filter(tipo='activo')
                self.fields['cuenta_anticipos_proveedores'].queryset = cuentas.filter(tipo='activo')
                self.fields['cuenta_patrimonio_apertura'].queryset = cuentas.filter(tipo='patrimonio')

        return ConfigForm

    def get(self, request):
        from django.shortcuts import render
        obj = ConfiguracionContable.get()
        form = self._get_form_class()(instance=obj)
        return render(request, self.template_name, {'form': form, 'titulo': 'Configuración Contable'})

    def post(self, request):
        from django.shortcuts import render
        obj = ConfiguracionContable.get()
        form = self._get_form_class()(request.POST, instance=obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Configuración guardada.')
            return redirect('contabilidad:configuracion')
        return render(request, self.template_name, {'form': form, 'titulo': 'Configuración Contable'})


# ---------------------------------------------------------------------------
# Libro Diario — CRUD Asientos
# ---------------------------------------------------------------------------

class LibroDiarioListView(GestionMixin, ListView):
    model = AsientoContable
    template_name = 'admin/contabilidad/diario_list.html'
    context_object_name = 'asientos'
    paginate_by = 40

    def get_queryset(self):
        qs = AsientoContable.objects.prefetch_related('lineas')
        tipo = self.request.GET.get('tipo')
        estado = self.request.GET.get('estado')
        desde = self.request.GET.get('desde')
        hasta = self.request.GET.get('hasta')
        if tipo:
            qs = qs.filter(tipo=tipo)
        if estado:
            qs = qs.filter(estado=estado)
        if desde:
            qs = qs.filter(fecha__gte=parse_date(desde))
        if hasta:
            qs = qs.filter(fecha__lte=parse_date(hasta))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Libro Diario'
        ctx['tipo_choices'] = AsientoContable.TIPO_CHOICES
        ctx['estado_choices'] = AsientoContable.ESTADO_CHOICES
        return ctx


class AsientoDetailView(GestionMixin, DetailView):
    model = AsientoContable
    template_name = 'admin/contabilidad/asiento_detail.html'
    context_object_name = 'asiento'

    def get_queryset(self):
        return super().get_queryset().prefetch_related('lineas__cuenta')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Asiento {self.object.numero}'
        return ctx


class AsientoCreateView(GestionMixin, View):
    template_name = 'admin/contabilidad/asiento_form.html'

    def _forms(self, data=None):
        from django import forms
        from django.forms import inlineformset_factory

        class AsientoForm(forms.ModelForm):
            class Meta:
                model = AsientoContable
                fields = ['fecha', 'descripcion', 'tipo']
                widgets = {
                    'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
                    'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
                    'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
                }

        class LineaForm(forms.ModelForm):
            class Meta:
                model = LineaAsiento
                fields = ['cuenta', 'descripcion', 'debe', 'haber']
                widgets = {
                    'cuenta': forms.Select(attrs={'class': 'form-select form-select-sm cuenta-select'}),
                    'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
                    'debe': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01', 'min': '0'}),
                    'haber': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01', 'min': '0'}),
                }

        LineaFormSet = inlineformset_factory(AsientoContable, LineaAsiento, form=LineaForm, extra=0, can_delete=True, min_num=2)
        form = AsientoForm(data)
        formset = LineaFormSet(data)
        return form, formset

    def get(self, request):
        from django.shortcuts import render
        form, formset = self._forms()
        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'cuentas': cuentas,
            'titulo': 'Nuevo Asiento Manual',
        })

    def post(self, request):
        from django.shortcuts import render
        from django.forms import inlineformset_factory

        class AsientoForm(__import__('django').forms.ModelForm):
            class Meta:
                model = AsientoContable
                fields = ['fecha', 'descripcion', 'tipo']

        class LineaForm(__import__('django').forms.ModelForm):
            class Meta:
                model = LineaAsiento
                fields = ['cuenta', 'descripcion', 'debe', 'haber']

        LineaFormSet = inlineformset_factory(AsientoContable, LineaAsiento, form=LineaForm, extra=0, can_delete=True)
        form = AsientoForm(request.POST)
        if form.is_valid():
            asiento = form.save(commit=False)
            asiento.creado_por = request.user
            asiento.save()
            formset = LineaFormSet(request.POST, instance=asiento)
            if formset.is_valid():
                formset.save()
                messages.success(request, f'Asiento {asiento.numero} creado.')
                return redirect('contabilidad:asiento_detail', pk=asiento.pk)
            else:
                asiento.delete()
        else:
            formset = LineaFormSet(request.POST)

        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'cuentas': cuentas,
            'titulo': 'Nuevo Asiento Manual',
        })


class AsientoUpdateView(GestionMixin, View):
    template_name = 'admin/contabilidad/asiento_form.html'

    def _get_asiento(self, pk):
        return get_object_or_404(AsientoContable, pk=pk, estado='borrador')

    def _formset_class(self):
        from django import forms
        from django.forms import inlineformset_factory

        class LineaForm(forms.ModelForm):
            class Meta:
                model = LineaAsiento
                fields = ['cuenta', 'descripcion', 'debe', 'haber']
                widgets = {
                    'cuenta': forms.Select(attrs={'class': 'form-select form-select-sm cuenta-select'}),
                    'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
                    'debe': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01', 'min': '0'}),
                    'haber': forms.NumberInput(attrs={'class': 'form-control form-control-sm text-end', 'step': '0.01', 'min': '0'}),
                }

        return inlineformset_factory(AsientoContable, LineaAsiento, form=LineaForm, extra=1, can_delete=True)

    def get(self, request, pk):
        from django import forms
        from django.shortcuts import render
        asiento = self._get_asiento(pk)

        class AsientoForm(forms.ModelForm):
            class Meta:
                model = AsientoContable
                fields = ['fecha', 'descripcion', 'tipo']
                widgets = {
                    'fecha': forms.DateInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
                    'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
                    'tipo': forms.Select(attrs={'class': 'form-select form-select-sm'}),
                }

        form = AsientoForm(instance=asiento)
        formset = self._formset_class()(instance=asiento)
        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'cuentas': cuentas,
            'asiento': asiento, 'titulo': f'Editar Asiento {asiento.numero}',
        })

    def post(self, request, pk):
        from django import forms
        from django.shortcuts import render
        asiento = self._get_asiento(pk)

        class AsientoForm(forms.ModelForm):
            class Meta:
                model = AsientoContable
                fields = ['fecha', 'descripcion', 'tipo']

        form = AsientoForm(request.POST, instance=asiento)
        formset = self._formset_class()(request.POST, instance=asiento)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Asiento actualizado.')
            return redirect('contabilidad:asiento_detail', pk=asiento.pk)

        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        return render(request, self.template_name, {
            'form': form, 'formset': formset, 'cuentas': cuentas,
            'asiento': asiento, 'titulo': f'Editar Asiento {asiento.numero}',
        })


class AsientoConfirmarView(GestionMixin, View):
    def post(self, request, pk):
        asiento = get_object_or_404(AsientoContable, pk=pk)
        if asiento.estado != 'borrador':
            messages.warning(request, 'Solo los asientos en borrador pueden confirmarse.')
        elif not asiento.esta_cuadrado:
            messages.error(request, f'El asiento no está cuadrado (Debe={asiento.total_debe} / Haber={asiento.total_haber}).')
        elif asiento.lineas.count() == 0:
            messages.error(request, 'El asiento no tiene líneas.')
        else:
            asiento.estado = 'confirmado'
            asiento.save(update_fields=['estado'])
            messages.success(request, f'Asiento {asiento.numero} confirmado.')
        return redirect('contabilidad:asiento_detail', pk=asiento.pk)


class AsientoAnularView(GestionMixin, View):
    def post(self, request, pk):
        asiento = get_object_or_404(AsientoContable, pk=pk)
        if asiento.estado == 'anulado':
            messages.warning(request, 'El asiento ya está anulado.')
        else:
            asiento.estado = 'anulado'
            asiento.save(update_fields=['estado'])
            messages.success(request, f'Asiento {asiento.numero} anulado.')
        return redirect('contabilidad:asiento_detail', pk=asiento.pk)

class AsientoDeleteView(GestionMixin, DeleteView):
    model = AsientoContable
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('contabilidad:diario_list')

    def form_valid(self, form):
        if self.object.estado == 'confirmado':
            messages.warning(self.request, 'Los asientos confirmados no pueden eliminarse. Anúlelo primero.')
            return redirect('contabilidad:asiento_detail', pk=self.object.pk)
        messages.success(self.request, f'Asiento {self.object.numero} eliminado.')
        return super().form_valid(form)

# ---------------------------------------------------------------------------
# Reportes Contables
# ---------------------------------------------------------------------------

class LibroMayorView(GestionMixin, View):
    template_name = 'admin/contabilidad/libro_mayor.html'

    def get(self, request):
        from django.shortcuts import render
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')
        cuenta_id = request.GET.get('cuenta')

        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        movimientos = []
        cuenta_sel = None

        if cuenta_id:
            cuenta_sel = get_object_or_404(PlanCuentas, pk=cuenta_id)
            qs = LineaAsiento.objects.filter(
                asiento__estado='confirmado',
                cuenta=cuenta_sel,
            ).select_related('asiento').order_by('asiento__fecha', 'asiento__numero', 'orden')
            if desde:
                qs = qs.filter(asiento__fecha__gte=parse_date(desde))
            if hasta:
                qs = qs.filter(asiento__fecha__lte=parse_date(hasta))

            saldo = 0
            for linea in qs:
                saldo += float(linea.debe) - float(linea.haber)
                movimientos.append({
                    'linea': linea,
                    'saldo': saldo,
                })

        return render(request, self.template_name, {
            'titulo': 'Libro Mayor',
            'cuentas': cuentas,
            'cuenta_sel': cuenta_sel,
            'movimientos': movimientos,
        })


class BalanceComprobacionView(GestionMixin, View):
    template_name = 'admin/contabilidad/balance_comprobacion.html'

    def get(self, request):
        from django.shortcuts import render
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')

        qs = LineaAsiento.objects.filter(asiento__estado='confirmado').select_related('cuenta')
        if desde:
            qs = qs.filter(asiento__fecha__gte=parse_date(desde))
        if hasta:
            qs = qs.filter(asiento__fecha__lte=parse_date(hasta))

        from collections import defaultdict
        from decimal import Decimal
        data = defaultdict(lambda: {'debe': Decimal('0'), 'haber': Decimal('0'), 'cuenta': None})
        for linea in qs:
            key = linea.cuenta_id
            data[key]['debe'] += linea.debe
            data[key]['haber'] += linea.haber
            data[key]['cuenta'] = linea.cuenta

        filas = []
        total_debe = Decimal('0')
        total_haber = Decimal('0')
        for key in sorted(data.keys(), key=lambda k: data[k]['cuenta'].codigo if data[k]['cuenta'] else ''):
            row = data[key]
            saldo = row['debe'] - row['haber']
            filas.append({
                'cuenta': row['cuenta'],
                'debe': row['debe'],
                'haber': row['haber'],
                'saldo': saldo,
            })
            total_debe += row['debe']
            total_haber += row['haber']

        return render(request, self.template_name, {
            'titulo': 'Balance de Comprobación',
            'filas': filas,
            'total_debe': total_debe,
            'total_haber': total_haber,
        })


class BalanceGeneralView(GestionMixin, View):
    template_name = 'admin/contabilidad/balance_general.html'

    def get(self, request):
        from django.shortcuts import render
        hasta = request.GET.get('hasta')

        qs = LineaAsiento.objects.filter(asiento__estado='confirmado').select_related('cuenta')
        if hasta:
            qs = qs.filter(asiento__fecha__lte=parse_date(hasta))

        from collections import defaultdict
        from decimal import Decimal
        saldos = defaultdict(Decimal)
        cuentas_map = {}
        for linea in qs:
            saldos[linea.cuenta_id] += linea.debe - linea.haber
            cuentas_map[linea.cuenta_id] = linea.cuenta

        activos, pasivos, patrimonio = [], [], []
        total_activo = Decimal('0')
        total_pasivo = Decimal('0')
        total_patrimonio = Decimal('0')

        for cid, saldo in saldos.items():
            if saldo == 0:
                continue
            cuenta = cuentas_map[cid]
            row = {'cuenta': cuenta, 'saldo': saldo}
            if cuenta.tipo == 'activo':
                activos.append(row)
                total_activo += saldo
            elif cuenta.tipo == 'pasivo':
                pasivos.append(row)
                total_pasivo += saldo
            elif cuenta.tipo == 'socio':
                patrimonio.append(row)
                total_patrimonio += saldo

        activos.sort(key=lambda r: r['cuenta'].codigo)
        pasivos.sort(key=lambda r: r['cuenta'].codigo)
        patrimonio.sort(key=lambda r: r['cuenta'].codigo)

        return render(request, self.template_name, {
            'titulo': 'Balance General',
            'activos': activos, 'total_activo': total_activo,
            'pasivos': pasivos, 'total_pasivo': total_pasivo,
            'patrimonio': patrimonio, 'total_patrimonio': total_patrimonio,
            'total_pasivo_patrimonio': total_pasivo + total_patrimonio,
        })


class EstadoResultadosView(GestionMixin, View):
    template_name = 'admin/contabilidad/estado_resultados.html'

    def get(self, request):
        from django.shortcuts import render
        desde = request.GET.get('desde')
        hasta = request.GET.get('hasta')

        qs = LineaAsiento.objects.filter(asiento__estado='confirmado').select_related('cuenta')
        if desde:
            qs = qs.filter(asiento__fecha__gte=parse_date(desde))
        if hasta:
            qs = qs.filter(asiento__fecha__lte=parse_date(hasta))

        from collections import defaultdict
        from decimal import Decimal
        saldos = defaultdict(Decimal)
        cuentas_map = {}
        for linea in qs:
            saldos[linea.cuenta_id] += linea.haber - linea.debe  # ingresos son saldo haber
            cuentas_map[linea.cuenta_id] = linea.cuenta

        ingresos, costos, gastos = [], [], []
        total_ingresos = Decimal('0')
        total_costos = Decimal('0')
        total_gastos = Decimal('0')

        for cid, saldo in saldos.items():
            if saldo == 0:
                continue
            cuenta = cuentas_map[cid]
            row = {'cuenta': cuenta, 'saldo': abs(saldo)}
            if cuenta.tipo == 'ingreso':
                ingresos.append(row)
                total_ingresos += abs(saldo)
            elif cuenta.tipo == 'costo':
                costos.append(row)
                total_costos += abs(saldo)
            elif cuenta.tipo == 'gasto':
                gastos.append(row)
                total_gastos += abs(saldo)

        ingresos.sort(key=lambda r: r['cuenta'].codigo)
        costos.sort(key=lambda r: r['cuenta'].codigo)
        gastos.sort(key=lambda r: r['cuenta'].codigo)

        utilidad = total_ingresos - total_costos - total_gastos

        return render(request, self.template_name, {
            'titulo': 'Estado de Resultados',
            'ingresos': ingresos, 'total_ingresos': total_ingresos,
            'costos': costos, 'total_costos': total_costos,
            'gastos': gastos, 'total_gastos': total_gastos,
            'utilidad': utilidad,
        })



# ---------------------------------------------------------------------------
# Centros de Costo
# ---------------------------------------------------------------------------

class CentroCostoListView(GestionMixin, ListView):
    model = CentroCosto
    template_name = 'admin/contabilidad/centro_costo_list.html'
    context_object_name = 'centros'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Centros de Costo'
        return ctx


class CentroCostoCreateView(GestionMixin, CreateView):
    model = CentroCosto
    template_name = 'admin/contabilidad/centro_costo_form.html'
    fields = ['codigo', 'nombre', 'descripcion', 'presupuesto_mensual', 'activo']
    success_url = reverse_lazy('contabilidad:centro_list')

    def form_valid(self, form):
        messages.success(self.request, 'Centro de costo creado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Centro de Costo'
        return ctx


class CentroCostoUpdateView(GestionMixin, UpdateView):
    model = CentroCosto
    template_name = 'admin/contabilidad/centro_costo_form.html'
    fields = ['codigo', 'nombre', 'descripcion', 'presupuesto_mensual', 'activo']
    success_url = reverse_lazy('contabilidad:centro_list')

    def form_valid(self, form):
        messages.success(self.request, 'Centro de costo actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar: {self.object}'
        return ctx


class CentroCostoReporteView(GestionMixin, View):
    template_name = 'admin/contabilidad/centro_costo_reporte.html'

    def get(self, request):
        from django.shortcuts import render
        from decimal import Decimal
        from django.utils import timezone
        from django.db.models import F

        hoy = timezone.now()
        mes = int(request.GET.get('mes', hoy.month))
        anio = int(request.GET.get('anio', hoy.year))

        MESES = {1:'Enero',2:'Febrero',3:'Marzo',4:'Abril',5:'Mayo',6:'Junio',
                 7:'Julio',8:'Agosto',9:'Septiembre',10:'Octubre',11:'Noviembre',12:'Diciembre'}

        centros = CentroCosto.objects.filter(activo=True)

        # ── Gastos: detalles de facturas recibidas ──
        from apps.proveedores.models import DetalleFacturaRecibida
        gastos_qs = (
            DetalleFacturaRecibida.objects
            .filter(centro_costo__isnull=False,
                    factura__fecha_emision__month=mes,
                    factura__fecha_emision__year=anio)
            .exclude(factura__estado='anulada')
            .annotate(subtotal=F('cantidad') * F('precio_unitario'))
            .values('centro_costo_id')
            .annotate(total=Sum('subtotal'))
        )
        gastos_map = {r['centro_costo_id']: r['total'] for r in gastos_qs}

        # ── Ingresos: detalles de facturas emitidas ──
        from apps.clientes.models import DetalleFacturaEmitida
        ingresos_qs = (
            DetalleFacturaEmitida.objects
            .filter(centro_costo__isnull=False,
                    factura__fecha_emision__month=mes,
                    factura__fecha_emision__year=anio)
            .exclude(factura__estado='anulada')
            .annotate(subtotal=F('cantidad') * F('precio_unitario'))
            .values('centro_costo_id')
            .annotate(total=Sum('subtotal'))
        )
        ingresos_map = {r['centro_costo_id']: r['total'] for r in ingresos_qs}

        # ── Remuneraciones ──
        from apps.rrhh.models import Remuneracion
        rem_qs = (
            Remuneracion.objects
            .filter(trabajador__centro_costo__isnull=False,
                    periodo_mes=mes,
                    periodo_anio=anio)
            .values('trabajador__centro_costo_id')
            .annotate(total=Sum('sueldo_bruto'))
        )
        rem_map = {r['trabajador__centro_costo_id']: r['total'] for r in rem_qs}

        # ── Costos de proyecto ──
        from apps.proyectos.models import CostoProyecto
        costos_qs = (
            CostoProyecto.objects
            .filter(centro_costo__isnull=False,
                    fecha__month=mes,
                    fecha__year=anio)
            .values('centro_costo_id')
            .annotate(total=Sum('monto'))
        )
        costos_map = {r['centro_costo_id']: r['total'] for r in costos_qs}

        filas = []
        total_presupuesto = Decimal('0')
        total_gastos_fact = Decimal('0')
        total_ingresos = Decimal('0')
        total_remuneraciones = Decimal('0')
        total_costos_proy = Decimal('0')

        for c in centros:
            g  = gastos_map.get(c.pk, Decimal('0')) or Decimal('0')
            ig = ingresos_map.get(c.pk, Decimal('0')) or Decimal('0')
            r  = rem_map.get(c.pk, Decimal('0')) or Decimal('0')
            p  = costos_map.get(c.pk, Decimal('0')) or Decimal('0')
            egresos = g + r + p
            resultado = ig - egresos
            presup = c.presupuesto_mensual or Decimal('0')
            desv = None
            if presup > 0:
                desv = ((egresos - presup) / presup * 100).quantize(Decimal('0.1'))
            filas.append({
                'centro': c,
                'gastos_facturas': g,
                'ingresos': ig,
                'remuneraciones': r,
                'costos_proyecto': p,
                'egresos': egresos,
                'resultado': resultado,
                'presupuesto': presup,
                'desviacion': desv,
            })
            total_presupuesto += presup
            total_gastos_fact += g
            total_ingresos += ig
            total_remuneraciones += r
            total_costos_proy += p

        total_egresos = total_gastos_fact + total_remuneraciones + total_costos_proy
        total_resultado = total_ingresos - total_egresos
        desv_total = None
        if total_presupuesto > 0:
            desv_total = ((total_egresos - total_presupuesto) / total_presupuesto * 100).quantize(Decimal('0.1'))

        anios_disponibles = list(range(hoy.year - 2, hoy.year + 2))

        return render(request, self.template_name, {
            'titulo': f'Reporte Centros de Costo — {MESES[mes]} {anio}',
            'filas': filas,
            'mes': mes,
            'anio': anio,
            'mes_nombre': MESES[mes],
            'meses': MESES,
            'anios_disponibles': anios_disponibles,
            'total_presupuesto': total_presupuesto,
            'total_gastos_fact': total_gastos_fact,
            'total_ingresos': total_ingresos,
            'total_remuneraciones': total_remuneraciones,
            'total_costos_proy': total_costos_proy,
            'total_egresos': total_egresos,
            'total_resultado': total_resultado,
            'desv_total': desv_total,
        })


# ---------------------------------------------------------------------------
# Asiento de Apertura — Saldos Iniciales
# ---------------------------------------------------------------------------

class AperturaContableView(GestionMixin, View):
    """
    Permite ingresar los saldos de apertura contable de la empresa.

    Crea (o reemplaza) un único AsientoContable de tipo 'apertura'. Al confirmarlo,
    todos los reportes (Balance General, Comprobación, Libro Mayor) lo incluyen
    automáticamente porque filtran por asiento__estado='confirmado', sin requerir
    ningún cambio en las vistas de reportes.

    Lógica de cuadre:
        DEBE  = activos con saldo
        HABER = pasivos con saldo
        La diferencia (DEBE - HABER) se registra automáticamente en
        ConfiguracionContable.cuenta_patrimonio_apertura (Resultados Acumulados / Capital).
    """
    template_name = 'admin/contabilidad/apertura.html'

    def _get_apertura(self):
        return AsientoContable.objects.filter(tipo='apertura').order_by('fecha').first()

    def get(self, request):
        from django.shortcuts import render
        import json
        apertura = self._get_apertura()
        cuentas = PlanCuentas.objects.filter(activa=True, acepta_movimientos=True).order_by('codigo')
        config = ConfiguracionContable.get()

        # Collect bank accounts linked to a PlanCuentas account (single source of truth: saldo_inicial)
        from apps.tesoreria.models import CuentaBancaria
        cuentas_bancarias = (
            CuentaBancaria.objects
            .filter(activa=True, cuenta_contable__isnull=False)
            .select_related('cuenta_contable', 'banco')
        )
        banco_cuenta_ids = {cb.cuenta_contable_id: cb for cb in cuentas_bancarias}

        # Pre-fill manual lines from existing apertura (excluding patrimonio and bank lines)
        patrimonio_id = config.cuenta_patrimonio_apertura_id if config else None
        lineas_existentes = []
        if apertura:
            for linea in apertura.lineas.select_related('cuenta').order_by('orden'):
                if linea.cuenta_id == patrimonio_id:
                    continue  # auto-balance line, recalculated on save
                if linea.cuenta_id in banco_cuenta_ids:
                    continue  # bank line, driven by saldo_inicial — don't show as manual
                lineas_existentes.append({
                    'cuenta_id': linea.cuenta_id,
                    'cuenta_str': str(linea.cuenta),
                    'monto': float(linea.debe if linea.debe > 0 else linea.haber),
                    'tipo': 'debe' if linea.debe > 0 else 'haber',
                    'from_banco': False,
                })

        cuentas_json = json.dumps([
            {'id': c.pk, 'label': str(c), 'tipo': c.tipo}
            for c in cuentas
            if c.pk not in banco_cuenta_ids  # bank accounts are shown separately, not in dropdown
        ])

        # Bank accounts summary for display (always shown, read-only)
        bancos_apertura = [
            {
                'cuenta_id': cb.cuenta_contable_id,
                'label': f'{cb.banco} — {cb.numero}',
                'cuenta_str': str(cb.cuenta_contable),
                'saldo_inicial': float(cb.saldo_inicial),
            }
            for cb in cuentas_bancarias
            if cb.saldo_inicial != 0
        ]

        return render(request, self.template_name, {
            'titulo': 'Saldos de Apertura',
            'apertura': apertura,
            'config': config,
            'cuentas_json': cuentas_json,
            'lineas_json': json.dumps(lineas_existentes),
            'bancos_apertura': bancos_apertura,
            'bancos_apertura_json': json.dumps(bancos_apertura),
            'fecha_apertura': apertura.fecha.isoformat() if apertura else '',
        })

    def post(self, request):
        from django.shortcuts import render, redirect
        from decimal import Decimal, InvalidOperation
        import json

        # ── Confirm existing borrador ──────────────────────────────────────
        if request.POST.get('action') == 'confirmar':
            apertura = self._get_apertura()
            if apertura and apertura.estado == 'borrador':
                if not apertura.esta_cuadrado:
                    messages.error(request, 'El asiento no está cuadrado (Debe ≠ Haber). Corrija los montos.')
                    return redirect('contabilidad:apertura')
                apertura.estado = 'confirmado'
                apertura.save(update_fields=['estado'])
                messages.success(request, f'Asiento de apertura {apertura.numero} confirmado. Todos los reportes lo incluirán.')
            return redirect('contabilidad:apertura')

        # ── Save / replace borrador ────────────────────────────────────────
        config = ConfiguracionContable.get()

        fecha_str = request.POST.get('fecha', '').strip()
        fecha = parse_date(fecha_str)
        if not fecha:
            messages.error(request, 'Ingrese una fecha de apertura válida.')
            return redirect('contabilidad:apertura')

        cuenta_ids = request.POST.getlist('cuenta_id')
        montos_raw = request.POST.getlist('monto')
        tipos = request.POST.getlist('tipo')  # 'debe' | 'haber'

        # ── Manual lines (non-bank accounts) ──────────────────────────────
        lineas = []
        errores = []
        for i, (cid, monto_str, tipo) in enumerate(zip(cuenta_ids, montos_raw, tipos), 1):
            try:
                cid = int(cid)
                monto = Decimal(monto_str.strip().replace('.', '').replace(',', '.'))
                if monto <= 0:
                    continue
                cuenta = PlanCuentas.objects.get(pk=cid, activa=True, acepta_movimientos=True)
                if tipo not in ('debe', 'haber'):
                    tipo = 'debe'
                lineas.append({'cuenta': cuenta, 'monto': monto, 'tipo': tipo})
            except (ValueError, InvalidOperation, PlanCuentas.DoesNotExist):
                errores.append(f'Fila {i}: datos inválidos.')

        # ── Auto-include bank accounts from saldo_inicial ─────────────────
        from apps.tesoreria.models import CuentaBancaria
        for cb in CuentaBancaria.objects.filter(activa=True, cuenta_contable__isnull=False).select_related('cuenta_contable'):
            if cb.saldo_inicial and cb.saldo_inicial != 0:
                lineas.append({
                    'cuenta': cb.cuenta_contable,
                    'monto': abs(cb.saldo_inicial),
                    'tipo': 'debe' if cb.saldo_inicial > 0 else 'haber',
                })

        if errores:
            for e in errores:
                messages.warning(request, e)

        if not lineas:
            messages.error(request, 'No hay líneas con montos válidos.')
            return redirect('contabilidad:apertura')

        # Check confirmed asiento can't be replaced
        existente = self._get_apertura()
        if existente and existente.estado == 'confirmado':
            messages.error(
                request,
                f'Ya existe un asiento de apertura confirmado ({existente.numero}). '
                'Anúlelo desde el Libro Diario antes de reemplazarlo.'
            )
            return redirect('contabilidad:apertura')

        total_debe = sum(l['monto'] for l in lineas if l['tipo'] == 'debe')
        total_haber = sum(l['monto'] for l in lineas if l['tipo'] == 'haber')
        diferencia = total_debe - total_haber  # positive → more assets than liabilities

        # Need patrimonio account if entry doesn't balance
        if diferencia != 0 and (not config or not config.cuenta_patrimonio_apertura):
            messages.error(
                request,
                'El asiento no cuadra y no hay cuenta de Patrimonio / Resultados Acumulados '
                'configurada en Configuración Contable. Configúrela primero o ingrese saldos que cuadren manualmente.'
            )
            return redirect('contabilidad:apertura')

        # Delete existing borrador
        if existente:
            existente.delete()

        # Create new apertura asiento
        apertura = AsientoContable.objects.create(
            fecha=fecha,
            descripcion='Saldos de Apertura',
            tipo='apertura',
            estado='borrador',
        )

        for i, l in enumerate(lineas, start=1):
            LineaAsiento.objects.create(
                asiento=apertura,
                cuenta=l['cuenta'],
                debe=l['monto'] if l['tipo'] == 'debe' else Decimal('0'),
                haber=l['monto'] if l['tipo'] == 'haber' else Decimal('0'),
                descripcion='Saldo de apertura',
                orden=i,
            )

        # Auto-balance line → cuenta_patrimonio_apertura
        if diferencia != 0 and config and config.cuenta_patrimonio_apertura:
            LineaAsiento.objects.create(
                asiento=apertura,
                cuenta=config.cuenta_patrimonio_apertura,
                debe=Decimal('0') if diferencia > 0 else abs(diferencia),
                haber=diferencia if diferencia > 0 else Decimal('0'),
                descripcion='Patrimonio / Resultados Acumulados (cuadre automático)',
                orden=len(lineas) + 1,
            )

        messages.success(
            request,
            f'Asiento de apertura {apertura.numero} guardado en borrador con {len(lineas)} líneas. '
            'Revíselo y confírmelo para que aparezca en los reportes.'
        )
        return redirect('contabilidad:apertura')
