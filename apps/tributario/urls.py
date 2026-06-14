from django.urls import path
from . import views

app_name = 'tributario'

urlpatterns = [
    path('', views.TributarioResumenView.as_view(), name='resumen'),
    path('compras/', views.RegistroCompraListView.as_view(), name='compra_list'),
    path('ventas/', views.RegistroVentaListView.as_view(), name='venta_list'),
    path('iva/', views.DeclaracionIVAListView.as_view(), name='iva_list'),
    path('iva/crear/', views.DeclaracionIVACreateView.as_view(), name='iva_create'),
    path('iva/<int:pk>/editar/', views.DeclaracionIVAUpdateView.as_view(), name='iva_update'),
    path('ppm/', views.PPMListView.as_view(), name='ppm_list'),
    path('ppm/crear/', views.PPMCreateView.as_view(), name='ppm_create'),
    path('ppm/<int:pk>/editar/', views.PPMUpdateView.as_view(), name='ppm_update'),
    path('ppm/<int:pk>/pagar/', views.PPMPagarView.as_view(), name='ppm_pagar'),
    path('f29/', views.F29ListView.as_view(), name='f29_list'),
    path('f29/crear/', views.F29CreateView.as_view(), name='f29_create'),
    path('f29/<int:pk>/editar/', views.F29UpdateView.as_view(), name='f29_update'),
    path('f29/<int:pk>/pagar/', views.F29PagarView.as_view(), name='f29_pagar'),
]
