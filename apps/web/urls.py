from django.urls import path
from . import views

app_name = 'web'

urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('proyectos/', views.ProyectosView.as_view(), name='proyectos'),
    path('servicios/', views.ServiciosView.as_view(), name='servicios'),
    path('nosotros/', views.NosotrosView.as_view(), name='nosotros'),
    path('contacto/', views.ContactoView.as_view(), name='contacto'),
    path('contacto/gracias/', views.ContactoGraciasView.as_view(), name='contacto_gracias'),
]
