import re
from pathlib import Path

import httpx

WEB = Path(__file__).parent.parent / "app" / "web"


def test_tela_e_servida_pelo_gateway(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "HelpDesk TI" in r.text and "microsserviços" in r.text
    assert cliente.get("/app.js").headers["content-type"].startswith("text/javascript")
    assert cliente.get("/estilo.css").headers["content-type"].startswith("text/css")


def test_tela_nao_tem_script_embutido(cliente):
    # A política de segurança (CSP) só aceita scripts de arquivo
    assert re.findall(r"<script(?![^>]*\bsrc=)", cliente.get("/").text) == []


def test_tela_fala_com_o_proprio_endereco(cliente):
    # API vazia = mesmo endereço do gateway: a tela não precisa saber onde estão os serviços
    assert 'const API = ""' in (WEB / "app.js").read_text()


def test_tela_tem_inventario_e_fluxo_para_abrir_chamado(cliente):
    pagina = cliente.get("/").text
    script = cliente.get("/app.js").text
    assert 'data-view="inventory"' in pagina and 'data-view-panel="inventory"' in pagina
    assert 'id="filtro-inventario"' in pagina and 'data-ticket-filter="em_atendimento"' in pagina
    assert "function renderizarInventario()" in script and 'data-report-asset="${esc(a.id)}"' in script


def test_tela_escapa_o_html(cliente):
    js = cliente.get("/app.js").text
    assert "const esc =" in js and "onclick" not in js
    # todo texto vindo da API passa por esc() antes de entrar no HTML
    assert "${esc(c.titulo)}" in js and "${c.titulo}" not in js


def test_cabecalhos_de_seguranca_na_tela(cliente):
    h = cliente.get("/").headers
    assert "script-src 'self'" in h["content-security-policy"] and "frame-ancestors 'none'" in h["content-security-policy"]
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "no-referrer" and "permissions-policy" in h


def test_cabecalhos_de_seguranca_tambem_nas_respostas_dos_servicos_e_nos_erros(cliente, servicos):
    assert cliente.get("/chamados").headers["x-content-type-options"] == "nosniff"
    servicos.fora.add("chamados")
    r = cliente.get("/chamados")
    assert r.status_code == 503 and "content-security-policy" in r.headers
    assert cliente.get("/rota-que-nao-existe").headers["x-frame-options"] == "DENY"


def test_cabecalhos_do_servico_nao_substituem_os_do_gateway(cliente, servicos):
    servicos.respostas["chamados"] = lambda req: httpx.Response(200, json={}, headers={"Content-Security-Policy": "default-src *"})
    assert cliente.get("/chamados").headers["content-security-policy"].startswith("default-src 'self'")


def test_resposta_com_token_nao_fica_em_cache(cliente):
    assert cliente.get("/chamados", headers={"Authorization": "Bearer abc"}).headers["cache-control"] == "no-store"


def test_documentacao_da_api_nao_e_exposta(cliente):
    for rota in ("/docs", "/redoc", "/openapi.json"):
        assert cliente.get(rota).status_code == 404
