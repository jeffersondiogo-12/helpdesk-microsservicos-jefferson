from app.notificacoes import servico


def test_cada_usuario_ve_so_as_proprias_notificacoes(sessao, cliente, contas):
    with sessao() as db:
        servico.registrar(db, "1-0", "ChamadoAberto", 2, "Aviso da Ana")
        servico.registrar(db, "2-0", "ChamadoAtribuido", 4, "Aviso da Carla")
    ana = cliente.get("/notificacoes", headers=contas["ana"]).json()
    assert [a["mensagem"] for a in ana] == ["Aviso da Ana"] and ana[0]["destinatario_id"] == 2
    assert [a["mensagem"] for a in cliente.get("/notificacoes", headers=contas["carla"]).json()] == ["Aviso da Carla"]
    assert cliente.get("/notificacoes", headers=contas["bia"]).json() == []


def test_o_aviso_nao_mostra_o_id_interno_do_evento(sessao, cliente, contas):
    with sessao() as db:
        servico.registrar(db, "1-0", "ChamadoAberto", 2, "Aviso")
    assert set(cliente.get("/notificacoes", headers=contas["ana"]).json()[0]) == {
        "id", "tipo", "destinatario_id", "mensagem", "criada_em"}


def test_avisos_em_ordem_de_chegada(sessao, cliente, contas):
    with sessao() as db:
        for i in range(3):
            servico.registrar(db, f"{i}-0", "ChamadoAberto", 2, f"Aviso {i}")
    assert [a["mensagem"] for a in cliente.get("/notificacoes", headers=contas["ana"]).json()] == ["Aviso 0", "Aviso 1", "Aviso 2"]


def test_nao_existe_rota_para_criar_aviso_pela_rede(cliente, contas):
    # Só a fila de eventos cria avisos
    assert cliente.post("/notificacoes", headers=contas["ana"], json={"mensagem": "oi"}).status_code == 405


def test_saude_e_publica(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"status": "ok", "servico": "notificacoes"}
