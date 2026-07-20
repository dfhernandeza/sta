from io import BytesIO
from pathlib import Path

from django.conf import settings
from PIL import Image as PILImage, ImageChops
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

from apps.web.models import ConfiguracionSitio


EMPRESA_RAZON_SOCIAL = 'SOLUCIONES TERMO ACUSTICAS SPA'
EMPRESA_RUT = '76.471.912-3'
EMPRESA_DIRECCION = 'SIMPSON 46, CHILLÁN'
EMPRESA_GIRO = 'Soluciones termoacústicas, muebles y terminaciones'


def _pesos(valor):
    return f'$ {round(valor or 0):,}'.replace(',', '.')


def _imagen(path, ancho, alto, recortar=False):
    if not path:
        return ''
    try:
        p = Path(path)
        if not p.exists():
            return ''
        if recortar:
            with PILImage.open(p) as original:
                imagen = original.convert('RGBA')
                alpha = imagen.getchannel('A')
                if alpha.getextrema()[0] < 255:
                    bbox = alpha.getbbox()
                else:
                    rgb = imagen.convert('RGB')
                    fondo = PILImage.new('RGB', rgb.size, 'white')
                    diferencia = ImageChops.difference(rgb, fondo).convert('L')
                    mascara = diferencia.point(lambda valor: 255 if valor > 12 else 0)
                    bbox = mascara.getbbox()
                if bbox:
                    margen_x = max(4, int((bbox[2] - bbox[0]) * .04))
                    margen_y = max(4, int((bbox[3] - bbox[1]) * .08))
                    bbox = (
                        max(0, bbox[0] - margen_x), max(0, bbox[1] - margen_y),
                        min(imagen.width, bbox[2] + margen_x),
                        min(imagen.height, bbox[3] + margen_y),
                    )
                    imagen = imagen.crop(bbox)
                memoria = BytesIO()
                imagen.save(memoria, format='PNG')
                memoria.seek(0)
                return Image(memoria, width=ancho, height=alto, kind='proportional')
        return Image(str(p), width=ancho, height=alto, kind='proportional')
    except (ValueError, OSError):
        return ''


