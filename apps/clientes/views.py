from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.forms import inlineformset_factory, ModelForm, TextInput, NumberInput, Select, Textarea, DateInput
from apps.core.mixins import GestionMixin, AppPermisoMixin
from django.db import transaction

class ClientesMixin(AppPermisoMixin):
    app_name = 'clientes'

from apps.contabilidad.utils import generar_asiento_factura_emitida
from apps.tributario.models import RegistroVenta
from .models import Cliente, FacturaEmitida, CuentaPorCobrar, DetalleFacturaEmitida


def _generar_asiento_automatico_factura_emitida(request, factura, reemplazar_borrador=False):
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
    asiento = generar_asiento_factura_emitida(factura, usuario=request.user)
    if asiento:
        messages.info(request, f'Se generó automáticamente el asiento {asiento.numero}.')
    else:
        messages.warning(
            request,
            'La factura se guardó, pero no se pudo generar el asiento automático. Revise la configuración contable.'
        )
    return asiento

def _sincronizar_cxc_factura(factura):
    """Crea, actualiza o elimina CxC de factura emitida cuando corresponde."""

    requiere_cxc = bool(factura.fecha_vencimiento)

    if not requiere_cxc:
        CuentaPorCobrar.objects.filter(
            factura=factura,
            estado='pendiente',
            monto_pagado=0
        ).delete()
        return None

    cxc, created = CuentaPorCobrar.objects.get_or_create(
        factura=factura,
        defaults={
            'fecha_vencimiento': factura.fecha_vencimiento,
            'monto': factura.total,
            'estado': 'pendiente',
        }
    )

    if not created:
        cxc.fecha_vencimiento = factura.fecha_vencimiento
        cxc.monto = factura.total

        if cxc.monto_pagado >= factura.total:
            cxc.estado = 'pagada'
        else:
            cxc.estado = 'pendiente'

        cxc.save(update_fields=[
            'fecha_vencimiento',
            'monto',
            'estado',
        ])

    return cxc

class FacturaEmitidaForm(ModelForm):
    class Meta:
        model = FacturaEmitida
        fields = ['numero', 'fecha_emision', 'fecha_vencimiento', 'cliente', 'proyecto',
                  'neto', 'estado', 'observaciones']
        widgets = {
            'numero':           TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'fecha_emision':    DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_vencimiento': DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'cliente':          Select(attrs={'class': 'form-select'}),
            'proyecto':         Select(attrs={'class': 'form-select'}),
            'neto':             NumberInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'estado':           Select(attrs={'class': 'form-select'}),
            'observaciones':    Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class DetalleEmitidaForm(ModelForm):
    class Meta:
        model = DetalleFacturaEmitida
        fields = ['descripcion', 'cantidad', 'precio_unitario', 'cuenta_contable', 'centro_costo']
        widgets = {
            'descripcion':     TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cantidad':        NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0', 'autocomplete': 'off'}),
            'precio_unitario': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0', 'autocomplete': 'off'}),
            'cuenta_contable': Select(attrs={'class': 'form-select form-select-sm'}),
            'centro_costo':    Select(attrs={'class': 'form-select form-select-sm'}),
        }

    # Editar el método __init__ para seleccionar solo cuentas de tipo 'ingreso'
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(tipo='ingreso', nivel=4)


DetalleEmitidaFormSet = inlineformset_factory(
    FacturaEmitida, DetalleFacturaEmitida,
    form=DetalleEmitidaForm,
    extra=0, can_delete=True,
)


