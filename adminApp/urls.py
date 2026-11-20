from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views_terminal import terminal_view, terminal_upload_arquivo, terminal_upload_fim

urlpatterns = [
    path('admin_dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('form_blog/', views.form_blog, name='form_blog'),
    path('terminal/', terminal_view, name='admin_terminal'),
    path('terminal/upload/<str:upload_id>/arquivo/', terminal_upload_arquivo, name='terminal_upload_arquivo'),
    path('terminal/upload/<str:upload_id>/fim/', terminal_upload_fim, name='terminal_upload_fim'),
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
    path('admin_mensagens/', views.admin_mensagens, name='admin_mensagens'),
    path('deletar_mensagem/<int:msg_id>/', views.deletar_mensagem, name='deletar_mensagem'),
]