def generar_orden_compra_pdf(orden):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
                            topMargin=12*mm, bottomMargin=59*mm)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8, leading=10)
    right = ParagraphStyle('right', parent=small, alignment=TA_RIGHT)
    title = ParagraphStyle('title', parent=styles['Title'], fontSize=17, textColor=colors.HexColor('#163B5C'), alignment=TA_CENTER)
    config = ConfiguracionSitio.actual()
    razon_social = getattr(config, 'razon_social', '') or EMPRESA_RAZON_SOCIAL
    rut_empresa = getattr(config, 'rut_empresa', '') or EMPRESA_RUT
    direccion_empresa = getattr(config, 'direccion_empresa', '') or EMPRESA_DIRECCION
    giro_empresa = getattr(config, 'giro_empresa', '') or EMPRESA_GIRO
    representante_legal = getattr(config, 'representante_legal', '') or 'Representante legal'
    logo_path = None
    if config and config.logo:
        try:
            logo_path = config.logo.path
        except (ValueError, NotImplementedError):
            pass
    if not logo_path:
        logo_path = Path(settings.BASE_DIR) / 'static' / 'img' / 'logo.png'
    logo = _imagen(logo_path, 35*mm, 18*mm)
    empresa_datos = Paragraph(
        f'<b>{razon_social}</b><br/>'
        f'<b>RUT:</b> {rut_empresa}<br/>'
        f'<b>Giro:</b> {giro_empresa}<br/>'
        f'<b>Dirección:</b> {direccion_empresa}',
        right,
    )
    story = [Table([[logo, empresa_datos, Paragraph(f'<b>ORDEN DE COMPRA</b><br/>{orden.numero}', title)]],
                   colWidths=[40*mm, 65*mm, 75*mm], style=TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')])), Spacer(1, 5*mm)]
    datos = [
        ['Fecha', orden.fecha.strftime('%d/%m/%Y'), 'Proyecto', str(orden.proyecto or '—')],
        ['Centro de Costo', str(orden.centro_costo or '—'), 'Solicitante', razon_social],
        ['Aprobado por', orden.aprobado_por.nombre_display if orden.aprobado_por else '—', 'Estado', orden.get_estado_display()],
    ]
    info = Table(datos, colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    info.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#BCC3C9')),('BACKGROUND',(0,0),(0,-1),colors.HexColor('#EEF1F3')),('BACKGROUND',(2,0),(2,-1),colors.HexColor('#EEF1F3')),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),5)]))
    story += [info, Spacer(1, 4*mm), Paragraph('<b>PROVEEDOR</b>', small)]
    proveedor = Table([
        ['Razón social', orden.proveedor_razon_social, 'RUT', orden.proveedor_rut],
        ['Dirección', orden.proveedor_direccion or '—', 'Teléfono', orden.proveedor_telefono or '—'],
        ['Correo', orden.proveedor_email or '—', '', ''],
    ], colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    proveedor.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#BCC3C9')),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8),('PADDING',(0,0),(-1,-1),5)]))
    story += [proveedor, Spacer(1, 5*mm)]
    filas = [['Ítem','Código','Descripción','Cantidad','Unidad','Precio Unitario','Total']]
    for i, d in enumerate(orden.detalles.all(), 1):
        filas.append([str(i), d.codigo or '—', Paragraph(d.descripcion, small), f'{d.cantidad:g}', d.get_unidad_medida_display(), _pesos(d.precio_unitario), _pesos(d.total)])
    detalle = Table(filas, repeatRows=1, colWidths=[9*mm,20*mm,59*mm,18*mm,20*mm,27*mm,27*mm])
    detalle.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#163B5C')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.35,colors.HexColor('#AEB5BC')),('FONTSIZE',(0,0),(-1,-1),7.5),('ALIGN',(3,1),(3,-1),'RIGHT'),('ALIGN',(5,1),(-1,-1),'RIGHT'),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('PADDING',(0,0),(-1,-1),4)]))
    story += [detalle, Spacer(1, 4*mm)]
    totales = Table([['Subtotal',_pesos(orden.subtotal)],['Descuento',_pesos(orden.descuento)],['Neto',_pesos(orden.neto)],['IVA 19%',_pesos(orden.iva)],['TOTAL',_pesos(orden.total)]], colWidths=[35*mm,35*mm], hAlign='RIGHT')
    totales.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.4,colors.HexColor('#BCC3C9')),('ALIGN',(1,0),(1,-1),'RIGHT'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#E8EEF3')),('FONTSIZE',(0,0),(-1,-1),8),('PADDING',(0,0),(-1,-1),5)]))
    story += [totales]
    if orden.observaciones or orden.condiciones_comerciales:
        story += [Spacer(1,4*mm), Paragraph(f'<b>Observaciones:</b> {orden.observaciones or "—"}', small), Paragraph(f'<b>Condiciones comerciales:</b> {orden.condiciones_comerciales or "—"}', small)]
    def dibujar_pie_firmas(canvas, documento):
        canvas.saveState()
        firma_sol = _imagen(
            config.firma_representante_legal.path
            if config and config.firma_representante_legal else None,
            70*mm, 28*mm, recortar=True,
        )
        firma_apr = _imagen(
            orden.firma_aprobador.path if orden.firma_aprobador else None,
            32*mm, 12*mm,
        )
        firmas = Table([
            [firma_sol, firma_apr],
            ['____________________________', '____________________________'],
            [representante_legal,
             orden.aprobado_por.nombre_display if orden.aprobado_por else 'Aprobador'],
            ['Representante legal', 'Aprobado por'],
            [razon_social, ''],
        ], colWidths=[82*mm, 82*mm])
        firmas.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TEXTCOLOR', (0, 3), (-1, -1), colors.HexColor('#6C757D')),
            ('TOPPADDING', (0, 0), (-1, 0), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        ancho, alto = firmas.wrap(doc.width, 38*mm)
        firmas.drawOn(canvas, doc.leftMargin + (doc.width - ancho) / 2, 7*mm)
        canvas.setStrokeColor(colors.HexColor('#D4D8DD'))
        canvas.line(doc.leftMargin, 5*mm, A4[0] - doc.rightMargin, 5*mm)
        canvas.setFont('Helvetica', 6.5)
        canvas.setFillColor(colors.HexColor('#6C757D'))
        canvas.drawCentredString(
            A4[0] / 2, 2.5*mm,
            f'{razon_social} · {orden.numero} · Página {documento.page}',
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=dibujar_pie_firmas, onLaterPages=dibujar_pie_firmas)
    return buffer.getvalue()
