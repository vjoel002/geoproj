import asyncio
import fcntl
import os
import pty
import struct
import sys
import termios

from channels.generic.websocket import AsyncWebsocketConsumer
from django.conf import settings


class TerminalConsumer(AsyncWebsocketConsumer):
    """
    Abre um pseudo-terminal (pty) real no servidor e faz a ponte entre
    ele e o WebSocket, permitindo um shell interativo completo no
    navegador (via xterm.js no frontend).

    ATENÇÃO — isso dá acesso de shell completo à máquina onde o Django
    roda, para quem conseguir abrir essa conexão. Leia security_notes.md
    antes de habilitar isso em qualquer ambiente acessível pela rede.
    """

    async def connect(self):
        user = self.scope.get("user")

        # Só aceita usuários autenticados e com is_superuser=True.
        # Ajuste essa checagem para o seu modelo de permissões se quiser
        # algo mais granular (ex: um grupo "pode_usar_terminal").
        if not user or not user.is_authenticated or not user.is_superuser:
            await self.close(code=4403)
            return

        await self.accept()

        # Por padrão aponta pra shell_simulacoes.py (comandos limitados
        # a ações de simulação). Pra voltar a um shell completo, defina
        # ADMIN_TERMINAL_SHELL = "/bin/bash" no settings.py.
        shell_cmd = getattr(
            settings,
            "ADMIN_TERMINAL_SHELL",
            os.path.join(os.path.dirname(__file__), "scripts", "shell_simulacoes.py"),
        )

        pid, fd = pty.fork()
        if pid == 0:
            # Processo filho: substitui a imagem do processo pelo comando
            # configurado, passando o usuário logado no ambiente (usado
            # pro log de auditoria dentro da shell restrita).
            env = os.environ.copy()
            env["ADMIN_TERMINAL_USER"] = user.get_username()

            if shell_cmd.endswith(".py"):
                os.execvpe(sys.executable, [sys.executable, shell_cmd], env)
            else:
                os.execvpe(shell_cmd, [shell_cmd], env)
        else:
            self.child_pid = pid
            self.fd = fd
            self._set_nonblocking(fd)
            loop = asyncio.get_event_loop()
            loop.add_reader(fd, self._on_pty_output)

    def _set_nonblocking(self, fd):
        flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    def _on_pty_output(self):
        try:
            data = os.read(self.fd, 4096)
        except OSError:
            data = b""

        if data:
            asyncio.create_task(self.send(text_data=data.decode(errors="ignore")))
        else:
            asyncio.create_task(self.close())

    async def disconnect(self, close_code):
        try:
            loop = asyncio.get_event_loop()
            loop.remove_reader(self.fd)
            os.close(self.fd)
            os.kill(self.child_pid, 9)
        except Exception:
            pass

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            return

        # Mensagem de controle de resize (enviada pelo frontend).
        # Tudo o mais é digitação normal, enviada direto pro pty.
        if text_data.startswith("\x01RESIZE:"):
            try:
                _, cols, rows = text_data.split(":")
                self._resize(int(cols), int(rows))
            except Exception:
                pass
            return

        os.write(self.fd, text_data.encode())

    def _resize(self, cols, rows):
        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
