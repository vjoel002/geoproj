from django.core.management.base import BaseCommand

from AppRas.models import FloodSimulation, FloodTimestep


class Command(BaseCommand):
    help = "Lista as simulações (FloodSimulation) cadastradas e quantos timesteps cada uma tem."

    def handle(self, *args, **options):
        simulacoes = FloodSimulation.objects.all().order_by("-created_at")

        if not simulacoes:
            self.stdout.write("Nenhuma simulação cadastrada ainda.")
            return

        for s in simulacoes:
            n_timesteps = FloodTimestep.objects.filter(simulation=s).count()
            processado = "processada" if s.is_processed else "pendente"
            self.stdout.write(
                f"[{s.id}] {s.name:<30} {processado:<12} {n_timesteps} timestep(s)  "
                f"({s.created_at:%d/%m/%Y %H:%M})"
            )