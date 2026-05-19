import httpx
from django.shortcuts import render
from django.http import StreamingHttpResponse, HttpResponse

def index(request):
    return render(request, 'geo/index.html')

def blog(request):
    return render(request, 'geo/blog.html')

def sobre(request):
    return render(request, 'geo/sobre.html')

def contato(request):
    return render(request, 'geo/contato.html')


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


