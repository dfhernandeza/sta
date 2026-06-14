from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum
from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.core.mixins import GestionMixin
from apps.core.templatetags.custom_tags import moneda_chilena
from .models import RegistroCompra, RegistroVenta, DeclaracionIVA, PPM, FormularioF29


MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]


def _anio_choices():
    from django.utils import timezone
    anio = timezone.now().year
    return [(y, str(y)) for y in range(anio - 3, anio + 3)]


SELECT_MES = forms.Select(choices=[('' , '— Mes —')] + MESES,
                           attrs={'class': 'form-select'})


class IVAForm(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = DeclaracionIVA
        fields = ['periodo_mes', 'periodo_anio', 'iva_debito', 'iva_credito', 'estado', 'fecha_presentacion']
        widgets = {
            'iva_debito':        forms.NumberInput(attrs={'class': 'form-control'}),
            'iva_credito':       forms.NumberInput(attrs={'class': 'form-control'}),
            'estado':            forms.Select(attrs={'class': 'form-select'}),
            'fecha_presentacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class PPMForm(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = PPM
        fields = ['periodo_mes', 'periodo_anio', 'base_imponible', 'tasa', 'monto', 'estado']
        widgets = {
            'base_imponible': forms.NumberInput(attrs={'class': 'form-control'}),
            'tasa':           forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'monto':          forms.NumberInput(attrs={'class': 'form-control'}),
            'estado':         forms.Select(attrs={'class': 'form-select'}),
        }


class F29Form(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = FormularioF29
        fields = ['periodo_mes', 'periodo_anio', 'iva_pagar', 'ppm_pagar', 'retenciones', 'estado', 'fecha_presentacion', 'folio']
        widgets = {
            'iva_pagar':          forms.NumberInput(attrs={'class': 'form-control'}),
            'ppm_pagar':          forms.NumberInput(attrs={'class': 'form-control'}),
            'retenciones':        forms.NumberInput(attrs={'class': 'form-control'}),
            'estado':             forms.Select(attrs={'class': 'form-select'}),
            'fecha_presentacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'folio':              forms.TextInput(attrs={'class': 'form-control'}),
        }


class TributarioResumenView(GestionMixin, TemplateView):
    template_name = 'admin/tributario/resumen.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['iva_pendientes'] = DeclaracionIVA.objects.filter(estado='borrador').order_by('-periodo_anio', '-periodo_mes')
        ctx['ppm_pendientes'] = PPM.objects.filter(estado='pendiente').order_by('-periodo_anio', '-periodo_mes')
        ctx['f29_pendientes'] = FormularioF29.objects.filter(estado='pendiente').order_by('-periodo_anio', '-periodo_mes')
        ctx['titulo'] = 'Módulo Tributario'

        anio_actual = timezone.now().year
        debito = RegistroVenta.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('iva_debito'))['s'] or 0
        credito = RegistroCompra.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('iva_credito'))['s'] or 0
        ctx['total_iva_debito'] = debito
        ctx['total_iva_credito'] = credito
        ctx['diferencia_iva'] = debito - credito
        ctx['total_ppm'] = PPM.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('monto'))['s'] or 0


        return ctx


class RegistroCompraListView(GestionMixin, ListView):
    model = RegistroCompra
    template_name = 'admin/tributario/compra_list.html'
    context_object_name = 'registros'
    paginate_by = 30

    def get_queryset(self):
        qs = RegistroCompra.objects.select_related('proveedor', 'factura')
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes:
            qs = qs.filter(periodo_mes=mes)
        if anio:
            qs = qs.filter(periodo_anio=anio)
        return qs.order_by('-periodo_anio', '-periodo_mes')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registro de Compras'
        totales = self.get_queryset().aggregate(
            total_neto=Sum('neto'), total_iva=Sum('iva_credito'), total=Sum('total')
        )
        ctx.update(totales)
        return ctx


