from django.urls import path

from . import views

urlpatterns = [
    path("", views.album_list, name="album_list"),
    path("<int:pk>/", views.album_detail, name="album_detail"),
]
