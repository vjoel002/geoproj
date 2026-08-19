from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def terminal_view(request):
    """
    Página que embute o xterm.js e abre a conexão WebSocket com o
    TerminalConsumer. @staff_member_required garante que só usuários
    logados no admin acessem essa URL — a checagem "de verdade"
    (is_superuser) acontece de novo no consumer, no handshake do
    WebSocket, porque a URL em si não impede alguém de tentar conectar
    direto no endpoint ws/.
    """
    return render(request, "admin/terminal.html")



