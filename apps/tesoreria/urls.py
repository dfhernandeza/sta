from django.urls import path
from . import views

app_name = 'tesoreria'

urlpatterns = [
    path('', views.TesoreriaResumenView.as_view(), name='resumen'),
    path('bancos/', views.BancoListView.as_view(), name='banco_list'),
    path('bancos/crear/', views.BancoCreateView.as_view(), name='banco_create'),
    path('bancos/<int:pk>/editar/', views.BancoUpdateView.as_view(), name='banco_update'),
    path('cuentas/', views.CuentaBancariaListView.as_view(), name='cuenta_list'),
    path('cuentas/crear/', views.CuentaBancariaCreateView.as_view(), name='cuenta_create'),
    path('cuentas/<int:pk>/editar/', views.CuentaBancariaUpdateView.as_view(), name='cuenta_update'),
    path('movimientos/', views.MovimientoListView.as_view(), name='movimiento_list'),
    path('movimientos/crear/', views.MovimientoCreateView.as_view(), name='movimiento_create'),
    path('movimientos/<int:pk>/editar/', views.MovimientoUpdateView.as_view(), name='movimiento_update'),
    path('movimientos/<int:pk>/eliminar/', views.MovimientoDeleteView.as_view(), name='movimiento_delete'),
    path('movimientos/<int:pk>/conciliar/', views.MovimientoConciliarView.as_view(), name='movimiento_conciliar'),
    path('movimientos/<int:pk>/desconciliar/', views.MovimientoDesconciliarView.as_view(), name='movimiento_desconciliar'),
    path('movimientos/<int:pk>/asiento/', views.GenerarAsientoMovimientoView.as_view(), name='movimiento_asiento'),
]
