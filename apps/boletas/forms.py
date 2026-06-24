from django import forms

from .models import BoletaHonorarios, PrestadorHonorarios


class PrestadorHonorariosForm(forms.ModelForm):
    class Meta:
        model = PrestadorHonorarios
        fields = [
            'rut', 'nombre', 'giro', 'direccion', 'comuna', 'ciudad', 'telefono', 'email',
            'banco', 'tipo_cuenta', 'numero_cuenta', 'activo', 'notas',
        ]
        widgets = {
            'rut': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'giro': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.TextInput(attrs={'class': 'form-control'}),
            'comuna': forms.TextInput(attrs={'class': 'form-control'}),
            'ciudad': forms.TextInput(attrs={'class': 'form-control'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'banco': forms.Select(attrs={'class': 'form-select'}),
            'tipo_cuenta': forms.Select(attrs={'class': 'form-select'}),
            'numero_cuenta': forms.TextInput(attrs={'class': 'form-control'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BoletaHonorariosForm(forms.ModelForm):
    class Meta:
        model = BoletaHonorarios
        fields = [
            'numero', 'fecha_emision', 'fecha_vencimiento', 'prestador', 'proyecto',
            'centro_costo', 'cuenta_contable', 'descripcion', 'bruto', 'tasa_retencion',
            'estado', 'observaciones',
        ]
        widgets = {
            'numero': forms.TextInput(attrs={'class': 'form-control'}),
            'fecha_emision': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'fecha_vencimiento': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}, format='%Y-%m-%d'),
            'prestador': forms.Select(attrs={'class': 'form-select'}),
            'proyecto': forms.Select(attrs={'class': 'form-select'}),
            'centro_costo': forms.Select(attrs={'class': 'form-select'}),
            'cuenta_contable': forms.Select(attrs={'class': 'form-select'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control'}),
            'bruto': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'tasa_retencion': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001', 'min': '0'}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cuenta_contable'].queryset = self.fields['cuenta_contable'].queryset.filter(
            tipo__in=['gasto', 'costo'], nivel=4
        )
        self.fields['prestador'].queryset = self.fields['prestador'].queryset.filter(activo=True)
