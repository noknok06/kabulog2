from django.conf import settings
from django.urls import path

from . import views

urlpatterns = []

# Dev-only quick login. Never mounted in production.
if settings.DEBUG:
    urlpatterns += [path("dev-login/", views.dev_login, name="dev_login")]
