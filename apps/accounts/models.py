from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('gerente', 'Gerente'),
        ('contador', 'Contador'),
        ('rrhh', 'Recursos Humanos'),
        ('tesorero', 'Tesorero'),
        ('vendedor', 'Vendedor'),
        ('operador', 'Operador'),
        ('solo_lectura', 'Solo Lectura'),
    ]

    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='operador', verbose_name='Rol')
    cargo = models.CharField(max_length=100, blank=True, verbose_name='Cargo')
    telefono = models.CharField(max_length=20, blank=True, verbose_name='Teléfono')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True, verbose_name='Avatar')
    app_permisos = models.JSONField(default=list, blank=True, verbose_name='Permisos de aplicaciones')

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.get_full_name() or self.username} ({self.get_rol_display()})'

    @property
    def nombre_display(self):
        return self.get_full_name() or self.username
