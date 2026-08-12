from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """
    Render the current request's querystring with the given keys
    overridden/removed, for building sort/pagination links that
    preserve active filters.

    Usage: ?{% qs sort="name" dir="asc" %}
    Pass a key with an empty string to remove it (e.g. page="").
    """
    request = context.get("request")
    params = request.GET.copy() if request else template.base.QueryDict(mutable=True)
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    # Changing sort/filters should reset pagination unless page is explicitly set
    if "page" not in kwargs and "page" in params:
        del params["page"]
    return params.urlencode()
