"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chamados.db")


def _ler_segredo() -> str:
    """O segredo vem do ambiente (.env) ou de um arquivo montado pelo Compose. Nunca do código.

    É o MESMO valor usado pelo serviço de Usuários para assinar os tokens.
    """
    segredo = os.getenv("JWT_SEGREDO", "")
    arquivo = os.getenv("JWT_SEGREDO_FILE", "")
    if not segredo and arquivo and Path(arquivo).is_file():
        segredo = Path(arquivo).read_text().strip()
    if len(segredo) < 32:
        raise RuntimeError("Defina JWT_SEGREDO com pelo menos 32 caracteres (o mesmo valor em todos os serviços).")
    return segredo


JWT_SEGREDO = _ler_segredo()
JWT_ALGORITMO = "HS256"
JWT_EMISSOR = "helpdesk-ti"

# Onde estão os outros serviços (dentro do Docker Compose, o nome do serviço vira o endereço)
USUARIOS_URL = os.getenv("USUARIOS_URL", "http://usuarios:8000").rstrip("/")
INVENTARIO_URL = os.getenv("INVENTARIO_URL", "http://inventario:8000").rstrip("/")
# Tempo máximo de espera por outro serviço. Passou disso, o chamado responde 503 em vez de ficar pendurado.
TIMEOUT_SEGUNDOS = float(os.getenv("TIMEOUT_SEGUNDOS", "3"))

# Fila de eventos (Redis Streams): o serviço de Notificações consome o que é publicado aqui
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS", "helpdesk.eventos")

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = os.getenv("DOCS", "0") == "1"
