from django.contrib import admin

from .models import Trabajador


@admin.register(Trabajador)
class TrabajadorAdmin(admin.ModelAdmin):
    list_display = (
        'rut',
        'nombre_completo',
        'usuario',
        'estado',
        'email',
    )
    list_filter = ('estado',)
    search_fields = (
        'rut',
        'nombres',
        'apellidos',
        'email',
        'usuario__username',
        'usuario__email',
    )
    list_select_related = ('usuario',)
