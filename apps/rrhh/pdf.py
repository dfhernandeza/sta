from io import BytesIO
from pathlib import Path

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from apps.web.models import ConfiguracionSitio


MESES = {
    1: 'ENERO', 2: 'FEBRERO', 3: 'MARZO', 4: 'ABRIL', 5: 'MAYO',
    6: 'JUNIO', 7: 'JULIO', 8: 'AGOSTO', 9: 'SEPTIEMBRE',
    10: 'OCTUBRE', 11: 'NOVIEMBRE', 12: 'DICIEMBRE',
}


def _pesos(valor):
    return f"$ {round(valor or 0):,}".replace(',', '.')


def _texto(c, texto, x, y, size=8, bold=False, align='left'):
    texto = str(texto or '—')
    font = 'Helvetica-Bold' if bold else 'Helvetica'
    c.setFont(font, size)
    if align == 'right':
        c.drawRightString(x, y, texto)
    elif align == 'center':
        c.drawCentredString(x, y, texto)
    else:
        c.drawString(x, y, texto)


def _logo_path(config):
    if config and config.logo:
        try:
            path = Path(config.logo.path)
            if path.exists():
                return path
        except (NotImplementedError, ValueError):
            pass
    path = Path(settings.BASE_DIR) / 'static' / 'img' / 'logo.png'
    return path if path.exists() else None


def _fila(c, y, etiqueta, monto, x1, x2, ancho, fondo=None, bold=False):
    if fondo:
        c.setFillColor(fondo)
        c.rect(x1, y - 4, ancho, 18, fill=1, stroke=0)
        c.setFillColor(colors.black)
    _texto(c, etiqueta, x1 + 6, y, 8, bold)
    _texto(c, _pesos(monto), x2 - 6, y, 8, bold, 'right')
    c.setStrokeColor(colors.HexColor('#D4D8DD'))
    c.line(x1, y - 4, x2, y - 4)


