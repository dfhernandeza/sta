from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.forms import CheckboxInput, inlineformset_factory, ModelForm, TextInput, Select, NumberInput
from apps.contabilidad.utils import generar_asiento_factura_recibida, generar_asiento_rendicion_gastos_recibida
from apps.core.mixins import GestionMixin
from apps.web import forms
from .models import DetalleRendicion, Proveedor, FacturaRecibida, DetalleFacturaRecibida, CuentaPorPagar, Anticipo, RendicionGastos
from apps.tributario.models import RegistroCompra


def _viernes_proxima_semana(fecha):
    """Devuelve el viernes de la semana siguiente a 'fecha'.
    Regla: cualquier día de la semana N se paga el viernes de la semana N+1.
    """
    lunes_actual = fecha - timedelta(days=fecha.weekday())  # weekday(): lunes=0
    return lunes_actual + timedelta(days=11)                # +7 (prox semana) +4 (viernes)


def _generar_asiento_automatico_factura(request, factura, reemplazar_borrador=False):
    """Genera asiento automático para facturas recibidas evitando duplicados."""
    asiento_activo = factura.asientos.exclude(estado='anulado').first()

    if asiento_activo:
        if asiento_activo.estado == 'confirmado':
            messages.warning(
                request,
                f'No se regeneró el asiento automático porque la factura ya tiene un asiento confirmado ({asiento_activo.numero}).'
            )
            return asiento_activo
        if asiento_activo.estado == 'borrador' and reemplazar_borrador:
            asiento_activo.delete()
        elif asiento_activo.estado == 'borrador':
            return asiento_activo

    asiento = generar_asiento_factura_recibida(factura, usuario=request.user)
    if asiento:
        messages.info(request, f'Se generó automáticamente el asiento {asiento.numero}.')
    else:
        messages.warning(
            request,
            'La factura se guardó, pero no se pudo generar el asiento automático. Revise la configuración contable.'
        )
    return asiento


def _sincronizar_cxp_factura(factura):
    """Crea/actualiza CxP de factura cuando corresponde."""
    requiere_cxp = bool(factura.pago_por_trabajador_id or factura.fecha_vencimiento)
    if not requiere_cxp:
        return None

    fecha_venc = factura.fecha_vencimiento or factura.fecha_emision
    cxp, created = CuentaPorPagar.objects.get_or_create(
        factura=factura,
        defaults={
            'fecha_vencimiento': fecha_venc,
            'monto': factura.total,
        }
    )
    if not created:
        cxp.fecha_vencimiento = fecha_venc
        cxp.monto = factura.total
        cxp.save(update_fields=['fecha_vencimiento', 'monto'])
    return cxp


