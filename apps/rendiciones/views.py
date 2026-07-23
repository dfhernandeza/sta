import logging

from django.views.generic import ListView, CreateView, DetailView, DeleteView, View
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from django.db.models import Sum, Value
from django.db.models.functions import Replace, Upper
from django.forms import inlineformset_factory, ModelForm, TextInput, Select, NumberInput

from apps.core.mixins import AppPermisoMixin
from .models import RendicionGastos, DetalleRendicion
from apps.proveedores.models import CuentaPorPagar
from apps.rrhh.models import Trabajador

logger = logging.getLogger(__name__)


class RendicionesMixin(AppPermisoMixin):
    app_name = 'rendiciones'

    def acceso_solo_rendiciones(self):
        """Indica si el usuario debe limitarse a sus propias rendiciones."""
        permisos = set(self.request.user.app_permisos or [])
        return not self.request.user.is_superuser and permisos == {'rendiciones'}

    def get_trabajador_usuario(self):
        """Relaciona al usuario con el trabajador usando su RUT como username."""
        rut_usuario = ''.join(
            caracter for caracter in self.request.user.username.upper()
            if caracter.isalnum()
        )
        if not rut_usuario:
            raise PermissionDenied('El usuario no estÃ¡ asociado a un trabajador.')

        trabajador = (
            Trabajador.objects
            .annotate(
                rut_normalizado=Upper(
                    Replace(
                        Replace(
                            Replace('rut', Value('.'), Value('')),
                            Value('-'), Value(''),
                        ),
                        Value(' '), Value(''),
                    )
                )
            )
            .filter(rut_normalizado=rut_usuario)
            .first()
        )
        if trabajador is None:
            raise PermissionDenied('El usuario no estÃ¡ asociado a un trabajador.')
        return trabajador

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.acceso_solo_rendiciones():
            queryset = queryset.filter(trabajador=self.get_trabajador_usuario())
        return queryset


def _viernes_proxima_semana(fecha):
    """Devuelve el viernes de la semana siguiente a 'fecha'."""
    lunes_actual = fecha - timedelta(days=fecha.weekday())
    return lunes_actual + timedelta(days=11)


# Transiciones válidas de estado para RendicionGastos
_TRANSICIONES_RENDICION = {
    'borrador':  ['enviado'],
    'enviado':   ['aprobado', 'rechazado'],
    'rechazado': ['borrador'],
    'aprobado':  [],
}


class DetalleRendicionForm(ModelForm):
    class Meta:
        model = DetalleRendicion
        fields = ['fecha_gasto', 'n_boleta_factura', 'descripcion', 'monto', 'centro_costo', 'cuenta_contable', 'proveedor']
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
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(
            tipo__in=['gasto', 'costo'],
            nivel=4
        )


DetalleRendicionFormSet = inlineformset_factory(
    RendicionGastos, DetalleRendicion,
    form=DetalleRendicionForm,
    extra=0, can_delete=True,
)


class RendicionGastosListView(RendicionesMixin, ListView):
    model = RendicionGastos
    template_name = 'admin/rendiciones/rendicion_list.html'
    context_object_name = 'rendiciones'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Rendiciones de Gastos'
        return ctx


