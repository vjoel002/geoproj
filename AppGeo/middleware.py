from ipware import get_client_ip
from django.contrib.gis.geoip2 import GeoIP2
from .models import Visita

PAGINAS_MONITORADAS = ['/', '/blog/', '/sobre/', '/contato/', '/simulacao/']

class VisitaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path
        if path in PAGINAS_MONITORADAS and request.method == 'GET':
            try:
                ip, _ = get_client_ip(request)
                pais = ''
                cidade = ''
                if ip and ip != '127.0.0.1':
                    try:
                        g = GeoIP2()
                        info = g.city(ip)
                        pais = info.get('country_name', '')
                        cidade = info.get('city', '')
                    except Exception:
                        pass
                Visita.objects.create(
                    pagina=path,
                    ip=ip,
                    pais=pais,
                    cidade=cidade,
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
                )
            except Exception:
                pass

        return response