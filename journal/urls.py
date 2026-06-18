from django.urls import path

from . import views

app_name = "journal"

urlpatterns = [
    path("compose/", views.compose, name="compose"),
    path("library/", views.library, name="library"),
    path("karte/", views.karte_index, name="karte_index"),
    path("karte/<str:ticker>/", views.karte, name="karte"),
    path("autosave/", views.autosave, name="autosave"),
    path("publish/", views.publish, name="publish"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/score/", views.score, name="score"),
    path("<int:pk>/result/", views.result_edit, name="result"),
]
