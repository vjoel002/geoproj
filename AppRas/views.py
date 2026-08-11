"""
views.py — Página do viewer (mapa + player) e API JSON que alimenta o
JavaScript com a lista de timesteps (URL do PNG + bounds + timestamp).
"""
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
