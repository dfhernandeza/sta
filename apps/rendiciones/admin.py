from django.contrib import admin
from .models import RendicionGastos, DetalleRendicion


class DetalleRendicionInline(admin.TabularInline):
    model = DetalleRendicion
    extra = 0


@admin.register(RendicionGastos)
class RendicionGastosAdmin(admin.ModelAdmin):
    list_display = ['indice_rendicion', 'trabajador', 'fecha', 'estado', 'motivo_del_gasto']
    list_filter = ['estado']
    search_fields = ['trabajador__nombre_completo', 'motivo_del_gasto']
    inlines = [DetalleRendicionInline]
