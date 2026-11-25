"""Dependências do FastAPI para exigir login e perfil, só com o token (sem banco de usuários)."""
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import tokens

esquema = HTTPBearer(auto_error=False)

NAO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Faça login para continuar.",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass(frozen=True)
class UsuarioLogado:
    id: int
    perfil: str
    token: str  # o token original, para repassar quando este serviço chamar outro


def usuario_atual(credenciais: HTTPAuthorizationCredentials | None = Depends(esquema)) -> UsuarioLogado:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise NAO_AUTENTICADO
    try:
        usuario_id, perfil = tokens.ler(credenciais.credentials)
    except tokens.TokenInvalido:
        raise NAO_AUTENTICADO
    return UsuarioLogado(usuario_id, perfil, credenciais.credentials)


def exigir_perfil(*perfis: str):
    """Libera a rota só para os perfis informados."""
    def verificar(usuario: UsuarioLogado = Depends(usuario_atual)) -> UsuarioLogado:
        if usuario.perfil not in perfis:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Você não tem permissão para esta ação.")
        return usuario
    return verificar
