# Serviço de Notificações (bônus)

Não é chamado pelos outros serviços: ele **escuta eventos** que o serviço de Chamados publica na fila
(Redis Streams, stream `helpdesk.eventos`) e grava os avisos no seu próprio banco
(SQLite em `/dados/notificacoes.db`, volume `notificacoes-dados`).

| Evento | Quem recebe o aviso |
|---|---|
| `ChamadoAberto` | solicitante (com o prazo do SLA) |
| `ChamadoAtribuido` | técnico |
| `ChamadoResolvido` | solicitante |

- **Se este serviço cair**, os chamados continuam sendo abertos; os eventos ficam guardados no Redis e os avisos
  são gravados quando ele voltar (grupo de consumidores + `XACK`).
- **Entrega repetida não duplica:** o id do evento é único no banco.
- Evento malformado é descartado (e registrado no log) para não travar os seguintes.

| Método | Rota | Quem pode |
|---|---|---|
| GET | `/notificacoes` | Logado (cada um vê só as suas) |
| GET | `/saude` | Todos |

**Variáveis:** `JWT_SEGREDO` (ou `JWT_SEGREDO_FILE`), `DATABASE_URL`, `REDIS_URL`, `STREAM_EVENTOS`,
`GRUPO_CONSUMIDORES`, `NOME_CONSUMIDOR`, `CONSUMIDOR` (0 desliga a leitura da fila), `DOCS`.

```bash
cd notificacoes
pip install -r requirements-dev.txt
pytest -q    # os testes usam um Redis de mentira (fakeredis)
```
