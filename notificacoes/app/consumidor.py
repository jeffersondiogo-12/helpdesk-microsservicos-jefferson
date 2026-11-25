"""Leitor dos eventos do HelpDesk (Redis Streams).

Os eventos ficam guardados no Redis até este serviço confirmá-los (XACK). Se ele estiver
fora do ar, os avisos são gravados quando voltar. A entrega é "pelo menos uma vez";
como `evento_id` é único no banco, cada evento vira no máximo um aviso.
"""
import json
import logging
import threading

import redis

from app.config import CONSUMIDOR, GRUPO, REDIS_URL, STREAM_EVENTOS
from app.notificacoes import servico

log = logging.getLogger("notificacoes.consumidor")

BLOCO_MS = 2000  # quanto tempo esperar por eventos novos antes de checar se é para parar


def cliente_redis() -> redis.Redis:
    return redis.Redis.from_url(
        REDIS_URL, decode_responses=True, protocol=2, socket_connect_timeout=2, socket_timeout=BLOCO_MS / 1000 + 3
    )


def preparar(r: redis.Redis) -> None:
    """Cria o grupo de consumidores lendo o stream desde o começo: não perde eventos anteriores."""
    try:
        r.xgroup_create(STREAM_EVENTOS, GRUPO, id="0", mkstream=True)
    except redis.ResponseError as erro:
        if "BUSYGROUP" not in str(erro):  # o grupo já existe: está tudo certo
            raise


def tratar(nova_sessao, r: redis.Redis, id_mensagem: str, campos: dict) -> None:
    """Grava o aviso de um evento e só depois confirma a mensagem no Redis."""
    try:
        tipo = campos["tipo"]
        aviso = servico.aviso_do_evento(tipo, json.loads(campos["dados"]))
    except (KeyError, ValueError, TypeError):
        # Evento que nunca vai dar certo: descarta, para não travar os seguintes
        log.error("Evento %s malformado; descartado.", id_mensagem)
        aviso = None
    if aviso:
        with nova_sessao() as db:
            servico.registrar(db, id_mensagem, tipo, aviso[0], aviso[1])
    r.xack(STREAM_EVENTOS, GRUPO, id_mensagem)


def processar_lote(r: redis.Redis, nova_sessao, pendentes: bool = False, bloco_ms: int | None = None) -> int:
    """Lê um lote e trata cada evento. `pendentes=True` relê o que ficou sem confirmação. Devolve quantos leu."""
    resposta = r.xreadgroup(
        GRUPO, CONSUMIDOR, {STREAM_EVENTOS: "0" if pendentes else ">"}, count=20,
        block=None if pendentes else (BLOCO_MS if bloco_ms is None else bloco_ms),
    )
    mensagens = resposta[0][1] if resposta else []
    for id_mensagem, campos in mensagens:
        tratar(nova_sessao, r, id_mensagem, campos)
    return len(mensagens)


def executar(r: redis.Redis, nova_sessao, parar: threading.Event) -> None:
    """Laço do consumidor, numa thread do serviço. Se o Redis cair, tenta de novo até ele voltar."""
    pendentes = True  # ao ligar, primeiro termina o que ficou sem confirmação da vez anterior
    preparado = False
    while not parar.is_set():
        try:
            if not preparado:
                preparar(r)
                preparado = True
            if processar_lote(r, nova_sessao, pendentes) == 0:
                pendentes = False
        except redis.RedisError:
            log.warning("Redis indisponível; tentando de novo em instantes.")
            preparado = False
            parar.wait(2)
        except Exception:
            log.exception("Falha ao gravar o aviso; o evento será tentado de novo.")
            pendentes = True
            parar.wait(2)
