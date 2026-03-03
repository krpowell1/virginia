from __future__ import annotations

import os
from pathlib import Path

from decouple import Csv, config

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------
SECRET_KEY: str = config("DJANGO_SECRET_KEY")
DEBUG: bool = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS: list[str] = config(
    "DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv()
)
DOMAIN: str = config("DOMAIN", default="localhost")
CSRF_TRUSTED_ORIGINS: list[str] = [f"https://{DOMAIN}"]
if DEBUG:
    CSRF_TRUSTED_ORIGINS.append(f"http://{DOMAIN}")

# Production security hardening
if not DEBUG:
    SECURE_SSL_REDIRECT: bool = True
    SECURE_HSTS_SECONDS: int = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS: bool = True
    SECURE_HSTS_PRELOAD: bool = True
    SESSION_COOKIE_SECURE: bool = True
    CSRF_COOKIE_SECURE: bool = True
    SECURE_PROXY_SSL_HEADER: tuple[str, str] = ("HTTP_X_FORWARDED_PROTO", "https")

# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------
INSTALLED_APPS: list[str] = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "django_htmx",
    "django_ical",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "django_otp_webauthn",
    # Local
    "apps.cases",
    "apps.accounts",
]

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF: str = "config.urls"

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

WSGI_APPLICATION: str = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — SQLite with WAL mode
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path(
            config("DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3"))
        ),
    }
}


def _set_sqlite_pragmas(sender: type, connection: object, **kwargs: object) -> None:
    """Set SQLite PRAGMAs on every new connection.

    WAL mode enables concurrent reads during writes.
    synchronous=NORMAL is safe with WAL and improves write performance.
    """
    if getattr(connection, "vendor", None) == "sqlite":
        cursor = connection.cursor()  # type: ignore[union-attr]
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.execute("PRAGMA foreign_keys=ON;")


from django.db.backends.signals import connection_created  # noqa: E402

connection_created.connect(_set_sqlite_pragmas)

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "America/Chicago"
USE_I18N: bool = True
USE_TZ: bool = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL: str = "static/"
STATIC_ROOT: Path = BASE_DIR / "staticfiles"
STATICFILES_DIRS: list[Path] = [BASE_DIR / "static"]
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# ---------------------------------------------------------------------------
# Default primary key field type
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Session — 8-hour cookie lifetime
# ---------------------------------------------------------------------------
SESSION_COOKIE_AGE: int = 8 * 60 * 60  # 8 hours in seconds
SESSION_SAVE_EVERY_REQUEST: bool = True

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
LOGIN_URL: str = "/accounts/login/"
LOGIN_REDIRECT_URL: str = "/"
LOGOUT_REDIRECT_URL: str = "/accounts/login/"

# ---------------------------------------------------------------------------
# Authentication backends
# ---------------------------------------------------------------------------
AUTHENTICATION_BACKENDS: list[str] = [
    "django_otp_webauthn.backends.WebAuthnBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ---------------------------------------------------------------------------
# WebAuthn / Passkeys (Face ID)
# ---------------------------------------------------------------------------
OTP_WEBAUTHN_RP_ID: str = config("WEBAUTHN_RP_ID", default="localhost")
OTP_WEBAUTHN_RP_NAME: str = "Defense Case Manager"
OTP_WEBAUTHN_ALLOWED_ORIGINS: list[str] = [
    config("WEBAUTHN_ORIGIN", default="http://localhost:8000")
]
OTP_WEBAUTHN_ALLOW_PASSWORDLESS_LOGIN: bool = True

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
