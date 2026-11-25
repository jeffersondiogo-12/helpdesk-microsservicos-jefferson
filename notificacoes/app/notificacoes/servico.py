"""Regras do módulo de notificações. É a porta pública do módulo."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.notificacoes.modelos import Notificacao


def aviso_do_evento(tipo: str, dados: dict) -> tuple[int, str] | None:
    """Decide quem recebe e o que diz o aviso de cada evento (os mesmos textos do monólito).

    O serviço de Chamados publica só o que aconteceu; quem decide o aviso é este serviço.
    Devolve None para tipos que não conhece: outro serviço pode publicar eventos novos sem quebrar este.
    """
    numero = dados["chamado_id"]
    if tipo == "ChamadoAberto":
        prazo = datetime.fromisoformat(dados["prazo_sla"])
        return dados["solicitante_id"], f"Seu chamado #{numero} foi aberto. Prazo: {prazo:%d/%m %H:%M}."
    if tipo == "ChamadoAtribuido":
        return dados["tecnico_id"], f"O chamado #{numero} foi atribuído a você."
    if tipo == "ChamadoResolvido":
        return dados["solicitante_id"], f"Seu chamado #{numero} foi resolvido. Confirme se está tudo certo."
    return None


def registrar(db: Session, evento_id: str, tipo: str, destinatario_id: int, mensagem: str) -> Notificacao | None:
    """Registra um aviso. No mundo real, aqui seria enviado um e-mail ou SMS.

    Se o evento já foi tratado (entrega repetida), não grava de novo e devolve None.
    """
    aviso = Notificacao(
        evento_id=evento_id, tipo=tipo, destinatario_id=destinatario_id, mensagem=mensagem, criada_em=datetime.now()
    )
    db.add(aviso)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    db.refresh(aviso)
    return aviso


def listar(db: Session, destinatario_id: int | None = None) -> list[Notificacao]:
    consulta = select(Notificacao).order_by(Notificacao.id)
    if destinatario_id:
        consulta = consulta.where(Notificacao.destinatario_id == destinatario_id)
    return list(db.scalars(consulta))
