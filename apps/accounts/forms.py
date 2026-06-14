from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django import forms
from .models import CustomUser


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'cargo', 'telefono')


class CustomUserChangeForm(UserChangeForm):
    password = None  # No mostrar campo de contraseña en edición general

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'cargo', 'telefono', 'avatar', 'is_active')
