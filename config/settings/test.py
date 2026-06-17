"""Test settings: dev behaviour (DEBUG on for dev-login / as_of), minus the
debug toolbar so the test client stays clean and fast."""
from .dev import *  # noqa: F401,F403
from .dev import INSTALLED_APPS, MIDDLEWARE

INSTALLED_APPS = [a for a in INSTALLED_APPS if a != "debug_toolbar"]
MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
