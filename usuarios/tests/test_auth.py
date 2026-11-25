"""Login e tokens: o que o serviço de Usuários emite e como confere."""
from datetime import datetime, timedelta, timezone

import jwt

from app import config
from app.auth import tokens
from app.usuarios.modelos import Usuario
from tests.conftest import SENHA


def token_com(**mudancas):
    """Monta um token com as mesmas regras do serviço, mudando só o que o teste quer."""
    agora = datetime.now(timezone.utc)
    dados = {"sub": "1", "perfil": "admin", "iss": config.JWT_EMISSOR, "iat": agora, "exp": agora + timedelta(hours=1)}
    dados.update(mudancas)
    chave = dados.pop("_chave", config.JWT_SEGREDO)
    algoritmo = dados.pop("_alg", "HS256")
    return jwt.encode({k: v for k, v in dados.items() if v is not None}, chave, algorithm=algoritmo)


def eu(cliente, token):
    return cliente.get("/auth/eu", headers={"Authorization": f"Bearer {token}"})


def test_login_devolve_token_e_dados_publicos(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ANA@x.com", "senha": SENHA})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["token_type"] == "bearer" and corpo["usuario"]["perfil"] == "solicitante"
    assert "senha" not in corpo["usuario"] and "senha_hash" not in corpo["usuario"]
    # o token carrega o perfil: é assim que os outros serviços sabem quem pode o quê
    assert tokens.ler(corpo["access_token"]) == (corpo["usuario"]["id"], "solicitante")


def test_login_com_senha_errada(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_login_com_email_inexistente_tem_a_mesma_mensagem(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ninguem@x.com", "senha": "errada123"})
    assert r.status_code == 401 and r.json()["detail"] == "E-mail ou senha inválidos."


def test_login_recusa_campos_extras(cliente, contas):
    r = cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA, "perfil": "admin"})
    assert r.status_code == 422


def test_bloqueio_apos_varias_senhas_erradas(cliente, contas):
    for _ in range(config.LOGIN_MAX_FALHAS):
        cliente.post("/auth/login", json={"email": "ana@x.com", "senha": "errada123"})
    # mesmo com a senha certa, fica bloqueado por um tempo
    assert cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA}).status_code == 429


def test_rotas_exigem_login(cliente, contas):
    for metodo, rota in [("get", "/usuarios"), ("get", "/usuarios/1"), ("get", "/auth/eu"), ("post", "/usuarios")]:
        r = getattr(cliente, metodo)(rota)
        assert r.status_code == 401 and r.headers["www-authenticate"] == "Bearer", rota


def test_token_valido_funciona(cliente, contas):
    r = eu(cliente, token_com(sub=str(contas["ana"]["id"]), perfil="solicitante"))
    assert r.status_code == 200 and r.json()["email"] == "ana@x.com"


def test_token_adulterado(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"] + "x"
    assert cliente.get("/auth/eu", headers={"Authorization": token}).status_code == 401


def test_token_assinado_com_outro_segredo(cliente, contas):
    falso = token_com(sub=str(contas["admin"]["id"]), _chave="segredo-de-outra-pessoa-com-mais-de-32-caracteres")
    assert eu(cliente, falso).status_code == 401


def test_token_sem_assinatura_alg_none(cliente, contas):
    falso = token_com(sub=str(contas["admin"]["id"]), _chave=None, _alg="none")
    assert eu(cliente, falso).status_code == 401


def test_token_expirado(cliente, contas):
    antigo = datetime.now(timezone.utc) - timedelta(hours=2)
    vencido = token_com(sub=str(contas["ana"]["id"]), iat=antigo, exp=antigo + timedelta(minutes=5))
    assert eu(cliente, vencido).status_code == 401


def test_token_de_outro_emissor(cliente, contas):
    assert eu(cliente, token_com(sub=str(contas["ana"]["id"]), iss="outro-sistema")).status_code == 401


def test_token_sem_perfil_ou_com_perfil_desconhecido(cliente, contas):
    assert eu(cliente, token_com(sub=str(contas["ana"]["id"]), perfil=None)).status_code == 401
    assert eu(cliente, token_com(sub=str(contas["ana"]["id"]), perfil="superadmin")).status_code == 401


def test_cabecalho_sem_bearer(cliente, contas):
    token = contas["ana"]["headers"]["Authorization"].split(" ")[1]
    assert cliente.get("/auth/eu", headers={"Authorization": f"Basic {token}"}).status_code == 401


def test_usuario_desativado_perde_o_acesso_na_hora(sessao, cliente, contas):
    with sessao() as db:
        db.query(Usuario).filter_by(email="ana@x.com").one().ativo = False
        db.commit()
    assert cliente.get("/auth/eu", headers=contas["ana"]["headers"]).status_code == 401
    assert cliente.post("/auth/login", json={"email": "ana@x.com", "senha": SENHA}).status_code == 401


def test_senha_guardada_com_hash(sessao, contas):
    with sessao() as db:
        u = db.query(Usuario).filter_by(email="ana@x.com").one()
        assert SENHA not in u.senha_hash and u.senha_hash.startswith("scrypt$")
