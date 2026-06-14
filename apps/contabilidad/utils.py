"""
Utilidades para la generación semi-automática de asientos contables.
Todas las funciones devuelven un AsientoContable en estado 'borrador',
o None si falta la configuración necesaria.
"""
from decimal import Decimal
from django.utils import timezone
from .models import ConfiguracionContable, AsientoContable, LineaAsiento


def get_config():
    """Devuelve la ConfiguracionContable (singleton) o None si no existe."""
    try:
        return ConfiguracionContable.objects.get(pk=1)
    except ConfiguracionContable.DoesNotExist:
        return None


def _add_linea(asiento, cuenta, debe=0, haber=0, descripcion='', orden=0):
    """Helper para crear una LineaAsiento."""
    return LineaAsiento.objects.create(
        asiento=asiento,
        cuenta=cuenta,
        debe=Decimal(str(debe)),
        haber=Decimal(str(haber)),
        descripcion=descripcion,
        orden=orden,
    )


def generar_asiento_factura_emitida(factura, usuario=None):
    """
    Genera el asiento de reconocimiento de una factura de venta:
        DEBE  : cuenta_cxc          = factura.total
        HABER : cuenta por detalle  = subtotal (o cuenta_ventas_default si no tiene)
        HABER : cuenta_iva_debito   = factura.iva
    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    if not config or not config.cuenta_cxc or not config.cuenta_iva_debito:
        return None

    asiento = AsientoContable.objects.create(
        fecha=factura.fecha_emision,
        descripcion=f'Factura emitida N° {factura.numero} – {factura.cliente.razon_social}',
        tipo='factura_venta',
        estado='borrador',
        factura_emitida=factura,
        creado_por=usuario,
    )

    # Línea DEBE: CxC por total
    _add_linea(asiento, config.cuenta_cxc, debe=factura.total,
               descripcion=f'CxC Factura {factura.numero}', orden=1)

    # Líneas HABER: ingresos por detalle
    orden = 10
    detalles = factura.detalles.select_related('cuenta_contable').all()
    subtotal_asignado = Decimal('0.00')
    for det in detalles:
        subtotal = (det.cantidad * det.precio_unitario).quantize(Decimal('0.01'))
        cuenta_ingreso = det.cuenta_contable or config.cuenta_ventas_default
        _add_linea(asiento, cuenta_ingreso, haber=subtotal,
                   descripcion=det.descripcion[:200], orden=orden)
        subtotal_asignado += subtotal
        orden += 1

    # Si no hay detalles o quedó diferencia vs neto, asignar a ventas_default
    diferencia_neto = (factura.neto - subtotal_asignado).quantize(Decimal('0.01'))
    if diferencia_neto != Decimal('0.00'):
        _add_linea(asiento, config.cuenta_ventas_default, haber=diferencia_neto,
                   descripcion='Ingresos s/n detalle', orden=orden)

    # Línea HABER: IVA Débito Fiscal
    _add_linea(asiento, config.cuenta_iva_debito, haber=factura.iva,
               descripcion='IVA Débito Fiscal', orden=orden + 1)

    return asiento


def generar_asiento_factura_recibida(factura, usuario=None):
    """
    Genera el asiento de reconocimiento de una factura de compra:
        DEBE  : cuenta por detalle  = monto (o cuenta_compras_default si no tiene)
        DEBE  : cuenta_iva_credito  = factura.iva
        HABER : cuenta_cxp          = factura.total
    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    if not config or not config.cuenta_cxp or not config.cuenta_iva_credito:
        return None

    if factura.pago_por_trabajador:
        descripcion_asiento = (
            f'Factura recibida N° {factura.numero} pagada por trabajador '
            f'{factura.pago_por_trabajador.nombre_completo}'
        )
        descripcion_cxp = f'CxP Reembolso {factura.pago_por_trabajador.nombre_completo}'
    else:
        descripcion_asiento = f'Factura recibida N° {factura.numero} – {factura.proveedor.razon_social}'
        descripcion_cxp = f'CxP Factura {factura.numero}'

    asiento = AsientoContable.objects.create(
        fecha=factura.fecha_emision,
        descripcion=descripcion_asiento,
        tipo='factura_compra',
        estado='borrador',
        factura_recibida=factura,
        creado_por=usuario,
    )

    # Líneas DEBE: costos/gastos por detalle (afectos y exentos a sus propias cuentas)
    orden = 1
    detalles = factura.detalles.select_related('cuenta_contable').all()
    afecto_asignado = Decimal('0.00')   # solo acumula líneas afectas a IVA
    for det in detalles:
        subtotal = (det.cantidad * det.precio_unitario).quantize(Decimal('0.01'))
        cuenta_costo = det.cuenta_contable or config.cuenta_compras_default
        _add_linea(asiento, cuenta_costo, debe=subtotal,
                   descripcion=det.descripcion[:200], orden=orden)
        if not det.exento_iva:
            afecto_asignado += subtotal
        orden += 1

    # Diferencia vs neto AFECTO (factura.neto no incluye exentos)
    diferencia_neto = (factura.neto - afecto_asignado).quantize(Decimal('0.01'))
    if diferencia_neto != Decimal('0.00'):
        _add_linea(asiento, config.cuenta_compras_default, debe=diferencia_neto,
                   descripcion='Costo s/n detalle', orden=orden)
        orden += 1

    # Línea DEBE: IVA Crédito Fiscal
    _add_linea(asiento, config.cuenta_iva_credito, debe=factura.iva,
               descripcion='IVA Crédito Fiscal', orden=orden)

    # Línea HABER: CxP por total
    _add_linea(asiento, config.cuenta_cxp, haber=factura.total,
               descripcion=descripcion_cxp, orden=orden + 1)

    return asiento

