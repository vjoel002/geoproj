"""
views.py — Página do viewer (mapa + player) e API JSON que alimenta o
JavaScript com a lista de timesteps (URL do PNG + bounds + timestamp).
"""
import os

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404

from .models import FloodSimulation


def simulation_list(request):
    """Lista todas as simulações disponíveis (processadas)."""
    simulations = FloodSimulation.objects.filter(is_processed=True)
    return render(request, "AppRas/simulation_list.html", {
        "simulations": simulations,
    })


def simulation_viewer(request, pk):
    """Página principal: mapa Leaflet com player de timesteps."""
    simulation = get_object_or_404(FloodSimulation, pk=pk)
    return render(request, "AppRas/simulation_viewer.html", {
        "simulation": simulation,
    })


def simulation_timesteps_api(request, pk):
    """
    API JSON consumida pelo player JS.

    Resposta:
    {
        "bounds": [[south, west], [north, east]],
        "depth_max": 9.28,
        "timesteps": [
            {"timestamp": "2025-04-03T17:00:00", "label": "03/04 17:00",
             "overlay_url": "/media/.../17_00_00.png",
             "bounds": [[south, west], [north, east]]},
            ...
        ]
    }
    """
    simulation = get_object_or_404(FloodSimulation, pk=pk)
    timesteps = simulation.timesteps.filter(is_processed=True).order_by("timestamp")

    data = {
        "simulation_name": simulation.name,
        "bounds": simulation.bounds_leaflet,
        "depth_min": simulation.global_depth_min,
        "depth_max": simulation.global_depth_max,
        "timesteps": [
            {
                "timestamp": ts.timestamp.isoformat(),
                "label": ts.timestamp.strftime("%d/%m/%Y %H:%M"),
                "overlay_url": ts.overlay_png.url if ts.overlay_png else None,
                "bounds": ts.bounds_leaflet,
                "depth_max": ts.depth_max,
            }
            for ts in timesteps
        ],
    }
    return JsonResponse(data)


# --- Upload remoto de simulações -------------------------------------
#
# Permite enviar uma simulação a partir de qualquer PC (ex: script
# PowerShell enviar_simulacao.ps1) sem precisar que a pasta exista no
# servidor. O cliente manda um .zip com os Depth*.tif; o servidor
# extrai numa pasta temporária e roda o import_flood_simulation.
#
# Autenticação: header "Authorization: Bearer <token>", onde o token é
# a variável de ambiente SIMULACOES_UPLOAD_TOKEN (defina no .env).

import fnmatch
import hmac
import io
import tempfile
import zipfile

from django.core.management import CommandError, call_command
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST


def _token_valido(request):
    esperado = os.environ.get("SIMULACOES_UPLOAD_TOKEN", "")
    if not esperado:
        return False
    recebido = request.headers.get("Authorization", "")
    if not recebido.startswith("Bearer "):
        return False
    return hmac.compare_digest(recebido[len("Bearer "):].strip(), esperado)


@csrf_exempt
@require_POST
def simulation_upload_api(request):
    if not _token_valido(request):
        return JsonResponse({"ok": False, "erro": "token inválido ou ausente"}, status=401)

    nome = (request.POST.get("nome") or "").strip()
    descricao = (request.POST.get("descricao") or "").strip()
    arquivo = request.FILES.get("arquivo")
    if not nome or arquivo is None:
        return JsonResponse(
            {"ok": False, "erro": "campos obrigatórios: 'arquivo' (.zip) e 'nome'"}, status=400
        )

    saida = io.StringIO()
    with tempfile.TemporaryDirectory(prefix="upload_sim_") as pasta:
        try:
            with zipfile.ZipFile(arquivo) as zf:
                extraidos = 0
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    # Usa só o nome do arquivo (ignora subpastas do zip),
                    # o que também impede path traversal ("../../etc").
                    base = os.path.basename(info.filename.replace("\\", "/"))
                    if not fnmatch.fnmatch(base.lower(), "depth*.tif"):
                        continue
                    with zf.open(info) as src, open(os.path.join(pasta, base), "wb") as dst:
                        while chunk := src.read(1024 * 1024):
                            dst.write(chunk)
                    extraidos += 1
        except zipfile.BadZipFile:
            return JsonResponse({"ok": False, "erro": "arquivo enviado não é um .zip válido"}, status=400)

        if extraidos == 0:
            return JsonResponse(
                {"ok": False, "erro": "nenhum arquivo Depth*.tif encontrado no .zip"}, status=400
            )

        try:
            call_command(
                "import_flood_simulation",
                folder=pasta, name=nome, description=descricao,
                stdout=saida, stderr=saida, no_color=True,
            )
        except CommandError as exc:
            return JsonResponse({"ok": False, "erro": str(exc), "log": saida.getvalue()}, status=400)

    simulacao = FloodSimulation.objects.filter(name=nome).first()
    return JsonResponse({
        "ok": True,
        "id": simulacao.pk if simulacao else None,
        "url": f"/flood/{simulacao.pk}/" if simulacao else None,
        "log": saida.getvalue(),
    })
