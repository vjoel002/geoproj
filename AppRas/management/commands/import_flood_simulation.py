"""
Management command: importa todos os .tif de uma pasta (export do RAS
Mapper) para uma FloodSimulation, criando os FloodTimestep e disparando
o processamento automaticamente.

Uso:
    python manage.py import_flood_simulation --folder "C:/caminho/para/export_rasmapper" --name "Cheia Rio X - Abril 2025"
"""
import glob
import os

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from AppRas.models import FloodSimulation, FloodTimestep
from AppRas.raster_processing import parse_timestamp_from_filename
from AppRas.services import process_simulation_timesteps


class Command(BaseCommand):
    help = "Importa uma pasta de GeoTIFFs de profundidade (HEC-RAS/RAS Mapper) como uma FloodSimulation"

    def add_arguments(self, parser):
        parser.add_argument(
            "--folder", required=True,
            help="Pasta contendo os arquivos Depth__*.tif"
        )
        parser.add_argument(
            "--name", required=True,
            help="Nome da simulação a ser criada"
        )
        parser.add_argument(
            "--pattern", default="Depth*.tif",
            help="Padrão glob dos arquivos (default: Depth*.tif, cobre variações como 'Depth__...' ou 'Depth (...)...')"
        )

    def handle(self, *args, **options):
        folder = options["folder"]
        name = options["name"]
        pattern = options["pattern"]

        if not os.path.isdir(folder):
            raise CommandError(f"Pasta não encontrada: {folder}")

        files = sorted(glob.glob(os.path.join(folder, pattern)))
        if not files:
            raise CommandError(f"Nenhum arquivo encontrado com padrão '{pattern}' em {folder}")

        self.stdout.write(f"Encontrados {len(files)} arquivo(s).")

        simulation, created = FloodSimulation.objects.get_or_create(name=name)
        if created:
            self.stdout.write(self.style.SUCCESS(f"Simulação '{name}' criada."))
        else:
            self.stdout.write(f"Usando simulação existente '{name}'.")

        imported = 0
        for filepath in files:
            filename = os.path.basename(filepath)
            try:
                timestamp = parse_timestamp_from_filename(filename)
            except ValueError as exc:
                self.stdout.write(self.style.WARNING(f"Pulando {filename}: {exc}"))
                continue

            if FloodTimestep.objects.filter(simulation=simulation, timestamp=timestamp).exists():
                self.stdout.write(f"Já existe timestep para {timestamp}, pulando.")
                continue

            with open(filepath, "rb") as f:
                ts = FloodTimestep(simulation=simulation, timestamp=timestamp)
                ts.geotiff.save(filename, File(f), save=True)
            imported += 1
            self.stdout.write(f"  + {filename} -> {timestamp}")

        self.stdout.write(f"\n{imported} timestep(s) importado(s). Processando...")
        processed = process_simulation_timesteps(simulation)
        self.stdout.write(self.style.SUCCESS(
            f"Concluído: {processed} timestep(s) processado(s) com sucesso."
        ))
        self.stdout.write(f"Acesse: /flood/{simulation.pk}/")
