"""Segurança do serviço de Inventário: todo pedido precisa de um token válido."""
from datetime import datetime, timedelta, timezone

from tests.conftest import cabecalho, token_de

ROTAS = [("get", "/ativos"), ("get", "/ativos/1"), ("post", "/ativos")]
PC = {"patrimonio": "PAT-9", "tipo": "outro", "descricao": "Switch", "setor": "TI"}


def test_rotas_exigem_login(cliente):
    for metodo, rota in ROTAS:
        r = getattr(cliente, metodo)(rota)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", rota


def test_token_adulterado(cliente, contas):
    h = {"Authorization": contas["carla"]["Authorization"] + "x"}
    assert cliente.get("/ativos", headers=h).status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    falso = token_de(1, "admin", chave="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/ativos", headers=cabecalho(falso)).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    assert cliente.get("/ativos", headers=cabecalho(token_de(1, "admin", chave=None, alg="none"))).status_code == 401


def test_token_expirado(cliente):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = token_de(2, "solicitante", iat=antigo, exp=antigo + timedelta(minutes=5))
    assert cliente.get("/ativos", headers=cabecalho(vencido)).status_code == 401


def test_token_de_outro_emissor(cliente):
    assert cliente.get("/ativos", headers=cabecalho(token_de(2, "solicitante", iss="outro"))).status_code == 401


def test_token_sem_perfil_ou_com_perfil_desconhecido(cliente):
    assert cliente.get("/ativos", headers=cabecalho(token_de(2, None))).status_code == 401
    assert cliente.get("/ativos", headers=cabecalho(token_de(2, "superadmin"))).status_code == 401


def test_cabecalho_sem_bearer(cliente, contas):
    token = contas["carla"]["Authorization"].split(" ")[1]
    assert cliente.get("/ativos", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_solicitante_nao_cadastra_ativo(cliente, contas):
    assert cliente.post("/ativos", headers=contas["ana"], json=PC).status_code == 403


def test_o_perfil_do_token_decide_a_permissao(cliente):
    # Mesmo usuário (id 4), perfis diferentes no token: só o de técnico cadastra
    assert cliente.post("/ativos", headers=cabecalho(token_de(4, "solicitante")), json=PC).status_code == 403
    assert cliente.post("/ativos", headers=cabecalho(token_de(4, "tecnico")), json=PC).status_code == 201


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"descricao": "' + "x" * 70000 + '"}'
    r = cliente.post("/ativos", headers={**contas["carla"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413
