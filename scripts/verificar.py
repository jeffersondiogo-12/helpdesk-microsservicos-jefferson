#!/usr/bin/env python3
"""Confere o HelpDesk em microsserviços já rodando, falando só com o gateway (só biblioteca padrão).

Uso:
    python scripts/verificar.py              # fluxo + segurança (o que deve passar sempre)
    python scripts/verificar.py fluxo        # abrir, atribuir, comentar, resolver e fechar + avisos por evento
    python scripts/verificar.py seguranca    # sem token = 401, solicitante não vê chamado alheio, permissões
    python scripts/verificar.py falha        # rode ANTES:  docker compose stop inventario

O endereço do gateway é http://127.0.0.1:8000 (mude com a variável GATEWAY_URL).
Sai com código 0 se tudo passou e 1 se algo falhou (serve também na integração contínua).
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("GATEWAY_URL", "http://127.0.0.1:8000").rstrip("/")
SENHA = os.getenv("SENHA_EXEMPLO", "Helpdesk2026")
falhas = 0


def chamar(metodo, caminho, corpo=None, token=None):
    """Faz uma requisição ao gateway. Devolve (status, json)."""
    cabecalhos = {"Accept": "application/json"}
    dados = None
    if corpo is not None:
        dados = json.dumps(corpo).encode()
        cabecalhos["Content-Type"] = "application/json"
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"
    pedido = urllib.request.Request(BASE + caminho, data=dados, method=metodo, headers=cabecalhos)
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            status, bruto = resposta.status, resposta.read()
    except urllib.error.HTTPError as erro:
        status, bruto = erro.code, erro.read()
    try:
        return status, json.loads(bruto)
    except ValueError:
        return status, {}


def titulo(texto):
    print(f"\n== {texto} ==")


def conferir(descricao, condicao, detalhe=""):
    global falhas
    if condicao:
        print(f"  OK      {descricao}")
    else:
        falhas += 1
        print(f"  FALHOU  {descricao}" + (f"  ({detalhe})" if detalhe else ""))
    return condicao


def entrar(email):
    status, corpo = chamar("POST", "/auth/login", {"email": email, "senha": SENHA})
    if status != 200:
        sys.exit(f"Não consegui entrar como {email} (status {status}). Os dados de exemplo estão ligados (DADOS_EXEMPLO=1)?")
    return corpo["access_token"], corpo["usuario"]["id"]


def esperar(condicao, segundos=10):
    fim = time.time() + segundos
    while time.time() < fim:
        if condicao():
            return True
        time.sleep(0.5)
    return condicao()


def tem_aviso(token, trecho):
    status, avisos = chamar("GET", "/notificacoes", token=token)
    return status == 200 and any(trecho in a["mensagem"] for a in avisos)


def novo_chamado(token, **extra):
    corpo = {"titulo": "Chamado de verificação", "descricao": "Criado por scripts/verificar.py", "prioridade": "alta", **extra}
    return chamar("POST", "/chamados", corpo, token)


def fluxo():
    titulo("Fluxo completo de um chamado, tudo pelo gateway")
    tok_carla, id_carla = entrar("carla@empresa.com")
    tok_ana, _ = entrar("ana@empresa.com")

    status, ativos = chamar("GET", "/ativos", token=tok_carla)
    conferir("lista os equipamentos (serviço de Inventário)", status == 200 and len(ativos) > 0)
    status, chamado = novo_chamado(tok_ana, ativo_id=ativos[0]["id"] if status == 200 and ativos else None)
    conferir("Ana abre um chamado com equipamento (Chamados confere no Inventário)", status == 201 and chamado.get("status") == "aberto", f"status {status}")
    numero = chamado.get("id")

    status, chamado = chamar("PATCH", f"/chamados/{numero}/atribuir", {"tecnico_id": id_carla}, tok_carla)
    conferir("Carla atribui o chamado a ela (Chamados confere no serviço de Usuários)",
             status == 200 and chamado.get("status") == "em_atendimento" and chamado.get("tecnico_id") == id_carla, f"status {status}")
    status, _ = chamar("POST", f"/chamados/{numero}/comentarios", {"texto": "Verificando o equipamento."}, tok_carla)
    conferir("Carla comenta", status == 201)
    status, chamado = chamar("PATCH", f"/chamados/{numero}/status", {"status": "resolvido"}, tok_carla)
    conferir("Carla marca como resolvido", status == 200 and chamado.get("status") == "resolvido")
    status, chamado = chamar("PATCH", f"/chamados/{numero}/status", {"status": "fechado"}, tok_ana)
    conferir("Ana confirma e fecha", status == 200 and chamado.get("status") == "fechado")
    status, painel = chamar("GET", "/chamados/painel", token=tok_carla)
    conferir("o painel responde", status == 200 and painel.get("total", 0) >= 1)

    conferir("evento ChamadoAberto virou aviso para a Ana (serviço de Notificações)",
             esperar(lambda: tem_aviso(tok_ana, f"Seu chamado #{numero} foi aberto")))
    conferir("evento ChamadoAtribuido virou aviso para a Carla",
             esperar(lambda: tem_aviso(tok_carla, f"O chamado #{numero} foi atribuído a você")))
    conferir("evento ChamadoResolvido virou aviso para a Ana",
             esperar(lambda: tem_aviso(tok_ana, f"Seu chamado #{numero} foi resolvido")))


def seguranca():
    titulo("Segurança")
    for rota in ("/chamados", "/chamados/painel", "/usuarios", "/ativos", "/notificacoes", "/auth/eu"):
        status, _ = chamar("GET", rota)
        conferir(f"GET {rota} sem token -> 401", status == 401, f"veio {status}")
    status, _ = chamar("GET", "/chamados", token="isto.nao.e.um.token")
    conferir("token inventado -> 401", status == 401, f"veio {status}")
    cabecalho = base64.urlsafe_b64encode(b'{"alg":"none","typ":"JWT"}').rstrip(b"=").decode()
    corpo = base64.urlsafe_b64encode(b'{"sub":"1","perfil":"admin","iss":"helpdesk-ti"}').rstrip(b"=").decode()
    status, _ = chamar("GET", "/usuarios", token=f"{cabecalho}.{corpo}.")
    conferir("token sem assinatura (alg none) fingindo ser admin -> 401", status == 401, f"veio {status}")
    status, _ = chamar("POST", "/auth/login", {"email": "ana@empresa.com", "senha": "senha-errada"})
    conferir("login com senha errada -> 401", status == 401, f"veio {status}")

    tok_ana, id_ana = entrar("ana@empresa.com")
    tok_bruno, _ = entrar("bruno@empresa.com")
    tok_carla, _ = entrar("carla@empresa.com")
    status, chamado = novo_chamado(tok_bruno)
    numero = chamado.get("id")
    status, _ = chamar("GET", f"/chamados/{numero}", token=tok_ana)
    conferir("Ana tenta abrir o chamado do Bruno -> 404 (nem revela que existe)", status == 404, f"veio {status}")
    status, lista = chamar("GET", "/chamados", token=tok_ana)
    conferir("a lista da Ana só tem chamados dela", status == 200 and all(c["solicitante_id"] == id_ana for c in lista))
    status, _ = chamar("POST", f"/chamados/{numero}/comentarios", {"texto": "intrusa"}, tok_ana)
    conferir("Ana não comenta no chamado do Bruno -> 404", status == 404, f"veio {status}")
    status, _ = chamar("PATCH", f"/chamados/{numero}/atribuir", {"tecnico_id": 4}, tok_ana)
    conferir("solicitante não atribui chamado -> 403", status == 403, f"veio {status}")
    status, _ = chamar("POST", "/ativos", {"patrimonio": "PAT-9", "tipo": "outro", "descricao": "Switch", "setor": "TI"}, tok_ana)
    conferir("solicitante não cadastra equipamento -> 403", status == 403, f"veio {status}")
    status, _ = chamar("POST", "/usuarios", {"nome": "Intrusa", "email": "i@x.com", "perfil": "admin", "senha": "Forte1234"}, tok_ana)
    conferir("solicitante não cria usuário -> 403", status == 403, f"veio {status}")
    status, _ = chamar("GET", f"/chamados/{numero}", token=tok_carla)
    conferir("a técnica vê o chamado do Bruno -> 200", status == 200, f"veio {status}")
    status, _ = chamar("GET", "/docs")
    conferir("a documentação interativa não fica exposta -> 404", status == 404, f"veio {status}")


def falha():
    titulo("Um serviço fora do ar (rode antes:  docker compose stop inventario)")
    status, saude = chamar("GET", "/saude")
    estados = saude.get("servicos", {})
    if not conferir("o /saude do gateway mostra o Inventário fora do ar", status == 200 and estados.get("inventario") == "fora do ar", str(estados)):
        print("          Dica: o Inventário precisa estar parado para este teste.")
    conferir("e os outros serviços seguem no ar", all(estados.get(s) == "ok" for s in ("usuarios", "chamados", "notificacoes")), str(estados))

    tok_carla, _ = entrar("carla@empresa.com")
    tok_ana, _ = entrar("ana@empresa.com")
    status, usuarios = chamar("GET", "/usuarios", token=tok_carla)
    conferir("a lista de usuários continua funcionando", status == 200 and len(usuarios) > 0)
    status, _ = chamar("GET", "/chamados", token=tok_carla)
    conferir("a lista de chamados continua funcionando", status == 200)
    status, erro = chamar("GET", "/ativos", token=tok_carla)
    conferir("listar equipamentos -> 503 com mensagem clara (vem do gateway)", status == 503 and "Inventário" in erro.get("detail", ""), f"{status} {erro}")
    status, erro = novo_chamado(tok_ana, ativo_id=1)
    conferir("abrir chamado COM equipamento -> 503 com mensagem clara (vem do serviço de Chamados)",
             status == 503 and "Inventário" in erro.get("detail", ""), f"{status} {erro}")
    print(f"          Mensagem: {erro.get('detail')}")
    status, _ = novo_chamado(tok_ana)
    conferir("abrir chamado SEM equipamento continua funcionando", status == 201, f"veio {status}")


COMANDOS = {"fluxo": fluxo, "seguranca": seguranca, "falha": falha}


def main(argumentos):
    nomes = argumentos or ["fluxo", "seguranca"]
    desconhecidos = [n for n in nomes if n not in COMANDOS]
    if desconhecidos:
        sys.exit(f"Comando desconhecido: {desconhecidos[0]}. Use: {', '.join(COMANDOS)}")
    try:
        for nome in nomes:
            COMANDOS[nome]()
    except urllib.error.URLError as erro:
        sys.exit(f"Não consegui falar com o gateway em {BASE} ({erro.reason}). Rode antes:  docker compose up --build")
    print(f"\n{'Tudo certo.' if not falhas else f'{falhas} verificação(ões) falharam.'}")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
