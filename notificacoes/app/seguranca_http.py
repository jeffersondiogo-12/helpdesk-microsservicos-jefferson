"""Proteções aplicadas às respostas do serviço.

O serviço só devolve JSON e fica atrás do gateway, que aplica os cabeçalhos da tela (CSP etc.).
Aqui ficam o limite de tamanho do corpo e dois cabeçalhos baratos.
"""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import TAMANHO_MAXIMO_REQUISICAO


class CabecalhosDeSeguranca(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tamanho = request.headers.get("content-length")
        if tamanho and (not tamanho.isdigit() or int(tamanho) > TAMANHO_MAXIMO_REQUISICAO):
            return JSONResponse(status_code=413, content={"detail": "Requisição grande demais."})

        resposta = await call_next(request)
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        if request.headers.get("authorization"):
            resposta.headers["Cache-Control"] = "no-store"
        return resposta
