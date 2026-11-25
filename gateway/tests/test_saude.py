import httpx


def test_tudo_no_ar(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "gateway": "ok", "servicos": {
        "usuarios": "ok", "inventario": "ok", "chamados": "ok", "notificacoes": "ok"}}


def test_mostra_qual_servico_esta_fora_do_ar(cliente, servicos):
    servicos.fora.add("inventario")
    r = cliente.get("/saude")
    assert r.status_code == 200  # o gateway em si está de pé
    assert r.json()["status"] == "degradado"
    assert r.json()["servicos"] == {"usuarios": "ok", "inventario": "fora do ar", "chamados": "ok", "notificacoes": "ok"}


def test_servico_que_responde_com_erro_aparece_com_problemas(cliente, servicos):
    servicos.respostas["chamados"] = lambda req: httpx.Response(503, json={"status": "falha"})
    assert cliente.get("/saude").json()["servicos"]["chamados"] == "com problemas"


def test_servico_lento_nao_trava_o_saude(cliente, servicos):
    servicos.lentos.add("notificacoes")
    assert cliente.get("/saude").json()["servicos"]["notificacoes"] == "fora do ar"


def test_saude_e_publica(cliente):
    assert cliente.get("/saude").status_code == 200  # sem token
