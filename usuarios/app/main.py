"""Serviço de Usuários do HelpDesk TI.

Dono da tabela de usuários e do login. É o único serviço que cria tokens JWT.
Roda sozinho, com o seu próprio banco, atrás do API Gateway.
"""
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import dados_exemplo
from app.auth.rotas import router as auth_router
from app.config import DOCS_ATIVA
from app.database import Base, SessionLocal, engine, get_db
from app.erros import NaoEncontrado, RegraDeNegocio, SemPermissao
from app.seguranca_http import CabecalhosDeSeguranca
from app.usuarios.rotas import router as usuarios_router


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Cria as tabelas e, se pedido, os dados de exemplo ao iniciar."""
    Base.metadata.create_all(engine)
    if os.getenv("DADOS_EXEMPLO", "1") == "1":
        with SessionLocal() as db:
            dados_exemplo.carregar(db)
    yield


app = FastAPI(
    title="HelpDesk TI · serviço de Usuários", version="3.0.0", lifespan=ciclo_de_vida,
    docs_url="/docs" if DOCS_ATIVA else None, redoc_url=None,
    openapi_url="/openapi.json" if DOCS_ATIVA else None,
)
app.add_middleware(CabecalhosDeSeguranca)

app.include_router(auth_router)
app.include_router(usuarios_router)


@app.exception_handler(NaoEncontrado)
def tratar_nao_encontrado(request: Request, erro: NaoEncontrado):
    return JSONResponse(status_code=404, content={"detail": str(erro)})


@app.exception_handler(RegraDeNegocio)
def tratar_regra(request: Request, erro: RegraDeNegocio):
    return JSONResponse(status_code=422, content={"detail": str(erro)})


@app.exception_handler(SemPermissao)
def tratar_sem_permissao(request: Request, erro: SemPermissao):
    return JSONResponse(status_code=403, content={"detail": str(erro)})


@app.exception_handler(IntegrityError)
def tratar_conflito(request: Request, erro: IntegrityError):
    # Não expõe detalhes do banco na resposta
    return JSONResponse(status_code=409, content={"detail": "O registro conflita com outro já existente."})


@app.get("/saude", tags=["Saúde"])
def saude(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))  # o banco deste serviço responde?
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "falha", "servico": "usuarios"})
    return {"status": "ok", "servico": "usuarios"}
