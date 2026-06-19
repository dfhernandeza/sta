from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    # Clientes
    path('', views.ClienteListView.as_view(), name='cliente_list'),
    path('crear/', views.ClienteCreateView.as_view(), name='cliente_create'),
    path('<int:pk>/', views.ClienteDetailView.as_view(), name='cliente_detail'),
    path('<int:pk>/editar/', views.ClienteUpdateView.as_view(), name='cliente_update'),
    # Facturas emitidas
    path('facturas/', views.FacturaEmitidaListView.as_view(), name='factura_list'),
    path('facturas/crear/', views.FacturaEmitidaCreateView.as_view(), name='factura_create'),
    path('facturas/<int:pk>/', views.FacturaEmitidaDetailView.as_view(), name='factura_detail'),
    path('facturas/<int:pk>/editar/', views.FacturaEmitidaUpdateView.as_view(), name='factura_update'),
    path('facturas/<int:pk>/eliminar/', views.FacturaEmitidaDeleteView.as_view(), name='factura_delete'),
    # CxC
    path('cxc/', views.CuentaPorCobrarListView.as_view(), name='cxc_list'),
    path('cxc/<int:pk>/pagar/', views.CxCPagarView.as_view(), name='cxc_pagar'),
    path('cxc/<int:pk>/anular/', views.AnularPagoCxCView.as_view(), name='cxc_anular'),
    # Asiento contable
    path('facturas/<int:pk>/asiento/', views.GenerarAsientoFacturaEmitidaView.as_view(), name='factura_asiento'),
]
