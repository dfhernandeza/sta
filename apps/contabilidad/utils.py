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


def generar_asiento_pago_anticipo(anticipo, movimiento, usuario=None):
    """
    Genera el asiento de pago de un anticipo laboral:

        DEBE : Anticipos a Trabajadores (activo)             = anticipo.monto
        HABER: Banco (cuenta_contable de la CuentaBancaria)  = anticipo.monto

    El anticipo se registra como un activo (por cobrar al trabajador) en vez de un gasto.
    El gasto se reconoce al descontarlo de la remuneración en generar_asiento_pago_remuneracion.

    Si cuenta_anticipos_trabajadores no está configurada, hace fallback a
    generar_asiento_movimiento_bancario() para mantener compatibilidad.

    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    cuenta_banco = movimiento.cuenta.cuenta_contable

    if not config or not cuenta_banco:
        return None

    if not config.cuenta_anticipos_trabajadores:
        return generar_asiento_movimiento_bancario(movimiento, usuario=usuario)

    descripcion = f'Anticipo {anticipo.trabajador.nombre_completo} — {anticipo.fecha}'
    asiento = AsientoContable.objects.create(
        fecha=movimiento.fecha,
        descripcion=descripcion,
        tipo='pago_anticipo',
        estado='borrador',
        movimiento_bancario=movimiento,
        creado_por=usuario,
    )

    # DEBE: Anticipos a Trabajadores (activo — el trabajador nos debe este monto)
    _add_linea(asiento, config.cuenta_anticipos_trabajadores, debe=anticipo.monto,
               descripcion=f'Anticipo por descontar — {anticipo.trabajador.nombre_completo}',
               orden=1)

    # HABER: Banco (salida de efectivo)
    _add_linea(asiento, cuenta_banco, haber=anticipo.monto,
               descripcion='Pago banco (anticipo)', orden=2)

    return asiento


def generar_asiento_pago_anticipo_proveedor(anticipo, movimiento, usuario=None):
    """
    Genera el asiento de pago de un anticipo a proveedor:

        DEBE : Anticipos a Proveedores (activo)              = anticipo.monto
        HABER: Banco (cuenta_contable de la CuentaBancaria)  = anticipo.monto

    El anticipo se registra como activo (el proveedor nos debe bienes/servicios).
    Cuando el proveedor entrega la factura y se aplica el anticipo, la CxP se reduce
    manualmente vía movimiento bancario usando esta misma cuenta como contrapartida.

    Si cuenta_anticipos_proveedores no está configurada, hace fallback a
    generar_asiento_movimiento_bancario() para mantener compatibilidad.

    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    cuenta_banco = movimiento.cuenta.cuenta_contable

    if not config or not cuenta_banco:
        return None

    if not config.cuenta_anticipos_proveedores:
        return generar_asiento_movimiento_bancario(movimiento, usuario=usuario)

    descripcion = f'Anticipo {anticipo.proveedor.razon_social} — {anticipo.fecha}'
    asiento = AsientoContable.objects.create(
        fecha=movimiento.fecha,
        descripcion=descripcion,
        tipo='pago_anticipo_proveedor',
        estado='borrador',
        movimiento_bancario=movimiento,
        creado_por=usuario,
    )

    # DEBE: Anticipos a Proveedores (activo — el proveedor nos debe entrega)
    _add_linea(asiento, config.cuenta_anticipos_proveedores, debe=anticipo.monto,
               descripcion=f'Anticipo por aplicar — {anticipo.proveedor.razon_social}',
               orden=1)

    # HABER: Banco (salida de efectivo)
    _add_linea(asiento, cuenta_banco, haber=anticipo.monto,
               descripcion='Pago banco (anticipo proveedor)', orden=2)

    return asiento


