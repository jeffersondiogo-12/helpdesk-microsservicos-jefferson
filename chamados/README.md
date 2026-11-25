# Serviço de Chamados

Dono dos chamados e dos comentários (SQLite em `/dados/chamados.db`, volume `chamados-dados`).
Guarda só os **ids** de solicitante, técnico e equipamento: eles moram em outros bancos, então **não há chave estrangeira**.

| Método | Rota | Quem pode |
|---|---|---|
| POST | `/chamados` | Logado (o solicitante é quem está logado) |
| GET | `/chamados` | Logado (solicitante vê só os seus) |
| GET | `/chamados/painel` | Logado |
| GET | `/chamados/{id}` | Envolvidos (para os outros, 404) |
| PATCH | `/chamados/{id}/atribuir` | Técnico e admin |
| PATCH | `/chamados/{id}/status` | Técnico e admin (solicitante: fechar ou reabrir o seu) |
| POST | `/chamados/{id}/comentarios` | Envolvidos |
| GET | `/saude` | Todos |

## Como fala com os outros serviços

| Ao... | Faz | Se o outro estiver fora do ar |
|---|---|---|
| abrir um chamado **com equipamento** | `GET {INVENTARIO_URL}/ativos/{id}` | **503** com mensagem clara; o chamado não é criado |
| **atribuir** um técnico | `GET {USUARIOS_URL}/usuarios/{id}` (confere o perfil) | **503**; nada muda no chamado |
| abrir, atribuir ou resolver | publica `ChamadoAberto`, `ChamadoAtribuido` ou `ChamadoResolvido` na fila (Redis) | o chamado é salvo do mesmo jeito (o aviso pode atrasar) |

- O **token do usuário é repassado** (`Authorization`) em toda chamada: o outro serviço também confere.
- Toda chamada tem **tempo limite** (`TIMEOUT_SEGUNDOS`, padrão 3 s).
- Listar, ver, comentar, painel e abrir chamado **sem** equipamento não dependem de ninguém.
- Os pontos de integração estão em `app/clientes.py` (HTTP) e `app/eventos.py` (fila).

**Variáveis:** `JWT_SEGREDO` (ou `JWT_SEGREDO_FILE`), `DATABASE_URL`, `USUARIOS_URL`, `INVENTARIO_URL`,
`TIMEOUT_SEGUNDOS`, `REDIS_URL`, `STREAM_EVENTOS`, `DADOS_EXEMPLO`, `DOCS`.

```bash
cd chamados
pip install -r requirements-dev.txt
pytest -q    # os testes simulam Usuários, Inventário e Redis (MockTransport e fakeredis)
```
