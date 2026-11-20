from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def terminal_view(request):
    """
    Página que embute o xterm.js e abre a conexão WebSocket com o
    TerminalConsumer. @staff_member_required garante que só usuários
    logados no admin acessem essa URL — a checagem "de verdade"
    (is_superuser) acontece de novo no consumer, no handshake do
    WebSocket, porque a URL em si não impede alguém de tentar conectar
    direto no endpoint ws/.
    """
    return render(request, "admin/terminal.html")





# --- Upload de pasta pelo navegador (comando enviar_simulacao) --------
#
# A shell restrita roda no servidor e não lê arquivos do PC do usuário.
# Quando o usuário digita `enviar_simulacao`, a shell cria uma pasta
# UPLOAD_ROOT/<upload_id>/ e pede pro navegador (via sequência OSC) abrir
# um seletor de pasta. O JS da página manda cada Depth*.tif pra
# terminal_upload_arquivo e, no fim, chama terminal_upload_fim, que cria
# o marcador ".concluido" que a shell está esperando.

import fnmatch
import os
import re
import tempfile

from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST

UPLOAD_ROOT = os.environ.get(
    "ADMIN_TERMINAL_UPLOAD_ROOT",
    os.path.join(tempfile.gettempdir(), "appras_uploads"),
)
_UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _pasta_upload(request, upload_id):
    """Valida usuário e id; devolve a pasta criada pela shell ou levanta 404."""
    if not (request.user.is_authenticated and request.user.is_superuser):
        return None
    if not _UPLOAD_ID_RE.match(upload_id):
        raise Http404
    pasta = os.path.join(UPLOAD_ROOT, upload_id)
    # Só aceita pastas criadas por uma shell ativa e ainda não finalizadas.
    if not os.path.isdir(pasta) or os.path.exists(os.path.join(pasta, ".concluido")):
        raise Http404
    return pasta


@require_POST
def terminal_upload_arquivo(request, upload_id):
    pasta = _pasta_upload(request, upload_id)
    if pasta is None:
        return HttpResponseForbidden()

    arquivo = request.FILES.get("arquivo")
    if arquivo is None:
        return JsonResponse({"ok": False, "erro": "campo 'arquivo' ausente"}, status=400)

    nome = os.path.basename(arquivo.name.replace("\\", "/"))
    if not fnmatch.fnmatch(nome.lower(), "depth*.tif"):
        return JsonResponse({"ok": False, "erro": f"arquivo ignorado: {nome}"}, status=400)

    # Grava com nome temporário e renomeia no fim, pra shell nunca contar
    # (nem importar) um arquivo pela metade.
    destino = os.path.join(pasta, nome)
    parcial = destino + ".parcial"
    with open(parcial, "wb") as f:
        for chunk in arquivo.chunks():
            f.write(chunk)
    os.replace(parcial, destino)
    return JsonResponse({"ok": True})


@require_POST
def terminal_upload_fim(request, upload_id):
    pasta = _pasta_upload(request, upload_id)
    if pasta is None:
        return HttpResponseForbidden()
    marcador = ".cancelado" if request.POST.get("cancelado") == "1" else ".concluido"
    open(os.path.join(pasta, marcador), "w").close()
    return JsonResponse({"ok": True})
