from django.urls import path
from . import views

app_name = 'rrhh'

urlpatterns = [
    path('', views.TrabajadorListView.as_view(), name='trabajador_list'),
    path('crear/', views.TrabajadorCreateView.as_view(), name='trabajador_create'),
    path('<int:pk>/', views.TrabajadorDetailView.as_view(), name='trabajador_detail'),
    path('<int:pk>/editar/', views.TrabajadorUpdateView.as_view(), name='trabajador_update'),
    path('remuneraciones/', views.RemuneracionListView.as_view(), name='remuneracion_list'),
    path('remuneraciones/procesar/', views.RemuneracionPeriodoView.as_view(), name='remuneracion_procesar'),
    path('remuneraciones/procesar/<int:mes>/<int:anio>/', views.RemuneracionPeriodoDetalleView.as_view(), name='remuneracion_procesar_detalle'),
    path('remuneraciones/crear/', views.RemuneracionCreateView.as_view(), name='remuneracion_create'),
    path('remuneraciones/<int:pk>/editar/', views.RemuneracionUpdateView.as_view(), name='remuneracion_update'),
    path('remuneraciones/<int:pk>/eliminar/', views.RemuneracionDeleteView.as_view(), name='remuneracion_delete'),
    path('remuneraciones/<int:pk>/pagar/', views.RemuneracionPagarView.as_view(), name='remuneracion_pagar'),
    path('api/trabajador/<int:pk>/', views.RemuneracionDatosAPI.as_view(), name='trabajador_datos_api'),
    path('anticipos/', views.AnticipoLaboralListView.as_view(), name='anticipo_list'),
    path('anticipos/crear/', views.AnticipoLaboralCreateView.as_view(), name='anticipo_create'),
    path('anticipos/<int:pk>/editar/', views.AnticipoLaboralUpdateView.as_view(), name='anticipo_update'),
    path('anticipos/<int:pk>/eliminar/', views.AnticipoLaboralDeleteView.as_view(), name='anticipo_delete'),
    path('anticipos/<int:pk>/pagar/', views.AnticipoLaboralPagarView.as_view(), name='anticipo_pagar'),
    path('cargos/', views.CargoTrabajadorListView.as_view(), name='cargo_list'),
    path('cargos/crear/', views.CargoTrabajadorCreateView.as_view(), name='cargo_create'),
    path('cargos/<int:pk>/', views.CargoTrabajadorDetailView.as_view(), name='cargo_detail'),
    path('cargos/<int:pk>/editar/', views.CargoTrabajadorUpdateView.as_view(), name='cargo_update'),
]
