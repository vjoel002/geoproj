from django.shortcuts import render, redirect, get_object_or_404
from adminApp.models import Admin, Post
from django.contrib.auth.decorators import login_required
from AppGeo.models import Contato
from AppGeo.models import Visita
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count
from django.db.models.functions import TruncDate
import json
from django.core.paginator import Paginator

'''@login_required
def admin_dashboard(request):
    posts = Post.objects.all().order_by('-id')
    return render(request, 'admin/dashboard.html', {'posts': posts})'''

def form_blog(request):
    return render(request, 'admin/formBlog.html')

def login(request):
    return render(request, 'admin/login.html')

def formulaire(request):
    if request.method == "POST":
        name = request.POST.get("nome")
        email = request.POST.get("email")
        password = request.POST.get("password")
        Admin.objects.create(name=name, email=email, password=password)
        return redirect("sucesso")
    return render(request, "formBlog.html")


@login_required
def criar_post(request):
    if request.method == 'POST':
        post = Post()
        post.titulo = request.POST.get('titulo')
        post.conteudo = request.POST.get('conteudo')
        post.status = request.POST.get('status')
        post.visibilidade = request.POST.get('visibilidade')
        if request.FILES.get('imagem_destaque'):
            post.imagem_destaque = request.FILES['imagem_destaque']
        post.save()
        return redirect('editar_post', post_id=post.id)

    return render(request, 'admin/adminblog.html', {'post': None})

@login_required
def visualizar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'admin/visualizar_post.html', {'post': post})

@login_required
def editar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        post.titulo = request.POST.get('titulo')
        post.conteudo = request.POST.get('conteudo')
        post.status = request.POST.get('status')
        post.visibilidade = request.POST.get('visibilidade')
        if request.POST.get('remover_imagem') == '1':
            post.imagem_destaque = None
        elif request.FILES.get('imagem_destaque'):
            post.imagem_destaque = request.FILES['imagem_destaque']
        post.save()
        return redirect('editar_post', post_id=post.id)
    return render(request, 'admin/adminblog.html', {'post': post})

@login_required
def deletar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        post.delete()
        return redirect('admin_dashboard')
    return redirect('admin_dashboard')


from .models import Sobre

@login_required
def admin_sobre(request):
    sobre = Sobre.objects.first()

    if request.method == 'POST':
        if not sobre:
            sobre = Sobre()

        sobre.nome = request.POST.get('nome', '')
        sobre.titulo_profissional = request.POST.get('titulo_profissional', '')
        sobre.bio = request.POST.get('bio', '')
        sobre.email = request.POST.get('email', '')
        sobre.telefone = request.POST.get('telefone', '')
        sobre.linkedin = request.POST.get('linkedin', '')
        sobre.github = request.POST.get('github', '')
        sobre.lattes = request.POST.get('lattes', '')
        sobre.portfolio = request.POST.get('portfolio', '')

        if request.POST.get('remover_foto') == '1':
            sobre.foto = None
        elif request.FILES.get('foto'):
            sobre.foto = request.FILES['foto']

        sobre.save()
        return redirect('admin_sobre')

    return render(request, 'admin/admin_sobre.html', {'sobre': sobre})


def sobre(request):
    sobre = Sobre.objects.first()
    return render(request, 'sobre.html', {'sobre': sobre})

# +++++++++++++++++++++++++++++++++ mensagem do contato +++++++++++++++++++++++++++++++++++
@login_required
def admin_mensagens(request):
    todas_mensagens = Contato.objects.all()

    # Paginação — 10 mensagens por página
    paginator = Paginator(todas_mensagens, 10)
    pagina_num = request.GET.get('page', 1)
    mensagens = paginator.get_page(pagina_num)

    # Marcar como lida ao abrir o detalhe
    msg_id = request.GET.get('id')
    msg_detalhe = None
    if msg_id:
        msg_detalhe = get_object_or_404(Contato, id=msg_id)
        if not msg_detalhe.read:
            msg_detalhe.read = True
            msg_detalhe.save()

    nao_lidas = todas_mensagens.filter(read=False).count()
    return render(request, 'admin/admin_mensagens.html', {
        'mensagens': mensagens,
        'msg_detalhe': msg_detalhe,
        'nao_lidas': nao_lidas,
    })


@login_required
def deletar_mensagem(request, msg_id):
    msg = get_object_or_404(Contato, id=msg_id)
    if request.method == 'POST':
        msg.delete()
    return redirect('admin_mensagens')


@login_required
def admin_dashboard(request):
    posts = Post.objects.all().order_by('-id')

    # Visitas dos últimos 30 dias
    trinta_dias = timezone.now() - timedelta(days=30)
    visitas_periodo = Visita.objects.filter(criado_em__gte=trinta_dias)

    # Total geral
    total_visitas = Visita.objects.count()

    # Visitas hoje
    hoje = timezone.now().date()
    visitas_hoje = Visita.objects.filter(criado_em__date=hoje).count()

    # Por página
    por_pagina = (
        Visita.objects.values('pagina')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    # Por dia (últimos 30 dias) — para o gráfico
    por_dia = (
        visitas_periodo
        .annotate(dia=TruncDate('criado_em'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )
    #graf_labels = [str(v['dia']) for v in por_dia]
    #graf_data   = [v['total'] for v in por_dia]

    graf_labels = json.dumps([str(v['dia']) for v in por_dia])
    graf_data   = json.dumps([v['total'] for v in por_dia])

    # Top países
    top_paises = (
        Visita.objects.exclude(pais='')
        .values('pais')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    # Top cidades
    top_cidades = (
        Visita.objects.exclude(cidade='')
        .values('cidade', 'pais')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    return render(request, 'admin/dashboard.html', {
        'posts': posts,
        'total_visitas': total_visitas,
        'visitas_hoje': visitas_hoje,
        'por_pagina': por_pagina,
        'graf_labels': graf_labels,
        'graf_data': graf_data,
        'top_paises': top_paises,
        'top_cidades': top_cidades,
    })





