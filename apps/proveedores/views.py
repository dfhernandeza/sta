import logging
from decimal import Decimal, ROUND_HALF_UP

from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, View
from django.urls import reverse_lazy, reverse
from django.contrib import messages

logger = logging.getLogger(__name__)
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from django.forms import CheckboxInput, inlineformset_factory, ModelForm, TextInput, Select, NumberInput
from apps.contabilidad.utils import generar_asiento_factura_recibida, generar_asiento_nota_credito_recibida
from apps.core.mixins import GestionMixin, AppPermisoMixin
from django.db import transaction


class ProveedoresMixin(AppPermisoMixin):
    app_name = 'proveedores'


from apps.web import forms
from .models import (
    Proveedor, FacturaRecibida, DetalleFacturaRecibida,
    NotaCreditoRecibida, DetalleNotaCreditoRecibida,
    CuentaPorPagar, Anticipo,
)
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


def _generar_asiento_automatico_nota_credito(request, nota_credito, reemplazar_borrador=False):
    """Genera asiento automático para notas de crédito evitando duplicados."""
    asiento_activo = nota_credito.asientos.exclude(estado='anulado').first()

    if asiento_activo:
        if asiento_activo.estado == 'confirmado':
            messages.warning(
                request,
                f'No se regeneró el asiento automático porque la nota de crédito ya tiene un asiento confirmado ({asiento_activo.numero}).'
            )
            return asiento_activo
        if asiento_activo.estado == 'borrador' and reemplazar_borrador:
            asiento_activo.delete()
        elif asiento_activo.estado == 'borrador':
            return asiento_activo

    asiento = generar_asiento_nota_credito_recibida(nota_credito, usuario=request.user)
    if asiento:
        messages.info(request, f'Se generó automáticamente el asiento {asiento.numero}.')
    else:
        messages.warning(
            request,
            'La nota de crédito se guardó, pero no se pudo generar el asiento automático. Revise la configuración contable.'
        )
    return asiento


def _total_notas_credito_activas(factura):
    return factura.notas_credito.exclude(estado='anulada').aggregate(
        total=Sum('total')
    )['total'] or Decimal('0')


def _calcular_totales_desde_formset(formset):
    neto = Decimal('0')
    exento = Decimal('0')

    for detalle_form in formset.forms:
        if not detalle_form.cleaned_data or detalle_form.cleaned_data.get('DELETE'):
            continue
        cantidad = detalle_form.cleaned_data.get('cantidad') or Decimal('0')
        precio = detalle_form.cleaned_data.get('precio_unitario') or Decimal('0')
        subtotal = cantidad * precio
        if detalle_form.cleaned_data.get('exento_iva'):
            exento += subtotal
        else:
            neto += subtotal

    neto = neto.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    exento = exento.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    iva = (neto * Decimal('0.19')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total = neto + exento + iva

    return {
        'neto': neto,
        'exento': exento,
        'iva': iva,
        'total': total,
    }


def _sincronizar_cxp_factura(factura):
    """Crea, actualiza o elimina CxP de factura cuando corresponde."""

    requiere_cxp = bool(
        factura.pago_por_trabajador_id or factura.fecha_vencimiento
    )

    if not requiere_cxp:
        CuentaPorPagar.objects.filter(
            factura=factura,
            estado='pendiente',
            monto_pagado=0
        ).delete()
        return None

    fecha_venc = factura.fecha_vencimiento or factura.fecha_emision
    monto_cxp = max(factura.total - _total_notas_credito_activas(factura), Decimal('0'))

    cxp, created = CuentaPorPagar.objects.get_or_create(
        factura=factura,
        defaults={
            'fecha_vencimiento': fecha_venc,
            'monto': monto_cxp,
            'estado': 'pagada' if monto_cxp == 0 else 'pendiente',
        }
    )

    if not created:
        cxp.fecha_vencimiento = fecha_venc
        cxp.monto = monto_cxp

        if cxp.monto_pagado >= monto_cxp:
            cxp.estado = 'pagada'
        else:
            cxp.estado = 'pendiente'

        cxp.save(update_fields=[
            'fecha_vencimiento',
            'monto',
            'estado',
        ])

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
            tipo__in=['gasto', 'costo', 'activo'],  # Incluimos 'activo' para permitir cuentas de activo si es necesario
            nivel=4
        )


DetalleFormSet = inlineformset_factory(
    FacturaRecibida, DetalleFacturaRecibida,
    form=DetalleFacturaForm,
    extra=0, can_delete=True,
)


