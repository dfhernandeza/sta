from django import template

register = template.Library()

@register.filter
def moneda_chilena(value):
    try:
        return "${:,.0f}".format(float(value)).replace(",", ".")
    except:
        return value