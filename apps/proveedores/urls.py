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
    path('facturas/<int:pk>/eliminar/', views.FacturaRecibidaDeleteView.as_view(), name='factura_delete'),
    path('facturas/<int:pk>/notas-credito/crear/', views.NotaCreditoRecibidaCreateView.as_view(), name='nota_credito_create'),
    path('notas-credito/', views.NotaCreditoRecibidaListView.as_view(), name='nota_credito_list'),
    path('notas-credito/<int:pk>/', views.NotaCreditoRecibidaDetailView.as_view(), name='nota_credito_detail'),
    path('notas-credito/<int:pk>/eliminar/', views.NotaCreditoRecibidaDeleteView.as_view(), name='nota_credito_delete'),
    # CxP
    path('cxp/', views.CuentaPorPagarListView.as_view(), name='cxp_list'),
    path('cxp/nomina-bci/', views.NominaBCIExportView.as_view(), name='cxp_nomina_bci'),
    path('cxp/<int:pk>/', views.CuentaPorPagarDetailView.as_view(), name='cxp_detail'),
    path('cxp/<int:pk>/cerrar-residual/', views.CxPCerrarSaldoResidualView.as_view(), name='cxp_cerrar_residual'),
    path('cxp/<int:pk>/pagar/', views.CxPPagarView.as_view(), name='cxp_pagar'),
    path('cxp/<int:pk>/anular/', views.AnularPagoCxPView.as_view(), name='cxp_anular'),
    # Asiento contable
    path('facturas/<int:pk>/asiento/', views.GenerarAsientoFacturaRecibidaView.as_view(), name='factura_asiento'),
    # Anticipos
    path('anticipos/', views.AnticipoListView.as_view(), name='anticipo_list'),
    path('anticipos/crear/', views.AnticipoCreateView.as_view(), name='anticipo_create'),
    path('anticipos/<int:pk>/editar/', views.AnticipoUpdateView.as_view(), name='anticipo_update'),
    path('anticipos/<int:pk>/eliminar/', views.AnticipoDeleteView.as_view(), name='anticipo_delete'),
    path('anticipos/<int:pk>/pagar/', views.AnticipoProveedorPagarView.as_view(), name='anticipo_pagar'),
]
