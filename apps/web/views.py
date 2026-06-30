from django.views.generic import TemplateView, ListView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import MiembroEquipo, PaginaWeb, ProyectoPortafolio, SeccionWeb, Servicio
from .forms import ContactoForm


class WebContextMixin:
    page_slug = None

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if not self.page_slug:
            return ctx

        pagina = PaginaWeb.objects.filter(slug=self.page_slug, activo=True).first()
        secciones = {}

        if pagina:
            qs = SeccionWeb.objects.filter(
                pagina=pagina,
                activo=True,
            ).prefetch_related('items').order_by('orden', 'clave')
            for seccion in qs:
                seccion.items_activos = [
                    item for item in seccion.items.all() if item.activo
                ]
                secciones[seccion.clave] = seccion

        ctx['pagina'] = pagina
        ctx['secciones'] = secciones
        return ctx


class IndexView(WebContextMixin, TemplateView):
    template_name = 'web/index.html'
    page_slug = 'inicio'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['proyectos_destacados'] = ProyectoPortafolio.objects.filter(
            destacado=True, activo=True
        ).order_by('orden')[:6]
        ctx['servicios'] = Servicio.objects.filter(activo=True).order_by('orden')[:6]
        return ctx


class ProyectosView(WebContextMixin, ListView):
    model = ProyectoPortafolio
    template_name = 'web/proyectos.html'
    context_object_name = 'proyectos'
    page_slug = 'proyectos'

    def get_queryset(self):
        qs = ProyectoPortafolio.objects.filter(activo=True).order_by('orden', '-creado_en')
        categoria = self.request.GET.get('categoria')
        if categoria:
            qs = qs.filter(categoria=categoria)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias'] = ProyectoPortafolio.CATEGORIA_CHOICES
        ctx['categoria_activa'] = self.request.GET.get('categoria', '')
        return ctx


class ServiciosView(WebContextMixin, TemplateView):
    template_name = 'web/servicios.html'
    page_slug = 'servicios'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['servicios'] = Servicio.objects.filter(activo=True).order_by('orden')
        return ctx


class NosotrosView(WebContextMixin, TemplateView):
    template_name = 'web/nosotros.html'
    page_slug = 'nosotros'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipo'] = MiembroEquipo.objects.filter(activo=True).order_by('orden')
        return ctx


class ContactoView(WebContextMixin, FormView):
    template_name = 'web/contacto.html'
    form_class = ContactoForm
    success_url = reverse_lazy('web:contacto_gracias')
    page_slug = 'contacto'

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ContactoGraciasView(WebContextMixin, TemplateView):
    template_name = 'web/contacto_gracias.html'
    page_slug = 'contacto_gracias'
