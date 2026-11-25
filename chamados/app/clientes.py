"""Chamadas pela rede aos outros serviços (no monólito eram chamadas de função).

- O token do usuário é repassado no cabeçalho `Authorization`: o outro serviço também confere.
- Toda chamada tem tempo limite (TIMEOUT_SEGUNDOS).
- Qualquer falha do outro serviço (fora do ar, lento, resposta estranha) vira `ServicoIndisponivel`,
  que a API responde com 503 e uma mensagem clara, sem travar.
- shortcut: sem nova tentativa nem "disjuntor" (circuit breaker); com tráfego alto, vale adicionar.
"""
import logging

import httpx

from app.auth.dependencias import NAO_AUTENTICADO
from app.config import INVENTARIO_URL, TIMEOUT_SEGUNDOS, USUARIOS_URL
from app.erros import NaoEncontrado, RegraDeNegocio, ServicoIndisponivel

log = logging.getLogger("chamados.clientes")

_http: httpx.Client | None = None


def http() -> httpx.Client:
    """Um cliente só para o serviço inteiro (reaproveita conexões), já com o tempo limite."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=httpx.Timeout(TIMEOUT_SEGUNDOS, connect=min(2.0, TIMEOUT_SEGUNDOS)))
    return _http


def usar_cliente(cliente: httpx.Client | None) -> None:
    """Troca o cliente HTTP (os testes usam isto para simular os outros serviços)."""
    global _http
    _http = cliente


def _buscar(nome: str, url: str, token: str) -> dict | None:
    """GET no outro serviço. Devolve o JSON, ou None se ele respondeu 404."""
    try:
        resposta = http().get(url, headers={"Authorization": f"Bearer {token}"})
    except httpx.TimeoutException:
        log.warning("O serviço de %s não respondeu em %ss: %s", nome, TIMEOUT_SEGUNDOS, url)
        raise ServicoIndisponivel(f"O serviço de {nome} demorou demais para responder. Tente novamente em instantes.")
    except httpx.HTTPError:
        log.warning("O serviço de %s está fora do ar: %s", nome, url)
        raise ServicoIndisponivel(f"O serviço de {nome} está indisponível. Tente novamente em instantes.")
    if resposta.status_code == 404:
        return None
    if resposta.status_code == 401:
        raise NAO_AUTENTICADO  # o outro serviço recusou o token do usuário
    try:
        if resposta.status_code == 200:
            return resposta.json()
    except ValueError:
        pass
    log.warning("O serviço de %s respondeu algo inesperado (%s): %s", nome, resposta.status_code, url)
    raise ServicoIndisponivel(f"O serviço de {nome} respondeu com erro. Tente novamente em instantes.")


def obter_ativo(ativo_id: int, token: str) -> dict:
    """Confere no serviço de Inventário se o equipamento existe."""
    ativo = _buscar("Inventário", f"{INVENTARIO_URL}/ativos/{ativo_id}", token)
    if ativo is None:
        raise NaoEncontrado(f"Ativo {ativo_id} não encontrado.")
    return ativo


def obter_tecnico(usuario_id: int, token: str) -> dict:
    """Confere no serviço de Usuários se a pessoa existe e é técnica."""
    usuario = _buscar("Usuários", f"{USUARIOS_URL}/usuarios/{usuario_id}", token)
    if usuario is None:
        raise NaoEncontrado(f"Usuário {usuario_id} não encontrado.")
    if usuario.get("perfil") != "tecnico":
        raise RegraDeNegocio(f"Usuário {usuario_id} não é técnico.")
    return usuario