class DetalleNotaCreditoForm(ModelForm):
    class Meta:
        model = DetalleNotaCreditoRecibida
        fields = ['descripcion', 'cuenta_contable', 'cantidad', 'precio_unitario', 'centro_costo', 'exento_iva']
        widgets = {
            'descripcion': TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cuenta_contable': Select(attrs={'class': 'form-select form-select-sm'}),
            'cantidad': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0'}),
            'precio_unitario': NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '1', 'min': '0'}),
            'centro_costo': Select(attrs={'class': 'form-select form-select-sm'}),
            'exento_iva': CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(
            tipo__in=['gasto', 'costo', 'activo'],
            nivel=4
        )


DetalleNotaCreditoFormSet = inlineformset_factory(
    NotaCreditoRecibida, DetalleNotaCreditoRecibida,
    form=DetalleNotaCreditoForm,
    extra=0, can_delete=True,
)


def _detalle_nota_credito_formset_factory(extra=0):
    return inlineformset_factory(
        NotaCreditoRecibida, DetalleNotaCreditoRecibida,
        form=DetalleNotaCreditoForm,
        extra=extra, can_delete=True,
    )


def _initial_detalles_nota_credito_desde_factura(factura):
    return [
        {
            'descripcion': detalle.descripcion,
            'cuenta_contable': detalle.cuenta_contable_id,
            'cantidad': detalle.cantidad,
            'precio_unitario': detalle.precio_unitario,
            'centro_costo': detalle.centro_costo_id,
            'exento_iva': detalle.exento_iva,
        }
        for detalle in factura.detalles.select_related('cuenta_contable', 'centro_costo').all()
    ]




class ProveedorListView(ProveedoresMixin, ListView):
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


