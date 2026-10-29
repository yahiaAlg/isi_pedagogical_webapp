import os

from django.conf import settings
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pedagogical.settings")

_django_app = get_wsgi_application()


def application(environ, start_response):
    """Strip the mount prefix from PATH_INFO when the host doesn't (IIS).

    IIS mounts the app at /pedagogy and passes the full path (/pedagogy/admin)
    as PATH_INFO, while FORCE_SCRIPT_NAME already adds /pedagogy back, which
    yields /pedagogy/pedagogy/... A prefix-stripping proxy (nginx) is
    unaffected because the prefix is already gone by then.
    """
    prefix = settings.FORCE_SCRIPT_NAME or ""
    path = environ.get("PATH_INFO", "")
    if prefix and (path == prefix or path.startswith(prefix + "/")):
        environ["PATH_INFO"] = path[len(prefix) :] or "/"
    return _django_app(environ, start_response)
