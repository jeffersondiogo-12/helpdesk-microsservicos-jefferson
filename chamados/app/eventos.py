"""Publica os eventos do chamado na fila (Redis Streams).

O serviço de Notificações lê a fila por conta própria. Se o Redis ou o serviço de Notificações
estiverem fora do ar, o chamado é salvo do mesmo jeito: só o aviso atrasa (ou, no pior caso, se perde).
shortcut: se o Redis cair exatamente neste instante, o evento se perde; para não perder, usar
o padrão "outbox" (gravar o evento na mesma transação do chamado e publicar depois).
"""
import json
import logging

import redis

from app.config import REDIS_URL, STREAM_EVENTOS

log = logging.getLogger("chamados.eventos")

_redis: redis.Redis | None = None


def fila() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.Redis.from_url(
            REDIS_URL, decode_responses=True, protocol=2, socket_connect_timeout=1, socket_timeout=1
        )
    return _redis


def usar_fila(cliente) -> None:
    """Troca o cliente do Redis (os testes usam isto para um Redis de mentira)."""
    global _redis
    _redis = cliente


def publicar(tipo: str, dados: dict) -> None:
    """Publica um evento (por exemplo, "ChamadoAberto") com os dados do que aconteceu."""
    try:
        # maxlen: a fila guarda só os últimos eventos, para não crescer para sempre
        fila().xadd(STREAM_EVENTOS, {"tipo": tipo, "dados": json.dumps(dados)}, maxlen=10_000, approximate=True)
    except redis.RedisError as erro:
        log.warning("Não foi possível publicar o evento %s (%s: %s); o chamado foi salvo mesmo assim.",
                    tipo, type(erro).__name__, erro)
