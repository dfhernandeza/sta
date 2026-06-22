from django.urls import path
from . import views

app_name = 'contabilidad'

urlpatterns = [
    # Plan de Cuentas
    path('', views.PlanCuentasListView.as_view(), name='plan_list'),
    path('crear/', views.PlanCuentasCreateView.as_view(), name='plan_create'),
    path('<int:pk>/editar/', views.PlanCuentasUpdateView.as_view(), name='plan_update'),
    path('<int:pk>/eliminar/', views.PlanCuentasDeleteView.as_view(), name='plan_delete'),

    # Configuración Contable
    path('configuracion/', views.ConfiguracionContableView.as_view(), name='configuracion'),

    # Libro Diario
    path('diario/', views.LibroDiarioListView.as_view(), name='diario_list'),
    path('diario/crear/', views.AsientoCreateView.as_view(), name='asiento_create'),
    path('diario/<int:pk>/', views.AsientoDetailView.as_view(), name='asiento_detail'),
    path('diario/<int:pk>/editar/', views.AsientoUpdateView.as_view(), name='asiento_update'),
    path('diario/<int:pk>/confirmar/', views.AsientoConfirmarView.as_view(), name='asiento_confirmar'),
    path('diario/<int:pk>/anular/', views.AsientoAnularView.as_view(), name='asiento_anular'),
    path('diario/<int:pk>/eliminar/', views.AsientoDeleteView.as_view(), name='asiento_delete'),
    path('diario/exportar/', views.AsientosExcelView.as_view(), name='diario_export'),

    # Reportes
    path('mayor/', views.LibroMayorView.as_view(), name='libro_mayor'),
    path('balance-comprobacion/', views.BalanceComprobacionView.as_view(), name='balance_comprobacion'),
    path('balance-general/', views.BalanceGeneralView.as_view(), name='balance_general'),
    path('estado-resultados/', views.EstadoResultadosView.as_view(), name='estado_resultados'),

    # Centros de Costo
    path('centros/', views.CentroCostoListView.as_view(), name='centro_list'),
    path('centros/crear/', views.CentroCostoCreateView.as_view(), name='centro_create'),
    path('centros/<int:pk>/editar/', views.CentroCostoUpdateView.as_view(), name='centro_update'),
    path('centros/reporte/', views.InformeCentroCostoView.as_view(), name='centro_reporte'),
    path('centros/<int:pk>/detalle/', views.CentroCostoDetalleView.as_view(), name='centro_detalle'),

    # Saldos de Apertura
    path('apertura/', views.AperturaContableView.as_view(), name='apertura'),
]
