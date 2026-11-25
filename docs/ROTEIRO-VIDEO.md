# Texto para falar no video

## README

Ola! Neste video vou apresentar o HelpDesk de TI, um sistema de chamados que foi reorganizado em microsservicos. Primeiro vou mostrar a proposta e a arquitetura no README; em seguida, vou iniciar o sistema com Docker e demonstrar o fluxo pela tela.

O sistema permite que os usuarios entrem com suas contas, cadastrem e consultem equipamentos e abram chamados de suporte. Os tecnicos podem receber chamados, atualizar o andamento e registrar a resolucao.

Neste diagrama vemos como os componentes se comunicam. A tela envia as requisicoes para o API Gateway, que e a unica entrada do sistema e encaminha cada requisicao ao servico responsavel. Temos servicos separados para Usuarios, Inventario, Chamados e Notificacoes.

Cada servico tem seu proprio banco de dados. O servico de Chamados consulta Usuarios para validar tecnicos e consulta Inventario para validar equipamentos. Essas comunicacoes acontecem pela rede interna. Quando um chamado gera uma notificacao, Chamados publica um evento no Redis e Notificacoes processa esse evento.

Tambem mantivemos a verificacao de acesso em cada servico. O token e validado antes de atender uma requisicao, e os servicos internos nao ficam expostos diretamente para fora do Docker. Assim, cada parte tem uma responsabilidade definida e uma falha pode ser tratada sem necessariamente derrubar o sistema inteiro.

No README estao documentados os comandos para iniciar o projeto, as contas de demonstracao, as rotas, os testes e as decisoes da arquitetura. A separacao em servicos facilita evoluir cada parte, mas tambem traz mais componentes e exige tratar comunicacao pela rede, como atrasos e indisponibilidade.

## Docker e sistema

Agora vou iniciar o projeto pelo Docker Compose. Com o Docker Desktop aberto, uso o comando `docker compose up --build -d`. Esse comando constroi as imagens que forem necessarias e inicia os servicos em segundo plano.

Com `docker compose ps`, posso conferir o estado dos containers. Gateway, Usuarios, Inventario, Chamados, Notificacoes e Redis estao saudaveis. O unico servico com uma porta publicada e o Gateway, na porta 8000. O container de segredos executa uma vez para preparar o segredo de autenticacao e depois termina, como esperado.

Agora vou abrir o sistema pelo endereco `http://localhost:8000` e entrar com a conta de demonstracao da Carla, que e tecnica.

Na tela, vou abrir um chamado e selecionar um equipamento. Antes de registrar o chamado, o servico de Chamados consulta o servico de Inventario para confirmar que esse equipamento existe. Depois vou atribuir o chamado a uma tecnica, atualizar o status e concluir o atendimento.

As notificacoes aparecem no painel depois que o servico de Notificacoes recebe e processa os eventos da fila. Esse fluxo mostra como os servicos colaboram sem compartilhar o mesmo banco de dados.

Tambem posso entrar como solicitante. Nesse perfil, a pessoa acompanha os proprios chamados, mas nao tem acesso aos chamados de outros usuarios. Essa permissao e verificada pelo sistema, nao apenas pela tela.

Para concluir, este projeto transformou uma aplicacao monolitica em servicos separados, mantendo o fluxo principal de atendimento. O Gateway centraliza o acesso, cada servico cuida dos proprios dados e a comunicacao entre eles e feita pela rede. Obrigada por assistir.
