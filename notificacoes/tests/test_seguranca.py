"""Segurança do serviço de Notificações: todo pedido precisa de um token válido."""
from datetime import datetime, timedelta, timezone

from tests.conftest import cabecalho, token_de


def test_rota_exige_login(cliente):
    r = cliente.get("/notificacoes")
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


def test_token_adulterado(cliente, contas):
    assert cliente.get("/notificacoes", headers={"Authorization": contas["ana"]["Authorization"] + "x"}).status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    falso = token_de(2, "solicitante", chave="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/notificacoes", headers=cabecalho(falso)).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    assert cliente.get("/notificacoes", headers=cabecalho(token_de(2, "admin", chave=None, alg="none"))).status_code == 401


def test_token_expirado(cliente):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = token_de(2, "solicitante", iat=antigo, exp=antigo + timedelta(minutes=5))
    assert cliente.get("/notificacoes", headers=cabecalho(vencido)).status_code == 401


def test_token_sem_perfil(cliente):
    assert cliente.get("/notificacoes", headers=cabecalho(token_de(2, None))).status_code == 401
