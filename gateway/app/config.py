"""Configurações do gateway, lidas das variáveis de ambiente."""
import os

# Onde está cada serviço (dentro do Docker Compose, o nome do serviço vira o endereço)
SERVICOS = {
    "usuarios": os.getenv("USUARIOS_URL", "http://usuarios:8000").rstrip("/"),
    "inventario": os.getenv("INVENTARIO_URL", "http://inventario:8000").rstrip("/"),
    "chamados": os.getenv("CHAMADOS_URL", "http://chamados:8000").rstrip("/"),
    "notificacoes": os.getenv("NOTIFICACOES_URL", "http://notificacoes:8000").rstrip("/"),
}
NOMES = {"usuarios": "Usuários", "inventario": "Inventário", "chamados": "Chamados", "notificacoes": "Notificações"}

# Qual serviço atende cada rota. Rota que não está aqui não é encaminhada (responde 404).
ROTAS = {
    "/auth": "usuarios",
    "/usuarios": "usuarios",
    "/ativos": "inventario",
    "/chamados": "chamados",
    "/notificacoes": "notificacoes",
}

# Tempo máximo de espera por um serviço. Precisa ser MAIOR que o do serviço de Chamados
# para os outros dois (3 s), senão o gateway desiste antes de o Chamados responder o 503.
TIMEOUT_SEGUNDOS = float(os.getenv("GATEWAY_TIMEOUT_SEGUNDOS", "10"))

# Tamanho máximo do corpo de uma requisição (em bytes)
TAMANHO_MAXIMO_REQUISICAO = 64 * 1024
