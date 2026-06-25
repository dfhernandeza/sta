"""
Utilidades para la generación semi-automática de asientos contables.
Todas las funciones devuelven un AsientoContable en estado 'borrador',
o None si falta la configuración necesaria.
"""
from decimal import Decimal
from django.utils import timezone
from django.db.models import Sum
from .models import ConfiguracionContable, AsientoContable, LineaAsiento


def get_config():
    """Devuelve la ConfiguracionContable (singleton) o None si no existe."""
    try:
        return ConfiguracionContable.objects.get(pk=1)
    except ConfiguracionContable.DoesNotExist:
        return None


def _add_linea(asiento, cuenta, debe=0, haber=0, descripcion='', orden=0, centro_costo=None):
    """Helper para crear una LineaAsiento."""
    if cuenta is None:
        raise ValueError(
            f'No se puede crear la línea "{descripcion}": la cuenta contable no está configurada. '
            'Revise la Configuración Contable.'
        )
    return LineaAsiento.objects.create(
        asiento=asiento,
        cuenta=cuenta,
        debe=Decimal(str(debe)),
        haber=Decimal(str(haber)),
        descripcion=descripcion,
        orden=orden,
        centro_costo=centro_costo,
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

    # Líneas HABER: ingresos por detalle
    orden = 10
    detalles = factura.detalles.select_related('cuenta_contable', 'centro_costo').all()
    suma_afecto = Decimal('0')
    suma_exento = Decimal('0')
    for det in detalles:
        subtotal = (det.cantidad * det.precio_unitario).quantize(Decimal('0.0001'))
        cuenta_ingreso = det.cuenta_contable or config.cuenta_ventas_default
        descripcion_detallada = f'{det.descripcion[:150]} (Factura {factura.numero} Cant: {det.cantidad} x Precio Unit: {det.precio_unitario})'
        _add_linea(asiento, cuenta_ingreso, haber=subtotal,
                   descripcion=descripcion_detallada, orden=orden,
                   centro_costo=det.centro_costo)
        if getattr(det, 'exento_iva', False):
            suma_exento += subtotal
        else:
            suma_afecto += subtotal
        orden += 1

    # IVA y total calculados desde los subtotales (garantiza que Debe = Haber)
    iva_calculado = (suma_afecto * Decimal('0.19')).quantize(Decimal('0.01'))
    total_calculado = suma_afecto + suma_exento + iva_calculado

    # Línea DEBE: CxC por total calculado
    _add_linea(asiento, config.cuenta_cxc, debe=total_calculado,
               descripcion=f'CxC Factura {factura.numero}', orden=1)

    # Línea HABER: IVA Débito Fiscal
    _add_linea(asiento, config.cuenta_iva_debito, haber=iva_calculado,
               descripcion=f'IVA Débito Fiscal (Factura {factura.numero})',
               orden=orden)

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
    detalles = factura.detalles.select_related('cuenta_contable', 'centro_costo').all()
    suma_afecto = Decimal('0')
    suma_exento = Decimal('0')
    for det in detalles:
        subtotal = (det.cantidad * det.precio_unitario).quantize(Decimal('0.0001'))
        cuenta_costo = det.cuenta_contable or config.cuenta_compras_default
        descripcion_detallada = f'{det.descripcion[:150]} (Factura {factura.numero} Cant: {det.cantidad} x Precio Unit: {det.precio_unitario})'
        _add_linea(asiento, cuenta_costo, debe=subtotal,
                   descripcion=descripcion_detallada, orden=orden,
                   centro_costo=det.centro_costo)
        if det.exento_iva:
            suma_exento += subtotal
        else:
            suma_afecto += subtotal
        orden += 1

    # IVA y total calculados desde los subtotales (garantiza que Debe = Haber)
    iva_calculado = (suma_afecto * Decimal('0.19')).quantize(Decimal('0.01'))
    total_calculado = suma_afecto + suma_exento + iva_calculado

    descripcion_iva_credito_detallada = f'IVA Crédito Fiscal (Factura {factura.numero})'
    # Línea DEBE: IVA Crédito Fiscal
    _add_linea(asiento, config.cuenta_iva_credito, debe=iva_calculado,
               descripcion=descripcion_iva_credito_detallada, orden=orden)

    # Línea HABER: CxP por total
    _add_linea(asiento, config.cuenta_cxp, haber=total_calculado,
               descripcion=descripcion_cxp, orden=orden + 1)

    return asiento


def generar_asiento_nota_credito_recibida(nota_credito, usuario=None):
    """
    Genera el asiento de una nota de crédito de compra:
        DEBE  : cuenta_cxp          = monto que rebaja deuda pendiente
        DEBE  : anticipos proveedor = excedente si la factura ya estaba pagada
        HABER : cuenta por detalle  = monto (o cuenta_compras_default si no tiene)
        HABER : cuenta_iva_credito  = nota_credito.iva
    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    if not config or not config.cuenta_cxp or not config.cuenta_iva_credito:
        return None

    factura = nota_credito.factura
    es_factura_apertura = getattr(factura, 'origen', 'operacional') == 'apertura'
    if es_factura_apertura and not config.cuenta_patrimonio_apertura:
        return None

    asiento = AsientoContable.objects.create(
        fecha=nota_credito.fecha_emision,
        descripcion=(
            f'Nota de crédito recibida N° {nota_credito.numero} '
            f'aplicada a factura {factura.numero} - {nota_credito.proveedor.razon_social}'
        ),
        tipo='nota_credito_compra',
        estado='borrador',
        factura_recibida=factura,
        nota_credito_recibida=nota_credito,
        creado_por=usuario,
    )

    orden = 10
    detalles = nota_credito.detalles.select_related('cuenta_contable', 'centro_costo').all()
    suma_afecto = Decimal('0')
    suma_exento = Decimal('0')
    for det in detalles:
        subtotal = (det.cantidad * det.precio_unitario).quantize(Decimal('0.0001'))
        if det.exento_iva:
            suma_exento += subtotal
        else:
            suma_afecto += subtotal

        if not es_factura_apertura:
            cuenta_costo = det.cuenta_contable or config.cuenta_compras_default
            descripcion_detallada = (
                f'{det.descripcion[:150]} '
                f'(NC {nota_credito.numero} Cant: {det.cantidad} x Precio Unit: {det.precio_unitario})'
            )
            _add_linea(asiento, cuenta_costo, haber=subtotal,
                       descripcion=descripcion_detallada, orden=orden,
                       centro_costo=det.centro_costo)
            orden += 1

    iva_calculado = (suma_afecto * Decimal('0.19')).quantize(Decimal('0.01'))
    total_calculado = suma_afecto + suma_exento + iva_calculado

    total_otras_notas = factura.notas_credito.exclude(estado='anulada').exclude(
        pk=nota_credito.pk
    ).aggregate(total=Sum('total'))['total'] or Decimal('0')
    monto_factura_antes_nota = max(factura.total - total_otras_notas, Decimal('0'))
    try:
        monto_pagado = factura.cuenta_pagar.monto_pagado or Decimal('0')
    except Exception:
        monto_pagado = Decimal('0')
    saldo_cxp_antes_nota = max(monto_factura_antes_nota - monto_pagado, Decimal('0'))
    monto_rebaja_cxp = min(total_calculado, saldo_cxp_antes_nota)
    monto_credito_proveedor = total_calculado - monto_rebaja_cxp

    if monto_credito_proveedor > 0 and not config.cuenta_anticipos_proveedores:
        asiento.delete()
        return None

    orden_debe = 1
    if monto_rebaja_cxp > 0:
        _add_linea(asiento, config.cuenta_cxp, debe=monto_rebaja_cxp,
                   descripcion=f'Rebaja CxP por NC {nota_credito.numero}', orden=orden_debe)
        orden_debe += 1

    if monto_credito_proveedor > 0:
        _add_linea(asiento, config.cuenta_anticipos_proveedores, debe=monto_credito_proveedor,
                   descripcion=f'Crédito a favor proveedor por NC {nota_credito.numero}', orden=orden_debe)

    if es_factura_apertura:
        _add_linea(asiento, config.cuenta_patrimonio_apertura, haber=(suma_afecto + suma_exento),
                   descripcion=f'Reverso saldo de apertura por NC {nota_credito.numero}',
                   orden=orden)
        orden += 1

    _add_linea(asiento, config.cuenta_iva_credito, haber=iva_calculado,
               descripcion=f'Reverso IVA Crédito Fiscal (NC {nota_credito.numero})',
               orden=orden)

    return asiento


def generar_asiento_boleta_honorarios(boleta, usuario=None):
    """
    Genera el asiento de una boleta de honorarios:
        DEBE  : gasto/costo honorarios       = bruto
        HABER : cuenta_cxp                   = liquido a pagar
        HABER : retenciones honorarios       = retencion
    Retorna el AsientoContable creado (borrador) o None.
    """
    config = get_config()
    if not config or not config.cuenta_cxp:
        return None

    cuenta_gasto = boleta.cuenta_contable or config.cuenta_honorarios_default or config.cuenta_compras_default
    cuenta_retencion = config.cuenta_retenciones_honorarios or config.cuenta_impuestos_sii

    if not cuenta_gasto or (boleta.retencion > 0 and not cuenta_retencion):
        return None

    asiento = AsientoContable.objects.create(
        fecha=boleta.fecha_emision,
        descripcion=f'Boleta honorarios N° {boleta.numero} - {boleta.prestador.nombre}',
        tipo='boleta_honorarios',
        estado='borrador',
        boleta_honorarios=boleta,
        creado_por=usuario,
    )

    _add_linea(asiento, cuenta_gasto, debe=boleta.bruto,
               descripcion=boleta.descripcion[:200], orden=1,
               centro_costo=boleta.centro_costo)
    _add_linea(asiento, config.cuenta_cxp, haber=boleta.liquido,
               descripcion=f'CxP Boleta {boleta.numero}', orden=2)

    if boleta.retencion > 0:
        _add_linea(asiento, cuenta_retencion, haber=boleta.retencion,
                   descripcion=f'Retención honorarios Boleta {boleta.numero}', orden=3)

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
                   descripcion=det.descripcion[:200], orden=orden,
                   centro_costo=det.centro_costo)
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


def generar_asiento_aplicacion_anticipo_proveedor(aplicacion, usuario=None):
    """
    Genera el asiento para aplicar un anticipo de proveedor contra una CxP:

        DEBE : Cuentas por Pagar           = aplicacion.monto
        HABER: Anticipos a Proveedores     = aplicacion.monto
    """
    config = get_config()
    if not config or not config.cuenta_cxp or not config.cuenta_anticipos_proveedores:
        return None

    cxp = aplicacion.cuenta_pagar
    anticipo = aplicacion.anticipo
    documento = cxp.factura.numero if cxp.factura else f'CxP #{cxp.pk}'

    asiento = AsientoContable.objects.create(
        fecha=aplicacion.fecha,
        descripcion=(
            f'Aplicación de anticipo proveedor {anticipo.proveedor.razon_social} '
            f'a {documento}'
        ),
        tipo='ajuste',
        estado='borrador',
        factura_recibida=cxp.factura,
        creado_por=usuario,
    )

    _add_linea(asiento, config.cuenta_cxp, debe=aplicacion.monto,
               descripcion=f'Aplicación de anticipo a {documento}', orden=1)
    _add_linea(asiento, config.cuenta_anticipos_proveedores, haber=aplicacion.monto,
               descripcion=f'Rebaja anticipo proveedor {anticipo.proveedor.razon_social}', orden=2)

    return asiento


def generar_asiento_devengamiento_remuneracion(remuneracion, usuario=None):
    """
    Genera el asiento de DEVENGAMIENTO al crear/liquidar una remuneración (base devengada):

        DEBE : Gasto Sueldos (operacional o administrativo)  = sueldo_bruto
        HABER: AFP por Pagar                                 = descuento_afp    (si > 0)
        HABER: Salud por Pagar                               = descuento_salud  (si > 0)
        HABER: Impuestos SII por Pagar                       = impuesto_unico   (si > 0)
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
    impuesto_unico   = remuneracion.impuesto_unico      or Decimal('0')
    otros_descuentos = remuneracion.otros_descuentos    or Decimal('0')
    anticipo         = remuneracion.anticipo_descontado or Decimal('0')

    if descuento_afp > 0 and not config.cuenta_afp_por_pagar:
        return None
    if descuento_salud > 0 and not config.cuenta_salud_por_pagar:
        return None
    if impuesto_unico > 0 and not config.cuenta_impuestos_sii:
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
    centro_costo_trab = getattr(remuneracion.trabajador, 'centro_costo', None)
    # DEBE: gasto sueldos por el bruto completo
    _add_linea(asiento, cuenta_gasto, debe=remuneracion.sueldo_bruto,
               descripcion=f'Gasto sueldo bruto — {remuneracion.trabajador.nombre_completo}',
               orden=orden, centro_costo=centro_costo_trab)
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

    # HABER: Impuesto Único de Segunda Categoría por Pagar
    if impuesto_unico > 0 and config.cuenta_impuestos_sii:
        _add_linea(asiento, config.cuenta_impuestos_sii, haber=impuesto_unico,
                   descripcion='Impuesto Único por Pagar', orden=orden)
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
        HABER: Impuestos SII      = impuesto_unico
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
    impuesto_unico   = remuneracion.impuesto_unico      or Decimal('0')
    otros_descuentos = remuneracion.otros_descuentos    or Decimal('0')
    anticipo         = remuneracion.anticipo_descontado or Decimal('0')

    puede_balancear = True
    if descuento_afp > 0 and not config.cuenta_afp_por_pagar:
        puede_balancear = False
    if descuento_salud > 0 and not config.cuenta_salud_por_pagar:
        puede_balancear = False
    if impuesto_unico > 0 and not config.cuenta_impuestos_sii:
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

    if impuesto_unico > 0 and config.cuenta_impuestos_sii:
        _add_linea(asiento, config.cuenta_impuestos_sii, haber=impuesto_unico,
                   descripcion='Impuesto Único por Pagar', orden=orden)
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
