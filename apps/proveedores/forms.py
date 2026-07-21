from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import DetalleOrdenCompra, OrdenCompra


class OrdenCompraForm(forms.ModelForm):
    class Meta:
        model = OrdenCompra
        fields = [
            'fecha', 'proyecto', 'centro_costo', 'proveedor', 'descuento',
            'observaciones', 'condiciones_comerciales',
        ]
        widgets = {
            'fecha': forms.DateInput(attrs={'type': 'date'}),
            'descuento': forms.NumberInput(attrs={'min': '0', 'step': '1'}),
            'observaciones': forms.Textarea(attrs={'rows': 3}),
            'condiciones_comerciales': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_descuento(self):
        descuento = self.cleaned_data.get('descuento') or Decimal('0')
        if descuento < 0:
            raise forms.ValidationError('El descuento no puede ser negativo.')
        return descuento


class DetalleOrdenCompraForm(forms.ModelForm):
    class Meta:
        model = DetalleOrdenCompra
        fields = ['codigo', 'descripcion', 'cantidad', 'unidad_medida', 'precio_unitario']
        widgets = {
            'codigo': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0.0001', 'step': '0.0001'}),
            'unidad_medida': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'precio_unitario': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0', 'step': '0.0001'}),
        }

    def clean_cantidad(self):
        cantidad = self.cleaned_data.get('cantidad')
        if cantidad is not None and cantidad <= 0:
            raise forms.ValidationError('La cantidad debe ser mayor que cero.')
        return cantidad


DetalleOrdenCompraFormSet = inlineformset_factory(
    OrdenCompra, DetalleOrdenCompra, form=DetalleOrdenCompraForm,
    extra=1, can_delete=True, min_num=1, validate_min=True,
)
