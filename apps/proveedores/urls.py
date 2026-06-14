from django.urls import path
from . import views

app_name = 'proveedores'

urlpatterns = [
    # Proveedores
    path('', views.ProveedorListView.as_view(), name='proveedor_list'),
    path('crear/', views.ProveedorCreateView.as_view(), name='proveedor_create'),
    path('<int:pk>/', views.ProveedorDetailView.as_view(), name='proveedor_detail'),
    path('<int:pk>/editar/', views.ProveedorUpdateView.as_view(), name='proveedor_update'),
    # Facturas recibidas
    path('facturas/', views.FacturaRecibidaListView.as_view(), name='factura_list'),
    path('facturas/crear/', views.FacturaRecibidaCreateView.as_view(), name='factura_create'),
    path('facturas/<int:pk>/', views.FacturaRecibidaDetailView.as_view(), name='factura_detail'),
    path('facturas/<int:pk>/editar/', views.FacturaRecibidaUpdateView.as_view(), name='factura_update'),
    # CxP
    path('cxp/', views.CuentaPorPagarListView.as_view(), name='cxp_list'),
    path('cxp/<int:pk>/pagar/', views.CxPPagarView.as_view(), name='cxp_pagar'),
    # Asiento contable
    path('facturas/<int:pk>/asiento/', views.GenerarAsientoFacturaRecibidaView.as_view(), name='factura_asiento'),
    # Anticipos
    path('anticipos/', views.AnticipoListView.as_view(), name='anticipo_list'),
    path('anticipos/crear/', views.AnticipoCreateView.as_view(), name='anticipo_create'),
    # Rendiciones de gastos
    path('rendiciones/', views.RendicionGastosListView.as_view(), name='rendicion_list'),
    path('rendiciones/crear/', views.RendicionGastosCreateView.as_view(), name='rendicion_create'),
    path('rendiciones/<int:pk>/', views.RendicionGastosDetailView.as_view(), name='rendicion_detail'),
    path('rendiciones/<int:pk>/asiento/', views.GenerarAsientoRendicionView.as_view(), name='rendicion_asiento'),
]
