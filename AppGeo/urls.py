from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('blog/', views.blog, name='blog'),
    path('sobre/', views.sobre, name='sobre'),
    path('contato/', views.contato, name='contato'),
    path("geojson/municipios/stream", views.proxy_geojson_stream, name="geojson_stream"),
    path("download/shapefile/<str:cd_mun>", views.proxy_shapefile, name="shapefile"),
]