def generar_asiento_rendicion_gastos_recibida(rendicion, usuario=None):
    """
    Genera el asiento de reconocimiento de una rendición de gastos:
        DEBE  : cuenta por detalle  = monto
        HABER : cuenta_cxp          = monto total
    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    if not config or not config.cuenta_cxp:
        return None

    asiento = AsientoContable.objects.create(
        fecha=timezone.now().date(),
        descripcion=f'Rendición de Gastos N° {rendicion.id} – {rendicion.trabajador.nombre_completo}',
        tipo='rendicion_gastos',
        estado='borrador',
        rendicion_gastos=rendicion,
        creado_por=usuario,
    )

    # Líneas DEBE: gastos por detalle
    orden = 1
    detalles = rendicion.detalles.select_related('centro_costo', 'cuenta_contable').all()
    monto_total = Decimal('0.00')
    for det in detalles:
        _add_linea(asiento, det.cuenta_contable, debe=det.monto,
                   descripcion=det.descripcion[:200], orden=orden)
        monto_total += det.monto
        orden += 1

    # Línea HABER: CxP por total
    _add_linea(asiento, config.cuenta_cxp, haber=monto_total,
               descripcion=f'CxP Rendición Gastos {rendicion.id}', orden=orden)

    return asiento


def generar_asiento_movimiento_bancario(movimiento, usuario=None):
    """
    Genera el asiento de un movimiento bancario:
        Ingreso: DEBE cuenta_bancaria.cuenta_contable / HABER movimiento.cuenta_contable
        Egreso : DEBE movimiento.cuenta_contable    / HABER cuenta_bancaria.cuenta_contable
    Retorna el AsientoContable creado (borrador) o None.
    """
    cuenta_banco = movimiento.cuenta.cuenta_contable
    cuenta_contrapartida = movimiento.cuenta_contable

    if not cuenta_banco or not cuenta_contrapartida:
        return None

    tipo_label = movimiento.get_tipo_display()
    asiento = AsientoContable.objects.create(
        fecha=movimiento.fecha,
        descripcion=f'{tipo_label} bancario: {movimiento.descripcion[:200]}',
        tipo='movimiento_banco',
        estado='borrador',
        movimiento_bancario=movimiento,
        creado_por=usuario,
    )

    if movimiento.tipo == 'ingreso':
        _add_linea(asiento, cuenta_banco, debe=movimiento.monto,
                   descripcion='Ingreso banco', orden=1)
        _add_linea(asiento, cuenta_contrapartida, haber=movimiento.monto,
                   descripcion=movimiento.descripcion[:200], orden=2)
    else:  # egreso
        _add_linea(asiento, cuenta_contrapartida, debe=movimiento.monto,
                   descripcion=movimiento.descripcion[:200], orden=1)
        _add_linea(asiento, cuenta_banco, haber=movimiento.monto,
                   descripcion='Pago banco', orden=2)

    return asiento
