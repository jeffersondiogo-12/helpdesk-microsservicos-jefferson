"""O consumidor: eventos da fila viram avisos, sem perder nem duplicar."""
import threading
import time

import pytest

from app import config, consumidor
from app.notificacoes import servico
from app.notificacoes.modelos import Notificacao
from tests.conftest import publicar


def avisos(sessao):
    with sessao() as db:
        return [(a.tipo, a.destinatario_id, a.mensagem) for a in servico.listar(db)]


def pendentes(fila):
    return fila.xpending(config.STREAM_EVENTOS, config.GRUPO)["pending"]


def test_chamado_aberto_avisa_o_solicitante_com_o_prazo(sessao, fila):
    publicar(fila, "ChamadoAberto", chamado_id=7, solicitante_id=2, prazo_sla="2026-11-12T10:30:00")
    consumidor.preparar(fila)
    assert consumidor.processar_lote(fila, sessao, bloco_ms=50) == 1
    assert avisos(sessao) == [("ChamadoAberto", 2, "Seu chamado #7 foi aberto. Prazo: 12/11 10:30.")]


def test_chamado_atribuido_avisa_o_tecnico(sessao, fila):
    publicar(fila, "ChamadoAtribuido", chamado_id=7, tecnico_id=4, solicitante_id=2)
    consumidor.preparar(fila)
    consumidor.processar_lote(fila, sessao, bloco_ms=50)
    assert avisos(sessao) == [("ChamadoAtribuido", 4, "O chamado #7 foi atribuído a você.")]


def test_chamado_resolvido_avisa_o_solicitante(sessao, fila):
    publicar(fila, "ChamadoResolvido", chamado_id=7, solicitante_id=2)
    consumidor.preparar(fila)
    consumidor.processar_lote(fila, sessao, bloco_ms=50)
    assert avisos(sessao) == [("ChamadoResolvido", 2, "Seu chamado #7 foi resolvido. Confirme se está tudo certo.")]


def test_evento_tratado_e_confirmado_na_fila(sessao, fila):
    publicar(fila, "ChamadoResolvido", chamado_id=1, solicitante_id=2)
    consumidor.preparar(fila)
    consumidor.processar_lote(fila, sessao, bloco_ms=50)
    assert pendentes(fila) == 0
    assert consumidor.processar_lote(fila, sessao, bloco_ms=50) == 0  # nada novo


def test_le_eventos_publicados_antes_de_o_grupo_existir(sessao, fila):
    publicar(fila, "ChamadoResolvido", chamado_id=1, solicitante_id=2)  # o serviço de Notificações ainda estava desligado
    consumidor.preparar(fila)
    consumidor.processar_lote(fila, sessao, bloco_ms=50)
    assert len(avisos(sessao)) == 1


def test_preparar_pode_ser_chamado_varias_vezes(fila):
    consumidor.preparar(fila)
    consumidor.preparar(fila)


def test_entrega_repetida_nao_duplica_o_aviso(sessao, fila):
    id_evento = publicar(fila, "ChamadoResolvido", chamado_id=1, solicitante_id=2)
    consumidor.preparar(fila)
    campos = {"tipo": "ChamadoResolvido", "dados": '{"chamado_id": 1, "solicitante_id": 2}'}
    consumidor.tratar(sessao, fila, id_evento, campos)
    consumidor.tratar(sessao, fila, id_evento, campos)  # a mesma mensagem entregue de novo
    assert len(avisos(sessao)) == 1


def test_evento_malformado_e_descartado_sem_travar_a_fila(sessao, fila):
    fila.xadd(config.STREAM_EVENTOS, {"tipo": "ChamadoAberto", "dados": "isto não é json"})
    fila.xadd(config.STREAM_EVENTOS, {"tipo": "ChamadoAberto", "dados": '{"chamado_id": 1}'})  # faltam campos
    fila.xadd(config.STREAM_EVENTOS, {"sem": "campos"})
    publicar(fila, "ChamadoResolvido", chamado_id=9, solicitante_id=2)
    consumidor.preparar(fila)
    assert consumidor.processar_lote(fila, sessao, bloco_ms=50) == 4
    assert [a[2] for a in avisos(sessao)] == ["Seu chamado #9 foi resolvido. Confirme se está tudo certo."]
    assert pendentes(fila) == 0


def test_tipo_de_evento_desconhecido_e_ignorado(sessao, fila):
    publicar(fila, "EquipamentoTrocado", chamado_id=1)
    consumidor.preparar(fila)
    consumidor.processar_lote(fila, sessao, bloco_ms=50)
    assert avisos(sessao) == [] and pendentes(fila) == 0


def test_se_o_banco_falhar_o_evento_nao_e_confirmado_e_volta_depois(sessao, fila):
    publicar(fila, "ChamadoResolvido", chamado_id=1, solicitante_id=2)
    consumidor.preparar(fila)

    def banco_fora():
        raise RuntimeError("banco fora do ar")

    with pytest.raises(RuntimeError):
        consumidor.processar_lote(fila, banco_fora, bloco_ms=50)
    assert pendentes(fila) == 1 and avisos(sessao) == []
    # banco de volta: relê o que ficou pendente
    assert consumidor.processar_lote(fila, sessao, pendentes=True) == 1
    assert len(avisos(sessao)) == 1 and pendentes(fila) == 0


def test_laco_do_consumidor_grava_avisos_e_para_quando_pedido(sessao, fila, monkeypatch):
    monkeypatch.setattr(consumidor, "BLOCO_MS", 50)
    parar = threading.Event()
    leitor = threading.Thread(target=consumidor.executar, args=(fila, sessao, parar), daemon=True)
    leitor.start()
    try:
        publicar(fila, "ChamadoAberto", chamado_id=3, solicitante_id=2, prazo_sla="2026-11-12T08:00:00")
        limite = time.time() + 5
        while time.time() < limite and not avisos(sessao):
            time.sleep(0.05)
        assert [a[:2] for a in avisos(sessao)] == [("ChamadoAberto", 2)]
    finally:
        parar.set()
        leitor.join(timeout=3)
    assert not leitor.is_alive()


def test_laco_termina_o_que_ficou_pendente_ao_ligar(sessao, fila, monkeypatch):
    monkeypatch.setattr(consumidor, "BLOCO_MS", 50)
    publicar(fila, "ChamadoResolvido", chamado_id=1, solicitante_id=2)
    consumidor.preparar(fila)
    fila.xreadgroup(config.GRUPO, config.CONSUMIDOR, {config.STREAM_EVENTOS: ">"}, count=1)  # leu e "caiu" sem confirmar
    assert pendentes(fila) == 1
    parar = threading.Event()
    leitor = threading.Thread(target=consumidor.executar, args=(fila, sessao, parar), daemon=True)
    leitor.start()
    try:
        limite = time.time() + 5
        while time.time() < limite and not avisos(sessao):
            time.sleep(0.05)
        assert len(avisos(sessao)) == 1
    finally:
        parar.set()
        leitor.join(timeout=3)
    assert pendentes(fila) == 0


def test_evento_id_e_unico_no_banco(sessao):
    with sessao() as db:
        assert servico.registrar(db, "1-0", "ChamadoAberto", 2, "a") is not None
        assert servico.registrar(db, "1-0", "ChamadoAberto", 2, "a") is None
        assert db.query(Notificacao).count() == 1
