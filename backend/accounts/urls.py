from django.urls import path
from . import views

urlpatterns = [
    path("secret/", views.secret, name="secret"),
    path("", views.index, name="index"),
]