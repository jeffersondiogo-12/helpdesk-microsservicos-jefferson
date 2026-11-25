"""Conferência dos tokens JWT (cópia do `ler` do serviço de Usuários, que é quem assina).

A assinatura, a validade, o emissor e o perfil vêm de dentro do token: este serviço
não precisa chamar o serviço de Usuários para saber quem está pedindo.
"""
import jwt

from app.config import JWT_ALGORITMO, JWT_EMISSOR, JWT_SEGREDO

PERFIS = {"solicitante", "tecnico", "admin"}


class TokenInvalido(Exception):
    pass


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
