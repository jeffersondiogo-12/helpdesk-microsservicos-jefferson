import os

# Segredo, banco e endereços dos outros serviços precisam estar definidos antes de importar a aplicação.
os.environ.setdefault("JWT_SEGREDO", "segredo-de-teste-com-mais-de-32-caracteres!")
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["USUARIOS_URL"] = "http://usuarios:8000"
os.environ["INVENTARIO_URL"] = "http://inventario:8000"

import json  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402

import fakeredis  # noqa: E402
import httpx  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import clientes, config, eventos  # noqa: E402
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


def eventos_publicados(fila) -> list[tuple[str, dict]]:
    return [(campos["tipo"], json.loads(campos["dados"])) for _, campos in fila.xrange(config.STREAM_EVENTOS)]


class Vizinhos:
    """Simula os serviços de Usuários e de Inventário (só o que o serviço de Chamados pergunta a eles)."""

    def __init__(self):
        self.usuarios = {
            1: {"id": 1, "nome": "Admin", "perfil": "admin"}, 2: {"id": 2, "nome": "Ana", "perfil": "solicitante"},
            3: {"id": 3, "nome": "Bia", "perfil": "solicitante"}, 4: {"id": 4, "nome": "Carla", "perfil": "tecnico"},
            5: {"id": 5, "nome": "Diego", "perfil": "tecnico"},
        }
        self.ativos = {1: {"id": 1, "patrimonio": "PAT-1", "tipo": "computador", "descricao": "Desktop", "setor": "TI"}}
        self.chamadas: list[tuple[str, str, str | None]] = []  # (serviço, caminho, cabeçalho Authorization)
        self.fora: set[str] = set()      # serviços "desligados": a conexão é recusada
        self.lentos: set[str] = set()    # serviços que estouram o tempo limite
        self.respostas: dict[str, tuple[int, str]] = {}  # serviço -> (status, corpo) fixos, para simular erros

    def atender(self, request: httpx.Request) -> httpx.Response:
        servico = request.url.host
        self.chamadas.append((servico, request.url.path, request.headers.get("authorization")))
        if servico in self.fora:
            raise httpx.ConnectError("Conexão recusada", request=request)
        if servico in self.lentos:
            raise httpx.ReadTimeout("Tempo esgotado", request=request)
        if servico in self.respostas:
            status, corpo = self.respostas[servico]
            return httpx.Response(status, content=corpo)
        tabela, prefixo = (self.usuarios, "/usuarios/") if servico == "usuarios" else (self.ativos, "/ativos/")
        item = tabela.get(int(request.url.path.removeprefix(prefixo)))
        return httpx.Response(200, json=item) if item else httpx.Response(404, json={"detail": "não encontrado"})


@pytest.fixture
def vizinhos():
    v = Vizinhos()
    clientes.usar_cliente(httpx.Client(transport=httpx.MockTransport(v.atender)))
    yield v
    clientes.usar_cliente(None)


@pytest.fixture
def fila():
    """Um Redis de mentira, novo a cada teste."""
    r = fakeredis.FakeRedis(server=fakeredis.FakeServer(), decode_responses=True)
    eventos.usar_fila(r)
    yield r
    eventos.usar_fila(None)


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
def cliente(sessao, vizinhos, fila):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def contas():
    """Um token para cada pessoa (ids iguais aos usuários simulados), sem precisar do serviço de Usuários."""
    quem = {"admin": (1, "admin"), "ana": (2, "solicitante"), "bia": (3, "solicitante"), "carla": (4, "tecnico")}
    return {nome: {"id": i, "headers": {"Authorization": f"Bearer {token_de(i, perfil)}"}} for nome, (i, perfil) in quem.items()}


@pytest.fixture
def ativo(vizinhos):
    return vizinhos.ativos[1]