class RegistroVentaListView(GestionMixin, ListView):
    model = RegistroVenta
    template_name = 'admin/tributario/venta_list.html'
    context_object_name = 'registros'
    paginate_by = 30

    def get_queryset(self):
        qs = RegistroVenta.objects.select_related('cliente', 'factura')
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes:
            qs = qs.filter(periodo_mes=mes)
        if anio:
            qs = qs.filter(periodo_anio=anio)
        return qs.order_by('-periodo_anio', '-periodo_mes')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registro de Ventas'
        totales = self.get_queryset().aggregate(
            total_neto=Sum('neto'), total_iva=Sum('iva_debito'), total=Sum('total')
        )
        ctx.update(totales)
        return ctx


class DeclaracionIVAListView(GestionMixin, ListView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_list.html'
    context_object_name = 'declaraciones'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Declaraciones IVA'
        return ctx


class DeclaracionIVACreateView(GestionMixin, CreateView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_form.html'
    form_class = IVAForm
    success_url = reverse_lazy('tributario:iva_list')

    def _calcular_periodo(self, mes, anio):
        debito = RegistroVenta.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('iva_debito'))['s'] or 0
        credito = RegistroCompra.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('iva_credito'))['s'] or 0
        return debito, credito

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                debito, credito = self._calcular_periodo(mes_int, anio_int)
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'iva_debito': debito,
                    'iva_credito': credito,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'Declaración IVA registrada.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Declaración IVA'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                debito, credito = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'debito': debito, 'credito': credito,
                    'diferencia': max(debito - credito, 0),
                }
            except (ValueError, TypeError):
                pass
        return ctx


class DeclaracionIVAUpdateView(GestionMixin, UpdateView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_form.html'
    form_class = IVAForm
    success_url = reverse_lazy('tributario:iva_list')

    def form_valid(self, form):
        messages.success(self.request, 'Declaración IVA actualizada.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Declaración IVA {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        return ctx


class PPMListView(GestionMixin, ListView):
    model = PPM
    template_name = 'admin/tributario/ppm_list.html'
    context_object_name = 'ppms'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'PPM'
        return ctx


class PPMCreateView(GestionMixin, CreateView):
    model = PPM
    template_name = 'admin/tributario/ppm_form.html'
    form_class = PPMForm
    success_url = reverse_lazy('tributario:ppm_list')

    def _calcular_periodo(self, mes, anio):
        base = RegistroVenta.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('neto'))['s'] or 0
        tasa = PPM._meta.get_field('tasa').default  # 0.0025
        monto = round(float(base) * float(tasa), 2)
        return base, monto

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                base, monto = self._calcular_periodo(mes_int, anio_int)
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'base_imponible': base,
                    'monto': monto,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'PPM registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo PPM'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                base, monto = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'base': base, 'monto': monto,
                }
            except (ValueError, TypeError):
                pass
        return ctx