class DetalleFacturaForm(ModelForm):
    class Meta:
        model = DetalleFacturaRecibida
        fields = ['descripcion', 'cuenta_contable', 'cantidad', 'precio_unitario', 'centro_costo', 'exento_iva']
        widgets = {
            'descripcion': TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cuenta_contable': Select(attrs={'class': 'form-select form-select-sm'}),
            'cantidad': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0'}),
            'precio_unitario': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0'}),
            'centro_costo': Select(attrs={'class': 'form-select form-select-sm'}),
            'exento_iva': CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # Editamos el init para filtrar las cuentas contables y mostrar solo las de tipo 'gasto' o 'costo' y de nivel 4
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(
            tipo__in=['gasto', 'costo'],
            nivel=4
        )


DetalleFormSet = inlineformset_factory(
    FacturaRecibida, DetalleFacturaRecibida,
    form=DetalleFacturaForm,
    extra=0, can_delete=True,
)




class ProveedorListView(GestionMixin, ListView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_list.html'
    context_object_name = 'proveedores'
    paginate_by = 20

    def get_queryset(self):
        qs = Proveedor.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(razon_social__icontains=q) | qs.filter(rut__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Proveedores'
        return ctx


class ProveedorCreateView(GestionMixin, CreateView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'banco', 'tipo_cuenta', 'numero_cuenta', 'notas', 'activo']
    success_url = reverse_lazy('proveedores:proveedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Proveedor registrado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Proveedor'
        return ctx


class ProveedorUpdateView(GestionMixin, UpdateView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'banco', 'tipo_cuenta', 'numero_cuenta', 'activo', 'notas']
    success_url = reverse_lazy('proveedores:proveedor_list')

    def form_valid(self, form):
        messages.success(self.request, 'Proveedor actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Proveedor: {self.object.razon_social}'
        return ctx


class ProveedorDetailView(GestionMixin, DetailView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_detail.html'
    context_object_name = 'proveedor'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['facturas'] = self.object.facturas.all().order_by('-fecha_emision')[:10]
        return ctx


class FacturaRecibidaListView(GestionMixin, ListView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_list.html'
    context_object_name = 'facturas'
    paginate_by = 25

    def get_queryset(self):
        qs = FacturaRecibida.objects.select_related('proveedor', 'proyecto', 'pago_por_trabajador').order_by('-fecha_emision')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(numero__icontains=q) | qs.filter(proveedor__razon_social__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estados'] = FacturaRecibida.ESTADO_CHOICES
        ctx['titulo'] = 'Facturas Recibidas'
        return ctx


class FacturaRecibidaCreateView(GestionMixin, CreateView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_form.html'
    fields = ['numero', 'fecha_emision', 'fecha_vencimiento', 'proveedor', 'proyecto', 'pago_por_trabajador', 'neto', 'exento', 'iva', 'total', 'estado', 'observaciones']
    success_url = reverse_lazy('proveedores:factura_list')

    def form_valid(self, form):
        formset = DetalleFormSet(self.request.POST, instance=form.instance)
        if not formset.is_valid():
            return self.form_invalid(form)
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()
        _sincronizar_cxp_factura(form.instance)
        RegistroCompra.objects.get_or_create(
            factura=form.instance,
            defaults={
                'proveedor': form.instance.proveedor,
                'periodo_mes': form.instance.fecha_emision.month,
                'periodo_anio': form.instance.fecha_emision.year,
                'neto': form.instance.neto,
                'iva_credito': form.instance.iva,
                'total': form.instance.total,
            }
        )
        _generar_asiento_automatico_factura(self.request, form.instance, reemplazar_borrador=False)
        messages.success(self.request, f'Factura {form.instance.numero} registrada exitosamente.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registrar Factura de Proveedor'
        if self.request.POST:
            ctx['detalle_formset'] = DetalleFormSet(self.request.POST)
        else:
            ctx['detalle_formset'] = DetalleFormSet()
        return ctx


class FacturaRecibidaUpdateView(GestionMixin, UpdateView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_form.html'
    fields = ['numero', 'fecha_emision', 'fecha_vencimiento', 'proveedor', 'proyecto', 'pago_por_trabajador', 'neto', 'exento', 'iva', 'total', 'estado', 'observaciones']
    success_url = reverse_lazy('proveedores:factura_list')

    def form_valid(self, form):
        formset = DetalleFormSet(self.request.POST, instance=self.object)
        if not formset.is_valid():
            return self.form_invalid(form)
        response = super().form_valid(form)
        formset.save()
        _sincronizar_cxp_factura(self.object)
        _generar_asiento_automatico_factura(self.request, self.object, reemplazar_borrador=True)
        messages.success(self.request, 'Factura actualizada.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Factura {self.object.numero}'
        if self.request.POST:
            ctx['detalle_formset'] = DetalleFormSet(self.request.POST, instance=self.object)
        else:
            ctx['detalle_formset'] = DetalleFormSet(instance=self.object)
        return ctx


class FacturaRecibidaDetailView(GestionMixin, DetailView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_detail.html'
    context_object_name = 'factura'


class CuentaPorPagarListView(GestionMixin, ListView):
    model = CuentaPorPagar
    template_name = 'admin/proveedores/cxp_list.html'
    context_object_name = 'cuentas'
    paginate_by = 25

    def get_queryset(self):
        return CuentaPorPagar.objects.select_related(
            'factura__proveedor', 'factura__pago_por_trabajador', 'rendicion__trabajador'
        ).order_by('fecha_vencimiento')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Cuentas por Pagar'
        return ctx


class CxPPagarView(GestionMixin, View):
    template_name = 'admin/proveedores/cxp_pagar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoForm(forms.Form):
            fecha_pago = forms.DateField(
            input_formats=['%Y-%m-%d'],
            widget=forms.DateInput(
                format='%Y-%m-%d',
                attrs={
                    'type': 'date',
                    'class': 'form-control'
                }
            ),
            label='Fecha de pago',
            )
            monto_pagado = forms.DecimalField(
                max_digits=15, decimal_places=2,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
                label='Monto pagado',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de pago',
                help_text='El egreso se registrará en esta cuenta.',
            )
            medio_pago = forms.ChoiceField(
                choices=[('', '— Seleccione —')] + CuentaPorPagar.MEDIO_PAGO_CHOICES,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Medio de pago',
            )
            numero_documento = forms.CharField(
                required=False, max_length=100,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° cheque, folio transferencia…'}),
                label='N° Documento / Referencia',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoForm(data=data, initial=initial)

    def get(self, request, pk):
        from django.shortcuts import render
        cxp = get_object_or_404(CuentaPorPagar, pk=pk)
        if cxp.estado == 'pagada':
            messages.info(request, 'Esta cuenta ya fue pagada.')
            return redirect('proveedores:cxp_list')
        form = self._build_form(initial={
            'fecha_pago': timezone.localdate(),
            'monto_pagado': cxp.saldo_pendiente,
        })
        return render(request, self.template_name, {'cxp': cxp, 'form': form})

    def post(self, request, pk):
        from django.shortcuts import render
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_movimiento_bancario

        cxp = get_object_or_404(CuentaPorPagar, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'cxp': cxp, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Actualizar CxP
        cxp.fecha_pago = d['fecha_pago']
        cxp.monto_pagado = d['monto_pagado']
        cxp.medio_pago = d['medio_pago']
        cxp.numero_documento = d['numero_documento']
        cxp.notas = d['notas']
        cxp.estado = 'pagada'
        cxp.save()

        # 2. Actualizar factura o rendición según corresponda
        if cxp.factura:
            cxp.factura.estado = 'pagada'
            cxp.factura.save()
        elif cxp.rendicion:
            cxp.rendicion.estado = 'pagada'
            cxp.rendicion.save()

        # 3. Crear MovimientoBancario (egreso)
        if cxp.factura:
            if cxp.factura.pago_por_trabajador:
                descripcion_mov = (
                    f'Reembolso factura {cxp.factura.numero} - '
                    f'{cxp.factura.pago_por_trabajador.nombre_completo}'
                )
            else:
                descripcion_mov = f'Pago {cxp.factura.numero} - {cxp.factura.proveedor.razon_social}'
        else:
            descripcion_mov = f'Reembolso rendición #{cxp.rendicion.id} - {cxp.rendicion.trabajador.nombre_completo}'
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='egreso',
            monto=d['monto_pagado'],
            descripcion=descripcion_mov,
            cuenta_contable=None,   # se intentará la cuenta CxP a continuación
            documento=d['numero_documento'],
        )

        # Asignar cuenta_contable del movimiento = cuenta CxP de ConfiguracionContable
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if config and config.cuenta_cxp:
                movimiento.cuenta_contable = config.cuenta_cxp
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # 4. Generar asiento contable borrador
        asiento = generar_asiento_movimiento_bancario(movimiento, usuario=request.user)

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
                'Verifique que la cuenta bancaria y la Config. Contable tengan cuentas asignadas.'
            )

        return redirect('proveedores:cxp_list')


class GenerarAsientoFacturaRecibidaView(GestionMixin, View):
    def post(self, request, pk):
        from apps.contabilidad.utils import generar_asiento_factura_recibida, get_config
        factura = get_object_or_404(FacturaRecibida, pk=pk)
        asiento_activo = factura.asientos.exclude(estado='anulado').first()
        if asiento_activo:
            messages.info(request, f'Esta factura ya tiene un asiento: {asiento_activo.numero}.')
            return redirect('contabilidad:asiento_detail', pk=asiento_activo.pk)
        if not get_config():
            messages.warning(request, 'Configure primero las cuentas contables antes de generar asientos.')
            return redirect('contabilidad:configuracion')
        asiento = generar_asiento_factura_recibida(factura, usuario=request.user)
        if asiento:
            messages.success(request, f'Asiento {asiento.numero} generado en borrador.')
            return redirect('contabilidad:asiento_detail', pk=asiento.pk)
        messages.error(request, 'No se pudo generar el asiento. Verifique la configuración contable.')
        return redirect('proveedores:factura_detail', pk=factura.pk)


class AnticipoListView(GestionMixin, ListView):
    model = Anticipo
    template_name = 'admin/proveedores/anticipo_list.html'
    context_object_name = 'anticipos'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Anticipos a Proveedores'
        return ctx


class AnticipoCreateView(GestionMixin, CreateView):
    model = Anticipo
    template_name = 'admin/proveedores/anticipo_form.html'
    fields = ['proveedor', 'fecha', 'monto', 'descripcion', 'proyecto', 'estado']
    success_url = reverse_lazy('proveedores:anticipo_list')

    def form_valid(self, form):
        messages.success(self.request, 'Anticipo registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Anticipo a Proveedor'
        return ctx

class RendicionGastosListView(GestionMixin, ListView):
    model = RendicionGastos
    template_name = 'admin/proveedores/rendicion_list.html'
    context_object_name = 'rendiciones'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Rendiciones de Gastos'
        return ctx


class DetalleRendicionForm(ModelForm):
    class Meta:
        model = DetalleRendicion    
        fields = ['fecha_gasto', 'n_boleta_factura', 'descripcion', 'monto', 'centro_costo', 'cuenta_contable' , 'proveedor']
        widgets = { 
            'fecha_gasto': TextInput(attrs={'type': 'date', 'class': 'form-control form-control-sm'}),
            'n_boleta_factura': TextInput(attrs={'class': 'form-control form-control-sm'}),
            'descripcion': TextInput(attrs={'class': 'form-control form-control-sm'}),
            'monto': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1'}),
            'centro_costo': Select(attrs={'class': 'form-select form-select-sm'}),
            'cuenta_contable': Select(attrs={'class': 'form-select form-select-sm'}),
            'proveedor': Select(attrs={'class': 'form-select form-select-sm'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrar cuentas contables para mostrar solo las de tipo 'gasto' o 'costo' y de nivel 4
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(
            tipo__in=['gasto', 'costo'],
            nivel=4
        )


DetalleRendicionFormSet = inlineformset_factory(
    RendicionGastos, DetalleRendicion,
    form=DetalleRendicionForm,
    extra=0, can_delete=True,
)


class RendicionGastosCreateView(GestionMixin, CreateView):
    model = RendicionGastos
    template_name = 'admin/proveedores/rendicion_form.html'
    fields = ['trabajador', 'proyecto', 'fecha', 'motivo_del_gasto']
    success_url = reverse_lazy('proveedores:rendicion_list')

    def form_valid(self, form):
        formset = DetalleRendicionFormSet(self.request.POST)
        if not formset.is_valid():
            return self.form_invalid(form)
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()
        # Creamos la cuenta por pagar usando los detalles ya guardados
        total_rendicion = self.object.detalles.aggregate(t=Sum('monto'))['t'] or 0
        if total_rendicion > 0:
            CuentaPorPagar.objects.create(
                rendicion=self.object,
                fecha_vencimiento=_viernes_proxima_semana(self.object.fecha),
                monto=total_rendicion,
            )

        messages.success(self.request, 'Rendición de gastos creada.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Rendición de Gastos'
        if self.request.POST:
            ctx['detalle_formset'] = DetalleRendicionFormSet(self.request.POST)
        else:
            ctx['detalle_formset'] = DetalleRendicionFormSet()
        return ctx

# Transiciones válidas de estado para RendicionGastos
_TRANSICIONES_RENDICION = {
    'borrador':  ['enviado'],
    'enviado':   ['aprobado', 'rechazado'],
    'rechazado': ['borrador'],
    'aprobado':  [],
}


class RendicionGastosDetailView(GestionMixin, DetailView):
    model = RendicionGastos
    template_name = 'admin/proveedores/rendicion_detail.html'
    context_object_name = 'rendicion'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['detalles'] = self.object.detalles.select_related(
            'centro_costo', 'cuenta_contable', 'proveedor'
        ).all()
        ctx['total'] = self.object.detalles.aggregate(t=Sum('monto'))['t'] or 0
        ctx['cuentas_pagar'] = self.object.cuentas_pagar.all()
        ctx['asiento'] = self.object.asientos.exclude(estado='anulado').first()
        ctx['transiciones'] = _TRANSICIONES_RENDICION.get(self.object.estado, [])
        return ctx

    def post(self, request, pk):
        rendicion = get_object_or_404(RendicionGastos, pk=pk)
        nuevo_estado = request.POST.get('estado')
        transiciones_validas = _TRANSICIONES_RENDICION.get(rendicion.estado, [])
        if nuevo_estado in transiciones_validas:
            rendicion.estado = nuevo_estado
            rendicion.save(update_fields=['estado'])
            labels = dict(RendicionGastos.ESTADO_CHOICES)
            messages.success(request, f'Estado actualizado a "{labels[nuevo_estado]}".') 
        else:
            messages.error(request, f'Transición de estado no permitida.')
        return redirect('proveedores:rendicion_detail', pk=rendicion.pk)


class GenerarAsientoRendicionView(GestionMixin, View):
    def post(self, request, pk):
        from apps.contabilidad.utils import generar_asiento_rendicion_gastos_recibida, get_config
        rendicion = get_object_or_404(RendicionGastos, pk=pk)
        asiento_activo = rendicion.asientos.exclude(estado='anulado').first()
        if asiento_activo:
            messages.info(request, f'Esta rendición ya tiene un asiento: {asiento_activo.numero}.')
            return redirect('contabilidad:asiento_detail', pk=asiento_activo.pk)
        if not get_config():
            messages.warning(request, 'Configure primero las cuentas contables antes de generar asientos.')
            return redirect('contabilidad:configuracion')
        asiento = generar_asiento_rendicion_gastos_recibida(rendicion, usuario=request.user)
        if asiento:
            messages.success(request, f'Asiento {asiento.numero} generado en borrador.')
            return redirect('contabilidad:asiento_detail', pk=asiento.pk)
        messages.error(request, 'No se pudo generar el asiento. Verifique la configuración contable.')
        return redirect('proveedores:rendicion_detail', pk=rendicion.pk)