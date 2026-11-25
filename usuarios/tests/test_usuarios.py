from app import dados_exemplo
from app.usuarios.modelos import Usuario


def test_admin_cria_usuario(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Davi", "email": "davi@x.com", "perfil": "tecnico", "senha": "Forte1234"})
    assert r.status_code == 201
    assert "senha" not in r.json() and "senha_hash" not in r.json()


def test_email_repetido_e_recusado(cliente, contas):
    dados = {"nome": "Ana 2", "email": "ANA@x.com", "perfil": "solicitante", "senha": "Forte1234"}
    assert cliente.post("/usuarios", headers=contas["admin"]["headers"], json=dados).status_code == 422


def test_senha_fraca_e_recusada(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "abcdefgh"})
    assert r.status_code == 422


def test_campos_extras_sao_recusados(cliente, contas):
    r = cliente.post("/usuarios", headers=contas["admin"]["headers"],
                     json={"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "Forte1234", "ativo": False})
    assert r.status_code == 422


def test_so_admin_cria_usuario(cliente, contas):
    dados = {"nome": "Eva", "email": "eva@x.com", "perfil": "admin", "senha": "Forte1234"}
    for quem in ("ana", "carla"):
        assert cliente.post("/usuarios", headers=contas[quem]["headers"], json=dados).status_code == 403


def test_a_permissao_vem_do_banco_e_nao_so_do_token(sessao, cliente, contas):
    # Se o perfil mudar no banco, vale o do banco (aqui o serviço é o dono do dado).
    with sessao() as db:
        db.query(Usuario).filter_by(email="carla@x.com").one().perfil = "solicitante"
        db.commit()
    dados = {"nome": "Eva", "email": "eva@x.com", "perfil": "solicitante", "senha": "Forte1234"}
    assert cliente.post("/usuarios", headers=contas["carla"]["headers"], json=dados).status_code == 403


def test_lista_publica_nao_mostra_email(cliente, contas):
    lista = cliente.get("/usuarios", headers=contas["ana"]["headers"]).json()
    assert len(lista) == 4 and all("email" not in u and "senha_hash" not in u for u in lista)


def test_lista_filtra_por_perfil(cliente, contas):
    tecnicos = cliente.get("/usuarios", params={"perfil": "tecnico"}, headers=contas["ana"]["headers"]).json()
    assert [u["nome"] for u in tecnicos] == ["Carla"]


def test_obter_usuario_por_id(cliente, contas):
    r = cliente.get(f"/usuarios/{contas['carla']['id']}", headers=contas["ana"]["headers"])
    assert r.status_code == 200 and r.json() == {"id": contas["carla"]["id"], "nome": "Carla", "perfil": "tecnico"}


def test_usuario_inexistente(cliente, contas):
    assert cliente.get("/usuarios/99", headers=contas["ana"]["headers"]).status_code == 404


def test_saude_e_publica(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"status": "ok", "servico": "usuarios"}


def test_requisicao_grande_demais(cliente, contas):
    corpo = '{"nome": "' + "x" * 70000 + '"}'
    r = cliente.post("/usuarios", headers={**contas["admin"]["headers"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


def test_usuarios_de_exemplo_sao_criados_uma_vez_e_na_ordem_esperada(sessao):
    with sessao() as db:
        dados_exemplo.carregar(db)
        dados_exemplo.carregar(db)
        nomes = {u.id: u.nome for u in db.query(Usuario).all()}
    # O serviço de Chamados conta com estes ids nos chamados de exemplo
    assert nomes == {1: "Admin TI", 2: "Ana Souza", 3: "Bruno Lima", 4: "Carla Dias", 5: "Diego Rocha"}
