"""Encaminha cada requisição para o serviço dono da rota e devolve a resposta dele."""
import logging

import httpx
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from app.config import NOMES, SERVICOS, TAMANHO_MAXIMO_REQUISICAO

log = logging.getLogger("gateway")

# Lista de permissão: só estes cabeçalhos passam. Nada que o cliente invente chega aos serviços.
ENVIAR = ("authorization", "content-type", "accept")
DEVOLVER = ("content-type", "www-authenticate", "retry-after")


def erro(status: int, mensagem: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": mensagem})


async def ler_corpo(request: Request) -> bytes | None:
    """Lê o corpo até o limite. Devolve None se passar (vale também para corpo sem Content-Length)."""
    corpo = bytearray()
    async for pedaco in request.stream():
        corpo += pedaco
        if len(corpo) > TAMANHO_MAXIMO_REQUISICAO:
            return None
    return bytes(corpo)


async def encaminhar(request: Request, servico: str) -> Response:
    caminho = request.url.path.rstrip("/") or "/"
    if ".." in caminho or "\\" in caminho:
        return erro(400, "Caminho inválido.")
    corpo = await ler_corpo(request)
    if corpo is None:
        return erro(413, "Requisição grande demais.")

    url = SERVICOS[servico] + caminho + (f"?{request.url.query}" if request.url.query else "")
    cabecalhos = {nome: valor for nome, valor in request.headers.items() if nome in ENVIAR}
    # O gateway é a borda: o IP de quem chamou é o que ele enxerga, nunca um X-Forwarded-For vindo de fora.
    # O serviço de Usuários usa este IP no limite de tentativas de login.
    cabecalhos["x-forwarded-for"] = request.client.host if request.client else "-"
    try:
        resposta = await request.app.state.http.request(request.method, url, headers=cabecalhos, content=corpo)
    except httpx.TimeoutException:
        log.warning("O serviço de %s demorou demais: %s %s", NOMES[servico], request.method, caminho)
        return erro(504, f"O serviço de {NOMES[servico]} demorou demais para responder.")
    except httpx.HTTPError:
        log.warning("O serviço de %s está fora do ar: %s %s", NOMES[servico], request.method, caminho)
        return erro(503, f"O serviço de {NOMES[servico]} está fora do ar. Tente novamente em instantes.")

    return Response(
        content=resposta.content, status_code=resposta.status_code,
        headers={nome: valor for nome, valor in resposta.headers.items() if nome in DEVOLVER},
    )
