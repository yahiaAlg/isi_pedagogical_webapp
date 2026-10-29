from django import template

register = template.Library()

@register.filter
def dict_get(d, key):
    """Safe dict lookup: {{ mydict|dict_get:key }}"""
    if isinstance(d, dict):
        return d.get(str(key))
    return None

@register.filter
def get_range(value):
    """Return range(value) for use in templates."""
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)