def _dibujar_liquidacion(c, remuneracion, config):
    width, height = A4
    margen = 38
    azul = colors.HexColor('#163B5C')
    gris = colors.HexColor('#F0F2F4')
    trabajador = remuneracion.trabajador
    empresa = getattr(config, 'razon_social', '') or 'SOLUCIONES TERMO ACUSTICAS SPA'
    rut_empresa = getattr(config, 'rut_empresa', '') or '76.471.912-3'
    direccion_empresa = getattr(config, 'direccion_empresa', '') or 'SIMPSON 46, CHILLÁN'

    logo = _logo_path(config)
    if logo:
        try:
            image = ImageReader(str(logo))
            iw, ih = image.getSize()
            max_w, max_h = 115, 55
            scale = min(max_w / iw, max_h / ih)
            c.drawImage(image, margen, height - 82, iw * scale, ih * scale,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    _texto(c, empresa, width - margen, height - 39, 11, True, 'right')
    _texto(c, rut_empresa, width - margen, height - 53, 8, False, 'right')
    _texto(c, direccion_empresa, width - margen, height - 67, 8, False, 'right')

    c.setFillColor(azul)
    c.roundRect(margen, height - 124, width - 2 * margen, 28, 5, fill=1, stroke=0)
    c.setFillColor(colors.white)
    titulo = f"LIQUIDACIÓN DE REMUNERACIONES · {MESES[remuneracion.periodo_mes]} {remuneracion.periodo_anio}"
    _texto(c, titulo, width / 2, height - 114, 11, True, 'center')
    c.setFillColor(colors.black)

    y = height - 153
    datos = [
        ('Trabajador', trabajador.nombre_completo, 'RUT', trabajador.rut),
        ('Cargo', trabajador.cargo or '—', 'Fecha ingreso', trabajador.fecha_ingreso.strftime('%d/%m/%Y')),
        ('AFP', trabajador.get_afp_display() if trabajador.afp else '—',
         'Salud', trabajador.get_isapre_display() if trabajador.isapre else '—'),
        ('Centro de costo', trabajador.centro_costo or '—', 'Estado', remuneracion.get_estado_display()),
    ]
    c.setStrokeColor(colors.HexColor('#AEB5BC'))
    c.roundRect(margen, y - 68, width - 2 * margen, 82, 4, fill=0, stroke=1)
    for izq_et, izq_val, der_et, der_val in datos:
        _texto(c, izq_et + ':', margen + 8, y, 7, True)
        _texto(c, izq_val, margen + 88, y, 8)
        _texto(c, der_et + ':', width / 2 + 8, y, 7, True)
        _texto(c, der_val, width / 2 + 84, y, 8)
        y -= 18

    y -= 20
    gap = 12
    col_w = (width - 2 * margen - gap) / 2
    x_h = margen
    x_d = margen + col_w + gap
    for x, titulo_col in ((x_h, 'HABERES'), (x_d, 'DESCUENTOS')):
        c.setFillColor(azul)
        c.rect(x, y, col_w, 22, fill=1, stroke=0)
        c.setFillColor(colors.white)
        _texto(c, titulo_col, x + col_w / 2, y + 7, 9, True, 'center')
    c.setFillColor(colors.black)

    y -= 18
    haberes = [
        ('Sueldo base', remuneracion.sueldo_base),
        ('Horas extraordinarias', remuneracion.horas_extra),
        ('Bonos', remuneracion.bono),
    ]
    descuentos = [
        ('AFP', remuneracion.descuento_afp),
        ('Salud', remuneracion.descuento_salud),
        ('Seguro cesantía', remuneracion.seguro_cesantia_trabajador),
        ('Impuesto único', remuneracion.impuesto_unico),
        ('Anticipos', remuneracion.anticipo_descontado),
        ('Otros descuentos', remuneracion.otros_descuentos),
    ]
    filas = max(len(haberes), len(descuentos))
    for i in range(filas):
        if i < len(haberes):
            _fila(c, y, *haberes[i], x_h, x_h + col_w, col_w)
        if i < len(descuentos):
            _fila(c, y, *descuentos[i], x_d, x_d + col_w, col_w)
        y -= 22

    total_descuentos = remuneracion.descuentos + (remuneracion.anticipo_descontado or 0)
    _fila(c, y, 'TOTAL HABERES', remuneracion.sueldo_bruto,
          x_h, x_h + col_w, col_w, gris, True)
    _fila(c, y, 'TOTAL DESCUENTOS', total_descuentos,
          x_d, x_d + col_w, col_w, gris, True)

    descuentos_legales = remuneracion.descuentos
    liquido_mes = (remuneracion.sueldo_bruto or 0) - descuentos_legales
    anticipo = remuneracion.anticipo_descontado or 0

    y -= 34
    resumen_x = margen + 58
    resumen_w = width - 2 * margen - 116
    resumen_top = y + 14
    resumen_filas = [
        ('Total Haberes', remuneracion.sueldo_bruto, False),
        ('(-) Descuentos Legales', descuentos_legales, False),
        ('Líquido del Mes', liquido_mes, True),
        ('(-) Anticipo recibido', anticipo, False),
        ('Líquido a pagar', remuneracion.liquido_pagar, True),
    ]
    c.setStrokeColor(colors.HexColor('#AEB5BC'))
    c.roundRect(resumen_x, resumen_top - 102, resumen_w, 102, 4, fill=0, stroke=1)
    for indice, (concepto, monto, destacado) in enumerate(resumen_filas):
        fila_y = resumen_top - 17 - indice * 19
        if destacado:
            c.setFillColor(gris)
            c.rect(resumen_x + 1, fila_y - 5, resumen_w - 2, 19, fill=1, stroke=0)
            c.setFillColor(colors.black)
        _texto(c, concepto, resumen_x + 9, fila_y, 8.5, destacado)
        _texto(c, _pesos(monto), resumen_x + resumen_w - 9, fila_y,
               8.5, destacado, 'right')

    y = resumen_top - 140
    c.setFillColor(azul)
    c.roundRect(margen, y, width - 2 * margen, 42, 6, fill=1, stroke=0)
    c.setFillColor(colors.white)
    _texto(c, 'LÍQUIDO A PAGAR', margen + 14, y + 15, 12, True)
    _texto(c, _pesos(remuneracion.liquido_pagar), width - margen - 14, y + 14, 15, True, 'right')
    c.setFillColor(colors.black)

    y = 86
    _texto(c, 'Declaro haber recibido conforme el alcance líquido indicado en esta liquidación.',
           width / 2, y + 26, 8, False, 'center')
    c.line(margen + 30, y, margen + 200, y)
    c.line(width - margen - 200, y, width - margen - 30, y)
    _texto(c, 'Firma empleador', margen + 115, y - 14, 8, False, 'center')
    _texto(c, 'Firma trabajador', width - margen - 115, y - 14, 8, False, 'center')
    _texto(c, trabajador.nombre_completo, width - margen - 115, y - 27, 7, True, 'center')
    _texto(c, trabajador.rut, width - margen - 115, y - 38, 7, False, 'center')

    c.setFillColor(colors.HexColor('#6C757D'))
    _texto(c, f'Documento generado por el sistema · Devengamiento: {remuneracion.fecha_devengamiento:%d/%m/%Y}',
           width / 2, 24, 6.5, False, 'center')


def generar_liquidaciones_pdf(remuneraciones):
    remuneraciones = list(remuneraciones)
    buffer = BytesIO()
    documento = canvas.Canvas(buffer, pagesize=A4, pageCompression=1)
    config = ConfiguracionSitio.actual()
    for remuneracion in remuneraciones:
        _dibujar_liquidacion(documento, remuneracion, config)
        documento.showPage()
    documento.save()
    buffer.seek(0)
    return buffer.getvalue()
