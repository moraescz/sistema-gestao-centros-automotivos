# cadastros/templatetags/custom_filters.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite acessar um item de um dicionário em um template Django.
    """
    return dictionary.get(key)

@register.filter
def safe_default_if_none(value, default=""):
    return value if value is not None else default

@register.filter
def startswith(text, starts):
    """Retorna True se text começar com starts."""
    if isinstance(text, str):
        return text.startswith(starts)
    return False