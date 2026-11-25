"""API Gateway do HelpDesk TI: o único ponto de entrada do sistema (porta 8000).

Serve a tela e encaminha cada rota para o serviço certo. Os serviços e os bancos
não publicam portas: só o gateway é alcançável de fora do Docker.
"""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse

from app.config import ROTAS, SERVICOS, TIMEOUT_SEGUNDOS
from app.proxy import encaminhar
from app.seguranca_http import CabecalhosDeSeguranca

WEB = Path(__file__).parent / "web"
METODOS = ["GET", "POST", "PATCH"]  # os únicos que a API usa


def criar_app(transporte: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """Monta o gateway. Os testes passam um `transporte` falso no lugar da rede."""

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(TIMEOUT_SEGUNDOS, connect=2.0), transport=transporte)
        yield
        await app.state.http.aclose()

    app = FastAPI(
        title="HelpDesk TI · API Gateway", version="3.0.0", lifespan=ciclo_de_vida,
        docs_url=None, redoc_url=None, openapi_url=None,
    )
    app.add_middleware(CabecalhosDeSeguranca)

    def rota_para(servico: str):
        async def encaminhar_para_o_servico(request: Request):
            return await encaminhar(request, servico)
        return encaminhar_para_o_servico

    for prefixo, servico in ROTAS.items():
        app.add_api_route(prefixo, rota_para(servico), methods=METODOS, include_in_schema=False)
        app.add_api_route(prefixo + "/{resto:path}", rota_para(servico), methods=METODOS, include_in_schema=False)

    @app.get("/saude", tags=["Saúde"])
    async def saude(request: Request):
        """O gateway está de pé? E quais serviços estão no ar?"""
        async def conferir(servico: str) -> tuple[str, str]:
            try:
                resposta = await request.app.state.http.get(f"{SERVICOS[servico]}/saude", timeout=2.0)
            except httpx.HTTPError:
                return servico, "fora do ar"
            return servico, "ok" if resposta.status_code == 200 else "com problemas"

        estados = dict(await asyncio.gather(*(conferir(s) for s in SERVICOS)))
        todos_ok = all(estado == "ok" for estado in estados.values())
        return {"status": "ok" if todos_ok else "degradado", "gateway": "ok", "servicos": estados}

    @app.get("/", include_in_schema=False)
    def tela_inicial():
        return FileResponse(WEB / "index.html")

    @app.get("/app.js", include_in_schema=False)
    def script():
        return FileResponse(WEB / "app.js", media_type="text/javascript")

    @app.get("/estilo.css", include_in_schema=False)
    def estilo():
        return FileResponse(WEB / "estilo.css", media_type="text/css")

    return app


app = criar_app()