class ProveedorCreateView(ProveedoresMixin, CreateView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'banco', 'tipo_cuenta', 'numero_cuenta', 'notas', 'activo']
    success_url = reverse_lazy('proveedores:proveedor_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Proveedor creado: %s (RUT: %s) por %s', self.object.razon_social, self.object.rut, self.request.user)
        messages.success(self.request, 'Proveedor registrado exitosamente.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Proveedor'
        return ctx


class ProveedorUpdateView(ProveedoresMixin, UpdateView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_form.html'
    fields = ['rut', 'razon_social', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email', 'contacto', 'banco', 'tipo_cuenta', 'numero_cuenta', 'activo', 'notas']
    success_url = reverse_lazy('proveedores:proveedor_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        logger.info('Proveedor actualizado: %s (pk=%s) por %s', self.object.razon_social, self.object.pk, self.request.user)
        messages.success(self.request, 'Proveedor actualizado.')
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Proveedor: {self.object.razon_social}'
        return ctx


class ProveedorDetailView(ProveedoresMixin, DetailView):
    model = Proveedor
    template_name = 'admin/proveedores/proveedor_detail.html'
    context_object_name = 'proveedor'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['facturas'] = self.object.facturas.all().order_by('-fecha_emision')[:10]
        return ctx


class FacturaRecibidaListView(ProveedoresMixin, ListView):
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


class FacturaRecibidaCreateView(ProveedoresMixin, CreateView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_form.html'
    fields = ['numero', 'fecha_emision', 'fecha_vencimiento', 'proveedor', 'proyecto', 'pago_por_trabajador', 'neto', 'exento', 'iva', 'total', 'estado', 'observaciones']
    success_url = reverse_lazy('proveedores:factura_list')

    def get_form(self, form_class=None):
        from django.forms import DateInput, HiddenInput
        form = super().get_form(form_class)
        for fname in ['fecha_emision', 'fecha_vencimiento']:
            if fname in form.fields:
                form.fields[fname].widget = DateInput(attrs={'class': 'form-control'}, format='%Y-%m-%d')
        for fname in ['neto', 'exento', 'iva', 'total']:
            if fname in form.fields:
                form.fields[fname].required = False
                form.fields[fname].widget = HiddenInput()
        return form

    def form_valid(self, form):
        formset = DetalleFormSet(self.request.POST, instance=form.instance)
        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        totales = _calcular_totales_desde_formset(formset)
        if totales['total'] <= 0:
            form.add_error('total', 'La factura debe tener al menos una línea y un total mayor que cero.')
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        for campo, valor in totales.items():
            setattr(form.instance, campo, valor)

        self.object = form.save()
        formset.instance = self.object
        formset.save()
        _sincronizar_cxp_factura(self.object)
        RegistroCompra.objects.get_or_create(
            factura=self.object,
            tipo_documento='factura',
            defaults={
                'proveedor': self.object.proveedor,
                'periodo_mes': self.object.fecha_emision.month,
                'periodo_anio': self.object.fecha_emision.year,
                'neto': self.object.neto,
                'iva_credito': self.object.iva,
                'total': self.object.total,
            }
        )
        _generar_asiento_automatico_factura(self.request, self.object, reemplazar_borrador=False)
        logger.info('Factura recibida creada: %s (proveedor: %s) por %s', self.object.numero, self.object.proveedor, self.request.user)
        messages.success(self.request, f'Factura {self.object.numero} registrada exitosamente.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registrar Factura de Proveedor'
        if 'detalle_formset' not in ctx:
            if self.request.POST:
                ctx['detalle_formset'] = DetalleFormSet(self.request.POST)
            else:
                ctx['detalle_formset'] = DetalleFormSet()
        return ctx


class FacturaRecibidaUpdateView(ProveedoresMixin, UpdateView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_form.html'
    fields = ['numero', 'fecha_emision', 'fecha_vencimiento', 'proveedor', 'proyecto', 'pago_por_trabajador', 'neto', 'exento', 'iva', 'total', 'estado', 'observaciones']
    success_url = reverse_lazy('proveedores:factura_list')

    def dispatch(self, request, *args, **kwargs):
        factura = self.get_object()
        if factura.estado in ('pagada', 'anulada'):
            messages.error(
                request,
                f'No se puede editar la factura porque está en estado "{factura.get_estado_display()}".'
            )
            return redirect('proveedores:factura_detail', pk=factura.pk)
        if factura.asientos.filter(estado='confirmado').exists():
            messages.error(
                request,
                'No se puede editar la factura porque tiene un asiento contable confirmado.'
            )
            return redirect('proveedores:factura_detail', pk=factura.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        from django.forms import DateInput, HiddenInput
        form = super().get_form(form_class)
        for fname in ['fecha_emision', 'fecha_vencimiento']:
            if fname in form.fields:
                form.fields[fname].widget = DateInput(attrs={'class': 'form-control'}, format='%Y-%m-%d')
        for fname in ['neto', 'exento', 'iva', 'total']:
            if fname in form.fields:
                form.fields[fname].required = False
                form.fields[fname].widget = HiddenInput()
        return form

    def form_valid(self, form):
        formset = DetalleFormSet(self.request.POST, instance=self.object)

        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        with transaction.atomic():
            totales = _calcular_totales_desde_formset(formset)
            if totales['total'] <= 0:
                form.add_error('total', 'La factura debe tener al menos una línea y un total mayor que cero.')
                return self.render_to_response(
                    self.get_context_data(form=form, detalle_formset=formset)
                )

            for campo, valor in totales.items():
                setattr(form.instance, campo, valor)

            self.object = form.save()
            formset.save()

            factura = self.object

            # Sincronizar Cuenta por Pagar
            _sincronizar_cxp_factura(factura)

            # Actualizar Registro de Compra
            RegistroCompra.objects.update_or_create(
                factura=factura,
                tipo_documento='factura',
                defaults={
                    'proveedor': factura.proveedor,
                    'nota_credito': None,
                    'periodo_mes': factura.fecha_emision.month,
                    'periodo_anio': factura.fecha_emision.year,
                    'neto': factura.neto,
                    'iva_credito': factura.iva,
                    'total': factura.total,
                }
            )

            # Regenerar asiento automático
            _generar_asiento_automatico_factura(
                self.request,
                factura,
                reemplazar_borrador=True
            )

        logger.info(
            'Factura recibida actualizada: %s (pk=%s) por %s',
            self.object.numero,
            self.object.pk,
            self.request.user
        )

        messages.success(self.request, 'Factura actualizada.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Factura {self.object.numero}'
        if 'detalle_formset' not in ctx:
            if self.request.POST:
                ctx['detalle_formset'] = DetalleFormSet(self.request.POST, instance=self.object)
            else:
                ctx['detalle_formset'] = DetalleFormSet(instance=self.object)
        return ctx


class FacturaRecibidaDetailView(ProveedoresMixin, DetailView):
    model = FacturaRecibida
    template_name = 'admin/proveedores/factura_detail.html'
    context_object_name = 'factura'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['notas_credito'] = self.object.notas_credito.select_related('proveedor').order_by('-fecha_emision')
        ctx['total_notas_credito'] = _total_notas_credito_activas(self.object)
        return ctx


class NotaCreditoRecibidaCreateView(ProveedoresMixin, CreateView):
    model = NotaCreditoRecibida
    template_name = 'admin/proveedores/nota_credito_form.html'
    fields = ['numero', 'fecha_emision', 'neto', 'exento', 'iva', 'total', 'estado', 'observaciones']

    def dispatch(self, request, *args, **kwargs):
        self.factura = get_object_or_404(FacturaRecibida, pk=kwargs['pk'])
        if self.factura.estado == 'anulada':
            messages.error(request, 'No se puede crear una nota de crédito para una factura anulada.')
            return redirect('proveedores:factura_detail', pk=self.factura.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('proveedores:factura_detail', kwargs={'pk': self.factura.pk})

    def get_initial(self):
        initial = super().get_initial()
        initial.update({
            'fecha_emision': timezone.localdate(),
            'estado': 'aplicada',
        })
        return initial

    def get_form(self, form_class=None):
        from django.forms import DateInput, HiddenInput
        form = super().get_form(form_class)
        if 'fecha_emision' in form.fields:
            form.fields['fecha_emision'].widget = DateInput(attrs={'class': 'form-control'}, format='%Y-%m-%d')
        for fname in ['neto', 'exento', 'iva', 'total']:
            if fname in form.fields:
                form.fields[fname].required = False
                form.fields[fname].widget = HiddenInput()
        return form

    def form_valid(self, form):
        form.instance.factura = self.factura
        form.instance.proveedor = self.factura.proveedor
        formset = DetalleNotaCreditoFormSet(self.request.POST, instance=form.instance)

        if not formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        lineas_activas = [
            form_det for form_det in formset.forms
            if form_det.cleaned_data and not form_det.cleaned_data.get('DELETE')
        ]
        totales = _calcular_totales_desde_formset(formset)
        if not lineas_activas or totales['total'] <= 0:
            form.add_error('total', 'La nota de crédito debe tener al menos una línea y un total mayor que cero.')
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        total_existente = _total_notas_credito_activas(self.factura)
        if form.instance.estado != 'anulada' and total_existente + totales['total'] > self.factura.total:
            form.add_error(
                'total',
                'El total de notas de crédito activas no puede superar el total de la factura.'
            )
            return self.render_to_response(
                self.get_context_data(form=form, detalle_formset=formset)
            )

        for campo, valor in totales.items():
            setattr(form.instance, campo, valor)

        with transaction.atomic():
            self.object = form.save()
            formset.instance = self.object
            formset.save()

            if self.object.estado != 'anulada':
                RegistroCompra.objects.update_or_create(
                    nota_credito=self.object,
                    tipo_documento='nota_credito',
                    defaults={
                        'proveedor': self.object.proveedor,
                        'factura': None,
                        'periodo_mes': self.object.fecha_emision.month,
                        'periodo_anio': self.object.fecha_emision.year,
                        'neto': -self.object.neto,
                        'iva_credito': -self.object.iva,
                        'total': -self.object.total,
                    }
                )
                _sincronizar_cxp_factura(self.factura)
                _generar_asiento_automatico_nota_credito(
                    self.request,
                    self.object,
                    reemplazar_borrador=False
                )

        logger.info(
            'Nota de crédito recibida creada: %s (factura: %s, proveedor: %s) por %s',
            self.object.numero,
            self.factura.numero,
            self.object.proveedor,
            self.request.user
        )
        messages.success(self.request, f'Nota de crédito {self.object.numero} registrada exitosamente.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Nueva Nota de Crédito para Factura {self.factura.numero}'
        ctx['factura'] = self.factura
        ctx['saldo_disponible_nota_credito'] = self.factura.total - _total_notas_credito_activas(self.factura)
        if 'detalle_formset' not in ctx:
            if self.request.POST:
                ctx['detalle_formset'] = DetalleNotaCreditoFormSet(self.request.POST)
            else:
                initial_detalles = _initial_detalles_nota_credito_desde_factura(self.factura)
                FormSet = _detalle_nota_credito_formset_factory(extra=len(initial_detalles))
                ctx['detalle_formset'] = FormSet(initial=initial_detalles)
        return ctx


class NotaCreditoRecibidaDetailView(ProveedoresMixin, DetailView):
    model = NotaCreditoRecibida
    template_name = 'admin/proveedores/nota_credito_detail.html'
    context_object_name = 'nota_credito'


class FacturaRecibidaDeleteView(ProveedoresMixin, DeleteView):
    model = FacturaRecibida
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('proveedores:factura_list')

    def dispatch(self, request, *args, **kwargs):
        factura = self.get_object()
        if factura.estado in ('pagada', 'anulada'):
            messages.error(
                request,
                f'No se puede eliminar la factura porque está en estado "{factura.get_estado_display()}".'
            )
            return redirect('proveedores:factura_detail', pk=factura.pk)
        if factura.asientos.filter(estado='confirmado').exists():
            messages.error(
                request,
                'No se puede eliminar la factura porque tiene un asiento contable confirmado.'
            )
            return redirect('proveedores:factura_detail', pk=factura.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse('proveedores:factura_detail', kwargs={'pk': self.object.pk})
        return ctx

    def form_valid(self, form):
        factura = self.object
        factura.asientos.filter(estado='borrador').delete()
        logger.warning('Factura recibida eliminada: %s (pk=%s) por %s', factura.numero, factura.pk, self.request.user)
        messages.success(self.request, f'Factura {factura.numero} eliminada.')
        return super().form_valid(form)


class CuentaPorPagarListView(ProveedoresMixin, ListView):
    model = CuentaPorPagar
    template_name = 'admin/proveedores/cxp_list.html'
    context_object_name = 'cuentas'
    paginate_by = 25

    def get_queryset(self):

        # Filtramos por estado si se pasa en GET
        estado = self.request.GET.get('estado')
        proveedor = self.request.GET.get('proveedor')

        cuentas = CuentaPorPagar.objects.select_related(
            'factura__proveedor', 'factura__pago_por_trabajador',
            'rendicion__trabajador', 'boleta_honorarios__prestador'
        ).order_by('fecha_vencimiento') 

        if estado:
            cuentas = cuentas.filter(estado=estado)
        
        if proveedor:
            cuentas = cuentas.filter(factura__proveedor_id=proveedor)
        
        return cuentas

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Cuentas por Pagar'
        ctx['proveedores'] = Proveedor.objects.filter(facturas__cuenta_pagar__isnull=False).distinct()

        total_pendiente = self.get_queryset().filter(estado='pendiente').aggregate(total=Sum('monto'))['total'] or 0
        ctx['total_pendiente'] = total_pendiente

        return ctx


class CxPPagarView(ProveedoresMixin, View):
    template_name = 'admin/proveedores/cxp_pagar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        # Filtramos cuentas bancarias activas y que tengan cuenta_contable asignada para evitar errores al generar el asiento

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True, cuenta_contable__isnull=False).select_related('banco')

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

        # 2. Actualizar documento asociado según corresponda
        if cxp.factura:
            cxp.factura.estado = 'pagada'
            cxp.factura.save()
        elif cxp.boleta_honorarios:
            cxp.boleta_honorarios.estado = 'pagada'
            cxp.boleta_honorarios.save(update_fields=['estado'])
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
        elif cxp.boleta_honorarios:
            descripcion_mov = f'Pago boleta {cxp.boleta_honorarios.numero} - {cxp.boleta_honorarios.prestador.nombre}'
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

        # Vincular movimiento a la CxP
        cxp.movimiento_pago = movimiento
        cxp.save(update_fields=['movimiento_pago'])

        # 4. Generar asiento contable borrador
        asiento = generar_asiento_movimiento_bancario(movimiento, usuario=request.user)

        if asiento:
            logger.info('CxP pk=%s pagada. Movimiento=%s, asiento=%s. Usuario: %s', cxp.pk, movimiento.pk, asiento.numero, request.user)
            messages.success(
                request,
                f'Pago registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            logger.warning('CxP pk=%s pagada sin asiento generado. Movimiento=%s. Usuario: %s', cxp.pk, movimiento.pk, request.user)
            messages.success(request, 'Pago registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable automáticamente. '
                'Verifique que la cuenta bancaria y la Config. Contable tengan cuentas asignadas.'
            )

        return redirect('proveedores:cxp_list')


class AnularPagoCxPView(ProveedoresMixin, View):
    """Revierte un pago: elimina el movimiento bancario y su asiento (borrador),
    y deja la CxP y la factura/rendición en estado pendiente."""

    def post(self, request, pk):
        from django.db import transaction
        cxp = get_object_or_404(CuentaPorPagar, pk=pk)

        if cxp.estado != 'pagada':
            messages.error(request, 'Esta cuenta no está en estado pagada.')
            return redirect('proveedores:cxp_list')

        movimiento = cxp.movimiento_pago
        if movimiento:
            asiento_confirmado = movimiento.asientos.filter(estado='confirmado').exists()
            if asiento_confirmado:
                messages.error(
                    request,
                    'No se puede anular el pago porque el asiento contable del movimiento está confirmado. '
                    'Anúle el asiento primero.'
                )
                return redirect('proveedores:cxp_list')

        with transaction.atomic():
            if movimiento:
                movimiento.asientos.filter(estado='borrador').delete()
                movimiento.delete()

            # Revertir CxP
            cxp.estado = 'pendiente'
            cxp.monto_pagado = 0
            cxp.fecha_pago = None
            cxp.medio_pago = ''
            cxp.numero_documento = ''
            cxp.notas = ''
            cxp.movimiento_pago = None
            cxp.save()

            # Revertir documento asociado
            if cxp.factura:
                cxp.factura.estado = 'pendiente'
                cxp.factura.save(update_fields=['estado'])
            elif cxp.boleta_honorarios:
                cxp.boleta_honorarios.estado = 'pendiente'
                cxp.boleta_honorarios.save(update_fields=['estado'])
            elif cxp.rendicion:
                cxp.rendicion.estado = 'aprobado'
                cxp.rendicion.save(update_fields=['estado'])

        logger.warning('Pago anulado para CxP pk=%s por %s', cxp.pk, request.user)
        messages.success(request, 'Pago anulado correctamente. La cuenta quedó pendiente de pago.')
        return redirect('proveedores:cxp_list')


class GenerarAsientoFacturaRecibidaView(ProveedoresMixin, View):
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


class AnticipoListView(ProveedoresMixin, ListView):
    model = Anticipo
    template_name = 'admin/proveedores/anticipo_list.html'
    context_object_name = 'anticipos'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Anticipos a Proveedores'
        return ctx


class AnticipoCreateView(ProveedoresMixin, CreateView):
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


class AnticipoProveedorPagarView(ProveedoresMixin, View):
    template_name = 'admin/proveedores/anticipo_pagar.html'

    def _build_form(self, data=None, initial=None):
        from django import forms
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoAnticipoProveedorForm(forms.Form):
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

        return PagoAnticipoProveedorForm(data=data, initial=initial)

    def get(self, request, pk):
        from django.shortcuts import render
        anticipo = get_object_or_404(Anticipo, pk=pk)
        if anticipo.estado != 'pendiente':
            messages.info(request, f'Este anticipo ya está en estado "{anticipo.get_estado_display()}".')
            return redirect('proveedores:anticipo_list')
        form = self._build_form(initial={'fecha_pago': timezone.localdate()})
        return render(request, self.template_name, {'anticipo': anticipo, 'form': form})

    def post(self, request, pk):
        from django.shortcuts import render
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_pago_anticipo_proveedor

        anticipo = get_object_or_404(Anticipo, pk=pk)
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'anticipo': anticipo, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']

        # 1. Crear MovimientoBancario (egreso)
        descripcion_mov = f'Anticipo {anticipo.proveedor.razon_social} - {anticipo.fecha}'
        movimiento = MovimientoBancario.objects.create(
            cuenta=cuenta_bancaria,
            fecha=d['fecha_pago'],
            tipo='egreso',
            monto=anticipo.monto,
            descripcion=descripcion_mov,
            cuenta_contable=None,
        )

        # Asignar cuenta_contable del movimiento = cuenta_anticipos_proveedores (fallback a compras)
        try:
            from apps.contabilidad.models import ConfiguracionContable
            config = ConfiguracionContable.get()
            if config and config.cuenta_anticipos_proveedores:
                movimiento.cuenta_contable = config.cuenta_anticipos_proveedores
            elif config and config.cuenta_compras_default:
                movimiento.cuenta_contable = config.cuenta_compras_default
            if movimiento.cuenta_contable:
                movimiento.save(update_fields=['cuenta_contable'])
        except Exception:
            pass

        # 2. Generar asiento: DEBE Anticipos a Proveedores (activo) / HABER Banco
        asiento = generar_asiento_pago_anticipo_proveedor(anticipo, movimiento, usuario=request.user)

        if asiento:
            logger.info('Anticipo pk=%s pagado. Movimiento=%s, asiento=%s. Usuario: %s', anticipo.pk, movimiento.pk, asiento.numero, request.user)
            messages.success(
                request,
                f'Anticipo registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            logger.warning('Anticipo pk=%s pagado sin asiento generado. Movimiento=%s. Usuario: %s', anticipo.pk, movimiento.pk, request.user)
            messages.success(request, 'Anticipo registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('proveedores:anticipo_list')

