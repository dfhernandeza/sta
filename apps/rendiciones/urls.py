from django.urls import path
from . import views

app_name = 'rendiciones'

urlpatterns = [
    path('', views.RendicionGastosListView.as_view(), name='rendicion_list'),
    path('crear/', views.RendicionGastosCreateView.as_view(), name='rendicion_create'),
    path('<int:pk>/', views.RendicionGastosDetailView.as_view(), name='rendicion_detail'),
    path('<int:pk>/asiento/', views.GenerarAsientoRendicionView.as_view(), name='rendicion_asiento'),
]
