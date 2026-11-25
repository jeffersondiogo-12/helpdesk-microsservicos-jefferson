import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import criar_app


class Servicos:
    """Simula os serviços atrás do gateway: anota o que chegou e responde o que o teste mandar."""

    def __init__(self):
        self.recebidas: list[httpx.Request] = []
        self.fora: set[str] = set()      # serviços "desligados": a conexão é recusada
        self.lentos: set[str] = set()    # serviços que estouram o tempo limite
        self.respostas: dict = {}        # serviço -> função(request) -> httpx.Response

    def atender(self, request: httpx.Request) -> httpx.Response:
        self.recebidas.append(request)
        servico = request.url.host  # no Compose o nome do serviço é o endereço: http://chamados:8000
        if servico in self.fora:
            raise httpx.ConnectError("Conexão recusada", request=request)
        if servico in self.lentos:
            raise httpx.ReadTimeout("Tempo esgotado", request=request)
        if servico in self.respostas:
            return self.respostas[servico](request)
        return httpx.Response(200, json={"servico": servico, "caminho": request.url.path, "consulta": request.url.query.decode()})


@pytest.fixture
def servicos():
    return Servicos()


@pytest.fixture
def cliente(servicos):
    with TestClient(criar_app(transporte=httpx.MockTransport(servicos.atender))) as c:
        yield c
