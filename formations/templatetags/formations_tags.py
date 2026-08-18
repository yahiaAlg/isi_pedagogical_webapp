from django import template
from django.utils.safestring import mark_safe
import markdown

register = template.Library()


@register.filter(name="markdown")
def markdown_format(text):
    """
    Render Markdown text (e.g. Formation.description) as safe HTML.

    Usage in templates:
        {% load formations_tags %}
        {{ formation.description|markdown }}
    """
    if not text:
        return ""
    html = markdown.markdown(
        text,
        extensions=["extra", "nl2br", "sane_lists"],
    )
    return mark_safe(html)
