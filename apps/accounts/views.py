from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.contrib import messages
from apps.core.mixins import GestionMixin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm, UsuarioPermisosForm, UsuarioSetPasswordForm


class SuperuserRequiredMixin(GestionMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_superuser:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


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


class PerfilView(GestionMixin, TemplateView):
    template_name = 'admin/perfil.html'


class UsuarioListView(GestionMixin, ListView):
    model = CustomUser
    template_name = 'admin/usuarios/lista.html'
    context_object_name = 'usuarios'


class UsuarioCreateView(SuperuserRequiredMixin, CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'admin/usuarios/form.html'
    success_url = reverse_lazy('accounts:usuario_list')

    def form_valid(self, form):
        messages.success(self.request, 'Usuario creado exitosamente.')
        return super().form_valid(form)


class UsuarioUpdateView(SuperuserRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'admin/usuarios/form.html'
    success_url = reverse_lazy('accounts:usuario_list')

    def form_valid(self, form):
        messages.success(self.request, 'Usuario actualizado exitosamente.')
        return super().form_valid(form)


class UsuarioPermisosView(SuperuserRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UsuarioPermisosForm
    template_name = 'admin/usuarios/permisos.html'
    success_url = reverse_lazy('accounts:usuario_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['usuario'] = self.object
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Permisos de {self.object.username} actualizados.')
        return super().form_valid(form)


class UsuarioCambiarPasswordView(SuperuserRequiredMixin, View):
    template_name = 'admin/usuarios/cambiar_password.html'

    def get_usuario(self, pk):
        return get_object_or_404(CustomUser, pk=pk)

    def get(self, request, pk):
        usuario = self.get_usuario(pk)
        form = UsuarioSetPasswordForm(user=usuario)
        return render(request, self.template_name, {'form': form, 'usuario': usuario})

    def post(self, request, pk):
        usuario = self.get_usuario(pk)
        form = UsuarioSetPasswordForm(user=usuario, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Contraseña de {usuario.username} actualizada exitosamente.')
            return redirect('accounts:usuario_list')
        return render(request, self.template_name, {'form': form, 'usuario': usuario})