def generar_asiento_devengamiento_remuneracion(remuneracion, usuario=None):
    """
    Genera el asiento de DEVENGAMIENTO al crear/liquidar una remuneración (base devengada):

        DEBE : Gasto Sueldos (operacional o administrativo)  = sueldo_bruto
        HABER: AFP por Pagar                                 = descuento_afp    (si > 0)
        HABER: Salud por Pagar                               = descuento_salud  (si > 0)
        HABER: Anticipos a Trabajadores (liquida el activo)  = anticipo_descontado (si > 0)
        HABER: Sueldos por Pagar (otros descuentos)          = otros_descuentos  (si > 0)
        HABER: Sueldos por Pagar (neto al trabajador)        = liquido_pagar

    DEBE = HABER = sueldo_bruto (siempre balanceado).

    La línea HABER Anticipos a Trabajadores cancela el activo creado por
    generar_asiento_pago_anticipo cuando se entregó el adelanto; el costo
    queda reconocido aquí en DEBE Gasto Sueldos por el bruto completo.

    El pago posterior solo mueve Sueldos por Pagar → Banco (ver
    generar_asiento_pago_remuneracion).

    Si alguna cuenta necesaria no está configurada, devuelve None.
    """
    config = get_config()
    if not config:
        return None

    if remuneracion.trabajador.tipo_costo == 'operacional':
        cuenta_gasto = config.cuenta_sueldos_operacional
    else:
        cuenta_gasto = config.cuenta_sueldos_administrativo

    if not cuenta_gasto or not config.cuenta_sueldos_por_pagar:
        return None

    descuento_afp    = remuneracion.descuento_afp       or Decimal('0')
    descuento_salud  = remuneracion.descuento_salud     or Decimal('0')
    otros_descuentos = remuneracion.otros_descuentos    or Decimal('0')
    anticipo         = remuneracion.anticipo_descontado or Decimal('0')

    if descuento_afp > 0 and not config.cuenta_afp_por_pagar:
        return None
    if descuento_salud > 0 and not config.cuenta_salud_por_pagar:
        return None
    if anticipo > 0 and not (config.cuenta_anticipos_trabajadores or config.cuenta_sueldos_por_pagar):
        return None

    descripcion = (
        f'Devengamiento Rem. {remuneracion.trabajador.nombre_completo} '
        f'{remuneracion.periodo_mes:02d}/{remuneracion.periodo_anio}'
    )
    asiento = AsientoContable.objects.create(
        fecha=timezone.now().date(),
        descripcion=descripcion,
        tipo='devengamiento_remuneracion',
        estado='borrador',
        remuneracion=remuneracion,
        creado_por=usuario,
    )

    orden = 1
    # DEBE: gasto sueldos por el bruto completo
    _add_linea(asiento, cuenta_gasto, debe=remuneracion.sueldo_bruto,
               descripcion=f'Gasto sueldo bruto — {remuneracion.trabajador.nombre_completo}',
               orden=orden)
    orden += 1

    # HABER: AFP por Pagar
    if descuento_afp > 0 and config.cuenta_afp_por_pagar:
        _add_linea(asiento, config.cuenta_afp_por_pagar, haber=descuento_afp,
                   descripcion='AFP por Pagar', orden=orden)
        orden += 1

    # HABER: Salud por Pagar
    if descuento_salud > 0 and config.cuenta_salud_por_pagar:
        _add_linea(asiento, config.cuenta_salud_por_pagar, haber=descuento_salud,
                   descripcion='Salud por Pagar (Isapre/FONASA)', orden=orden)
        orden += 1

    # HABER: Anticipos a Trabajadores — liquida el activo creado al entregar el anticipo
    if anticipo > 0:
        if config.cuenta_anticipos_trabajadores:
            _add_linea(asiento, config.cuenta_anticipos_trabajadores, haber=anticipo,
                       descripcion='Anticipo descontado (liquida activo)', orden=orden)
        else:
            _add_linea(asiento, config.cuenta_sueldos_por_pagar, haber=anticipo,
                       descripcion='Anticipo descontado', orden=orden)
        orden += 1

    # HABER: Otros descuentos por Pagar
    if otros_descuentos > 0:
        _add_linea(asiento, config.cuenta_sueldos_por_pagar, haber=otros_descuentos,
                   descripcion='Otros descuentos por pagar', orden=orden)
        orden += 1

    # HABER: Sueldos por Pagar — neto líquido adeudado al trabajador
    _add_linea(asiento, config.cuenta_sueldos_por_pagar, haber=remuneracion.liquido_pagar,
               descripcion=f'Sueldo líquido por pagar — {remuneracion.trabajador.nombre_completo}',
               orden=orden)

    return asiento


