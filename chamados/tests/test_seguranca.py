"""Testes de segurança do serviço de Chamados: autenticação, permissões e validação de entrada."""
from datetime import datetime, timedelta, timezone

from tests.conftest import token_de


def h(token):
    return {"Authorization": f"Bearer {token}"}


def abrir(cliente, headers, **extra):
    return cliente.post("/chamados", headers=headers, json={"titulo": "Teste", "descricao": "Teste", "prioridade": "baixa", **extra})


# ---------- autenticação ----------

def test_rotas_exigem_login(cliente):
    for metodo, rota in [("get", "/chamados"), ("get", "/chamados/painel"), ("get", "/chamados/1"), ("post", "/chamados"),
                         ("patch", "/chamados/1/atribuir"), ("patch", "/chamados/1/status"), ("post", "/chamados/1/comentarios")]:
        r = getattr(cliente, metodo)(rota)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", rota


def test_token_adulterado(cliente, contas):
    assert cliente.get("/chamados", headers={"Authorization": contas["ana"]["headers"]["Authorization"] + "x"}).status_code == 401


def test_token_assinado_com_outro_segredo(cliente):
    falso = token_de(1, "admin", chave="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert cliente.get("/chamados", headers=h(falso)).status_code == 401


def test_token_sem_assinatura_alg_none(cliente):
    assert cliente.get("/chamados", headers=h(token_de(1, "admin", chave=None, alg="none"))).status_code == 401


def test_token_expirado(cliente):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = token_de(2, "solicitante", iat=antigo, exp=antigo + timedelta(minutes=5))
    assert cliente.get("/chamados", headers=h(vencido)).status_code == 401


def test_token_de_outro_emissor(cliente):
    assert cliente.get("/chamados", headers=h(token_de(2, "solicitante", iss="outro-sistema"))).status_code == 401


def test_token_sem_perfil_ou_com_perfil_desconhecido(cliente):
    assert cliente.get("/chamados", headers=h(token_de(2, None))).status_code == 401
    assert cliente.get("/chamados", headers=h(token_de(2, "superadmin"))).status_code == 401


def test_cabecalho_sem_bearer(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"].split(" ")[1]
    assert cliente.get("/chamados", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_resposta_com_token_nao_fica_em_cache(cliente, contas):
    r = cliente.get("/chamados", headers=contas["ana"]["headers"])
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"


# ---------- permissões ----------

def test_solicitante_nao_ve_chamado_de_outra_pessoa(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    assert cliente.get(f"/chamados/{cid}", headers=contas["bia"]["headers"]).status_code == 404
    assert cliente.get("/chamados", headers=contas["bia"]["headers"]).json() == []


def test_solicitante_nao_comenta_nem_muda_status_em_chamado_de_outra_pessoa(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    bia = contas["bia"]["headers"]
    assert cliente.post(f"/chamados/{cid}/comentarios", headers=bia, json={"texto": "oi"}).status_code == 404
    assert cliente.patch(f"/chamados/{cid}/status", headers=bia, json={"status": "fechado"}).status_code == 404


def test_solicitante_nao_atribui_nem_resolve(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    ana = contas["ana"]["headers"]
    assert cliente.patch(f"/chamados/{cid}/atribuir", headers=ana, json={"tecnico_id": contas["carla"]["id"]}).status_code == 403
    assert cliente.patch(f"/chamados/{cid}/status", headers=ana, json={"status": "em_atendimento"}).status_code == 403


def test_solicitante_nao_fecha_chamado_que_ainda_nao_foi_resolvido(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    assert cliente.patch(f"/chamados/{cid}/status", headers=contas["ana"]["headers"], json={"status": "fechado"}).status_code == 403


def test_tecnico_e_admin_veem_todos_os_chamados(cliente, contas):
    abrir(cliente, contas["ana"]["headers"])
    abrir(cliente, contas["bia"]["headers"])
    assert len(cliente.get("/chamados", headers=contas["carla"]["headers"]).json()) == 2
    assert len(cliente.get("/chamados", headers=contas["admin"]["headers"]).json()) == 2


def test_o_perfil_vem_do_token(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    # a mesma pessoa (id 3) com perfil de solicitante não vê; com perfil de técnico (no token) vê
    assert cliente.get(f"/chamados/{cid}", headers=h(token_de(3, "solicitante"))).status_code == 404
    assert cliente.get(f"/chamados/{cid}", headers=h(token_de(3, "tecnico"))).status_code == 200


def test_nao_da_para_abrir_chamado_em_nome_de_outro(cliente, contas):
    r = abrir(cliente, contas["ana"]["headers"], solicitante_id=contas["bia"]["id"])
    assert r.status_code == 422  # campo extra é recusado


def test_nao_da_para_comentar_em_nome_de_outro(cliente, contas):
    cid = abrir(cliente, contas["ana"]["headers"]).json()["id"]
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["ana"]["headers"],
                     json={"texto": "oi", "autor_id": contas["carla"]["id"]})
    assert r.status_code == 422


# ---------- entrada e respostas ----------

def test_titulo_grande_demais(cliente, contas):
    assert abrir(cliente, contas["ana"]["headers"], titulo="x" * 500).status_code == 422


def test_ativo_id_invalido(cliente, contas):
    assert abrir(cliente, contas["ana"]["headers"], ativo_id=0).status_code == 422
    assert abrir(cliente, contas["ana"]["headers"], ativo_id="../usuarios").status_code == 422


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"titulo": "' + "x" * 70000 + '"}'
    r = cliente.post("/chamados", headers={**contas["ana"]["headers"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_texto_com_html_e_guardado_como_texto(cliente, contas):
    r = abrir(cliente, contas["ana"]["headers"], titulo="<script>alert(1)</script>")
    assert r.status_code == 201 and r.json()["titulo"] == "<script>alert(1)</script>"
