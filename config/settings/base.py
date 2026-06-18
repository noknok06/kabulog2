"""
Base settings shared by all environments.

Everything that can be environment-driven is read from the environment via
django-environ. dev/prod parity is a first principle: the same PostgreSQL 16 +
pgvector is used everywhere; there is no SQLite fallback.
"""
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-only-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Dev-only quick-login identity (used only when DEBUG; see accounts.views.dev_login).
DEV_LOGIN_EMAIL = env("DEV_LOGIN_EMAIL", default="dev@example.com")

# --- Applications -----------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "django_htmx",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    # Provider is registered but left UNCONFIGURED in dev: no Google secrets needed.
    # Wiring Google OIDC later is config-only (see prod.py).
    "allauth.socialaccount.providers.openid_connect",
]

LOCAL_APPS = [
    "common",
    "accounts",
    "journal",
    "recall",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise is added in prod.py only; dev serves static via Django.
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "config.urls"

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
                "common.context_processors.as_of_date",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database (PostgreSQL only; no SQLite — dev/prod parity) -----------------
DATABASES = {"default": env.db("DATABASE_URL")}

# --- Semantic search (embeddings) -------------------------------------------
# "local"   = run an HF sentence-transformer on-box (private; no data leaves).
# "fallback"= deterministic hash embedding (no deps/network; tests use this).
# The backend is swappable; the model/dim are fixed to the VectorField column.
EMBEDDING_BACKEND = env("EMBEDDING_BACKEND", default="local")
EMBEDDING_MODEL = env("EMBEDDING_MODEL", default="intfloat/multilingual-e5-base")
EMBEDDING_DIM = 768  # must match journal.Entry.embedding's VectorField dimensions

# --- Auth -------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "account_login"

SITE_ID = 1

# allauth: email-first, no username, ready for OIDC.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
SOCIALACCOUNT_ADAPTER = "accounts.adapters.SocialAccountAdapter"

# --- I18N / TZ --------------------------------------------------------------
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# --- Static / media ---------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
# Plain static storage in dev/test; prod swaps in whitenoise's hashed/compressed
# manifest storage (see prod.py) which requires collectstatic.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Media is served via authorized Django views only (never public). Reserved for later.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Security cookies (HTTPS enforced in prod) ------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # JS reads the token to set the HTMX header
