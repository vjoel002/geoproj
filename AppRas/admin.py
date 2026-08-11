"""
admin.py — Upload de simulações no adminApp.

Fluxo de uso:
1. No admin, crie uma `FloodSimulation` (nome + descrição).
2. Na mesma tela, use o inline para subir os .tif (um FloodTimestep por
   arquivo) — ou use a action "Processar timesteps selecionados" depois
   de subir todos.
3. Ao salvar, um signal (ver apps.py/signals.py) ou a action do admin
   dispara `process_depth_geotiff` para gerar os PNGs.
"""
from django.contrib import admin
from django.utils.html import format_html

from .models import FloodSimulation, FloodTimestep
from .services import process_simulation_timesteps, reprocess_timestep


class FloodTimestepInline(admin.TabularInline):
    model = FloodTimestep
    extra = 1
    fields = ("geotiff", "timestamp", "is_processed", "depth_max", "preview")
    readonly_fields = ("timestamp", "is_processed", "depth_max", "preview")
    show_change_link = True

    def preview(self, obj):
        if obj.overlay_png:
            return format_html(
                '<img src="{}" style="max-height:60px;" />', obj.overlay_png.url
            )
        return "—"
    preview.short_description = "Preview"


@admin.register(FloodSimulation)
class FloodSimulationAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "timestep_count", "is_processed")
    list_filter = ("is_processed", "created_at")
    search_fields = ("name", "description")
    inlines = [FloodTimestepInline]
    actions = ["process_selected_simulations"]
    readonly_fields = (
        "bounds_west", "bounds_south", "bounds_east", "bounds_north",
        "global_depth_min", "global_depth_max", "is_processed",
    )

    def timestep_count(self, obj):
        return obj.timesteps.count()
    timestep_count.short_description = "Nº Timesteps"

    @admin.action(description="Processar GeoTIFFs (gerar overlays PNG)")
    def process_selected_simulations(self, request, queryset):
        total = 0
        for sim in queryset:
            count = process_simulation_timesteps(sim)
            total += count
        self.message_user(
            request, f"{total} timestep(s) processado(s) com sucesso."
        )


@admin.register(FloodTimestep)
class FloodTimestepAdmin(admin.ModelAdmin):
    list_display = (
        "simulation", "timestamp", "is_processed", "depth_max", "preview"
    )
    list_filter = ("simulation", "is_processed")
    readonly_fields = (
        "overlay_png", "bounds_west", "bounds_south", "bounds_east",
        "bounds_north", "depth_min", "depth_max", "is_processed",
        "processing_error", "preview_large",
    )
    actions = ["reprocess_selected"]

    def preview(self, obj):
        if obj.overlay_png:
            return format_html(
                '<img src="{}" style="max-height:40px;" />', obj.overlay_png.url
            )
        return "—"
    preview.short_description = "Preview"

    def preview_large(self, obj):
        if obj.overlay_png:
            return format_html(
                '<img src="{}" style="max-width:500px;" />', obj.overlay_png.url
            )
        return "Ainda não processado"
    preview_large.short_description = "Preview do overlay"

    @admin.action(description="Reprocessar GeoTIFF selecionado(s)")
    def reprocess_selected(self, request, queryset):
        ok, fail = 0, 0
        for ts in queryset:
            try:
                reprocess_timestep(ts)
                ok += 1
            except Exception as exc:
                fail += 1
                ts.processing_error = str(exc)
                ts.save(update_fields=["processing_error"])
        self.message_user(request, f"{ok} reprocessado(s), {fail} com erro.")
