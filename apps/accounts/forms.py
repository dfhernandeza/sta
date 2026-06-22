from django.contrib.auth.forms import UserCreationForm, UserChangeForm, SetPasswordForm
from django import forms
from .models import CustomUser

APPS_DISPONIBLES = [
    ('dashboard', 'Dashboard'),
    ('contabilidad', 'Contabilidad'),
    ('tesoreria', 'Tesorería'),
    ('clientes', 'Clientes'),
    ('proveedores', 'Proveedores'),
    ('proyectos', 'Proyectos'),
    ('rendiciones', 'Rendiciones'),
    ('rrhh', 'Recursos Humanos'),
    ('tributario', 'Tributario'),
]


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'cargo', 'telefono')


class CustomUserChangeForm(UserChangeForm):
    password = None  # No mostrar campo de contraseña en edición general

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'rol', 'cargo', 'telefono', 'avatar', 'is_active')


class UsuarioPermisosForm(forms.ModelForm):
    app_permisos = forms.MultipleChoiceField(
        choices=APPS_DISPONIBLES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Acceso a módulos',
    )

    class Meta:
        model = CustomUser
        fields = ('app_permisos',)

    def clean_app_permisos(self):
        return self.cleaned_data.get('app_permisos', [])


class UsuarioSetPasswordForm(SetPasswordForm):
    """Formulario para que el superusuario cambie la contraseña de otro usuario."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
