from app import dados_exemplo
from app.inventario.modelos import Ativo

PC = {"patrimonio": "PAT-1", "tipo": "computador", "descricao": "Dell", "setor": "TI"}


def test_tecnico_cadastra_ativo_e_filtra_por_setor(cliente, contas):
    h = contas["carla"]
    assert cliente.post("/ativos", headers=h, json={**PC, "patrimonio": "PAT-1", "tipo": "impressora", "setor": "RH"}).status_code == 201
    cliente.post("/ativos", headers=h, json={**PC, "patrimonio": "PAT-2"})
    assert len(cliente.get("/ativos", headers=h).json()) == 2
    assert len(cliente.get("/ativos", params={"setor": "RH"}, headers=h).json()) == 1


def test_admin_tambem_cadastra(cliente, contas):
    assert cliente.post("/ativos", headers=contas["admin"], json=PC).status_code == 201


def test_qualquer_usuario_logado_lista_e_consulta(cliente, contas):
    criado = cliente.post("/ativos", headers=contas["carla"], json=PC).json()
    assert cliente.get("/ativos", headers=contas["ana"]).json() == [criado]
    assert cliente.get(f"/ativos/{criado['id']}", headers=contas["ana"]).json() == criado


def test_ativo_inexistente(cliente, contas):
    r = cliente.get("/ativos/999", headers=contas["ana"])
    assert r.status_code == 404 and r.json()["detail"] == "Ativo 999 não encontrado."


def test_patrimonio_repetido_e_recusado(cliente, contas):
    cliente.post("/ativos", headers=contas["carla"], json=PC)
    r = cliente.post("/ativos", headers=contas["carla"], json={**PC, "descricao": "Outro"})
    assert r.status_code == 422 and "patrimônio" in r.json()["detail"]


def test_entrada_invalida_e_recusada(cliente, contas):
    h = contas["carla"]
    assert cliente.post("/ativos", headers=h, json={**PC, "patrimonio": "PAT 1!"}).status_code == 422   # caracteres inválidos
    assert cliente.post("/ativos", headers=h, json={**PC, "tipo": "geladeira"}).status_code == 422
    assert cliente.post("/ativos", headers=h, json={**PC, "descricao": "x" * 500}).status_code == 422
    assert cliente.post("/ativos", headers=h, json={**PC, "dono_id": 7}).status_code == 422             # campo extra


def test_saude_e_publica(cliente):
    r = cliente.get("/saude")
    assert r.status_code == 200 and r.json() == {"status": "ok", "servico": "inventario"}


def test_equipamentos_de_exemplo_sao_criados_uma_vez_e_na_ordem_esperada(sessao):
    with sessao() as db:
        dados_exemplo.carregar(db)
        dados_exemplo.carregar(db)
        patrimonios = {a.id: a.patrimonio for a in db.query(Ativo).all()}
    # O serviço de Chamados usa os ids 1 e 2 nos chamados de exemplo
    assert patrimonios == {1: "PAT-0001", 2: "PAT-0002", 3: "PAT-0003"}
