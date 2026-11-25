# Serviço de Inventário

Dono da tabela de equipamentos (computadores, impressoras e outros ativos de TI).
Roda sozinho, com o seu próprio banco (SQLite em `/dados/inventario.db`, volume `inventario-dados`).
Confere o token em todas as rotas, mas **não** consulta o serviço de Usuários: o perfil vem dentro do token.

| Método | Rota | Quem pode |
|---|---|---|
| POST | `/ativos` | Técnico e admin |
| GET | `/ativos` | Logado (filtro `?setor=`) |
| GET | `/ativos/{id}` | Logado (o serviço de Chamados usa para conferir o equipamento) |
| GET | `/saude` | Todos |

**Variáveis:** `JWT_SEGREDO` (ou `JWT_SEGREDO_FILE`), `DATABASE_URL`, `DADOS_EXEMPLO`, `DOCS`.

**Rodar sozinho, sem Docker** (Swagger em http://localhost:8002/docs):

```bash
cd inventario
pip install -r requirements-dev.txt
export JWT_SEGREDO=<o mesmo segredo dos outros serviços, com 32+ caracteres>
DOCS=1 uvicorn app.main:app --port 8002
pytest -q
```
