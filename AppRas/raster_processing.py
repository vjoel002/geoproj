"""
raster_processing.py — Converte GeoTIFF de profundidade do HEC-RAS em PNG
colorizado pronto para Leaflet (L.imageOverlay), igual ao comportamento
do RAS Mapper.

Dependências: rasterio, numpy, pillow, matplotlib
    pip install rasterio numpy pillow matplotlib
"""
import os
import re
from datetime import datetime
from pathlib import Path

# IMPORTANTE: em algumas máquinas Windows, instalar PostgreSQL/PostGIS
# define uma variável de ambiente global PROJ_LIB apontando para o
# proj.db do PostGIS, que costuma ser uma versão mais antiga/incompatível
# com a que o rasterio espera. Isso causa o erro:
#   "The EPSG code is unknown. PROJ: proj_create_from_database: ...
#    DATABASE.LAYOUT.VERSION.MINOR = X whereas a number >= Y is expected."
# Para evitar esse conflito, removemos PROJ_LIB/PROJ_DATA do ambiente
# ANTES de importar rasterio, forçando-o a usar o proj.db que já vem
# embutido no próprio pacote rasterio (instalado via pip).
os.environ.pop("PROJ_LIB", None)
os.environ.pop("PROJ_DATA", None)

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.transform import array_bounds
from PIL import Image
import matplotlib.colors as mcolors


# Paleta estilo RAS Mapper: raso (claro) -> fundo (escuro/roxo)
DEPTH_COLORS = [
    "#a8d5e5", "#5ab4d6", "#2c7fb8",
    "#225ea8", "#253494", "#1a1a6e", "#3d0b5e",
]
DEPTH_CMAP = mcolors.LinearSegmentedColormap.from_list("flood_depth", DEPTH_COLORS)

# Padrão de nome de arquivo do RAS Mapper. Aceita variações de separador
# que o HEC-RAS/RAS Mapper pode gerar dependendo da versão/config, ex:
#   Depth__03APR2025_17_00_00__Terrain_NEW_DSM.tif
#   Depth (03APR2025 17 00 00).Terrain.NEW_DSM.tif
FILENAME_PATTERN = re.compile(
    r"(\d{2})([A-Za-z]{3})(\d{4})[\s_\.\(]*(\d{2})[\s_\.:]*(\d{2})[\s_\.:]*(\d{2})"
)
MONTH_MAP = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def parse_timestamp_from_filename(filename: str) -> datetime:
    """
    Extrai a data/hora do nome de arquivo padrão HEC-RAS/RAS Mapper.
    Ex: 'Depth__03APR2025_17_00_00__Terrain_NEW_DSM.tif' -> datetime(2025, 4, 3, 17, 0, 0)
    """
    match = FILENAME_PATTERN.search(filename)
    if not match:
        raise ValueError(
            f"Não foi possível extrair timestamp do nome do arquivo: {filename}"
        )
    day, mon_str, year, hour, minute, second = match.groups()
    month = MONTH_MAP.get(mon_str.upper())
    if month is None:
        raise ValueError(f"Mês não reconhecido '{mon_str}' em {filename}")
    return datetime(int(year), month, int(day), int(hour), int(minute), int(second))


