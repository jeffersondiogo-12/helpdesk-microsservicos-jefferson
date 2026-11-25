"""Configurações lidas das variáveis de ambiente."""
import os
from pathlib import Path

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./inventario.db")


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

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024

DOCS_ATIVA = os.getenv("DOCS", "0") == "1"
