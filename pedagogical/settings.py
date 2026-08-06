import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY = os.environ["SECRET_KEY"]

DEBUG = os.environ.get("DEBUG", "False") == "True"

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# Spec §11.6 — base URL used to build the default QR-code verification link
# printed on attestations (e.g. https://isi-example.dz).
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")
    if o.strip()
]

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "import_export",
    # Local
    "core",
    "accounts",
    "clients",
    "resources",
    "formations",
    "documents",
    "reporting",
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "pedagogical.urls"

# ---------------------------------------------------------------------------
# Deployment environment switch
# ---------------------------------------------------------------------------
# Production hosts several sibling Django subprojects behind one reverse
# proxy, each mounted under its own path prefix (this project lives at
# /pedagogy). FORCE_SCRIPT_NAME tells Django about that prefix so
# reverse()/{% url %} and STATIC_URL/MEDIA_URL all resolve correctly
# through the proxy.
#
# Locally (`python manage.py runserver`) there is no reverse proxy adding
# that prefix, so forcing it breaks every URL — including runserver's own
# static/media serving in urls.py, which matches against the (already
# prefix-free) PATH_INFO it receives directly. Set DEPLOY_ENV=local in
# .env for local testing to drop the prefix entirely; leave it unset (or
# DEPLOY_ENV=production) for the real deployment.
DEPLOY_ENV = os.environ.get("DEPLOY_ENV", "production")

URL_PREFIX = (
    "" if DEPLOY_ENV == "local" else os.environ.get("URL_PREFIX", "/pedagogy")
)

FORCE_SCRIPT_NAME = URL_PREFIX or None
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "pedagogical.wsgi.application"

# ---------------------------------------------------------------------------
# Database — SQLite locally, PostgreSQL on Render
# ---------------------------------------------------------------------------
DB_ENGINE = os.environ.get("DB_ENGINE", "django.db.backends.sqlite3")

if DB_ENGINE == "django.db.backends.sqlite3":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.environ["DB_NAME"],
            "USER": os.environ["DB_USER"],
            "PASSWORD": os.environ["DB_PASSWORD"],
            "HOST": os.environ["DB_HOST"],
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Algiers"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files — WhiteNoise
# ---------------------------------------------------------------------------
# Derived from URL_PREFIX (see DEPLOY_ENV above): "/pedagogy/static/" in
# production, "/static/" when DEPLOY_ENV=local.
STATIC_URL = f"{URL_PREFIX}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Only include the project-level static/ dir if it actually exists.
# This avoids the W004 warning when the folder hasn't been created yet.
_STATIC_DIR = BASE_DIR / "static"
STATICFILES_DIRS = [_STATIC_DIR] if _STATIC_DIR.exists() else []

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# Media files
# ---------------------------------------------------------------------------
# Derived from URL_PREFIX too, for the same reason as STATIC_URL above.
MEDIA_URL = f"{URL_PREFIX}/media/"
MEDIA_ROOT = os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media"))

# ---------------------------------------------------------------------------
# Email — used for notifications (e.g. PV de délibération généré)
# Falls back to printing emails to the console when unconfigured, so local
# dev / tests never fail for lack of SMTP credentials.
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    (
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "mail.excellance-ms.dz")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "465"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "support@excellance-ms.dz")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "system2026*")
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "True") == "True"
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "False") == "True"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "support@excellance-ms.dz")

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# ---------------------------------------------------------------------------
# Security headers — production only
# ---------------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

# ---------------------------------------------------------------------------
# Logging — writes to logs/django.log so caught exceptions (e.g. document
# generation errors, which are shown to the user only as a generic flash
# message) are still visible on disk for debugging.
# ---------------------------------------------------------------------------
_LOG_DIR = BASE_DIR / "logs"
_LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": _LOG_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["file", "console"],
        "level": "INFO",
    },
}
