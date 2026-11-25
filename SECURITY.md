# Segurança

Este projeto é didático, mas segue práticas de segurança reais. Esta página explica o que já está protegido,
o que **mudou** ao separar o monólito em serviços e o que fica como responsabilidade de quem for colocar o sistema em produção.

## O que está protegido

| Risco | Proteção |
|---|---|
| Acesso sem login | Todas as rotas dos serviços, exceto `/auth/login` e `/saude`, exigem token JWT (`Authorization: Bearer ...`). **Cada serviço confere o token**; o gateway não é a única barreira. |
| Senhas vazadas do banco | Senhas guardadas só como hash **scrypt** com sal aleatório. A senha nunca é salva nem devolvida pela API. |
| Adivinhar senhas | Bloqueio temporário após 5 tentativas erradas (por e-mail e endereço IP). Mensagem igual para e-mail inexistente e senha errada. O gateway informa o IP real ao serviço de Usuários. |
| Token falsificado | Só o serviço de Usuários assina (HS256, segredo do servidor). Todo serviço confere assinatura, validade, emissor, algoritmo e perfil: tokens `alg: none`, de outro emissor, sem perfil ou com perfil desconhecido são recusados. |
| Ver ou mexer no que não é seu | Permissões por perfil em cada serviço: o solicitante só vê os próprios chamados e notificações; só técnicos e administradores atribuem e resolvem; só administradores criam usuários; só técnicos e administradores cadastram equipamentos. |
| Agir em nome de outra pessoa | O solicitante e o autor do comentário vêm do token, não do corpo da requisição. Campos extras são recusados. |
| Descobrir o que existe | Chamado de outra pessoa responde "não encontrado" (404), sem revelar que existe. A lista de usuários não mostra e-mails. |
| Alcançar um serviço sem passar pelo gateway | **Só o gateway publica porta** (`127.0.0.1:8000`). Usuários, Inventário, Chamados, Notificações e Redis ficam numa rede interna do Docker (`internal: true`): sem porta para fora e sem saída para a internet. |
| Cabeçalhos inventados pelo cliente | O gateway repassa só `Authorization`, `Content-Type` e `Accept`. `X-Forwarded-For` é sempre o IP que o gateway viu, nunca o que o cliente mandou. Caminhos com `..` são recusados e só as rotas conhecidas são encaminhadas. |
| Ler ou gravar no banco de outro serviço | Cada serviço tem o seu banco, em um volume que só ele monta. Não há chaves estrangeiras entre serviços. |
| Um serviço que cai ou trava | Chamadas entre serviços têm tempo limite (3 s) e falhas viram 503 com mensagem clara; o gateway responde 503/504. Um serviço fora do ar não derruba os outros. |
| XSS na tela | Todo texto vindo da API é escapado antes de entrar no HTML; não há scripts embutidos na página; a política CSP só permite scripts do próprio servidor. |
| Clickjacking e outros | Cabeçalhos `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, aplicados pelo gateway em todas as respostas. |
| Dados enormes | Limites de tamanho em todos os campos e corpo da requisição limitado a 64 KB, no gateway (inclusive sem `Content-Length`) e em cada serviço. |
| SQL injection | Acesso ao banco só pelo SQLAlchemy, com parâmetros (sem SQL montado com texto). |
| Erros que vazam detalhes | Erros de banco respondem com mensagem genérica; o gateway não repassa cabeçalhos internos dos serviços. |
| Dependências vulneráveis | Versões fixas, `pip-audit` por serviço no GitHub Actions a cada envio e Dependabot semanal (pip, Docker, Compose e Actions). |
| Contêiner | Cada serviço roda como usuário sem privilégios, com sistema de arquivos somente leitura, sem capacidades extras e `no-new-privileges`. |
| Segredos no código | O `JWT_SEGREDO` vem do `.env` (fora do Git) ou de um arquivo gerado num volume na primeira subida. Não existe segredo de reserva: sem um segredo de 32+ caracteres, o serviço não sobe. |

## O que mudou em relação ao monólito

São escolhas conscientes de quem separa um sistema em serviços:

- **Perfil e desativação valem no próximo login.** Inventário, Chamados e Notificações confiam no perfil que está dentro do token assinado, sem consultar Usuários. Se um perfil mudar ou um usuário for desativado, os outros serviços só percebem quando o token vence (`TOKEN_MINUTOS`, padrão 60). No serviço de Usuários a checagem continua imediata. (Hoje não há rota para mudar perfil nem desativar; o risco é para quando existir.)
- **O token do usuário é repassado** entre serviços. Não há uma "conta de serviço" separada: cada serviço decide com a identidade de quem pediu.
- **Dentro da rede interna o tráfego é HTTP puro**, e o Redis não tem senha. A rede é isolada, mas isso não serve se os serviços forem para máquinas diferentes.
- **O limite de tentativas de login continua em memória**, o que basta com uma instância do serviço de Usuários.
- Se o Redis estiver fora do ar no instante em que um chamado é aberto, **o aviso daquele chamado se perde** (o chamado é salvo normalmente).

## Antes de usar em produção

- Defina `JWT_SEGREDO` com pelo menos 32 caracteres aleatórios e tenha um plano de troca (rotação) do segredo.
- Rode com `DADOS_EXEMPLO=0` (os usuários de exemplo têm senha conhecida) e `DOCS=0`.
- Coloque o gateway atrás de HTTPS (por exemplo, um proxy reverso com certificado). Se os serviços saírem da mesma rede confiável, use TLS entre eles (ou mTLS).
- Troque o SQLite por um PostgreSQL por serviço (`DATABASE_URL`), com backup.
- Redis com senha e TLS; use o padrão "outbox" se não puder perder eventos.
- Com várias instâncias do serviço de Usuários, guarde o limite de tentativas de login em um armazenamento compartilhado (Redis).
- Se precisar derrubar um acesso na hora, adicione revogação de tokens (lista de bloqueio ou consulta a Usuários).

## Como relatar um problema

Encontrou uma falha? Não abra uma issue pública: envie os detalhes diretamente ao professor.
