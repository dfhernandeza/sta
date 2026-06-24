import logging

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.contabilidad.utils import generar_asiento_boleta_honorarios
from apps.core.mixins import AppPermisoMixin
from apps.proveedores.models import CuentaPorPagar

from .forms import BoletaHonorariosForm, PrestadorHonorariosForm
from .models import BoletaHonorarios, PrestadorHonorarios

logger = logging.getLogger(__name__)


class BoletasMixin(AppPermisoMixin):
    app_name = 'boletas'


def _sincronizar_cxp_boleta(boleta):
    if boleta.estado == 'anulada':
        CuentaPorPagar.objects.filter(boleta_honorarios=boleta, estado='pendiente', monto_pagado=0).delete()
        return None

    cxp, created = CuentaPorPagar.objects.get_or_create(
        boleta_honorarios=boleta,
        defaults={
            'fecha_vencimiento': boleta.fecha_vencimiento or boleta.fecha_emision,
            'monto': boleta.liquido,
            'estado': 'pendiente',
        }
    )
    if not created:
        cxp.fecha_vencimiento = boleta.fecha_vencimiento or boleta.fecha_emision
        cxp.monto = boleta.liquido
        cxp.estado = 'pagada' if cxp.monto_pagado >= boleta.liquido else 'pendiente'
        cxp.save(update_fields=['fecha_vencimiento', 'monto', 'estado'])
    return cxp


def _generar_asiento_automatico_boleta(request, boleta, reemplazar_borrador=False):
    asiento_activo = boleta.asientos.exclude(estado='anulado').first()
    if asiento_activo:
        if asiento_activo.estado == 'confirmado':
            messages.warning(
                request,
                f'No se regeneró el asiento automático porque la boleta ya tiene un asiento confirmado ({asiento_activo.numero}).'
            )
            return asiento_activo
        if asiento_activo.estado == 'borrador' and reemplazar_borrador:
            asiento_activo.delete()
        elif asiento_activo.estado == 'borrador':
            return asiento_activo

    asiento = generar_asiento_boleta_honorarios(boleta, usuario=request.user)
    if asiento:
        messages.info(request, f'Se generó automáticamente el asiento {asiento.numero}.')
    else:
        messages.warning(request, 'La boleta se guardó, pero no se pudo generar el asiento automático. Revise la configuración contable.')
    return asiento


class PrestadorHonorariosListView(BoletasMixin, ListView):
    model = PrestadorHonorarios
    template_name = 'admin/boletas/prestador_list.html'
    context_object_name = 'prestadores'
    paginate_by = 25

    def get_queryset(self):
        qs = PrestadorHonorarios.objects.all()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q) | qs.filter(rut__icontains=q)
        return qs


class PrestadorHonorariosCreateView(BoletasMixin, CreateView):
    model = PrestadorHonorarios
    form_class = PrestadorHonorariosForm
    template_name = 'admin/boletas/prestador_form.html'
    success_url = reverse_lazy('boletas:prestador_list')

    def form_valid(self, form):
        messages.success(self.request, 'Prestador registrado.')
        return super().form_valid(form)


class PrestadorHonorariosUpdateView(BoletasMixin, UpdateView):
    model = PrestadorHonorarios
    form_class = PrestadorHonorariosForm
    template_name = 'admin/boletas/prestador_form.html'
    success_url = reverse_lazy('boletas:prestador_list')

    def form_valid(self, form):
        messages.success(self.request, 'Prestador actualizado.')
        return super().form_valid(form)


class BoletaHonorariosListView(BoletasMixin, ListView):
    model = BoletaHonorarios
    template_name = 'admin/boletas/boleta_list.html'
    context_object_name = 'boletas'
    paginate_by = 25

    def get_queryset(self):
        qs = BoletaHonorarios.objects.select_related('prestador', 'proyecto').order_by('-fecha_emision', '-numero')
        estado = self.request.GET.get('estado')
        q = self.request.GET.get('q')
        if estado:
            qs = qs.filter(estado=estado)
        if q:
            qs = qs.filter(numero__icontains=q) | qs.filter(prestador__nombre__icontains=q) | qs.filter(prestador__rut__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_pendiente'] = self.get_queryset().filter(estado='pendiente').aggregate(total=Sum('liquido'))['total'] or 0
        return ctx


class BoletaHonorariosCreateView(BoletasMixin, CreateView):
    model = BoletaHonorarios
    form_class = BoletaHonorariosForm
    template_name = 'admin/boletas/boleta_form.html'
    success_url = reverse_lazy('boletas:boleta_list')

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            _sincronizar_cxp_boleta(self.object)
            _generar_asiento_automatico_boleta(self.request, self.object, reemplazar_borrador=False)
        logger.info('Boleta de honorarios creada: %s por %s', self.object.numero, self.request.user)
        messages.success(self.request, f'Boleta {self.object.numero} registrada.')
        return redirect(self.get_success_url())


class BoletaHonorariosUpdateView(BoletasMixin, UpdateView):
    model = BoletaHonorarios
    form_class = BoletaHonorariosForm
    template_name = 'admin/boletas/boleta_form.html'
    success_url = reverse_lazy('boletas:boleta_list')

    def dispatch(self, request, *args, **kwargs):
        boleta = self.get_object()
        if boleta.estado in ('pagada', 'anulada'):
            messages.error(request, f'No se puede editar la boleta porque está en estado "{boleta.get_estado_display()}".')
            return redirect('boletas:boleta_detail', pk=boleta.pk)
        if boleta.asientos.filter(estado='confirmado').exists():
            messages.error(request, 'No se puede editar la boleta porque tiene un asiento contable confirmado.')
            return redirect('boletas:boleta_detail', pk=boleta.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            _sincronizar_cxp_boleta(self.object)
            _generar_asiento_automatico_boleta(self.request, self.object, reemplazar_borrador=True)
        messages.success(self.request, 'Boleta actualizada.')
        return redirect(self.get_success_url())


class BoletaHonorariosDetailView(BoletasMixin, DetailView):
    model = BoletaHonorarios
    template_name = 'admin/boletas/boleta_detail.html'
    context_object_name = 'boleta'


class BoletaHonorariosDeleteView(BoletasMixin, DeleteView):
    model = BoletaHonorarios
    template_name = 'admin/confirm_delete.html'
    success_url = reverse_lazy('boletas:boleta_list')

    def dispatch(self, request, *args, **kwargs):
        boleta = self.get_object()
        if boleta.estado in ('pagada', 'anulada'):
            messages.error(request, f'No se puede eliminar la boleta porque está en estado "{boleta.get_estado_display()}".')
            return redirect('boletas:boleta_detail', pk=boleta.pk)
        if boleta.asientos.filter(estado='confirmado').exists():
            messages.error(request, 'No se puede eliminar la boleta porque tiene un asiento contable confirmado.')
            return redirect('boletas:boleta_detail', pk=boleta.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cancel_url'] = reverse('boletas:boleta_detail', kwargs={'pk': self.object.pk})
        return ctx

    def form_valid(self, form):
        self.object.asientos.filter(estado='borrador').delete()
        messages.success(self.request, f'Boleta {self.object.numero} eliminada.')
        return super().form_valid(form)
