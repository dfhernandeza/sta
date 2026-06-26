from django import template

register = template.Library()

@register.filter
def moneda_chilena(value):
    try:
        return "${:,.0f}".format(float(value)).replace(",", ".")
    except:
        return value


@register.filter
def moneda_chilena_decimales(value):
    try:
        formatted = "{:,.2f}".format(float(value))
        formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return f"${formatted}"
    except:
        return value
