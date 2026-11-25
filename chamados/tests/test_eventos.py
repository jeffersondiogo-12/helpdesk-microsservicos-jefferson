import redis

from app import eventos
from tests.conftest import eventos_publicados


class RedisFora:
    """Um Redis que não responde."""

    def xadd(self, *args, **kwargs):
        raise redis.ConnectionError("Redis fora do ar")


def abrir(cliente, contas, ativo_id=None):
    return cliente.post("/chamados", headers=contas["ana"]["headers"],
                        json={"titulo": "Teste", "descricao": "Teste", "prioridade": "baixa", "ativo_id": ativo_id})


def test_evento_vai_para_a_fila_com_tipo_e_dados(fila):
    eventos.publicar("ChamadoAberto", {"chamado_id": 1})
    assert eventos_publicados(fila) == [("ChamadoAberto", {"chamado_id": 1})]


def test_chamado_e_aberto_mesmo_com_o_redis_fora_do_ar(cliente, contas, caplog):
    eventos.usar_fila(RedisFora())
    r = abrir(cliente, contas)
    assert r.status_code == 201
    assert "Não foi possível publicar o evento ChamadoAberto" in caplog.text
    assert [c["id"] for c in cliente.get("/chamados", headers=contas["ana"]["headers"]).json()] == [r.json()["id"]]


def test_atribuir_e_resolver_seguem_funcionando_com_o_redis_fora_do_ar(cliente, contas):
    cid = abrir(cliente, contas).json()["id"]
    eventos.usar_fila(RedisFora())
    carla = contas["carla"]["headers"]
    assert cliente.patch(f"/chamados/{cid}/atribuir", headers=carla, json={"tecnico_id": contas["carla"]["id"]}).status_code == 200
    assert cliente.patch(f"/chamados/{cid}/status", headers=carla, json={"status": "resolvido"}).status_code == 200


def test_so_resolver_publica_evento_de_status(cliente, contas, fila):
    cid = abrir(cliente, contas).json()["id"]
    carla = contas["carla"]["headers"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=carla, json={"tecnico_id": contas["carla"]["id"]})
    cliente.patch(f"/chamados/{cid}/status", headers=carla, json={"status": "resolvido"})
    cliente.patch(f"/chamados/{cid}/status", headers=carla, json={"status": "fechado"})
    cliente.post(f"/chamados/{cid}/comentarios", headers=carla, json={"texto": "comentário não gera evento"})
    assert [t for t, _ in eventos_publicados(fila)] == ["ChamadoAberto", "ChamadoAtribuido", "ChamadoResolvido"]
