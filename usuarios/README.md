# Serviço de Usuários

Dono da tabela de usuários e do **login**. É o único serviço que **cria** tokens JWT; todos os outros só conferem.
Roda sozinho, com o seu próprio banco (SQLite em `/dados/usuarios.db`, volume `usuarios-dados`).

| Método | Rota | Quem pode |
|---|---|---|
| POST | `/auth/login` | Todos |
| GET | `/auth/eu` | Logado |
| POST | `/usuarios` | Admin |
| GET | `/usuarios` | Logado (lista sem e-mail) |
| GET | `/usuarios/{id}` | Logado (o serviço de Chamados usa para conferir o técnico) |
| GET | `/saude` | Todos |

**Variáveis:** `JWT_SEGREDO` (ou `JWT_SEGREDO_FILE`), `TOKEN_MINUTOS`, `DATABASE_URL`, `DADOS_EXEMPLO`,
`SENHA_EXEMPLO`, `LOGIN_MAX_FALHAS`, `LOGIN_JANELA_SEGUNDOS`, `DOCS`.

**Rodar sozinho, sem Docker** (Swagger em http://localhost:8001/docs):

```bash
cd usuarios
pip install -r requirements-dev.txt
export JWT_SEGREDO=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
DOCS=1 uvicorn app.main:app --port 8001
pytest -q
```
