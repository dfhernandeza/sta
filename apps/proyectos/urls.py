from django.urls import path
from . import views

app_name = 'proyectos'

urlpatterns = [
    path('', views.ProyectoListView.as_view(), name='proyecto_list'),
    path('crear/', views.ProyectoCreateView.as_view(), name='proyecto_create'),
    path('<int:pk>/', views.ProyectoDetailView.as_view(), name='proyecto_detail'),
    path('<int:pk>/editar/', views.ProyectoUpdateView.as_view(), name='proyecto_update'),
    path('<int:pk>/costos/crear/', views.CostoCreateView.as_view(), name='costo_create'),
    path('<int:pk>/presupuesto/', views.PresupuestoView.as_view(), name='presupuesto'),
]
