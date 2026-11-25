"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./usuarios.db")


def _ler_segredo() -> str:
    """O segredo vem do ambiente (.env) ou de um arquivo montado pelo Compose. Nunca do código.

    Todos os serviços precisam do MESMO valor: este serviço assina os tokens e os outros conferem.
    Por isso não existe segredo aleatório de reserva (cada serviço geraria um diferente).
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
TOKEN_MINUTOS = int(os.getenv("TOKEN_MINUTOS", "60"))

# Proteção contra tentativas de adivinhar senhas
LOGIN_MAX_FALHAS = int(os.getenv("LOGIN_MAX_FALHAS", "5"))
LOGIN_JANELA_SEGUNDOS = int(os.getenv("LOGIN_JANELA_SEGUNDOS", "300"))

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = os.getenv("DOCS", "0") == "1"
