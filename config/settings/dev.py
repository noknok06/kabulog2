"""Local development settings."""
from .base import *  # noqa: F401,F403
from .base import INSTALLED_APPS, MIDDLEWARE

DEBUG = True

# Email to console in dev (allauth flows, etc.).
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# django-debug-toolbar (optional, harmless if browser not local).
INSTALLED_APPS = INSTALLED_APPS + ["debug_toolbar"]
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE
INTERNAL_IPS = ["127.0.0.1"]
# Don't let the toolbar interfere with HTMX partial responses.
DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG and not request.headers.get("HX-Request")}

# Relaxed cookies for plain-HTTP local dev.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
