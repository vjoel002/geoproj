import httpx
from django.shortcuts import get_object_or_404, redirect, render
from django.http import StreamingHttpResponse, HttpResponse
from AppGeo.models import Contato
from adminApp.models import Sobre
from adminApp.models import Post
from django.core.paginator import Paginator

def index(request):
    return render(request, 'geo/index.html')

def blog(request):
    todos_posts = Post.objects.filter(status='publicado').order_by('-criado_em')
    paginator = Paginator(todos_posts, 6)
    pagina_num = request.GET.get('page', 1)
    posts = paginator.get_page(pagina_num)
    return render(request, 'geo/blog.html', {'posts': posts})

def post_detalhe(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'geo/post_detalhe.html', {'post': post})

def sobre(request):
    sobre = Sobre.objects.first()
    return render(request, 'geo/sobre.html', {'sobre': sobre})


def contato(request):
    enviado = False
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        phone = request.POST.get('phone', '')
        message = request.POST.get('message')
        if email and message:
            Contato.objects.create(name=name, email=email, phone=phone, message=message)
            enviado = True
            return redirect("sucesso")
    return render(request, 'geo/contato.html', {'enviado': enviado})

def sucesso(request):
    return render(request, 'geo/sucesso.html')

def simulacao(request):
    return render(request, 'geo/simulacao.html')

# +++++++++++++++++++++++++++++++++ Vanna AI +++++++++++++++++++++++++++++++++++

def proxy_geojson_stream(request):
    tolerance = request.GET.get("tolerance", "0.005")
    url = f"http://localhost:8001/geojson/municipios/stream?tolerance={tolerance}"

    def generate():
        with httpx.stream("GET", url) as r:
            for chunk in r.iter_bytes():
                yield chunk

    return StreamingHttpResponse(generate(), content_type="application/geo+json")

def proxy_shapefile(request, cd_mun):
    url = f"http://localhost:8001/download/shapefile/{cd_mun}"
    resp = httpx.get(url)
    response = HttpResponse(resp.content, content_type="application/zip")
    response["Content-Disposition"] = resp.headers.get("Content-Disposition", "")
    return response

# +++++++++++++++++++++++++++++++++ Vanna AI +++++++++++++++++++++++++++++++++++


