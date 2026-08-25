from django.core.management.base import BaseCommand, CommandError

from AppRas.models import FloodSimulation, FloodTimestep


class Command(BaseCommand):
    help = "Apaga uma FloodSimulation (e seus timesteps) pelo id, com confirmação."

    def add_arguments(self, parser):
        parser.add_argument("id", type=int, help="id da simulação a apagar")
        parser.add_argument(
            "--yes", action="store_true",
            help="pula a confirmação (use com cuidado)"
        )

    def handle(self, *args, **options):
        sim_id = options["id"]

        try:
            simulacao = FloodSimulation.objects.get(id=sim_id)
        except FloodSimulation.DoesNotExist:
            raise CommandError(f"Nenhuma simulação encontrada com id={sim_id}")

        nome = simulacao.name
        n_timesteps = FloodTimestep.objects.filter(simulation=simulacao).count()

        if not options["yes"]:
            self.stdout.write(
                f"Vai apagar a simulação [{sim_id}] '{nome}' e seus {n_timesteps} timestep(s)."
            )
            resposta = input("Confirma? (digite 'sim' para apagar): ").strip().lower()
            if resposta != "sim":
                self.stdout.write("Cancelado.")
                return

        simulacao.delete()
        self.stdout.write(self.style.SUCCESS(f"Simulação [{sim_id}] '{nome}' apagada."))