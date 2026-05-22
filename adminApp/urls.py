from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('form_blog/', views.form_blog, name='form_blog'),
    #path('login/', auth_views.LoginView.as_view(), name='login'),
    path('login/', auth_views.LoginView.as_view(template_name='admin/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('formulaire/', views.formulaire, name='formulaire'),
    path('criar_post/', views.criar_post, name='criar_post'),
    path('visualizar_post/<int:post_id>/', views.visualizar_post, name='visualizar_post'),
    path('editar_post/<int:post_id>/', views.editar_post, name='editar_post'),
    path('deletar_post/<int:post_id>/', views.deletar_post, name='deletar_post'),
    path('admin_sobre/', views.admin_sobre, name='admin_sobre'),
    path('sobre/', views.sobre, name='sobre'),
]


