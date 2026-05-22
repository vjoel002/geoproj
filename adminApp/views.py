'''from django.shortcuts import render, redirect

from adminApp.models import Admin

def admin_dashboard(request):
    posts = Post.objects.all().order_by('-id')
    return render(request, 'admin/dashboard.html', {'posts': posts})

def form_blog(request):
    return render(request, 'admin/formBlog.html')

def login(request):
    return render(request, 'admin/login.html')

# ++++++++++++++++++++++++++++++ Exemplo de envio de dados para o banco ++++++++++++++++++++++++++++++

def formulaire(request):
    if request.method == "POST":
        name = request.POST.get("nome")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # salva no banco
        Admin.objects.create(name=name, email=email, password=password)
        return redirect("sucesso")

    return render(request, "formBlog.html")

# ++++++++++++++++++++++++++++++ Administração do blog ++++++++++++++++++++++++++++++

from django.shortcuts import render, redirect, get_object_or_404
from .models import Post

def editar_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)

    if request.method == 'POST':
        post.titulo = request.POST.get('titulo')
        post.conteudo = request.POST.get('conteudo')
        post.status = request.POST.get('status')
        post.visibilidade = request.POST.get('visibilidade')

        # ✅ Trata remoção de imagem
        if request.POST.get('remover_imagem') == '1':
            post.imagem_destaque = None
        # ✅ Nome do campo corrigido
        elif request.FILES.get('imagem_destaque'):
            post.imagem_destaque = request.FILES['imagem_destaque']

        post.save()
        return redirect('editar_post', post_id=post.id)

    return render(request, 'admin/adminblog.html', {'post': post})'''


from django.shortcuts import render, redirect, get_object_or_404
from adminApp.models import Admin, Post
from django.contrib.auth.decorators import login_required
from AppGeo.models import Contato

@login_required
def admin_dashboard(request):
    posts = Post.objects.all().order_by('-id')
    return render(request, 'admin/dashboard.html', {'posts': posts})

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


@login_required
def admin_mensagens(request):
    mensagens = Contato.objects.all()
    # Marcar como lida ao abrir o detalhe
    msg_id = request.GET.get('id')
    msg_detalhe = None
    if msg_id:
        msg_detalhe = get_object_or_404(Contato, id=msg_id)
        if not msg_detalhe.lida:
            msg_detalhe.lida = True
            msg_detalhe.save()
    nao_lidas = mensagens.filter(lida=False).count()
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