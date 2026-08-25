#!/usr/bin/env python3
"""
Shell restrita usada dentro do terminal do painel admin.

Objetivo: dar acesso de linha de comando SÓ para as ações de
simulação (HEC-RAS / AppRas), sem abrir shell de verdade no servidor.

Cada comando digitado passa por uma lista de comandos permitidos antes
de virar uma chamada de subprocess — SEM shell=True e SEM montar
strings de comando por concatenação, então não dá pra escapar pra um
`; rm -rf /` ou coisa parecida.
"""

import os
import pathlib
import shlex
import subprocess
import sys

try:
    import readline  # noqa: F401  (habilita histórico/edição de linha no Linux)
except ImportError:
    # Windows não tem readline por padrão. Sem ele a shell ainda
    # funciona normalmente, só perde histórico de comandos com seta
    # pra cima/pra baixo (dá pra resolver com "pip install pyreadline3"
    # se quiser essa função em dev no Windows).
    pass
from datetime import datetime, timezone

# --- configuração --------------------------------------------------

# Esse script mora em adminApp/scripts/shell_simulacoes.py — subindo
# dois níveis chega na raiz do projeto, onde fica o manage.py. Assim
# funciona tanto no seu WSL quanto no Render depois, sem hardcode.
_RAIZ_PROJETO = pathlib.Path(__file__).resolve().parents[2]
MANAGE_PY = str(_RAIZ_PROJETO / "manage.py")
PYTHON = sys.executable

LOG_FILE = str(_RAIZ_PROJETO / "logs" / "terminal_admin.log")

USUARIO = os.environ.get("ADMIN_TERMINAL_USER", "desconhecido")


def log(linha):
    """Registra cada comando digitado, com usuário e timestamp."""
    ts = datetime.now(timezone.utc).isoformat()
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] [{USUARIO}] {linha}\n")
    except OSError:
        pass


def cmd_importar_simulacao(args):
    if len(args) not in (2, 3):
        print('uso: importar_simulacao <caminho_da_pasta> "<nome da barragem>" ["<descrição>"]')
        print(
            'exemplo: importar_simulacao /home/joelv/uploads/newfolder1 "Nome da Barragem" "Cenário de chuva intensa, cota máxima 120m"'
        )
        return

    pasta, nome = args[0], args[1]
    descricao = args[2] if len(args) == 3 else None

    if not os.path.isdir(pasta):
        print(f"pasta não encontrada: {pasta}")
        return

    print(f"Importando '{nome}' a partir de {pasta}...")
    comando = [PYTHON, MANAGE_PY, "import_flood_simulation", "--folder", pasta, "--name", nome]
    if descricao:
        comando += ["--description", descricao]
    subprocess.run(comando, check=False)


def cmd_deletar_simulacao(args):
    if len(args) != 1 or not args[0].isdigit():
        print("uso: deletar_simulacao <id>")
        print("exemplo: deletar_simulacao 3   (use 'status' pra ver os ids)")
        return

    # subprocess.run herda stdin/stdout, então a confirmação
    # interativa do management command funciona normalmente aqui.
    subprocess.run(
        [PYTHON, MANAGE_PY, "deletar_simulacao", args[0]],
        check=False,
    )


def cmd_status(args):
    subprocess.run([PYTHON, MANAGE_PY, "status_simulacoes"], check=False)


def cmd_ajuda(args):
    print("Comandos disponíveis:")
    for nome, (_, descricao) in sorted(COMANDOS.items()):
        print(f"  {nome:<20} {descricao}")


COMANDOS = {
    "importar_simulacao": (
        cmd_importar_simulacao,
        'importa uma simulação a partir de uma pasta com os GeoTIFFs: importar_simulacao <pasta> "<nome>" ["<descrição>"]',
    ),
    "deletar_simulacao": (
        cmd_deletar_simulacao,
        "apaga uma simulação pelo id (com confirmação): deletar_simulacao <id>",
    ),
    "status": (cmd_status, "lista as simulações cadastradas e quantos timesteps cada uma tem"),
    "ajuda": (cmd_ajuda, "mostra esta ajuda"),
    "help": (cmd_ajuda, "mostra esta ajuda"),
}


def main():
    print("Shell restrita — AppRas. Digite 'ajuda' para ver os comandos, 'sair' para encerrar.")
    while True:
        try:
            linha = input("appras> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not linha:
            continue

        log(linha)

        if linha in ("sair", "exit", "quit"):
            break

        try:
            partes = shlex.split(linha)
        except ValueError as e:
            print(f"erro ao interpretar comando: {e}")
            continue

        comando, *args = partes
        entrada = COMANDOS.get(comando)
        if entrada is None:
            print(f"comando não reconhecido: {comando} (digite 'ajuda')")
            continue

        funcao, _ = entrada
        try:
            funcao(args)
        except Exception as e:
            print(f"erro ao executar comando: {e}")


if __name__ == "__main__":
    main()
