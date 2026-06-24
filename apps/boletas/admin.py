from django.contrib import admin

from .models import BoletaHonorarios, PrestadorHonorarios


@admin.register(PrestadorHonorarios)
class PrestadorHonorariosAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'rut', 'email', 'activo']
    search_fields = ['nombre', 'rut']
    list_filter = ['activo']


@admin.register(BoletaHonorarios)
class BoletaHonorariosAdmin(admin.ModelAdmin):
    list_display = ['indice_honorarios', 'numero', 'prestador', 'fecha_emision', 'bruto', 'retencion', 'liquido', 'estado']
    search_fields = ['numero', 'prestador__nombre', 'prestador__rut']
    list_filter = ['estado']