class ClienteListView(ClientesMixin, ListView):
    model = Cliente
    template_name = 'admin/clientes/cliente_list.html'
    context_object_name = 'clientes'
    paginate_by = 20

    def get_queryset(self):
        qs = Cliente.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(razon_social__icontains=q) | qs.filter(rut__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Clientes'
        return ctx


class ClienteCreateView(ClientesMixin, CreateView):
    model = Cliente
    template_name = 'admin/clientes/cliente_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'notas', 'activo']
    success_url = reverse_lazy('clientes:cliente_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente registrado exitosamente.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Cliente'
        return ctx


class ClienteUpdateView(ClientesMixin, UpdateView):
    model = Cliente
    template_name = 'admin/clientes/cliente_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'activo', 'notas']
    success_url = reverse_lazy('clientes:cliente_list')

    def form_valid(self, form):
        messages.success(self.request, 'Cliente actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Cliente: {self.object.razon_social}'
        return ctx


class ClienteDetailView(ClientesMixin, DetailView):
    model = Cliente
    template_name = 'admin/clientes/cliente_detail.html'
    context_object_name = 'cliente'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['facturas'] = self.object.facturas.all().order_by('-fecha_emision')[:10]
        return ctx


class FacturaEmitidaListView(ClientesMixin, ListView):
    model = FacturaEmitida
    template_name = 'admin/clientes/factura_list.html'
    context_object_name = 'facturas'
    paginate_by = 25

    def get_queryset(self):
        qs = FacturaEmitida.objects.select_related('cliente', 'proyecto').order_by('-fecha_emision')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(numero__icontains=q) | qs.filter(cliente__razon_social__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estados'] = FacturaEmitida.ESTADO_CHOICES
        ctx['titulo'] = 'Facturas Emitidas'
        return ctx


class FacturaEmitidaCreateView(ClientesMixin, CreateView):
    model = FacturaEmitida
    template_name = 'admin/clientes/factura_form.html'
    form_class = FacturaEmitidaForm
    success_url = reverse_lazy('clientes:factura_list')

    def form_valid(self, form):
        formset = DetalleEmitidaFormSet(self.request.POST, instance=form.instance)
        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()

        _sincronizar_cxc_factura(form.instance)

        RegistroVenta.objects.get_or_create(
            factura=form.instance,
            defaults={
                'cliente': form.instance.cliente,
                'periodo_mes': form.instance.fecha_emision.month,
                'periodo_anio': form.instance.fecha_emision.year,
                'neto': form.instance.neto,
                'iva_debito': form.instance.iva,
                'total': form.instance.total,
            }
        )
        _generar_asiento_automatico_factura_emitida(self.request, form.instance, reemplazar_borrador=False)
        messages.success(self.request, f'Factura {form.instance.numero} creada exitosamente.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Factura'
        if 'detalle_formset' not in ctx:
            if self.request.POST:
                ctx['detalle_formset'] = DetalleEmitidaFormSet(self.request.POST)
            else:
                ctx['detalle_formset'] = DetalleEmitidaFormSet()
        return ctx


class FacturaEmitidaUpdateView(ClientesMixin, UpdateView):
    model = FacturaEmitida
    template_name = 'admin/clientes/factura_form.html'
    form_class = FacturaEmitidaForm
    success_url = reverse_lazy('clientes:factura_list')

    def dispatch(self, request, *args, **kwargs):
        factura = self.get_object()
        if factura.estado in ('pagada', 'anulada'):
            messages.error(
                request,
                f'No se puede editar la factura porque está en estado "{factura.get_estado_display()}".'
            )
            return redirect('clientes:factura_detail', pk=factura.pk)
        if factura.asientos.filter(estado='confirmado').exists():
            messages.error(
                request,
                'No se puede editar la factura porque tiene un asiento contable confirmado.'
            )
            return redirect('clientes:factura_detail', pk=factura.pk)
        return super().dispatch(request, *args, **kwargs)


    def form_valid(self, form):
        formset = DetalleEmitidaFormSet(self.request.POST, instance=self.object)

        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        with transaction.atomic():
            response = super().form_valid(form)
            formset.save()

            factura = self.object

            _sincronizar_cxc_factura(factura)

            RegistroVenta.objects.update_or_create(
                factura=factura,
                defaults={
                    'cliente': factura.cliente,
                    'periodo_mes': factura.fecha_emision.month,
                    'periodo_anio': factura.fecha_emision.year,
                    'neto': factura.neto,
                    'iva_debito': factura.iva,
                    'total': factura.total,
                }
            )

            _generar_asiento_automatico_factura_emitida(
                self.request,
                factura,
                reemplazar_borrador=True
            )

        messages.success(self.request, 'Factura actualizada.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Factura {self.object.numero}'
        if 'detalle_formset' not in ctx:
            if self.request.POST:
                ctx['detalle_formset'] = DetalleEmitidaFormSet(self.request.POST, instance=self.object)
            else:
                ctx['detalle_formset'] = DetalleEmitidaFormSet(instance=self.object)
        return ctx


class FacturaEmitidaDetailView(ClientesMixin, DetailView):
    model = FacturaEmitida
    template_name = 'admin/clientes/factura_detail.html'
    context_object_name = 'factura'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['asiento'] = self.object.asientos.exclude(estado='anulado').first()
        return ctx


class FacturaEmitidaDeleteView(ClientesMixin, DeleteView):
    model = FacturaEmitida
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('clientes:factura_list')

    def dispatch(self, request, *args, **kwargs):
        factura = self.get_object()
        if factura.estado in ('pagada', 'anulada'):
            messages.error(
                request,
                f'No se puede eliminar la factura porque está en estado "{factura.get_estado_display()}".'
            )
            return redirect('clientes:factura_detail', pk=factura.pk)
        if factura.asientos.filter(estado='confirmado').exists():
            messages.error(
                request,
                'No se puede eliminar la factura porque tiene un asiento contable confirmado.'
            )
            return redirect('clientes:factura_detail', pk=factura.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse('clientes:factura_detail', kwargs={'pk': self.object.pk})
        return ctx

    def form_valid(self, form):
        factura = self.object
        factura.asientos.filter(estado='borrador').delete()
        messages.success(self.request, f'Factura {factura.numero} eliminada.')
        return super().form_valid(form)


class CuentaPorCobrarListView(ClientesMixin, ListView):
    model = CuentaPorCobrar
    template_name = 'admin/clientes/cxc_list.html'
    context_object_name = 'cuentas'
    paginate_by = 25

    def get_queryset(self):
        return CuentaPorCobrar.objects.select_related(
            'factura__cliente'
        ).order_by('fecha_vencimiento')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Cuentas por Cobrar'
        return ctx


class CxCPagarView(ClientesMixin, View):
    template_name = 'admin/clientes/cxc_cobrar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class CobroForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de cobro',
            )
            monto_cobrado = forms.DecimalField(
                max_digits=15, decimal_places=2,
                widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
                label='Monto cobrado',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de depósito',
                help_text='El ingreso se registrará en esta cuenta.',
            )
            medio_cobro = forms.ChoiceField(
                choices=[('', '— Seleccione —')] + CuentaPorCobrar.MEDIO_COBRO_CHOICES,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Medio de cobro',
            )
            numero_documento = forms.CharField(
                required=False, max_length=100,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° transferencia, cheque, depósito…'}),
                label='N° Documento / Referencia',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return CobroForm(data=data, initial=initial)

    def get(self, request, pk):
        cxc = get_object_or_404(CuentaPorCobrar, pk=pk)
        if cxc.estado == 'pagada':
            messages.info(request, 'Esta cuenta ya fue cobrada.')
            return redirect('clientes:cxc_list')
        from django.shortcuts import render
        form = self._build_form(initial={
            'fecha_pago': timezone.now().date(),
            'monto_cobrado': cxc.saldo_pendiente,
        })
        return render(request, self.template_name, {'cxc': cxc, 'form': form})

    def post(self, request, pk):
        from django.shortcuts import render
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_movimiento_bancario

        cxc = get_object_or_404(CuentaPorCobrar, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'cxc': cxc, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Actualizar CxC
        cxc.fecha_pago = d['fecha_pago']
        cxc.monto_pagado = d['monto_cobrado']
        cxc.medio_cobro = d['medio_cobro']
        cxc.numero_documento = d['numero_documento']
        cxc.notas = d['notas']
        cxc.estado = 'pagada'
        cxc.save()

        # 2. Actualizar factura
        cxc.factura.estado = 'pagada'
        cxc.factura.save()

        # 3. Crear MovimientoBancario (ingreso)
        descripcion_mov = f'Cobro {cxc.factura.numero} - {cxc.factura.cliente.razon_social}'
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='ingreso',
            monto=d['monto_cobrado'],
            descripcion=descripcion_mov,
            cuenta_contable=None,
            documento=d['numero_documento'][:50],
        )

        # Asignar cuenta_contable = cuenta CxC de ConfiguracionContable
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if config and config.cuenta_cxc:
                movimiento.cuenta_contable = config.cuenta_cxc
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # Vincular movimiento a la CxC
        cxc.movimiento_pago = movimiento
        cxc.save(update_fields=['movimiento_pago'])

        # 4. Generar asiento contable borrador
        asiento = generar_asiento_movimiento_bancario(movimiento, usuario=request.user)

        if asiento:
            messages.success(
                request,
                f'Cobro registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'Cobro registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable automáticamente. '
                'Verifique que la cuenta bancaria y la Config. Contable tengan cuentas asignadas.'
            )

        return redirect('clientes:cxc_list')


class AnularPagoCxCView(ClientesMixin, View):
    """Revierte un cobro: elimina el movimiento bancario y su asiento (borrador),
    y deja la CxC y la factura en estado pendiente."""

    def post(self, request, pk):
        from django.db import transaction
        cxc = get_object_or_404(CuentaPorCobrar, pk=pk)

        if cxc.estado != 'pagada':
            messages.error(request, 'Esta cuenta no está en estado pagada.')
            return redirect('clientes:cxc_list')

        movimiento = cxc.movimiento_pago
        if movimiento:
            asiento_confirmado = movimiento.asientos.filter(estado='confirmado').exists()
            if asiento_confirmado:
                messages.error(
                    request,
                    'No se puede anular el cobro porque el asiento contable del movimiento está confirmado. '
                    'Anúle el asiento primero.'
                )
                return redirect('clientes:cxc_list')

        with transaction.atomic():
            if movimiento:
                movimiento.asientos.filter(estado='borrador').delete()
                movimiento.delete()

            # Revertir CxC
            cxc.estado = 'pendiente'
            cxc.monto_pagado = 0
            cxc.fecha_pago = None
            cxc.medio_cobro = ''
            cxc.numero_documento = ''
            cxc.notas = ''
            cxc.movimiento_pago = None
            cxc.save()

            # Revertir factura
            cxc.factura.estado = 'pendiente'
            cxc.factura.save(update_fields=['estado'])

        messages.success(request, 'Cobro anulado correctamente. La cuenta quedó pendiente de cobro.')
        return redirect('clientes:cxc_list')


class GenerarAsientoFacturaEmitidaView(ClientesMixin, View):
    def post(self, request, pk):
        from apps.contabilidad.utils import generar_asiento_factura_emitida, get_config
        factura = get_object_or_404(FacturaEmitida, pk=pk)
        # Check duplicate
        asiento_activo = factura.asientos.exclude(estado='anulado').first()
        if asiento_activo:
            messages.info(request, f'Esta factura ya tiene un asiento: {asiento_activo.numero}.')
            return redirect('contabilidad:asiento_detail', pk=asiento_activo.pk)
        if not get_config():
            messages.warning(request, 'Configure primero las cuentas contables antes de generar asientos.')
            return redirect('contabilidad:configuracion')
        asiento = generar_asiento_factura_emitida(factura, usuario=request.user)
        if asiento:
            messages.success(request, f'Asiento {asiento.numero} generado en borrador.')
            return redirect('contabilidad:asiento_detail', pk=asiento.pk)
        messages.error(request, 'No se pudo generar el asiento. Verifique la configuración contable.')
        return redirect('clientes:factura_detail', pk=factura.pk)
