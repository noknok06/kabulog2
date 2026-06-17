"""
Dev-only quick login. Mounted only when DEBUG is on (see urls.py), so it cannot
exist in production. Lets us walk the core loop without Google secrets locally.
"""
from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.http import Http404
from django.shortcuts import redirect

User = get_user_model()


def dev_login(request):
    if not settings.DEBUG:
        raise Http404()
    email = getattr(settings, "DEV_LOGIN_EMAIL", None) or "dev@example.com"
    user, _ = User.objects.get_or_create(
        email=email,
        defaults={"is_staff": True, "is_superuser": True},
    )
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return redirect("home")
