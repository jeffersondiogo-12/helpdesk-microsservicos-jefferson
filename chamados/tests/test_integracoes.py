"""Falhas e repasse de token nas chamadas aos outros serviços (Usuários e Inventário)."""
import pytest

from app import clientes, config
from tests.conftest import eventos_publicados


def abrir(cliente, contas, ativo_id=1, quem="ana"):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": "alta", "ativo_id": ativo_id}
    return cliente.post("/chamados", headers=contas[quem]["headers"], json=dados)


def abrir_sem_equipamento(cliente, contas, quem="ana"):
    dados = {"titulo": "Acesso", "descricao": "Preciso de acesso", "prioridade": "baixa"}
    return cliente.post("/chamados", headers=contas[quem]["headers"], json=dados)


# ---------- o token do usuário é repassado ----------

def test_repassa_o_token_ao_inventario(cliente, contas, vizinhos):
    abrir(cliente, contas)
    assert vizinhos.chamadas == [("inventario", "/ativos/1", contas["ana"]["headers"]["Authorization"])]


def test_repassa_o_token_aos_usuarios_ao_atribuir(cliente, contas, vizinhos):
    cid = abrir_sem_equipamento(cliente, contas).json()["id"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": contas["carla"]["id"]})
    assert vizinhos.chamadas == [("usuarios", f"/usuarios/{contas['carla']['id']}", contas["carla"]["headers"]["Authorization"])]


def test_sem_token_nenhum_outro_servico_e_chamado(cliente, vizinhos):
    r = cliente.post("/chamados", json={"titulo": "Teste", "descricao": "Teste", "prioridade": "baixa", "ativo_id": 1})
    assert r.status_code == 401 and vizinhos.chamadas == []


def test_se_o_outro_servico_recusar_o_token_a_resposta_e_401(cliente, contas, vizinhos):
    vizinhos.respostas["inventario"] = (401, '{"detail": "Faça login para continuar."}')
    r = abrir(cliente, contas)
    assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer"


# ---------- Inventário fora do ar ----------

def test_inventario_fora_do_ar_da_erro_claro_e_nao_cria_o_chamado(cliente, contas, vizinhos, fila):
    vizinhos.fora.add("inventario")
    r = abrir(cliente, contas)
    assert r.status_code == 503
    assert r.json()["detail"] == "O serviço de Inventário está indisponível. Tente novamente em instantes."
    assert r.headers["retry-after"] == "5"
    assert cliente.get("/chamados", headers=contas["carla"]["headers"]).json() == []
    assert eventos_publicados(fila) == []


def test_inventario_fora_do_ar_nao_derruba_o_resto(cliente, contas, vizinhos):
    cid = abrir(cliente, contas).json()["id"]
    vizinhos.fora.add("inventario")
    ana, carla = contas["ana"]["headers"], contas["carla"]["headers"]
    assert abrir_sem_equipamento(cliente, contas).status_code == 201            # sem equipamento, abre normalmente
    assert cliente.get("/chamados", headers=carla).status_code == 200            # lista
    assert cliente.get(f"/chamados/{cid}", headers=ana).status_code == 200       # detalhe
    assert cliente.get("/chamados/painel", headers=carla).status_code == 200     # painel
    assert cliente.post(f"/chamados/{cid}/comentarios", headers=ana, json={"texto": "oi"}).status_code == 201
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=carla, json={"tecnico_id": contas["carla"]["id"]})
    assert r.status_code == 200                                                  # atribuir depende só dos Usuários


def test_inventario_lento_estoura_o_tempo_limite(cliente, contas, vizinhos):
    vizinhos.lentos.add("inventario")
    r = abrir(cliente, contas)
    assert r.status_code == 503 and r.json()["detail"] == "O serviço de Inventário demorou demais para responder. Tente novamente em instantes."


@pytest.mark.parametrize("status,corpo", [(500, "erro interno"), (502, ""), (503, '{"detail": "x"}'), (200, "isto não é json")])
def test_resposta_estranha_do_inventario_vira_503(cliente, contas, vizinhos, status, corpo):
    vizinhos.respostas["inventario"] = (status, corpo)
    r = abrir(cliente, contas)
    assert r.status_code == 503 and r.json()["detail"] == "O serviço de Inventário respondeu com erro. Tente novamente em instantes."


# ---------- Usuários fora do ar ----------

def test_usuarios_fora_do_ar_da_erro_claro_e_nao_atribui(cliente, contas, vizinhos, fila):
    cid = abrir(cliente, contas).json()["id"]
    vizinhos.fora.add("usuarios")
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": contas["carla"]["id"]})
    assert r.status_code == 503 and r.json()["detail"] == "O serviço de Usuários está indisponível. Tente novamente em instantes."
    c = cliente.get(f"/chamados/{cid}", headers=contas["carla"]["headers"]).json()
    assert c["status"] == "aberto" and c["tecnico_id"] is None
    assert [t for t, _ in eventos_publicados(fila)] == ["ChamadoAberto"]


def test_usuarios_fora_do_ar_nao_derruba_o_resto(cliente, contas, vizinhos):
    vizinhos.fora.add("usuarios")
    assert abrir(cliente, contas).status_code == 201
    assert cliente.get("/chamados", headers=contas["carla"]["headers"]).status_code == 200


def test_os_dois_fora_do_ar_e_o_servico_de_chamados_segue_de_pe(cliente, contas, vizinhos):
    vizinhos.fora.update({"usuarios", "inventario"})
    assert abrir(cliente, contas).status_code == 503
    assert abrir_sem_equipamento(cliente, contas).status_code == 201
    assert cliente.get("/saude").status_code == 200


def test_servico_volta_a_funcionar_sem_reiniciar_nada(cliente, contas, vizinhos):
    vizinhos.fora.add("inventario")
    assert abrir(cliente, contas).status_code == 503
    vizinhos.fora.clear()  # docker compose start inventario
    assert abrir(cliente, contas).status_code == 201


# ---------- tempo limite ----------

def test_cliente_http_tem_tempo_limite():
    clientes.usar_cliente(None)
    http = clientes.http()
    try:
        assert http.timeout.read == config.TIMEOUT_SEGUNDOS
        assert 0 < http.timeout.connect <= 2.0
    finally:
        http.close()
        clientes.usar_cliente(None)
