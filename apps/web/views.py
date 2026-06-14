from django.views.generic import TemplateView, ListView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import ProyectoPortafolio, Servicio, MiembroEquipo, ContactoMensaje
from .forms import ContactoForm


class IndexView(TemplateView):
    template_name = 'web/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['proyectos_destacados'] = ProyectoPortafolio.objects.filter(
            destacado=True, activo=True
        ).order_by('orden')[:6]
        ctx['servicios'] = Servicio.objects.filter(activo=True).order_by('orden')[:6]
        return ctx


class ProyectosView(ListView):
    model = ProyectoPortafolio
    template_name = 'web/proyectos.html'
    context_object_name = 'proyectos'

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


class ServiciosView(TemplateView):
    template_name = 'web/servicios.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['servicios'] = Servicio.objects.filter(activo=True).order_by('orden')
        return ctx


class NosotrosView(TemplateView):
    template_name = 'web/nosotros.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['equipo'] = MiembroEquipo.objects.filter(activo=True).order_by('orden')
        return ctx


class ContactoView(FormView):
    template_name = 'web/contacto.html'
    form_class = ContactoForm
    success_url = reverse_lazy('web:contacto_gracias')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ContactoGraciasView(TemplateView):
    template_name = 'web/contacto_gracias.html'
