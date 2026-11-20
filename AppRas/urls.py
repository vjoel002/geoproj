"""
urls.py — Inclua no urls.py principal do projeto:

    from django.urls import path, include
    urlpatterns = [
        ...
        path("flood/", include("AppRas.urls")),
    ]
"""
from django.urls import path
from . import views

app_name = "AppRas"

urlpatterns = [
    path("", views.simulation_list, name="simulation_list"),
    path("<int:pk>/", views.simulation_viewer, name="simulation_viewer"),
    path("api/upload/", views.simulation_upload_api, name="simulation_upload_api"),
    path("<int:pk>/api/timesteps/", views.simulation_timesteps_api, name="simulation_timesteps_api"),
]
