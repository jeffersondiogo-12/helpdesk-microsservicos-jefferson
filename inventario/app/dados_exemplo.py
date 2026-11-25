"""Cria os equipamentos de exemplo quando o banco está vazio (só para aula).

ATENÇÃO: o serviço de Chamados usa os ids 1 e 2 nos chamados de exemplo
(1 = computador, 2 = impressora). Por isso a ordem abaixo não deve mudar.
"""
from sqlalchemy.orm import Session

from app.inventario import servico as inventario
from app.inventario.esquemas import AtivoCriar


def carregar(db: Session) -> None:
    if inventario.listar(db):
        return
    inventario.criar(db, AtivoCriar(patrimonio="PAT-0001", tipo="computador", descricao="Desktop Dell OptiPlex", setor="Financeiro"))
    inventario.criar(db, AtivoCriar(patrimonio="PAT-0002", tipo="impressora", descricao="Impressora HP LaserJet", setor="RH"))
    inventario.criar(db, AtivoCriar(patrimonio="PAT-0003", tipo="notebook", descricao="Notebook Lenovo ThinkPad", setor="TI"))
