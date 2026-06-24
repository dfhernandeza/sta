from django.urls import path

from . import views

app_name = 'boletas'

urlpatterns = [
    path('', views.BoletaHonorariosListView.as_view(), name='boleta_list'),
    path('crear/', views.BoletaHonorariosCreateView.as_view(), name='boleta_create'),
    path('<int:pk>/', views.BoletaHonorariosDetailView.as_view(), name='boleta_detail'),
    path('<int:pk>/editar/', views.BoletaHonorariosUpdateView.as_view(), name='boleta_update'),
    path('<int:pk>/eliminar/', views.BoletaHonorariosDeleteView.as_view(), name='boleta_delete'),
    path('prestadores/', views.PrestadorHonorariosListView.as_view(), name='prestador_list'),
    path('prestadores/crear/', views.PrestadorHonorariosCreateView.as_view(), name='prestador_create'),
    path('prestadores/<int:pk>/editar/', views.PrestadorHonorariosUpdateView.as_view(), name='prestador_update'),
]
