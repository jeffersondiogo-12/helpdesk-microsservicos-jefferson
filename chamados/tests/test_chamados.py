from datetime import datetime, timedelta

from app import dados_exemplo
from app.chamados import repositorio
from app.chamados.modelos import Chamado
from tests.conftest import eventos_publicados


def abrir(cliente, contas, ativo, quem="ana", prioridade="alta", **extra):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": prioridade, "ativo_id": ativo["id"], **extra}
    return cliente.post("/chamados", headers=contas[quem]["headers"], json=dados)


def atribuir(cliente, contas, cid, tecnico="carla", quem="carla"):
    return cliente.patch(f"/chamados/{cid}/atribuir", headers=contas[quem]["headers"], json={"tecnico_id": contas[tecnico]["id"]})


def status(cliente, contas, cid, novo, quem="carla"):
    return cliente.patch(f"/chamados/{cid}/status", headers=contas[quem]["headers"], json={"status": novo})


def test_abrir_calcula_sla_e_publica_o_evento(cliente, contas, ativo, fila):
    r = abrir(cliente, contas, ativo, prioridade="critica")
    assert r.status_code == 201
    c = r.json()
    assert c["solicitante_id"] == contas["ana"]["id"] and c["status"] == "aberto" and c["ativo_id"] == ativo["id"]
    horas = (datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])).total_seconds() / 3600
    assert round(horas) == 4
    [(tipo, dados)] = eventos_publicados(fila)
    assert tipo == "ChamadoAberto"
    assert dados["chamado_id"] == c["id"] and dados["solicitante_id"] == contas["ana"]["id"]
    assert datetime.fromisoformat(dados["prazo_sla"]) == datetime.fromisoformat(c["prazo_sla"])


def test_sla_por_prioridade(cliente, contas, ativo):
    for prioridade, horas in {"critica": 4, "alta": 8, "media": 24, "baixa": 72}.items():
        c = abrir(cliente, contas, ativo, prioridade=prioridade).json()
        total = (datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])).total_seconds() / 3600
        assert round(total) == horas


def test_abrir_sem_equipamento_nao_chama_o_inventario(cliente, contas, vizinhos):
    r = cliente.post("/chamados", headers=contas["ana"]["headers"], json={"titulo": "Acesso", "descricao": "Preciso", "prioridade": "baixa"})
    assert r.status_code == 201 and r.json()["ativo_id"] is None
    assert vizinhos.chamadas == []


def test_abrir_com_ativo_inexistente(cliente, contas, ativo, fila):
    r = abrir(cliente, contas, ativo, ativo_id=999)
    assert r.status_code == 404 and r.json()["detail"] == "Ativo 999 não encontrado."
    assert cliente.get("/chamados", headers=contas["carla"]["headers"]).json() == []
    assert eventos_publicados(fila) == []  # chamado que não foi aberto não gera evento


def test_atribuir_muda_status_e_publica_o_evento(cliente, contas, ativo, fila):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = atribuir(cliente, contas, cid)
    assert r.status_code == 200 and r.json()["status"] == "em_atendimento" and r.json()["tecnico_id"] == contas["carla"]["id"]
    assert eventos_publicados(fila)[-1] == (
        "ChamadoAtribuido", {"chamado_id": cid, "tecnico_id": contas["carla"]["id"], "solicitante_id": contas["ana"]["id"]})


def test_so_tecnico_pode_ser_atribuido(cliente, contas, ativo, fila):
    cid = abrir(cliente, contas, ativo).json()["id"]
    for pessoa in ("ana", "admin"):
        r = atribuir(cliente, contas, cid, tecnico=pessoa)
        assert r.status_code == 422 and "não é técnico" in r.json()["detail"]
    assert [t for t, _ in eventos_publicados(fila)] == ["ChamadoAberto"]


def test_atribuir_a_usuario_inexistente(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=contas["carla"]["headers"], json={"tecnico_id": 999})
    assert r.status_code == 404


