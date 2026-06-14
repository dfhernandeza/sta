from django.contrib.auth.mixins import LoginRequiredMixin as DjangoLoginRequired
from django.contrib import messages


class BootstrapFormMixin:
    """
    Inyecta las clases Bootstrap 5 en todos los widgets del form
    automáticamente, sin necesidad de modificar cada views.py ni forms.py.
    Se activa solo cuando la vista tiene un form (CreateView, UpdateView, etc.).
    """

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            widget = field.widget
            existing = widget.attrs.get('class', '')
            wtype = type(widget).__name__

            if wtype == 'CheckboxInput':
                css = 'form-check-input'
            elif 'Select' in wtype:
                css = 'form-select'
            elif wtype == 'Textarea':
                css = 'form-control'
                if 'rows' not in widget.attrs:
                    widget.attrs['rows'] = 3
            elif wtype == 'DateInput':
                css = 'form-control'
                widget.attrs.setdefault('type', 'date')
            elif wtype == 'DateTimeInput':
                css = 'form-control'
                widget.attrs.setdefault('type', 'datetime-local')
            elif wtype == 'NumberInput':
                css = 'form-control'
            elif wtype == 'EmailInput':
                css = 'form-control'
            elif wtype == 'PasswordInput':
                css = 'form-control'
            elif wtype == 'FileInput':
                css = 'form-control'
            else:
                css = 'form-control'

            if css not in existing:
                widget.attrs['class'] = (existing + ' ' + css).strip()
        return form


class LoginRequiredMixin(DjangoLoginRequired, BootstrapFormMixin):
    """Mixin que redirige al login de gestion/ si no está autenticado."""
    login_url = '/gestion/login/'


class GestionMixin(LoginRequiredMixin):
    """Mixin base para todas las vistas del panel de gestión."""
    pass
