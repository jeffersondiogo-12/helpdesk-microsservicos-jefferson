import os

# O segredo e o banco precisam existir antes de importar a aplicação (a configuração é lida na importação).
os.environ.setdefault("JWT_SEGREDO", "segredo-de-teste-com-mais-de-32-caracteres!")
os.environ.setdefault("DATABASE_URL", "sqlite://")

from datetime import datetime, timedelta, timezone  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import config  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


def token_de(usuario_id: int, perfil: str | None, **mudancas) -> str:
    """Faz um token como o serviço de Usuários faria (este serviço só confere, nunca cria)."""
    agora = datetime.now(timezone.utc)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iss": config.JWT_EMISSOR, "iat": agora,
             "exp": agora + timedelta(hours=1)}
    chave = mudancas.pop("chave", config.JWT_SEGREDO)
    algoritmo = mudancas.pop("alg", "HS256")
    dados.update(mudancas)
    return jwt.encode({k: v for k, v in dados.items() if v is not None}, chave, algorithm=algoritmo)


def cabecalho(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sessao(monkeypatch):
    """Banco novo, em memória, para cada teste."""
    monkeypatch.setenv("DADOS_EXEMPLO", "0")
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Sessao = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def db_de_teste():
        db = Sessao()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = db_de_teste
    yield Sessao
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(sessao):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def contas():
    """Um token para cada perfil, sem precisar do serviço de Usuários."""
    return {
        "admin": cabecalho(token_de(1, "admin")),
        "ana": cabecalho(token_de(2, "solicitante")),
        "carla": cabecalho(token_de(4, "tecnico")),
    }
