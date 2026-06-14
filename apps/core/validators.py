import re
from django.core.exceptions import ValidationError


def validar_rut(value):
    """
    Valida RUT chileno en formato XX.XXX.XXX-X o XXXXXXXX-X.
    Verifica el dígito verificador mediante el algoritmo módulo 11.
    """
    rut = re.sub(r'[\.\s]', '', value).upper()
    if not re.match(r'^\d{7,8}-[\dK]$', rut):
        raise ValidationError(
            'Ingrese un RUT válido en formato XX.XXX.XXX-X (ej: 12.345.678-9)'
        )

    cuerpo, dv = rut.split('-')
    suma = 0
    multiplicador = 2
    for digito in reversed(cuerpo):
        suma += int(digito) * multiplicador
        multiplicador = multiplicador + 1 if multiplicador < 7 else 2

    resto = 11 - (suma % 11)
    if resto == 11:
        dv_calculado = '0'
    elif resto == 10:
        dv_calculado = 'K'
    else:
        dv_calculado = str(resto)

    if dv != dv_calculado:
        raise ValidationError('El RUT ingresado no es válido (dígito verificador incorrecto).')


def formatear_rut(rut_raw: str) -> str:
    """
    Formatea un RUT limpio (sin puntos) al formato XX.XXX.XXX-X.
    Ejemplo: '12345678-9' → '12.345.678-9'
    """
    rut = re.sub(r'[\.\s]', '', rut_raw).upper()
    if '-' in rut:
        cuerpo, dv = rut.split('-')
        cuerpo_formateado = '{:,}'.format(int(cuerpo)).replace(',', '.')
        return f'{cuerpo_formateado}-{dv}'
    return rut
