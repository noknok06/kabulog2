from django.urls import path

from . import views

app_name = "recall"

urlpatterns = [
    path("recall/<int:pk>/dismiss/", views.dismiss, name="dismiss"),
]
