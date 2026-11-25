# API Gateway

**Único ponto de entrada** do HelpDesk (porta 8000). Serve a tela e encaminha cada rota ao serviço dono dela.
Os serviços e os bancos não publicam portas: de fora do Docker, só o gateway é alcançável.

| Rota | Vai para |
|---|---|
| `/auth/*`, `/usuarios*` | serviço de Usuários |
| `/ativos*` | serviço de Inventário |
| `/chamados*` | serviço de Chamados |
| `/notificacoes` | serviço de Notificações |
| `/saude` | o próprio gateway: confere o `/saude` dos 4 serviços e mostra quais estão no ar |
| `/`, `/app.js`, `/estilo.css` | a tela (a mesma do monólito; chama a API no próprio endereço) |

Qualquer outra rota responde 404 sem chegar a nenhum serviço.

**O que o gateway faz**

- Repassa método, corpo, query string e só três cabeçalhos (`Authorization`, `Content-Type`, `Accept`).
  O que o cliente inventar (cookies, `X-Usuario-Id`, `X-Forwarded-For`...) não passa.
- Informa o IP real de quem chamou em `X-Forwarded-For` (o serviço de Usuários usa no limite de tentativas de login).
- Serviço fora do ar → **503** com mensagem clara; serviço lento → **504** (`GATEWAY_TIMEOUT_SEGUNDOS`, padrão 10 s).
  Um serviço fora não afeta as rotas dos outros.
- Mantém os cabeçalhos de segurança da tela (CSP etc.), o limite de 64 KB no corpo (inclusive sem `Content-Length`)
  e recusa caminhos com `..`.
- Não confere o token: quem confere é cada serviço (o gateway não é a única barreira).

**Variáveis:** `USUARIOS_URL`, `INVENTARIO_URL`, `CHAMADOS_URL`, `NOTIFICACOES_URL`, `GATEWAY_TIMEOUT_SEGUNDOS`.

```bash
cd gateway
pip install -r requirements-dev.txt
pytest -q    # os testes simulam os 4 serviços com httpx.MockTransport
```
