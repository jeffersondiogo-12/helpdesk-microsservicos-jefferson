"""Serviço de Notificações do HelpDesk TI.

Não é chamado pelos outros serviços: ele escuta os eventos que o serviço de Chamados
publica na fila (Redis) e grava os avisos no seu próprio banco. Se este serviço cair,
os chamados continuam sendo abertos e os avisos chegam quando ele voltar.
"""
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import consumidor
from app.config import CONSUMIDOR_ATIVO, DOCS_ATIVA
from app.database import Base, SessionLocal, engine, get_db
from app.notificacoes.rotas import router as notificacoes_router
from app.seguranca_http import CabecalhosDeSeguranca


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Cria as tabelas e liga o leitor da fila numa thread."""
    Base.metadata.create_all(engine)
    parar = threading.Event()
    leitor = None
    if CONSUMIDOR_ATIVO:
        leitor = threading.Thread(
            target=consumidor.executar, args=(consumidor.cliente_redis(), SessionLocal, parar),
            name="consumidor-de-eventos", daemon=True,
        )
        leitor.start()
    yield
    parar.set()
    if leitor:
        leitor.join(timeout=consumidor.BLOCO_MS / 1000 + 2)


app = FastAPI(
    title="HelpDesk TI · serviço de Notificações", version="3.0.0", lifespan=ciclo_de_vida,
    docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
    openapi_url="/openapi.json" if DOCS_ATIVA else None,
)
app.add_middleware(CabecalhosDeSeguranca)

app.include_router(notificacoes_router)


@app.exception_handler(IntegrityError)
def tratar_conflito(request: Request, erro: IntegrityError):
    # Não expõe detalhes do banco na resposta
    return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})


@app.get("/saude", tags=["Saúde"])
def saude(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))  # o banco deste serviço responde?
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "falha", "servico": "notificacoes"})
    return {"status": "ok", "servico": "notificacoes"}