class PPMUpdateView(GestionMixin, UpdateView):
    model = PPM
    template_name = 'admin/tributario/ppm_form.html'
    form_class = PPMForm
    success_url = reverse_lazy('tributario:ppm_list')

    def form_valid(self, form):
        messages.success(self.request, 'PPM actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar PPM {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        return ctx


class PPMPagarView(GestionMixin, View):
    template_name = 'admin/tributario/ppm_pagar.html'

    def _build_form(self, data=None, initial=None):
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoPPMForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El pago al SII se descontará de esta cuenta.',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoPPMForm(data=data, initial=initial)

    def get(self, request, pk):
        ppm = get_object_or_404(PPM, pk=pk)
        if ppm.estado == 'pagado':
            messages.info(request, 'Este PPM ya fue pagado.')
            return redirect('tributario:ppm_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(request, self.template_name, {'ppm': ppm, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_movimiento_bancario

        ppm = get_object_or_404(PPM, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'ppm': ppm, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Actualizar PPM
        ppm.estado = 'pagado'
        ppm.fecha_pago = d['fecha_pago']
        ppm.save()

        # 2. Crear MovimientoBancario (egreso)
        descripcion_mov = f'PPM {ppm.periodo_mes:02d}/{ppm.periodo_anio} - ${ppm.monto:,.0f}'
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='egreso',
            monto=ppm.monto,
            descripcion=descripcion_mov,
            cuenta_contable=None,
        )

        # Asignar cuenta_contable = cuenta impuestos SII
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if config and config.cuenta_impuestos_sii:
                movimiento.cuenta_contable = config.cuenta_impuestos_sii
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # 3. Generar asiento contable borrador
        asiento = generar_asiento_movimiento_bancario(movimiento, usuario=request.user)

        if asiento:
            messages.success(
                request,
                f'PPM pagado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'PPM pagado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('tributario:ppm_list')


class F29ListView(GestionMixin, ListView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_list.html'
    context_object_name = 'f29s'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Formularios F29'
        return ctx


class F29CreateView(GestionMixin, CreateView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_form.html'
    form_class = F29Form
    success_url = reverse_lazy('tributario:f29_list')

    def _calcular_periodo(self, mes, anio):
        iva_pagar = 0
        try:
            decl = DeclaracionIVA.objects.get(periodo_mes=mes, periodo_anio=anio)
            iva_pagar = decl.diferencia
        except DeclaracionIVA.DoesNotExist:
            pass
        ppm_pagar = 0
        try:
            ppm = PPM.objects.get(periodo_mes=mes, periodo_anio=anio)
            ppm_pagar = ppm.monto
        except PPM.DoesNotExist:
            pass
        return iva_pagar, ppm_pagar

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                iva_pagar, ppm_pagar = self._calcular_periodo(mes_int, anio_int)
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'iva_pagar': iva_pagar,
                    'ppm_pagar': ppm_pagar,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'F29 registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Formulario F29'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                iva_pagar, ppm_pagar = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'iva_pagar': iva_pagar,
                    'ppm_pagar': ppm_pagar,
                    'total': float(iva_pagar) + float(ppm_pagar),
                    'tiene_iva': DeclaracionIVA.objects.filter(periodo_mes=mes_int, periodo_anio=anio_int).exists(),
                    'tiene_ppm': PPM.objects.filter(periodo_mes=mes_int, periodo_anio=anio_int).exists(),
                }
            except (ValueError, TypeError):
                pass
        return ctx


class F29UpdateView(GestionMixin, UpdateView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_form.html'
    form_class = F29Form
    success_url = reverse_lazy('tributario:f29_list')

    def form_valid(self, form):
        messages.success(self.request, 'F29 actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar F29 {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        return ctx


# ---------------------------------------------------------------------------
# Pago F29 con automatismo contable
# ---------------------------------------------------------------------------

class F29PagarView(GestionMixin, View):
    template_name = 'admin/tributario/f29_pagar.html'

    def _build_form(self, data=None, initial=None):
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')        

        class PagoF29Form(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El pago al SII se descontará de esta cuenta.',
            )
            folio = forms.CharField(
                required=False, max_length=20,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° folio SII'}),
                label='N° Folio (opcional)',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoF29Form(data=data, initial=initial)

    def get(self, request, pk):
        f29 = get_object_or_404(FormularioF29, pk=pk)
        if f29.estado == 'pagado':
            messages.info(request, 'Este F29 ya fue pagado.')
            return redirect('tributario:f29_list')
        form = self._build_form(initial={
            'fecha_pago': timezone.now().date(),
            'folio': f29.folio,
        })
        return render(request, self.template_name, {'f29': f29, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_movimiento_bancario

        f29 = get_object_or_404(FormularioF29, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'f29': f29, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Actualizar F29
        f29.estado = 'pagado'
        f29.fecha_presentacion = d['fecha_pago']
        if d['folio']:
            f29.folio = d['folio']
        f29.save()

        # 2. Crear MovimientoBancario (egreso)
        descripcion_mov = (
            f'Pago F29 {f29.periodo_mes:02d}/{f29.periodo_anio} '
            f'(IVA: ${f29.iva_pagar:,.0f} | PPM: ${f29.ppm_pagar:,.0f})'
        )
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='egreso',
            monto=f29.total_pagar,
            descripcion=descripcion_mov[:300],
            cuenta_contable=None,
            documento=f29.folio[:50] if f29.folio else '',
        )

        # Asignar cuenta_contable = cuenta impuestos SII de ConfiguracionContable
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if config and config.cuenta_impuestos_sii:
                movimiento.cuenta_contable = config.cuenta_impuestos_sii
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # 3. Generar asiento contable borrador
        asiento = generar_asiento_movimiento_bancario(movimiento, usuario=request.user)

        if asiento:
            messages.success(
                request,
                f'Pago F29 registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'Pago F29 registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('tributario:f29_list')