def test_nao_atribui_chamado_resolvido_nem_fechado(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    status(cliente, contas, cid, "resolvido")
    assert atribuir(cliente, contas, cid).status_code == 422


def test_fluxo_completo_de_status(cliente, contas, ativo, fila):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    assert status(cliente, contas, cid, "resolvido").status_code == 200
    # o próprio solicitante confirma e fecha
    r = status(cliente, contas, cid, "fechado", quem="ana")
    assert r.json()["status"] == "fechado"
    assert [t for t, _ in eventos_publicados(fila)] == ["ChamadoAberto", "ChamadoAtribuido", "ChamadoResolvido"]
    assert eventos_publicados(fila)[-1][1] == {"chamado_id": cid, "solicitante_id": contas["ana"]["id"]}


def test_solicitante_pode_reabrir_chamado_resolvido(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    status(cliente, contas, cid, "resolvido")
    assert status(cliente, contas, cid, "em_atendimento", quem="ana").json()["status"] == "em_atendimento"


def test_transicao_invalida(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = status(cliente, contas, cid, "fechado")
    assert r.status_code == 422 and "Não é possível ir de 'aberto' para 'fechado'" in r.json()["detail"]


def test_iniciar_atendimento_sem_tecnico(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    assert status(cliente, contas, cid, "em_atendimento").status_code == 422


def test_comentar_usa_o_usuario_logado(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["carla"]["headers"], json={"texto": "Verificando a fonte."})
    assert r.status_code == 201 and r.json()["autor_id"] == contas["carla"]["id"]
    assert len(cliente.get(f"/chamados/{cid}", headers=contas["ana"]["headers"]).json()["comentarios"]) == 1


def test_chamado_fechado_nao_recebe_comentarios(cliente, contas, ativo):
    cid = abrir(cliente, contas, ativo).json()["id"]
    atribuir(cliente, contas, cid)
    status(cliente, contas, cid, "resolvido")
    status(cliente, contas, cid, "fechado")
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=contas["carla"]["headers"], json={"texto": "tarde demais"})
    assert r.status_code == 422


def test_listar_filtra_por_status_e_tecnico(cliente, contas, ativo):
    a = abrir(cliente, contas, ativo).json()["id"]
    abrir(cliente, contas, ativo)
    atribuir(cliente, contas, a)
    h = contas["carla"]["headers"]
    assert [c["id"] for c in cliente.get("/chamados", params={"status": "em_atendimento"}, headers=h).json()] == [a]
    assert [c["id"] for c in cliente.get("/chamados", params={"tecnico_id": contas["carla"]["id"]}, headers=h).json()] == [a]
    assert len(cliente.get("/chamados", headers=h).json()) == 2


def test_painel(cliente, contas, ativo):
    abrir(cliente, contas, ativo)
    abrir(cliente, contas, ativo, prioridade="baixa")
    p = cliente.get("/chamados/painel", headers=contas["carla"]["headers"]).json()
    assert p == {"total": 2, "por_status": {"aberto": 2}, "atrasados": 0}


def test_painel_conta_atrasados(sessao, cliente, contas):
    agora = datetime.now()
    with sessao() as db:
        repositorio.salvar(db, Chamado(titulo="Velho", descricao="x", prioridade="critica", status="aberto", solicitante_id=2,
                                       criado_em=agora - timedelta(hours=10), prazo_sla=agora - timedelta(hours=6)))
        repositorio.salvar(db, Chamado(titulo="Resolvido", descricao="x", prioridade="critica", status="resolvido", solicitante_id=2,
                                       criado_em=agora - timedelta(hours=10), prazo_sla=agora - timedelta(hours=6)))
    p = cliente.get("/chamados/painel", headers=contas["carla"]["headers"]).json()
    assert p["total"] == 2 and p["atrasados"] == 1  # chamado já resolvido não conta como atrasado


def test_painel_do_solicitante_conta_so_os_proprios(cliente, contas, ativo):
    abrir(cliente, contas, ativo, quem="ana")
    abrir(cliente, contas, ativo, quem="bia")
    assert cliente.get("/chamados/painel", headers=contas["bia"]["headers"]).json()["total"] == 1


def test_saude_e_publica(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"status": "ok", "servico": "chamados"}


def test_chamados_de_exemplo_sem_chamar_outros_servicos(sessao, fila, vizinhos):
    with sessao() as db:
        dados_exemplo.carregar(db)
        dados_exemplo.carregar(db)  # só na primeira vez
        chamados = repositorio.listar(db)
    assert [(c.titulo, c.solicitante_id, c.tecnico_id, c.ativo_id, c.status) for c in chamados] == [
        ("Computador não liga", 2, 4, 1, "em_atendimento"),
        ("Impressora atolando papel", 3, None, 2, "aberto"),
        ("Acesso ao sistema de RH", 3, None, None, "aberto"),
    ]
    assert [t for t, _ in eventos_publicados(fila)] == ["ChamadoAberto"] * 3 + ["ChamadoAtribuido"]
    assert vizinhos.chamadas == []  # os exemplos não dependem de os outros serviços já terem subido