def generar_asiento_pago_remuneracion(remuneracion, movimiento, usuario=None):
    """
    Genera el asiento de PAGO de una remuneración.

    Si ya existe un asiento de devengamiento para esta remuneración (generado al
    crear la liquidación), el asiento de pago es simple:
        DEBE : Sueldos por Pagar  = liquido_pagar
        HABER: Banco              = liquido_pagar

    Si NO existe devengamiento previo (compatibilidad con liquidaciones antiguas),
    genera el asiento compuesto completo:
        DEBE : Gasto Sueldos      = sueldo_bruto
        HABER: Banco              = liquido_pagar
        HABER: AFP por Pagar      = descuento_afp
        HABER: Salud por Pagar    = descuento_salud
        HABER: Anticipos a Trab.  = anticipo_descontado
        HABER: Sueldos por Pagar  = otros_descuentos

    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    cuenta_banco = movimiento.cuenta.cuenta_contable
    cuenta_gasto = movimiento.cuenta_contable

    if not config or not cuenta_banco:
        return None

    # Determinar si ya existe asiento de devengamiento
    tiene_devengamiento = remuneracion.asientos.filter(
        tipo='devengamiento_remuneracion'
    ).exists()

    descripcion = (
        f'Pago Rem. {remuneracion.trabajador.nombre_completo} '
        f'{remuneracion.periodo_mes:02d}/{remuneracion.periodo_anio}'
    )

    if tiene_devengamiento and config.cuenta_sueldos_por_pagar:
        # Asiento simple: liquida Sueldos por Pagar contra Banco
        asiento = AsientoContable.objects.create(
            fecha=movimiento.fecha,
            descripcion=descripcion,
            tipo='pago_remuneracion',
            estado='borrador',
            movimiento_bancario=movimiento,
            remuneracion=remuneracion,
            creado_por=usuario,
        )
        _add_linea(asiento, config.cuenta_sueldos_por_pagar, debe=remuneracion.liquido_pagar,
                   descripcion=f'Liquidación sueldo — {remuneracion.trabajador.nombre_completo}',
                   orden=1)
        _add_linea(asiento, cuenta_banco, haber=remuneracion.liquido_pagar,
                   descripcion='Pago banco (líquido)', orden=2)
        return asiento

    # --- Fallback: asiento compuesto (sin devengamiento previo) ---
    if not cuenta_gasto:
        return None

    descuento_afp    = remuneracion.descuento_afp       or Decimal('0')
    descuento_salud  = remuneracion.descuento_salud     or Decimal('0')
    otros_descuentos = remuneracion.otros_descuentos    or Decimal('0')
    anticipo         = remuneracion.anticipo_descontado or Decimal('0')

    puede_balancear = True
    if descuento_afp > 0 and not config.cuenta_afp_por_pagar:
        puede_balancear = False
    if descuento_salud > 0 and not config.cuenta_salud_por_pagar:
        puede_balancear = False
    if anticipo > 0 and not (config.cuenta_anticipos_trabajadores or config.cuenta_sueldos_por_pagar):
        puede_balancear = False
    if otros_descuentos > 0 and not config.cuenta_sueldos_por_pagar:
        puede_balancear = False

    if not puede_balancear:
        return generar_asiento_movimiento_bancario(movimiento, usuario=usuario)

    asiento = AsientoContable.objects.create(
        fecha=movimiento.fecha,
        descripcion=descripcion,
        tipo='pago_remuneracion',
        estado='borrador',
        movimiento_bancario=movimiento,
        remuneracion=remuneracion,
        creado_por=usuario,
    )

    orden = 1
    _add_linea(asiento, cuenta_gasto, debe=remuneracion.sueldo_bruto,
               descripcion=f'Gasto sueldo bruto — {remuneracion.trabajador.nombre_completo}',
               orden=orden)
    orden += 1

    _add_linea(asiento, cuenta_banco, haber=remuneracion.liquido_pagar,
               descripcion='Pago banco (líquido)', orden=orden)
    orden += 1

    if descuento_afp > 0 and config.cuenta_afp_por_pagar:
        _add_linea(asiento, config.cuenta_afp_por_pagar, haber=descuento_afp,
                   descripcion='AFP por Pagar', orden=orden)
        orden += 1

    if descuento_salud > 0 and config.cuenta_salud_por_pagar:
        _add_linea(asiento, config.cuenta_salud_por_pagar, haber=descuento_salud,
                   descripcion='Salud por Pagar (Isapre/FONASA)', orden=orden)
        orden += 1

    if anticipo > 0:
        if config.cuenta_anticipos_trabajadores:
            _add_linea(asiento, config.cuenta_anticipos_trabajadores, haber=anticipo,
                       descripcion='Anticipo descontado (liquida activo)', orden=orden)
        elif config.cuenta_sueldos_por_pagar:
            _add_linea(asiento, config.cuenta_sueldos_por_pagar, haber=anticipo,
                       descripcion='Anticipo descontado', orden=orden)
        orden += 1

    if otros_descuentos > 0 and config.cuenta_sueldos_por_pagar:
        _add_linea(asiento, config.cuenta_sueldos_por_pagar, haber=otros_descuentos,
                   descripcion='Otros descuentos por pagar', orden=orden)

    return asiento
