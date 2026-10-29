from django import template
from django.utils.safestring import mark_safe
import datetime
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


@register.filter(name="iso_date")
def iso_date(value):
    """
    Render a value as a plain "YYYY-MM-DD" string for <input type="date">.

    Deliberately NOT `{{ value|date:'Y-m-d' }}`: Django's `date` filter
    (and, worse, printing a date object with no filter at all) both run
    the value through locale-aware formatting/localization — under
    LANGUAGE_CODE="fr" that turns a real `date`/`datetime` object into
    "23 août 2026", and turns the raw ISO string Django keeps on a BOUND
    field after a validation error (e.g. "2026-08-23", exactly what the
    browser's native date input just posted) into an empty string,
    because `dateformat.format()` expects a date object and can't format
    a plain str. Either way, the native input silently blanks itself,
    since it only accepts an exact "yyyy-mm-dd" value — this filter is
    the one place both cases are handled explicitly: format real
    date/datetime objects to ISO ourselves (bypassing localization), and
    pass an already-ISO bound string straight through unchanged.

    Usage: {{ form.date_start.value|iso_date }}
    """
    if value in (None, ""):
        return ""
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value)
