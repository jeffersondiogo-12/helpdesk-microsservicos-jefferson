"""Cria chamados de exemplo quando o banco está vazio (só para aula).

Este serviço NÃO consulta os outros na hora de criar os exemplos (eles podem nem ter subido ainda).
Ele conta com os ids dos dados de exemplo dos outros serviços:
- Usuários: 2 = Ana, 3 = Bruno (solicitantes), 4 = Carla (técnica);
- Inventário: 1 = computador, 2 = impressora.
"""
from sqlalchemy.orm import Session

from app.chamados import repositorio, servico
from app.chamados.esquemas import ChamadoCriar


def carregar(db: Session) -> None:
    if repositorio.listar(db):
        return
    ANA, BRUNO, CARLA = 2, 3, 4
    c1 = servico.registrar_abertura(db, ChamadoCriar(
        titulo="Computador não liga", descricao="Apertei o botão e nada acontece.", prioridade="alta", ativo_id=1), ANA)
    servico.registrar_abertura(db, ChamadoCriar(
        titulo="Impressora atolando papel", descricao="Atola a cada 3 folhas.", prioridade="media", ativo_id=2), BRUNO)
    servico.registrar_abertura(db, ChamadoCriar(
        titulo="Acesso ao sistema de RH", descricao="Preciso de acesso para a nova estagiária.", prioridade="baixa"), BRUNO)
    servico.registrar_atribuicao(db, c1, CARLA)
