"""
Production settings (placeholder for the deferred deploy phase).

Google OIDC is a CONFIG-ONLY addition here — no model or view changes are needed
because all data is already owner-scoped on request.user.
"""
from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

DEBUG = False

# Serve hashed static files efficiently in production.
MIDDLEWARE = (
    MIDDLEWARE[:1] + ["whitenoise.middleware.WhiteNoiseMiddleware"] + MIDDLEWARE[1:]
)

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")

# Hashed + compressed static assets (run collectstatic at deploy).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# --- Google OIDC slot (fill from env when deploying) ------------------------
# SOCIALACCOUNT_PROVIDERS = {
#     "openid_connect": {
#         "APPS": [
#             {
#                 "provider_id": "google",
#                 "name": "Google",
#                 "client_id": env("GOOGLE_CLIENT_ID"),
#                 "secret": env("GOOGLE_CLIENT_SECRET"),
#                 "settings": {"server_url": "https://accounts.google.com"},
#             }
#         ]
#     }
# }
