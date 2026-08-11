"""
models.py — App de visualização de resultados HEC-RAS (estilo RAS Mapper)

Coloque este arquivo dentro do app `AppRas` (AppRas/models.py).
"""
from django.db import models
from django.urls import reverse


class FloodSimulation(models.Model):
    """
    Representa uma rodada de simulação do HEC-RAS (um conjunto de timesteps
    de profundidade exportados como GeoTIFF pelo RAS Mapper).
    """
    name = models.CharField(
        "Nome da simulação", max_length=255,
        help_text="Ex: Cheia Rio X - Abril 2025"
    )
    description = models.TextField("Descrição", blank=True)
    created_at = models.DateTimeField("Criado em", auto_now_add=True)

    # Bounds em EPSG:4326 da área total (calculado automaticamente
    # a partir do primeiro timestep processado)
    bounds_west = models.FloatField(null=True, blank=True)
    bounds_south = models.FloatField(null=True, blank=True)
    bounds_east = models.FloatField(null=True, blank=True)
    bounds_north = models.FloatField(null=True, blank=True)

    # Faixa global de profundidade (todos os timesteps), usada para manter
    # a MESMA escala de cor em toda a animação — essencial para o efeito
    # visual de "água subindo/descendo" ficar coerente entre os frames.
    global_depth_min = models.FloatField(default=0.0)
    global_depth_max = models.FloatField(null=True, blank=True)

    is_processed = models.BooleanField(
        "Processado", default=False,
        help_text="True quando todos os timesteps já foram convertidos para PNG"
    )

    class Meta:
        verbose_name = "Simulação de Inundação"
        verbose_name_plural = "Simulações de Inundação"
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("AppRas:simulation_viewer", args=[self.pk])

    @property
    def bounds_leaflet(self):
        """Retorna bounds no formato que o Leaflet espera: [[south, west], [north, east]]"""
        if None in (self.bounds_south, self.bounds_west, self.bounds_north, self.bounds_east):
            return None
        return [
            [self.bounds_south, self.bounds_west],
            [self.bounds_north, self.bounds_east],
        ]


def geotiff_upload_path(instance, filename):
    return f"flood_sim/{instance.simulation_id}/raw/{filename}"


def overlay_upload_path(instance, filename):
    return f"flood_sim/{instance.simulation_id}/overlays/{filename}"


class FloodTimestep(models.Model):
    """
    Um único frame/timestep da simulação (um arquivo GeoTIFF do HEC-RAS
    e o PNG colorizado correspondente, já em EPSG:4326, pronto para o mapa).
    """
    simulation = models.ForeignKey(
        FloodSimulation, on_delete=models.CASCADE, related_name="timesteps"
    )
    timestamp = models.DateTimeField(
        "Data/Hora da simulação",
        help_text="Extraído do nome do arquivo (ex: 03APR2025_17_00_00)"
    )

    geotiff = models.FileField(
        "Arquivo GeoTIFF original", upload_to=geotiff_upload_path
    )

    # Gerado automaticamente pelo processamento — não precisa subir manualmente
    overlay_png = models.ImageField(
        "Overlay PNG (gerado)", upload_to=overlay_upload_path,
        null=True, blank=True
    )

    # Bounds específicos deste frame em EPSG:4326 (pode variar ligeiramente
    # do bounds global se você optar por crop por timestep)
    bounds_west = models.FloatField(null=True, blank=True)
    bounds_south = models.FloatField(null=True, blank=True)
    bounds_east = models.FloatField(null=True, blank=True)
    bounds_north = models.FloatField(null=True, blank=True)

    depth_min = models.FloatField(null=True, blank=True)
    depth_max = models.FloatField(null=True, blank=True)

    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)

    class Meta:
        verbose_name = "Timestep de Inundação"
        verbose_name_plural = "Timesteps de Inundação"
        ordering = ["timestamp"]
        unique_together = ["simulation", "timestamp"]

    def __str__(self):
        return f"{self.simulation.name} — {self.timestamp:%d/%m/%Y %H:%M}"

    @property
    def bounds_leaflet(self):
        if None in (self.bounds_south, self.bounds_west, self.bounds_north, self.bounds_east):
            return None
        return [
            [self.bounds_south, self.bounds_west],
            [self.bounds_north, self.bounds_east],
        ]
