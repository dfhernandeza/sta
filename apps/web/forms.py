from django import forms
from .models import ContactoMensaje


class ContactoForm(forms.ModelForm):
    class Meta:
        model = ContactoMensaje
        fields = ['nombre', 'empresa', 'email', 'telefono', 'mensaje']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Su nombre'}),
            'empresa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Empresa (opcional)'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+56 9 XXXX XXXX'}),
            'mensaje': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Cuéntenos sobre su proyecto...'}),
        }
