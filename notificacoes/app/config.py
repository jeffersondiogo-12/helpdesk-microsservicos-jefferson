"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./notificacoes.db")


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

# Fila de eventos (Redis Streams). O serviço de Chamados publica; este serviço consome.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
STREAM_EVENTOS = os.getenv("STREAM_EVENTOS", "helpdesk.eventos")
GRUPO = os.getenv("GRUPO_CONSUMIDORES", "notificacoes")
# shortcut: nome fixo, serve para uma instância só; com várias, cada uma precisa de um nome próprio
CONSUMIDOR = os.getenv("NOME_CONSUMIDOR", "notificacoes-1")
CONSUMIDOR_ATIVO = os.getenv("CONSUMIDOR", "1") == "1"  # 0 desliga a leitura da fila (usado nos testes)

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = os.getenv("DOCS", "0") == "1"
