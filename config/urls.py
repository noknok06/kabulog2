from django.conf import settings
from django.contrib import admin
from django.urls import include, path

from recall import views as recall_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("accounts.urls")),  # dev-login (DEBUG only) lives here
    path("journal/", include("journal.urls")),
    path("", recall_views.home, name="home"),  # home == the place of recall
    path("", include("recall.urls")),  # recall actions (dismiss, …)
]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
    except ImportError:
        pass
