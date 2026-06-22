from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import get_object_or_404
from apps.core.mixins import GestionMixin, AppPermisoMixin

class ProyectosMixin(AppPermisoMixin):
    app_name = 'proyectos'

from .models import Proyecto, CostoProyecto, Presupuesto


class ProyectoListView(ProyectosMixin, ListView):
    model = Proyecto
    template_name = 'admin/proyectos/proyecto_list.html'
    context_object_name = 'proyectos'
    paginate_by = 20

    def get_queryset(self):
        qs = Proyecto.objects.select_related('cliente')
        estado = self.request.GET.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q) | qs.filter(codigo__icontains=q)
        return qs.order_by('-fecha_inicio', 'nombre')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['estados'] = Proyecto.ESTADO_CHOICES
        ctx['titulo'] = 'Proyectos'
        return ctx


class ProyectoCreateView(ProyectosMixin, CreateView):
    model = Proyecto
    template_name = 'admin/proyectos/proyecto_form.html'
    fields = ['codigo', 'nombre', 'cliente', 'estado', 'fecha_inicio', 'fecha_termino',
              'monto_contrato', 'descripcion', 'direccion_obra', 'destacado', 'mostrar_en_web']
    success_url = reverse_lazy('proyectos:proyecto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Proyecto creado exitosamente.')
        
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Proyecto'
        return ctx


class ProyectoUpdateView(ProyectosMixin, UpdateView):
    model = Proyecto
    template_name = 'admin/proyectos/proyecto_form.html'
    fields = ['codigo', 'nombre', 'cliente', 'estado', 'fecha_inicio', 'fecha_termino',
              'monto_contrato', 'descripcion', 'direccion_obra', 'destacado', 'mostrar_en_web']
    success_url = reverse_lazy('proyectos:proyecto_list')

    def form_valid(self, form):
        messages.success(self.request, 'Proyecto actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Proyecto: {self.object.nombre}'
        return ctx


class ProyectoDetailView(ProyectosMixin, DetailView):
    model = Proyecto
    template_name = 'admin/proyectos/proyecto_detail.html'
    context_object_name = 'proyecto'

    def get_context_data(self, **kwargs):
        from apps.proveedores.models import DetalleFacturaRecibida
        from django.db.models import F, ExpressionWrapper, DecimalField
        ctx = super().get_context_data(**kwargs)
        ctx['detalles_factura'] = DetalleFacturaRecibida.objects.filter(
            factura__proyecto=self.object
        ).exclude(
            factura__estado='anulada'
        ).select_related(
            'factura__proveedor', 'centro_costo', 'cuenta_contable'
        ).annotate(
            subtotal=ExpressionWrapper(
                F('cantidad') * F('precio_unitario'),
                output_field=DecimalField(max_digits=15, decimal_places=2)
            )
        ).order_by('-factura__fecha_emision')
        ctx['presupuestos'] = self.object.presupuestos.all()
        return ctx


class CostoCreateView(ProyectosMixin, CreateView):
    model = CostoProyecto
    template_name = 'admin/proyectos/costo_form.html'
    fields = ['fecha', 'descripcion', 'tipo', 'monto', 'centro_costo', 'cuenta_contable', 'proveedor', 'factura']

    def get_success_url(self):
        return reverse_lazy('proyectos:proyecto_detail', kwargs={'pk': self.kwargs['pk']})

    def form_valid(self, form):
        form.instance.proyecto_id = self.kwargs['pk']
        messages.success(self.request, 'Costo registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registrar Costo'
        ctx['proyecto'] = get_object_or_404(Proyecto, pk=self.kwargs['pk'])
        return ctx


class PresupuestoView(ProyectosMixin, DetailView):
    model = Proyecto
    template_name = 'admin/proyectos/presupuesto.html'
    context_object_name = 'proyecto'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['presupuestos'] = self.object.presupuestos.all()
        ctx['titulo'] = f'Presupuesto: {self.object.nombre}'
        return ctx
