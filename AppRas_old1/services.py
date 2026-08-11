"""
services.py — Orquestra o processamento dos GeoTIFFs usando os models
do Django (lê o FileField, chama raster_processing, salva o PNG de volta
no ImageField, atualiza bounds e flags).
"""
import os
from django.core.files import File
from django.conf import settings

from .raster_processing import (
    parse_timestamp_from_filename,
    process_depth_geotiff,
    compute_global_depth_range,
)


def process_simulation_timesteps(simulation) -> int:
    """
    Processa todos os timesteps ainda não processados de uma simulação.
    Primeiro calcula o range global de profundidade (para a escala de cor
    ser consistente entre frames), depois gera o PNG de cada um.

    Retorna o número de timesteps processados com sucesso.
    """
    timesteps = list(simulation.timesteps.all())
    if not timesteps:
        return 0

    # Garante que os timestamps estão preenchidos (extraídos do nome do
    # arquivo), necessário para ordenar a animação corretamente.
    for ts in timesteps:
        if ts.timestamp is None:
            ts.timestamp = parse_timestamp_from_filename(
                os.path.basename(ts.geotiff.name)
            )
            ts.save(update_fields=["timestamp"])

    # Calcula range global de profundidade (uma vez só, sobre todos os
    # arquivos) para manter a paleta de cor coerente ao longo da animação.
    if simulation.global_depth_max is None:
        paths = [ts.geotiff.path for ts in timesteps]
        depth_min, depth_max = compute_global_depth_range(paths)
        simulation.global_depth_min = depth_min
        simulation.global_depth_max = depth_max
        simulation.save(update_fields=["global_depth_min", "global_depth_max"])

    processed_count = 0
    sim_bounds = None

    for ts in timesteps:
        if ts.is_processed:
            processed_count += 1
            continue
        try:
            result = _process_single_timestep(ts, simulation)
            processed_count += 1
            sim_bounds = _merge_bounds(sim_bounds, result)
        except Exception as exc:
            ts.processing_error = str(exc)
            ts.save(update_fields=["processing_error"])

    if sim_bounds:
        simulation.bounds_west = sim_bounds["west"]
        simulation.bounds_south = sim_bounds["south"]
        simulation.bounds_east = sim_bounds["east"]
        simulation.bounds_north = sim_bounds["north"]

    simulation.is_processed = all(t.is_processed for t in simulation.timesteps.all())
    simulation.save()

    return processed_count


def reprocess_timestep(timestep):
    """Força o reprocessamento de um único timestep (ex: após corrigir erro)."""
    timestep.is_processed = False
    timestep.processing_error = ""
    return _process_single_timestep(timestep, timestep.simulation)


def _process_single_timestep(ts, simulation):
    out_dir = os.path.join(
        settings.MEDIA_ROOT, "flood_sim", str(simulation.pk), "overlays"
    )
    os.makedirs(out_dir, exist_ok=True)
    out_filename = f"{ts.timestamp:%Y%m%d_%H%M%S}.png"
    out_path = os.path.join(out_dir, out_filename)

    result = process_depth_geotiff(
        src_path=ts.geotiff.path,
        dst_png_path=out_path,
        depth_min=simulation.global_depth_min or 0.0,
        depth_max=simulation.global_depth_max,
    )

    with open(out_path, "rb") as f:
        ts.overlay_png.save(out_filename, File(f), save=False)

    ts.bounds_west = result["west"]
    ts.bounds_south = result["south"]
    ts.bounds_east = result["east"]
    ts.bounds_north = result["north"]
    ts.depth_min = result["depth_min"]
    ts.depth_max = result["depth_max"]
    ts.is_processed = True
    ts.processing_error = ""
    ts.save()

    return result


def _merge_bounds(current, new_result):
    if current is None:
        return {
            "west": new_result["west"], "south": new_result["south"],
            "east": new_result["east"], "north": new_result["north"],
        }
    return {
        "west": min(current["west"], new_result["west"]),
        "south": min(current["south"], new_result["south"]),
        "east": max(current["east"], new_result["east"]),
        "north": max(current["north"], new_result["north"]),
    }
