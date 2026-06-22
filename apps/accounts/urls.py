from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('perfil/', views.PerfilView.as_view(), name='perfil'),
    path('usuarios/', views.UsuarioListView.as_view(), name='usuario_list'),
    path('usuarios/crear/', views.UsuarioCreateView.as_view(), name='usuario_create'),
    path('usuarios/<int:pk>/editar/', views.UsuarioUpdateView.as_view(), name='usuario_update'),
    path('usuarios/<int:pk>/permisos/', views.UsuarioPermisosView.as_view(), name='usuario_permisos'),
    path('usuarios/<int:pk>/cambiar-password/', views.UsuarioCambiarPasswordView.as_view(), name='usuario_cambiar_password'),
]
