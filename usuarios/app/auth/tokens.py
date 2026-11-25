"""Criação e validação dos tokens JWT.

Só o serviço de Usuários cria tokens (`criar`). Todos os serviços conferem (`ler`):
assinatura, validade, emissor e perfil vêm de dentro do token.
"""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO, TOKEN_MINUTOS

PERFIS = {"solicitante", "tecnico", "admin"}


class TokenInvalido(Exception):
    pass


def criar(usuario_id: int, perfil: str) -> tuple[str, datetime]:
    agora = datetime.now(timezone.utc)
    expira = agora + timedelta(minutes=TOKEN_MINUTOS)
    dados = {"sub": str(usuario_id), "perfil": perfil, "iat": agora, "exp": expira, "iss": JWT_EMISSOR}
    return jwt.encode(dados, JWT_SEGREDO, algorithm=JWT_ALGORITMO), expira


def ler(token: str) -> tuple[int, str]:
    """Devolve (id do usuário, perfil) do token, ou lança TokenInvalido."""
    try:
        dados = jwt.decode(
            token, JWT_SEGREDO, algorithms=[JWT_ALGORITMO], issuer=JWT_EMISSOR,
            options={"require": ["exp", "iat", "sub", "iss", "perfil"]},
        )
        if dados["perfil"] not in PERFIS:
            raise ValueError("perfil desconhecido")
        return int(dados["sub"]), dados["perfil"]
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as erro:
        raise TokenInvalido() from erro
