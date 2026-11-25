import json

import httpx
import pytest

ROTAS = [
    ("POST", "/auth/login", "usuarios"), ("GET", "/auth/eu", "usuarios"),
    ("GET", "/usuarios", "usuarios"), ("POST", "/usuarios", "usuarios"), ("GET", "/usuarios/3", "usuarios"),
    ("GET", "/ativos", "inventario"), ("POST", "/ativos", "inventario"), ("GET", "/ativos/1", "inventario"),
    ("GET", "/chamados", "chamados"), ("POST", "/chamados", "chamados"), ("GET", "/chamados/painel", "chamados"),
    ("GET", "/chamados/7", "chamados"), ("PATCH", "/chamados/7/atribuir", "chamados"),
    ("PATCH", "/chamados/7/status", "chamados"), ("POST", "/chamados/7/comentarios", "chamados"),
    ("GET", "/notificacoes", "notificacoes"),
]


@pytest.mark.parametrize("metodo,caminho,servico", ROTAS)
def test_cada_rota_vai_para_o_servico_certo(cliente, servicos, metodo, caminho, servico):
    r = cliente.request(metodo, caminho, json=None if metodo == "GET" else {})
    assert r.status_code == 200
    assert r.json()["servico"] == servico and r.json()["caminho"] == caminho
    [recebida] = servicos.recebidas
    assert recebida.method == metodo


def test_metodo_corpo_e_consulta_chegam_ao_servico(cliente, servicos):
    cliente.patch("/chamados/7/status?x=1&y=a%20b", json={"status": "resolvido"})
    [recebida] = servicos.recebidas
    assert recebida.method == "PATCH" and recebida.url.query == b"x=1&y=a%20b"
    assert recebida.headers["content-type"] == "application/json"
    assert json.loads(recebida.content) == {"status": "resolvido"}


def test_barra_no_final_e_ignorada(cliente, servicos):
    assert cliente.get("/chamados/").status_code == 200
    assert servicos.recebidas[0].url.path == "/chamados"


def test_so_passam_os_cabecalhos_permitidos(cliente, servicos):
    cliente.get("/chamados", headers={
        "Authorization": "Bearer abc", "Accept": "application/json", "Cookie": "sessao=1",
        "X-Forwarded-For": "6.6.6.6", "X-Usuario-Id": "1", "X-Perfil": "admin",
    })
    [recebida] = servicos.recebidas
    assert recebida.headers["authorization"] == "Bearer abc"  # o token é repassado
    assert recebida.headers["x-forwarded-for"] == "testclient"  # o IP real, não o que o cliente mandou
    for proibido in ("cookie", "x-usuario-id", "x-perfil"):
        assert proibido not in recebida.headers


def test_devolve_status_corpo_e_so_os_cabecalhos_uteis(cliente, servicos):
    servicos.respostas["chamados"] = lambda req: httpx.Response(
        401, json={"detail": "Faça login para continuar."},
        headers={"WWW-Authenticate": "Bearer", "Retry-After": "5", "Set-Cookie": "x=1", "X-Interno": "segredo"})
    r = cliente.get("/chamados")
    assert r.status_code == 401 and r.json() == {"detail": "Faça login para continuar."}
    assert r.headers["www-authenticate"] == "Bearer" and r.headers["retry-after"] == "5"
    assert "set-cookie" not in r.headers and "x-interno" not in r.headers


@pytest.mark.parametrize("status", [201, 404, 422, 503])
def test_status_do_servico_passa_sem_mudar(cliente, servicos, status):
    servicos.respostas["chamados"] = lambda req: httpx.Response(status, json={"detail": "do serviço"})
    r = cliente.get("/chamados")
    assert r.status_code == status and r.json() == {"detail": "do serviço"}


# ---------- serviço fora do ar ----------

def test_servico_fora_do_ar_da_erro_claro(cliente, servicos):
    servicos.fora.add("inventario")
    r = cliente.get("/ativos")
    assert r.status_code == 503
    assert r.json()["detail"] == "O serviço de Inventário está fora do ar. Tente novamente em instantes."


def test_servico_lento_da_504(cliente, servicos):
    servicos.lentos.add("usuarios")
    r = cliente.get("/usuarios")
    assert r.status_code == 504 and r.json()["detail"] == "O serviço de Usuários demorou demais para responder."


def test_falha_de_protocolo_vira_503(cliente, servicos):
    def quebrar(request):
        raise httpx.RemoteProtocolError("conexão encerrada no meio", request=request)
    servicos.respostas["notificacoes"] = quebrar
    assert cliente.get("/notificacoes").status_code == 503


def test_um_servico_fora_nao_afeta_os_outros(cliente, servicos):
    servicos.fora.add("inventario")
    assert cliente.get("/ativos").status_code == 503
    assert cliente.get("/usuarios").status_code == 200
    assert cliente.get("/chamados").status_code == 200
    assert cliente.get("/notificacoes").status_code == 200


# ---------- o que NÃO é encaminhado ----------

def test_rota_desconhecida_nao_vai_a_lugar_nenhum(cliente, servicos):
    for caminho in ("/qualquer", "/saude-do-chamados", "/docs", "/openapi.json", "/authx", "/chamadosx"):
        assert cliente.get(caminho).status_code == 404, caminho
    assert servicos.recebidas == []


def test_metodos_que_a_api_nao_usa_sao_recusados(cliente, servicos):
    assert cliente.delete("/chamados/1").status_code == 405
    assert cliente.put("/usuarios/1", json={}).status_code == 405
    assert servicos.recebidas == []


def test_caminho_com_ponto_ponto_e_recusado(cliente, servicos):
    r = cliente.get("/chamados/%2e%2e/%2e%2e/saude")
    assert r.status_code == 400 and servicos.recebidas == []


def test_corpo_grande_demais_com_content_length(cliente, servicos):
    r = cliente.post("/chamados", content=b"x" * 70000, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and servicos.recebidas == []


def test_corpo_grande_demais_sem_content_length(cliente, servicos):
    def pedacos():
        yield b"x" * 40000
        yield b"x" * 40000
    r = cliente.post("/chamados", content=pedacos(), headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and servicos.recebidas == []