def process_depth_geotiff(
    src_path: str,
    dst_png_path: str,
    depth_min: float = 0.0,
    depth_max: float | None = None,
    pad_pixels: int = 5,
    alpha: int = 200,
):
    """
    Lê um GeoTIFF de profundidade (HEC-RAS), reprojeta para EPSG:3857
    (Web Mercator — CRS interno do Leaflet), recorta para a extensão de
    células com água (com margem), colore por profundidade e salva como
    PNG RGBA.

    Reprojetar para 3857 (e não 4326) é essencial para o alinhamento
    correto com os tiles de satélite/ruas do Leaflet: L.imageOverlay
    posiciona a imagem com base nos bounds lat/lon, mas internamente
    projeta para 3857. Em latitudes fora do equador, usar 4326 como
    CRS intermediário introduz distorção e causa deslocamento visual
    entre o overlay de inundação e o basemap.

    Os bounds retornados pelo processo são em EPSG:4326 (lat/lon), pois
    é o que o L.imageOverlay espera — mas foram derivados a partir dos
    cantos do raster em 3857, garantindo o alinhamento correto.

    Args:
        src_path: caminho do GeoTIFF de entrada.
        dst_png_path: caminho de saída do PNG.
        depth_min: profundidade mínima da escala de cor (geralmente 0).
        depth_max: profundidade máxima da escala de cor. Se None, usa o
            percentil 98 dos valores válidos DESTE arquivo.
        pad_pixels: margem (em pixels) ao redor da área molhada.
        alpha: opacidade do overlay (0-255).

    Returns:
        dict com bounds (west, south, east, north) em EPSG:4326 e
        depth_min/depth_max efetivamente usados.
    """
    from pyproj import Transformer

    # Reprojeta para EPSG:3857 (Web Mercator)
    dst_crs = "EPSG:3857"
    with rasterio.open(src_path) as src:
        nodata = src.nodata if src.nodata is not None else -9999.0

        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )

        dst_array = np.full((height, width), nodata, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst_array,
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=dst_crs,
            resampling=Resampling.bilinear,
            src_nodata=nodata,
            dst_nodata=nodata,
        )

    valid_mask = dst_array != nodata

    if not valid_mask.any():
        # Timestep sem água nenhuma (ex: início da simulação) — ainda
        # assim geramos um PNG vazio para não quebrar a sequência de frames.
        empty = np.zeros((1, 1, 4), dtype=np.uint8)
        Image.fromarray(empty, mode="RGBA").save(dst_png_path)
        full_bounds = array_bounds(height, width, transform)
        return {
            "west": full_bounds[0], "south": full_bounds[1],
            "east": full_bounds[2], "north": full_bounds[3],
            "depth_min": depth_min, "depth_max": depth_max or 0.0,
        }

    # Recorta para a bounding box da área com água (+ margem)
    rows = np.any(valid_mask, axis=1)
    cols = np.any(valid_mask, axis=0)
    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    rmin = max(0, rmin - pad_pixels)
    rmax = min(height - 1, rmax + pad_pixels)
    cmin = max(0, cmin - pad_pixels)
    cmax = min(width - 1, cmax + pad_pixels)

    cropped = dst_array[rmin:rmax + 1, cmin:cmax + 1]
    cropped_mask = valid_mask[rmin:rmax + 1, cmin:cmax + 1]

    crop_transform = rasterio.transform.from_origin(
        transform.c + cmin * transform.a,
        transform.f + rmin * transform.e,
        transform.a,
        -transform.e,
    )
    west, south, east, north = array_bounds(
        cropped.shape[0], cropped.shape[1], crop_transform
    )

    # Converte os bounds de EPSG:3857 (metros) para EPSG:4326 (lat/lon)
    # que é o que o L.imageOverlay do Leaflet espera como argumento.
    # Fazemos isso DEPOIS de reprojetar para 3857, não antes — isso garante
    # que os cantos do PNG estejam perfeitamente alinhados com os tiles
    # do Leaflet (que usa 3857 internamente), eliminando o deslocamento
    # visual em relação ao basemap de satélite.
    transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    west_lon, south_lat = transformer.transform(west, south)
    east_lon, north_lat = transformer.transform(east, north)

    effective_max = depth_max if depth_max is not None else float(
        np.percentile(cropped[cropped_mask], 98)
    )

    norm = mcolors.Normalize(vmin=depth_min, vmax=effective_max, clip=True)
    rgba = (DEPTH_CMAP(norm(cropped)) * 255).astype(np.uint8)
    rgba[:, :, 3] = np.where(cropped_mask, alpha, 0).astype(np.uint8)

    Path(dst_png_path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(dst_png_path)

    return {
        "west": west_lon, "south": south_lat,
        "east": east_lon, "north": north_lat,
        "depth_min": depth_min,
        "depth_max": effective_max,
    }


def compute_global_depth_range(geotiff_paths: list[str]) -> tuple[float, float]:
    """
    Varre todos os GeoTIFFs de uma simulação e calcula o range global de
    profundidade (percentil 98 do máximo entre todos os timesteps).
    Use o resultado como `depth_max` fixo em `process_depth_geotiff` para
    que a escala de cor não "pule" entre frames durante a animação.
    """
    global_max = 0.0
    for path in geotiff_paths:
        with rasterio.open(path) as src:
            arr = src.read(1)
            nodata = src.nodata if src.nodata is not None else -9999.0
            valid = arr[arr != nodata]
            if valid.size > 0:
                p98 = float(np.percentile(valid, 98))
                global_max = max(global_max, p98)
    return 0.0, global_max
