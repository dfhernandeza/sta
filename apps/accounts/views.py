from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm


class CustomLoginView(LoginView):
    template_name = 'admin/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy('dashboard:index')

    def form_invalid(self, form):
        messages.error(self.request, 'RUT/usuario o contraseña incorrectos.')
        return super().form_invalid(form)


class CustomLogoutView(LogoutView):
    next_page = '/gestion/login/'


class PerfilView(LoginRequiredMixin, TemplateView):
    template_name = 'admin/perfil.html'
    login_url = '/gestion/login/'


class UsuarioListView(LoginRequiredMixin, ListView):
    model = CustomUser
    template_name = 'admin/usuarios/lista.html'
    context_object_name = 'usuarios'
    login_url = '/gestion/login/'


class UsuarioCreateView(LoginRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'admin/usuarios/form.html'
    success_url = reverse_lazy('accounts:usuario_list')
    login_url = '/gestion/login/'

    def form_valid(self, form):
        messages.success(self.request, 'Usuario creado exitosamente.')
        return super().form_valid(form)


class UsuarioUpdateView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'admin/usuarios/form.html'
    success_url = reverse_lazy('accounts:usuario_list')
    login_url = '/gestion/login/'

    def form_valid(self, form):
        messages.success(self.request, 'Usuario actualizado exitosamente.')
        return super().form_valid(form)