class RendicionGastosCreateView(RendicionesMixin, CreateView):
    model = RendicionGastos
    template_name = 'admin/rendiciones/rendicion_form.html'
    fields = ['trabajador', 'proyecto', 'fecha', 'motivo_del_gasto']
    success_url = reverse_lazy('rendiciones:rendicion_list')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.acceso_solo_rendiciones():
            form.fields.pop('trabajador', None)
        return form

    def form_valid(self, form):
        if self.acceso_solo_rendiciones():
            form.instance.trabajador = self.get_trabajador_usuario()
        formset = DetalleRendicionFormSet(self.request.POST)
        if not formset.is_valid():
            return self.form_invalid(form)
        response = super().form_valid(form)
        formset.instance = self.object
        formset.save()
        total_rendicion = self.object.detalles.aggregate(t=Sum('monto'))['t'] or 0
        if total_rendicion > 0:
            CuentaPorPagar.objects.create(
                rendicion=self.object,
                fecha_vencimiento=_viernes_proxima_semana(self.object.fecha),
                monto=total_rendicion,
            )
        logger.info(
            'Rendición de gastos creada: pk=%s, trabajador=%s, total=%s por %s',
            self.object.pk, self.object.trabajador, total_rendicion, self.request.user
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


class RendicionGastosDetailView(RendicionesMixin, DetailView):
    model = RendicionGastos
    template_name = 'admin/rendiciones/rendicion_detail.html'
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
        ctx['es_superusuario'] = self.request.user.is_superuser
        return ctx

    def post(self, request, pk):
        rendicion = get_object_or_404(self.get_queryset(), pk=pk)
        nuevo_estado = request.POST.get('estado')
        transiciones_validas = _TRANSICIONES_RENDICION.get(rendicion.estado, [])
        if nuevo_estado in transiciones_validas:
            rendicion.estado = nuevo_estado
            rendicion.save(update_fields=['estado'])
            labels = dict(RendicionGastos.ESTADO_CHOICES)
            logger.info(
                'Rendición pk=%s cambio de estado a "%s" por %s',
                rendicion.pk, nuevo_estado, request.user
            )
            messages.success(request, f'Estado actualizado a "{labels[nuevo_estado]}".')
        else:
            logger.warning(
                'Transición inválida para rendición pk=%s: estado=%s, solicitado=%s por %s',
                rendicion.pk, rendicion.estado, nuevo_estado, request.user
            )
            messages.error(request, 'Transición de estado no permitida.')
        return redirect('rendiciones:rendicion_detail', pk=rendicion.pk)


class RendicionGastosDeleteView(RendicionesMixin, DeleteView):
    model = RendicionGastos
    template_name = 'admin/rendiciones/rendicion_confirm_delete.html'
    success_url = reverse_lazy('rendiciones:rendicion_list')

    def _motivo_bloqueo(self, rendicion):
        if rendicion.estado == 'pagada':
            return (
                'No se puede eliminar una rendición marcada como pagada. '
                'Anule primero el pago desde Cuentas por Pagar.'
            )

        if rendicion.asientos.filter(estado='confirmado').exists():
            return (
                'No se puede eliminar la rendición porque tiene un asiento contable confirmado. '
                'Anule o reverse el asiento antes de eliminarla.'
            )

        cuentas_pagar = rendicion.cuentas_pagar.prefetch_related('aplicaciones_anticipos')
        for cxp in cuentas_pagar:
            tiene_pago = (
                cxp.estado == 'pagada'
                or cxp.movimiento_pago_id is not None
                or (cxp.monto_pagado or 0) > 0
                or cxp.aplicaciones_anticipos.exists()
            )
            if tiene_pago:
                return (
                    'No se puede eliminar la rendición porque su cuenta por pagar tiene pagos '
                    'o anticipos aplicados. Anule primero el pago desde Cuentas por Pagar.'
                )
        return None

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        motivo = self._motivo_bloqueo(self.object)
        if motivo:
            messages.error(request, motivo)
            return redirect('rendiciones:rendicion_detail', pk=self.object.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse(
            'rendiciones:rendicion_detail',
            kwargs={'pk': self.object.pk},
        )
        ctx['cuentas_pagar'] = self.object.cuentas_pagar.all()
        ctx['asientos_borrador'] = self.object.asientos.filter(estado='borrador')
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            rendicion = RendicionGastos.objects.select_for_update().get(pk=self.object.pk)
            motivo = self._motivo_bloqueo(rendicion)
            if motivo:
                messages.error(self.request, motivo)
                return redirect('rendiciones:rendicion_detail', pk=rendicion.pk)

            rendicion_id = rendicion.pk
            indice = rendicion.indice_rendicion
            trabajador = rendicion.trabajador
            rendicion.asientos.filter(estado='borrador').delete()
            rendicion.cuentas_pagar.all().delete()
            rendicion.delete()

        logger.warning(
            'Rendición eliminada: pk=%s, índice=%s, trabajador=%s por %s',
            rendicion_id,
            indice,
            trabajador,
            self.request.user,
        )
        messages.success(self.request, f'Rendición {indice} eliminada correctamente.')
        return redirect(self.success_url)


class GenerarAsientoRendicionView(RendicionesMixin, View):
    def get_queryset(self):
        queryset = RendicionGastos.objects.all()
        if self.acceso_solo_rendiciones():
            queryset = queryset.filter(trabajador=self.get_trabajador_usuario())
        return queryset

    def post(self, request, pk):
        from apps.contabilidad.utils import generar_asiento_rendicion_gastos_recibida, get_config
        rendicion = get_object_or_404(self.get_queryset(), pk=pk)
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
        return redirect('rendiciones:rendicion_detail', pk=rendicion.pk)
