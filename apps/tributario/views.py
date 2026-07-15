from django.views.generic import ListView, CreateView, UpdateView, TemplateView
from django.views import View
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Prefetch
from django import forms
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from decimal import Decimal
from apps.core.mixins import GestionMixin, AppPermisoMixin

class TributarioMixin(AppPermisoMixin):
    app_name = 'tributario'

from apps.core.templatetags.custom_tags import moneda_chilena
from .models import RegistroCompra, RegistroVenta, DeclaracionIVA, PPM, FormularioF29


MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]


def _anio_choices():
    from django.utils import timezone
    anio = timezone.now().year
    return [(y, str(y)) for y in range(anio - 3, anio + 3)]


SELECT_MES = forms.Select(choices=[('' , '— Mes —')] + MESES,
                           attrs={'class': 'form-select'})


class IVAForm(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = DeclaracionIVA
        fields = ['periodo_mes', 'periodo_anio', 'iva_debito', 'iva_credito', 'estado', 'fecha_presentacion']
        widgets = {
            'iva_debito':        forms.NumberInput(attrs={'class': 'form-control'}),
            'iva_credito':       forms.NumberInput(attrs={'class': 'form-control'}),
            'estado':            forms.Select(attrs={'class': 'form-select'}),
            'fecha_presentacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = [
            ('borrador', 'Borrador'),
            ('presentado', 'Presentado'),
        ]


def _sincronizar_asiento_declaracion_iva(declaracion, usuario=None):
    from apps.contabilidad.utils import generar_asiento_declaracion_iva

    asiento_confirmado = declaracion.asientos.filter(
        tipo='centralizacion_iva',
        estado='confirmado',
    ).first()
    if asiento_confirmado:
        return asiento_confirmado

    declaracion.asientos.filter(
        tipo='centralizacion_iva',
        estado='borrador',
    ).delete()
    if declaracion.estado != 'presentado':
        return None

    return generar_asiento_declaracion_iva(declaracion, usuario=usuario)


def _sincronizar_asiento_ppm(ppm, usuario=None):
    from apps.contabilidad.utils import generar_asiento_devengamiento_ppm

    asiento_confirmado = ppm.asientos.filter(
        tipo='devengamiento_ppm',
        estado='confirmado',
    ).first()
    if asiento_confirmado:
        return asiento_confirmado

    ppm.asientos.filter(
        tipo='devengamiento_ppm',
        estado='borrador',
    ).delete()
    if ppm.estado != 'presentado':
        return None
    return generar_asiento_devengamiento_ppm(ppm, usuario=usuario)


def _f29_bloquea_cambio(periodo_mes, periodo_anio, campo, nuevo_valor):
    f29 = FormularioF29.objects.filter(
        periodo_mes=periodo_mes,
        periodo_anio=periodo_anio,
    ).first()
    if (
        f29
        and f29.estado in ['presentado', 'pagado']
        and getattr(f29, campo) != nuevo_valor
    ):
        return f29
    return None


def _actualizar_f29_pendiente(periodo_mes, periodo_anio, campo, valor):
    f29 = FormularioF29.objects.filter(
        periodo_mes=periodo_mes,
        periodo_anio=periodo_anio,
        estado='pendiente',
    ).first()
    if f29:
        setattr(f29, campo, valor)
        f29.save()
    return f29


class PPMForm(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = PPM
        fields = ['periodo_mes', 'periodo_anio', 'base_imponible', 'tasa', 'monto', 'estado']
        widgets = {
            'base_imponible': forms.NumberInput(attrs={'class': 'form-control'}),
            'tasa':           forms.NumberInput(attrs={'class': 'form-control', 'step': '0.0001'}),
            'monto':          forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'estado':         forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = [
            ('pendiente', 'Pendiente'),
            ('presentado', 'Presentado'),
        ]

    def clean(self):
        cleaned = super().clean()
        base = cleaned.get('base_imponible') or Decimal('0')
        tasa = cleaned.get('tasa') or Decimal('0')
        cleaned['monto'] = (base * tasa).quantize(Decimal('0.01'))
        return cleaned


class F29Form(forms.ModelForm):
    periodo_mes  = forms.ChoiceField(choices=MESES, widget=forms.Select(attrs={'class': 'form-select'}))
    periodo_anio = forms.ChoiceField(choices=_anio_choices, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = FormularioF29
        fields = ['periodo_mes', 'periodo_anio', 'iva_pagar', 'ppm_pagar', 'retenciones', 'estado', 'fecha_presentacion', 'folio']
        widgets = {
            'iva_pagar':          forms.NumberInput(attrs={'class': 'form-control'}),
            'ppm_pagar':          forms.NumberInput(attrs={'class': 'form-control'}),
            'retenciones':        forms.NumberInput(attrs={'class': 'form-control'}),
            'estado':             forms.Select(attrs={'class': 'form-select'}),
            'fecha_presentacion': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'folio':              forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['estado'].choices = [
            ('pendiente', 'Pendiente'),
            ('presentado', 'Presentado'),
        ]

    def clean(self):
        cleaned = super().clean()
        try:
            mes = int(cleaned.get('periodo_mes'))
            anio = int(cleaned.get('periodo_anio'))
        except (TypeError, ValueError):
            return cleaned

        iva_pagar = cleaned.get('iva_pagar') or Decimal('0')
        ppm_pagar = cleaned.get('ppm_pagar') or Decimal('0')

        if iva_pagar > 0:
            declaracion = DeclaracionIVA.objects.filter(
                periodo_mes=mes,
                periodo_anio=anio,
                estado='presentado',
            ).first()
            if not declaracion or declaracion.diferencia != iva_pagar:
                self.add_error(
                    'iva_pagar',
                    'El IVA debe coincidir con una declaración IVA presentada del período.',
                )

        if ppm_pagar > 0:
            ppm = PPM.objects.filter(
                periodo_mes=mes,
                periodo_anio=anio,
                estado='presentado',
            ).first()
            if not ppm or ppm.monto != ppm_pagar:
                self.add_error(
                    'ppm_pagar',
                    'El PPM debe coincidir con un PPM presentado del período.',
                )
        return cleaned


class TributarioResumenView(TributarioMixin, TemplateView):
    template_name = 'admin/tributario/resumen.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['iva_pendientes'] = DeclaracionIVA.objects.filter(estado='borrador').order_by('-periodo_anio', '-periodo_mes')
        ctx['ppm_pendientes'] = PPM.objects.filter(
            estado__in=['pendiente', 'presentado']
        ).order_by('-periodo_anio', '-periodo_mes')
        ctx['f29_pendientes'] = FormularioF29.objects.filter(
            estado__in=['pendiente', 'presentado']
        ).order_by('-periodo_anio', '-periodo_mes')
        ctx['titulo'] = 'Módulo Tributario'

        anio_actual = timezone.now().year
        debito = RegistroVenta.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('iva_debito'))['s'] or 0
        credito = RegistroCompra.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('iva_credito'))['s'] or 0
        ctx['total_iva_debito'] = debito
        ctx['total_iva_credito'] = credito
        ctx['diferencia_iva'] = debito - credito
        ctx['total_ppm'] = PPM.objects.filter(periodo_anio=anio_actual).aggregate(s=Sum('monto'))['s'] or 0


        return ctx


class RegistroCompraListView(TributarioMixin, ListView):
    model = RegistroCompra
    template_name = 'admin/tributario/compra_list.html'
    context_object_name = 'registros'
    paginate_by = 30

    def get_queryset(self):
        qs = RegistroCompra.objects.select_related('proveedor', 'factura', 'nota_credito')
        periodo = self.request.GET.get('periodo', '')
        try:
            anio, mes = map(int, periodo.split('-'))
            if not 1 <= mes <= 12:
                raise ValueError
        except (TypeError, ValueError):
            pass
        else:
            qs = qs.filter(periodo_mes=mes, periodo_anio=anio)
        return qs.order_by('-periodo_anio', '-periodo_mes')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registro de Compras'
        totales = self.get_queryset().aggregate(
            total_neto=Sum('neto'),
            total_iva_credito=Sum('iva_credito'),
            total_total=Sum('total'),
        )
        ctx.update(totales)
        return ctx


class RegistroVentaListView(TributarioMixin, ListView):
    model = RegistroVenta
    template_name = 'admin/tributario/venta_list.html'
    context_object_name = 'registros'
    paginate_by = 30

    def get_queryset(self):
        qs = RegistroVenta.objects.select_related('cliente', 'factura')
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes:
            qs = qs.filter(periodo_mes=mes)
        if anio:
            qs = qs.filter(periodo_anio=anio)
        return qs.order_by('-periodo_anio', '-periodo_mes')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Registro de Ventas'
        totales = self.get_queryset().aggregate(
            total_neto=Sum('neto'), total_iva=Sum('iva_debito'), total=Sum('total')
        )
        ctx.update(totales)
        return ctx


class DeclaracionIVAListView(TributarioMixin, ListView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_list.html'
    context_object_name = 'declaraciones'

    def get_queryset(self):
        from apps.contabilidad.models import AsientoContable

        return super().get_queryset().prefetch_related(
            Prefetch(
                'asientos',
                queryset=AsientoContable.objects.filter(
                    tipo='centralizacion_iva',
                ).exclude(estado='anulado').order_by('-id'),
                to_attr='asientos_centralizacion_activos',
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Declaraciones IVA'
        for declaracion in ctx['declaraciones']:
            declaracion.asiento_centralizacion = next(
                iter(declaracion.asientos_centralizacion_activos),
                None,
            )
        return ctx


class DeclaracionIVACreateView(TributarioMixin, CreateView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_form.html'
    form_class = IVAForm
    success_url = reverse_lazy('tributario:iva_list')

    def _calcular_periodo(self, mes, anio):
        debito = RegistroVenta.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('iva_debito'))['s'] or 0
        credito = RegistroCompra.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('iva_credito'))['s'] or 0
        return debito, credito

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                debito, credito = self._calcular_periodo(mes_int, anio_int)
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'iva_debito': debito,
                    'iva_credito': credito,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        iva_f29 = max(
            (form.instance.iva_debito or Decimal('0'))
            - (form.instance.iva_credito or Decimal('0')),
            Decimal('0'),
        ) if form.instance.estado == 'presentado' else Decimal('0')
        f29_bloqueado = _f29_bloquea_cambio(
            int(form.cleaned_data['periodo_mes']),
            int(form.cleaned_data['periodo_anio']),
            'iva_pagar',
            iva_f29,
        )
        if f29_bloqueado:
            form.add_error(
                'estado',
                f'El F29 del período está {f29_bloqueado.get_estado_display().lower()} '
                'y su IVA no puede modificarse.',
            )
            return self.form_invalid(form)

        if form.instance.estado == 'presentado' and not form.instance.fecha_presentacion:
            form.instance.fecha_presentacion = timezone.localdate()

        with transaction.atomic():
            self.object = form.save()
            asiento = _sincronizar_asiento_declaracion_iva(
                self.object,
                usuario=self.request.user,
            )
            _actualizar_f29_pendiente(
                self.object.periodo_mes,
                self.object.periodo_anio,
                'iva_pagar',
                self.object.diferencia if self.object.estado == 'presentado' else Decimal('0'),
            )

        if asiento:
            messages.success(
                self.request,
                f'Declaración IVA registrada. Se generó el asiento '
                f'{asiento.numero} en borrador.',
            )
        elif self.object.estado == 'presentado' and self.object.iva_debito > 0:
            messages.success(self.request, 'Declaración IVA registrada.')
            messages.warning(
                self.request,
                'No se pudo generar la centralización. Configure las cuentas de '
                'IVA Débito, IVA Crédito e Impuestos SII.',
            )
        else:
            messages.success(self.request, 'Declaración IVA registrada.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nueva Declaración IVA'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                debito, credito = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'debito': debito, 'credito': credito,
                    'diferencia': max(debito - credito, 0),
                }
            except (ValueError, TypeError):
                pass
        return ctx


class DeclaracionIVAUpdateView(TributarioMixin, UpdateView):
    model = DeclaracionIVA
    template_name = 'admin/tributario/iva_form.html'
    form_class = IVAForm
    success_url = reverse_lazy('tributario:iva_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado == 'pagado':
            messages.error(
                request,
                'No se puede editar una declaración cuyo F29 ya fue pagado.',
            )
            return redirect('tributario:iva_list')
        asiento_confirmado = self.object.asientos.filter(
            tipo='centralizacion_iva',
            estado='confirmado',
        ).first()
        if asiento_confirmado:
            messages.error(
                request,
                f'No se puede editar la declaración porque el asiento '
                f'{asiento_confirmado.numero} está confirmado. Anúlelo primero.',
            )
            return redirect('tributario:iva_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        iva_f29 = max(
            (form.instance.iva_debito or Decimal('0'))
            - (form.instance.iva_credito or Decimal('0')),
            Decimal('0'),
        ) if form.instance.estado == 'presentado' else Decimal('0')
        f29_bloqueado = _f29_bloquea_cambio(
            int(form.cleaned_data['periodo_mes']),
            int(form.cleaned_data['periodo_anio']),
            'iva_pagar',
            iva_f29,
        )
        if f29_bloqueado:
            form.add_error(
                'estado',
                f'El F29 del período está {f29_bloqueado.get_estado_display().lower()} '
                'y su IVA no puede modificarse.',
            )
            return self.form_invalid(form)

        if form.instance.estado == 'presentado' and not form.instance.fecha_presentacion:
            form.instance.fecha_presentacion = timezone.localdate()
        elif form.instance.estado == 'borrador':
            form.instance.fecha_presentacion = None

        with transaction.atomic():
            declaracion_bloqueada = DeclaracionIVA.objects.select_for_update().get(
                pk=self.object.pk
            )
            asiento_confirmado = declaracion_bloqueada.asientos.filter(
                tipo='centralizacion_iva',
                estado='confirmado',
            ).first()
            if asiento_confirmado:
                messages.error(
                    self.request,
                    f'El asiento {asiento_confirmado.numero} fue confirmado mientras '
                    'se editaba. No se guardaron los cambios.',
                )
                return redirect('tributario:iva_list')

            self.object = form.save()
            asiento = _sincronizar_asiento_declaracion_iva(
                self.object,
                usuario=self.request.user,
            )
            _actualizar_f29_pendiente(
                self.object.periodo_mes,
                self.object.periodo_anio,
                'iva_pagar',
                self.object.diferencia if self.object.estado == 'presentado' else Decimal('0'),
            )

        if asiento:
            messages.success(
                self.request,
                f'Declaración IVA actualizada. Se regeneró el asiento '
                f'{asiento.numero} en borrador.',
            )
        elif self.object.estado == 'presentado' and self.object.iva_debito > 0:
            messages.success(self.request, 'Declaración IVA actualizada.')
            messages.warning(
                self.request,
                'No se pudo generar la centralización. Revise la configuración contable.',
            )
        else:
            messages.success(self.request, 'Declaración IVA actualizada.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar Declaración IVA {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        ctx['asiento_centralizacion'] = self.object.asientos.filter(
            tipo='centralizacion_iva',
        ).exclude(estado='anulado').first()
        return ctx


class PPMListView(TributarioMixin, ListView):
    model = PPM
    template_name = 'admin/tributario/ppm_list.html'
    context_object_name = 'ppms'

    def get_queryset(self):
        from apps.contabilidad.models import AsientoContable

        return super().get_queryset().prefetch_related(
            Prefetch(
                'asientos',
                queryset=AsientoContable.objects.filter(
                    tipo='devengamiento_ppm',
                ).exclude(estado='anulado').order_by('-id'),
                to_attr='asientos_devengamiento_activos',
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'PPM'
        for ppm in ctx['ppms']:
            ppm.asiento_devengamiento = next(
                iter(ppm.asientos_devengamiento_activos),
                None,
            )
        return ctx


class PPMCreateView(TributarioMixin, CreateView):
    model = PPM
    template_name = 'admin/tributario/ppm_form.html'
    form_class = PPMForm
    success_url = reverse_lazy('tributario:ppm_list')

    def _calcular_periodo(self, mes, anio):
        base = RegistroVenta.objects.filter(
            periodo_mes=mes, periodo_anio=anio
        ).aggregate(s=Sum('neto'))['s'] or 0
        tasa = PPM._meta.get_field('tasa').default  # 0.0025
        monto = round(float(base) * float(tasa), 2)
        return base, monto

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                base, monto = self._calcular_periodo(mes_int, anio_int)
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'base_imponible': base,
                    'monto': monto,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        monto_f29 = (
            form.cleaned_data['monto']
            if form.instance.estado == 'presentado'
            else Decimal('0')
        )
        f29_bloqueado = _f29_bloquea_cambio(
            int(form.cleaned_data['periodo_mes']),
            int(form.cleaned_data['periodo_anio']),
            'ppm_pagar',
            monto_f29,
        )
        if f29_bloqueado:
            form.add_error(
                'estado',
                f'El F29 del período está {f29_bloqueado.get_estado_display().lower()} '
                'y su PPM no puede modificarse.',
            )
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            asiento = _sincronizar_asiento_ppm(
                self.object,
                usuario=self.request.user,
            )
            _actualizar_f29_pendiente(
                self.object.periodo_mes,
                self.object.periodo_anio,
                'ppm_pagar',
                self.object.monto if self.object.estado == 'presentado' else Decimal('0'),
            )

        if asiento:
            messages.success(
                self.request,
                f'PPM registrado. Se generó el asiento {asiento.numero} en borrador.',
            )
        elif self.object.estado == 'presentado':
            messages.success(self.request, 'PPM registrado.')
            messages.warning(
                self.request,
                'No se pudo generar el devengamiento. Configure PPM por Recuperar '
                'e Impuestos SII.',
            )
        else:
            messages.success(self.request, 'PPM registrado.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo PPM'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                base, monto = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'base': base, 'monto': monto,
                }
            except (ValueError, TypeError):
                pass
        return ctx

class PPMUpdateView(TributarioMixin, UpdateView):
    model = PPM
    template_name = 'admin/tributario/ppm_form.html'
    form_class = PPMForm
    success_url = reverse_lazy('tributario:ppm_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado == 'pagado':
            messages.error(request, 'No se puede editar un PPM pagado.')
            return redirect('tributario:ppm_list')
        asiento_confirmado = self.object.asientos.filter(
            tipo='devengamiento_ppm',
            estado='confirmado',
        ).first()
        if asiento_confirmado:
            messages.error(
                request,
                f'No se puede editar el PPM porque el asiento '
                f'{asiento_confirmado.numero} está confirmado. Anúlelo primero.',
            )
            return redirect('tributario:ppm_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        monto_f29 = (
            form.cleaned_data['monto']
            if form.instance.estado == 'presentado'
            else Decimal('0')
        )
        f29_bloqueado = _f29_bloquea_cambio(
            int(form.cleaned_data['periodo_mes']),
            int(form.cleaned_data['periodo_anio']),
            'ppm_pagar',
            monto_f29,
        )
        if f29_bloqueado:
            form.add_error(
                'estado',
                f'El F29 del período está {f29_bloqueado.get_estado_display().lower()} '
                'y su PPM no puede modificarse.',
            )
            return self.form_invalid(form)

        with transaction.atomic():
            ppm_bloqueado = PPM.objects.select_for_update().get(pk=self.object.pk)
            asiento_confirmado = ppm_bloqueado.asientos.filter(
                tipo='devengamiento_ppm',
                estado='confirmado',
            ).first()
            if asiento_confirmado:
                messages.error(
                    self.request,
                    f'El asiento {asiento_confirmado.numero} fue confirmado mientras '
                    'se editaba. No se guardaron los cambios.',
                )
                return redirect('tributario:ppm_list')
            self.object = form.save()
            asiento = _sincronizar_asiento_ppm(
                self.object,
                usuario=self.request.user,
            )
            _actualizar_f29_pendiente(
                self.object.periodo_mes,
                self.object.periodo_anio,
                'ppm_pagar',
                self.object.monto if self.object.estado == 'presentado' else Decimal('0'),
            )

        if asiento:
            messages.success(
                self.request,
                f'PPM actualizado. Se regeneró el asiento {asiento.numero} en borrador.',
            )
        elif self.object.estado == 'presentado':
            messages.success(self.request, 'PPM actualizado.')
            messages.warning(
                self.request,
                'No se pudo generar el devengamiento. Revise la configuración contable.',
            )
        else:
            messages.success(self.request, 'PPM actualizado.')
        return redirect(self.success_url)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar PPM {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        ctx['asiento_devengamiento'] = self.object.asientos.filter(
            tipo='devengamiento_ppm',
        ).exclude(estado='anulado').first()
        return ctx


class PPMPagarView(TributarioMixin, View):
    template_name = 'admin/tributario/ppm_pagar.html'

    @staticmethod
    def _f29_que_incluye(ppm):
        return FormularioF29.objects.filter(
            periodo_mes=ppm.periodo_mes,
            periodo_anio=ppm.periodo_anio,
            estado__in=['pendiente', 'presentado'],
            ppm_pagar__gt=0,
        ).first()

    def _build_form(self, data=None, initial=None):
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')

        class PagoPPMForm(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El pago al SII se descontará de esta cuenta.',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoPPMForm(data=data, initial=initial)

    def get(self, request, pk):
        ppm = get_object_or_404(PPM, pk=pk)
        if ppm.estado == 'pagado':
            messages.info(request, 'Este PPM ya fue pagado.')
            return redirect('tributario:ppm_list')
        if ppm.estado != 'presentado':
            messages.info(
                request,
                'Presente el PPM y confirme su asiento de devengamiento antes de pagarlo.',
            )
            return redirect('tributario:ppm_list')
        if not ppm.asientos.filter(
            tipo='devengamiento_ppm',
            estado='confirmado',
        ).exists():
            messages.info(
                request,
                'Confirme el asiento de devengamiento del PPM antes de registrar el pago.',
            )
            return redirect('tributario:ppm_list')
        f29 = self._f29_que_incluye(ppm)
        if f29:
            messages.info(
                request,
                f'El PPM está incluido en el F29 {f29.periodo_mes:02d}/{f29.periodo_anio}. '
                'Registre el pago desde el F29 para evitar duplicarlo.',
            )
            return redirect('tributario:f29_list')
        form = self._build_form(initial={'fecha_pago': timezone.now().date()})
        return render(request, self.template_name, {'ppm': ppm, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.utils import generar_asiento_movimiento_bancario
        from apps.contabilidad.models import ConfiguracionContable

        ppm = get_object_or_404(PPM, pk=pk)
        if ppm.estado == 'pagado':
            messages.error(request, 'Este PPM ya fue pagado.')
            return redirect('tributario:ppm_list')
        if ppm.estado != 'presentado' or not ppm.asientos.filter(
            tipo='devengamiento_ppm',
            estado='confirmado',
        ).exists():
            messages.error(
                request,
                'El PPM debe estar presentado y con su asiento confirmado antes del pago.',
            )
            return redirect('tributario:ppm_list')
        f29 = self._f29_que_incluye(ppm)
        if f29:
            messages.error(
                request,
                f'No se puede pagar este PPM por separado porque está incluido en el '
                f'F29 {f29.periodo_mes:02d}/{f29.periodo_anio}.',
            )
            return redirect('tributario:f29_list')
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'ppm': ppm, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']
        config = ConfiguracionContable.get()
        if not cuenta_bancaria.cuenta_contable_id or not config.cuenta_impuestos_sii_id:
            messages.error(
                request,
                'Configure la cuenta contable del banco y la cuenta Impuestos SII '
                'antes de registrar el pago.',
            )
            return render(request, self.template_name, {'ppm': ppm, 'form': form})

        with transaction.atomic():
            ppm = PPM.objects.select_for_update().get(pk=ppm.pk)
            if ppm.estado != 'presentado':
                messages.error(
                    request,
                    'El estado del PPM cambió mientras se registraba el pago.',
                )
                return redirect('tributario:ppm_list')

            # 1. Actualizar PPM
            ppm.estado = 'pagado'
            ppm.fecha_pago = d['fecha_pago']
            ppm.save()

            # 2. Crear MovimientoBancario (egreso)
            descripcion_mov = (
                f'PPM {ppm.periodo_mes:02d}/{ppm.periodo_anio} '
                f'- ${ppm.monto:,.0f}'
            )
            movimiento = MovimientoBancario.objects.create(
                cuenta=cuenta_bancaria,
                fecha=d['fecha_pago'],
                tipo='egreso',
                monto=ppm.monto,
                descripcion=descripcion_mov,
                cuenta_contable=config.cuenta_impuestos_sii,
            )

            # 3. Cancelar el pasivo con un asiento contable borrador.
            asiento = generar_asiento_movimiento_bancario(
                movimiento,
                usuario=request.user,
            )

        if asiento:
            messages.success(
                request,
                f'PPM pagado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'PPM pagado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('tributario:ppm_list')


class F29ListView(TributarioMixin, ListView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_list.html'
    context_object_name = 'f29s'

    def get_queryset(self):
        from django.db.models import DecimalField, F, OuterRef, Subquery, Value
        from django.db.models.functions import Coalesce, Greatest
        from apps.rrhh.models import Remuneracion

        impuestos_periodo = (
            Remuneracion.objects.filter(
                periodo_mes=OuterRef('periodo_mes'),
                periodo_anio=OuterRef('periodo_anio'),
                estado__in=['aprobado', 'pagado'],
            )
            .values('periodo_mes', 'periodo_anio')
            .annotate(total=Sum('impuesto_unico'))
            .values('total')
        )
        campo_monto = DecimalField(max_digits=15, decimal_places=2)
        queryset = super().get_queryset().annotate(
            impuesto_unico_remuneraciones=Coalesce(
                Subquery(impuestos_periodo, output_field=campo_monto),
                Value(Decimal('0')),
                output_field=campo_monto,
            )
        )
        return queryset.annotate(
            otras_retenciones=Greatest(
                F('retenciones') - F('impuesto_unico_remuneraciones'),
                Value(Decimal('0')),
                output_field=campo_monto,
            )
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Formularios F29'
        return ctx


class F29CreateView(TributarioMixin, CreateView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_form.html'
    form_class = F29Form
    success_url = reverse_lazy('tributario:f29_list')

    def _calcular_periodo(self, mes, anio):
        iva_pagar = 0
        try:
            decl = DeclaracionIVA.objects.get(
                periodo_mes=mes,
                periodo_anio=anio,
                estado='presentado',
            )
            iva_pagar = decl.diferencia
        except DeclaracionIVA.DoesNotExist:
            pass
        ppm_pagar = 0
        try:
            ppm = PPM.objects.get(
                periodo_mes=mes,
                periodo_anio=anio,
                estado='presentado',
            )
            ppm_pagar = ppm.monto
        except PPM.DoesNotExist:
            pass
        try:
            from apps.boletas.models import BoletaHonorarios
            retenciones = BoletaHonorarios.objects.filter(
                fecha_emision__month=mes,
                fecha_emision__year=anio,
            ).exclude(estado='anulada').aggregate(s=Sum('retencion'))['s'] or 0
        except Exception:
            retenciones = 0
        impuesto_remuneraciones = Decimal('0')
        try:
            from apps.rrhh.models import Remuneracion
            impuesto_remuneraciones = Remuneracion.objects.filter(
                periodo_mes=mes,
                periodo_anio=anio,
                estado__in=['aprobado', 'pagado'],
            ).aggregate(s=Sum('impuesto_unico'))['s'] or 0
            retenciones += impuesto_remuneraciones
        except Exception:
            pass
        return iva_pagar, ppm_pagar, retenciones, impuesto_remuneraciones

    def get_initial(self):
        initial = super().get_initial()
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                iva_pagar, ppm_pagar, retenciones, _ = self._calcular_periodo(
                    mes_int, anio_int
                )
                initial.update({
                    'periodo_mes': mes_int,
                    'periodo_anio': anio_int,
                    'iva_pagar': iva_pagar,
                    'ppm_pagar': ppm_pagar,
                    'retenciones': retenciones,
                })
            except (ValueError, TypeError):
                pass
        return initial

    def form_valid(self, form):
        messages.success(self.request, 'F29 registrado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = 'Nuevo Formulario F29'
        anio_actual = timezone.now().year
        ctx['anios_disponibles'] = list(range(anio_actual - 3, anio_actual + 3))
        mes = self.request.GET.get('mes')
        anio = self.request.GET.get('anio')
        if mes and anio:
            try:
                mes_int, anio_int = int(mes), int(anio)
                (
                    iva_pagar,
                    ppm_pagar,
                    retenciones,
                    impuesto_remuneraciones,
                ) = self._calcular_periodo(mes_int, anio_int)
                ctx['calculado'] = {
                    'mes': mes_int, 'anio': anio_int,
                    'iva_pagar': iva_pagar,
                    'ppm_pagar': ppm_pagar,
                    'retenciones': retenciones,
                    'impuesto_unico': impuesto_remuneraciones,
                    'total': float(iva_pagar) + float(ppm_pagar) + float(retenciones),
                    'tiene_iva': DeclaracionIVA.objects.filter(periodo_mes=mes_int, periodo_anio=anio_int).exists(),
                    'tiene_ppm': PPM.objects.filter(periodo_mes=mes_int, periodo_anio=anio_int).exists(),
                }
            except (ValueError, TypeError):
                pass
        return ctx


class F29UpdateView(TributarioMixin, UpdateView):
    model = FormularioF29
    template_name = 'admin/tributario/f29_form.html'
    form_class = F29Form
    success_url = reverse_lazy('tributario:f29_list')

    def dispatch(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.estado == 'pagado':
            messages.error(request, 'No se puede editar un F29 pagado.')
            return redirect('tributario:f29_list')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, 'F29 actualizado.')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['titulo'] = f'Editar F29 {self.object.periodo_mes:02d}/{self.object.periodo_anio}'
        return ctx


# ---------------------------------------------------------------------------
# Pago F29 con automatismo contable
# ---------------------------------------------------------------------------

class F29PagarView(TributarioMixin, View):
    template_name = 'admin/tributario/f29_pagar.html'

    def _build_form(self, data=None, initial=None):
        from apps.tesoreria.models import CuentaBancaria

        cuentas_bancarias = CuentaBancaria.objects.filter(activa=True).select_related('banco')        

        class PagoF29Form(forms.Form):
            fecha_pago = forms.DateField(
                widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
                label='Fecha de pago',
            )
            cuenta_bancaria = forms.ModelChoiceField(
                queryset=cuentas_bancarias,
                widget=forms.Select(attrs={'class': 'form-select'}),
                label='Cuenta bancaria de egreso',
                help_text='El pago al SII se descontará de esta cuenta.',
            )
            folio = forms.CharField(
                required=False, max_length=20,
                widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'N° folio SII'}),
                label='N° Folio (opcional)',
            )
            notas = forms.CharField(
                required=False,
                widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
                label='Notas',
            )

        return PagoF29Form(data=data, initial=initial)

    def get(self, request, pk):
        f29 = get_object_or_404(FormularioF29, pk=pk)
        if f29.estado == 'pagado':
            messages.info(request, 'Este F29 ya fue pagado.')
            return redirect('tributario:f29_list')
        if f29.estado != 'presentado':
            messages.info(request, 'Presente el F29 antes de registrar su pago.')
            return redirect('tributario:f29_list')
        form = self._build_form(initial={
            'fecha_pago': timezone.now().date(),
            'folio': f29.folio,
        })
        return render(request, self.template_name, {'f29': f29, 'form': form})

    def post(self, request, pk):
        from apps.tesoreria.models import MovimientoBancario
        from apps.contabilidad.models import ConfiguracionContable
        from apps.contabilidad.utils import generar_asiento_pago_f29

        f29 = get_object_or_404(FormularioF29, pk=pk)
        if f29.estado == 'pagado':
            messages.error(request, 'Este F29 ya fue pagado.')
            return redirect('tributario:f29_list')
        if f29.estado != 'presentado':
            messages.error(request, 'El F29 debe estar presentado antes de pagarlo.')
            return redirect('tributario:f29_list')
        ppm_periodo = PPM.objects.filter(
            periodo_mes=f29.periodo_mes,
            periodo_anio=f29.periodo_anio,
        ).first()
        if ppm_periodo and ppm_periodo.estado == 'pagado' and f29.ppm_pagar > 0:
            messages.error(
                request,
                'El PPM de este período ya fue pagado por separado. Ajuste el PPM del '
                'F29 a $0 antes de registrar el pago para evitar duplicarlo.',
            )
            return redirect('tributario:f29_list')
        form = self._build_form(data=request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {'f29': f29, 'form': form})

        d = form.cleaned_data
        cuenta_bancaria = d['cuenta_bancaria']
        config = ConfiguracionContable.get()
        if f29.iva_pagar > 0:
            declaracion = DeclaracionIVA.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado='presentado',
            ).first()
            if not declaracion or not declaracion.asientos.filter(
                tipo='centralizacion_iva',
                estado='confirmado',
            ).exists():
                messages.error(
                    request,
                    'La declaración IVA debe estar presentada y con su centralización '
                    'confirmada antes de pagar el F29.',
                )
                return redirect('tributario:f29_list')
        if f29.ppm_pagar > 0:
            ppm_presentado = PPM.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado='presentado',
            ).first()
            if not ppm_presentado or not ppm_presentado.asientos.filter(
                tipo='devengamiento_ppm',
                estado='confirmado',
            ).exists():
                messages.error(
                    request,
                    'El PPM debe estar presentado y con su devengamiento confirmado '
                    'antes de pagar el F29.',
                )
                return redirect('tributario:f29_list')
        if not cuenta_bancaria.cuenta_contable_id:
            messages.error(request, 'La cuenta bancaria no tiene una cuenta contable asociada.')
            return render(request, self.template_name, {'f29': f29, 'form': form})
        if f29.total_pagar <= 0:
            messages.error(request, 'El F29 no tiene un monto positivo pendiente de pago.')
            return render(request, self.template_name, {'f29': f29, 'form': form})
        if f29.total_pagar > 0 and not config.cuenta_impuestos_sii_id:
            messages.error(request, 'Configure la cuenta Impuestos SII antes de pagar el F29.')
            return render(request, self.template_name, {'f29': f29, 'form': form})

        with transaction.atomic():
            f29 = FormularioF29.objects.select_for_update().get(pk=f29.pk)
            if f29.estado != 'presentado':
                messages.error(
                    request,
                    'El estado del F29 cambió mientras se registraba el pago.',
                )
                return redirect('tributario:f29_list')

            # 1. Actualizar F29
            f29.estado = 'pagado'
            f29.fecha_presentacion = d['fecha_pago']
            if d['folio']:
                f29.folio = d['folio']
            f29.save()

            # 2. Crear MovimientoBancario (egreso)
            descripcion_mov = (
                f'Pago F29 {f29.periodo_mes:02d}/{f29.periodo_anio} '
                f'(IVA: ${f29.iva_pagar:,.0f} | PPM: ${f29.ppm_pagar:,.0f})'
            )
            movimiento = MovimientoBancario.objects.create(
                cuenta=cuenta_bancaria,
                fecha=d['fecha_pago'],
                tipo='egreso',
                monto=f29.total_pagar,
                descripcion=descripcion_mov[:300],
                cuenta_contable=config.cuenta_impuestos_sii,
                documento=f29.folio[:50] if f29.folio else '',
            )

            # 3. Cancelar el pasivo tributario con un asiento de pago.
            asiento = generar_asiento_pago_f29(
                f29,
                movimiento,
                usuario=request.user,
            )
            DeclaracionIVA.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado='presentado',
            ).update(estado='pagado')
            PPM.objects.filter(
                periodo_mes=f29.periodo_mes,
                periodo_anio=f29.periodo_anio,
                estado='presentado',
            ).update(
                estado='pagado',
                fecha_pago=d['fecha_pago'],
            )

        if asiento:
            messages.success(
                request,
                f'Pago F29 registrado. Movimiento bancario creado y asiento {asiento.numero} generado en borrador.'
            )
        else:
            messages.success(request, 'Pago F29 registrado y movimiento bancario creado.')
            messages.warning(
                request,
                'No se pudo generar el asiento contable. '
                'Verifique que la cuenta bancaria y la Configuración Contable tengan cuentas asignadas.'
            )

        return redirect('tributario:f29_list')
