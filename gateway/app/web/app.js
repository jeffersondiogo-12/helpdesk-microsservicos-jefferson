// Tela do HelpDesk. Todo texto vindo da API passa por esc() antes de ir para o HTML,
// para impedir que um título como <script> seja executado (XSS).
"use strict";
const API = "";  // em microsserviços, continua vazio: a tela é servida pelo gateway
const $ = (id) => document.getElementById(id);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (s) => new Date(s).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const ROTULO = { aberto: "aberto", em_atendimento: "em atendimento", resolvido: "resolvido", fechado: "fechado" };
const PAGINAS = {
  overview: { eyebrow: "CENTRAL DE SUPORTE", title: "Visão geral", description: "Acompanhe o atendimento e as atividades recentes." },
  tickets: { eyebrow: "GESTÃO DE ATENDIMENTO", title: "Chamados", description: "Pesquise solicitações, acompanhe status e atualize responsáveis." },
  inventory: { eyebrow: "GESTÃO DE ATIVOS", title: "Inventário", description: "Consulte equipamentos e relacione-os aos chamados." },
  create: { eyebrow: "CENTRAL DE SUPORTE", title: "Abrir chamado", description: "Conte para a equipe o que precisa de atenção." },
  notifications: { eyebrow: "CENTRAL DE SUPORTE", title: "Notificações", description: "Acompanhe as atualizações mais recentes dos seus chamados." },
};

let token = null, eu = null, usuarios = [], ativos = [], filtroStatus = "all", chamadoAtivo = null;
try { token = sessionStorage.getItem("token"); } catch (e) { token = null; }

async function req(metodo, caminho, corpo) {
  const cab = { "Content-Type": "application/json" };
  if (token) cab.Authorization = "Bearer " + token;
  const r = await fetch(API + caminho, { method: metodo, headers: cab, body: corpo ? JSON.stringify(corpo) : undefined });
  const dados = await r.json().catch(() => ({}));
  if (r.status === 401 && caminho !== "/auth/login") { sair(); throw new Error("Sessão expirada. Entre novamente."); }
  if (!r.ok) throw new Error(typeof dados.detail === "string" ? dados.detail : "Dados inválidos (" + r.status + ").");
  return dados;
}

function guardarToken(t) { token = t; try { t ? sessionStorage.setItem("token", t) : sessionStorage.removeItem("token"); } catch (e) {} }
function sair() {
  if ($("detalhe-chamado").open) $("detalhe-chamado").close();
  guardarToken(null); eu = null; chamadoAtivo = null; mostrar(false);
}
function mostrar(logado) {
  $("tela-login-wrapper").hidden = logado; $("tela-sistema").hidden = !logado; $("barra").hidden = !logado;
  if (logado) mudarPagina(paginaNaUrl() || "overview", false);
}
const nome = (id) => (usuarios.find((u) => u.id === id) || {}).nome || "—";
const equipe = () => eu && (eu.perfil === "tecnico" || eu.perfil === "admin");

function paginaNaUrl() {
  const pagina = location.hash.slice(1);
  return Object.prototype.hasOwnProperty.call(PAGINAS, pagina) ? pagina : null;
}

function mudarPagina(pagina, registrarHistorico = true) {
  const detalhes = PAGINAS[pagina];
  if (!detalhes) return;
  document.querySelectorAll("[data-view-panel]").forEach((painel) => {
    painel.hidden = painel.dataset.viewPanel !== pagina;
  });
  window.addEventListener("popstate", () => {
    if (token) mudarPagina(paginaNaUrl() || "overview", false);
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    if (link.dataset.view === pagina) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("page-eyebrow").textContent = detalhes.eyebrow;
  $("page-title").textContent = detalhes.title;
  $("page-description").textContent = detalhes.description;
  if (registrarHistorico && location.hash !== `#${pagina}`)
    history.pushState({ pagina }, "", `#${pagina}`);
}

async function carregar() {
  $("erro").textContent = "";
  $("erro-inventario").textContent = "";
  eu = await req("GET", "/auth/eu");
  $("quem").textContent = eu.nome + " (" + eu.perfil + ")";
  $("avatar").textContent = eu.nome.trim().charAt(0).toUpperCase();
  $("bem-vindo").textContent = eu.nome.trim().split(/\s+/)[0];
  // Cada parte da tela carrega separada: se um serviço cair, o resto continua aparecendo
  const avisosDeFalha = [];
  const tentar = (caminho, padrao) => req("GET", caminho).catch((e) => {
    avisosDeFalha.push(e.message);
    if (caminho === "/ativos") $("erro-inventario").textContent = e.message;
    return padrao;
  });
  const [lista, ativosCarregados, chamados, painel, avisos] = await Promise.all([
    tentar("/usuarios", []), tentar("/ativos", []), tentar("/chamados", []),
    tentar("/chamados/painel", { total: 0, por_status: {}, atrasados: 0 }), tentar("/notificacoes", []),
  ]);
  usuarios = lista;
  ativos = ativosCarregados;
  renderizarInventario();
  renderizarDestaques(chamados);
  const ps = painel.por_status;
  $("kpis").innerHTML = [["Total", painel.total], ["Abertos", ps.aberto || 0], ["Em atendimento", ps.em_atendimento || 0],
    ["Resolvidos", (ps.resolvido || 0) + (ps.fechado || 0)], ["Atrasados", painel.atrasados]]
    .map(([t, v]) => `<article class="kpi"><small>${esc(t)}</small><b>${esc(v)}</b></article>`).join("");
  const tecnicos = usuarios.filter((u) => u.perfil === "tecnico");
  $("lista").innerHTML = chamados.map((c) => {
    const busca = [c.id, c.titulo, nome(c.solicitante_id), nome(c.tecnico_id), c.prioridade, ROTULO[c.status]].join(" ").toLocaleLowerCase("pt-BR");
    return `<tr data-search="${esc(busca)}" data-status="${esc(c.status)}">
      <td>${esc(c.id)}</td><td><b>${esc(c.titulo)}</b><br><small>${esc(nome(c.solicitante_id))}</small></td>
      <td class="p-${esc(c.prioridade)}">${esc(c.prioridade)}</td>
      <td><span class="pill s-${esc(c.status)}">${esc(ROTULO[c.status])}</span></td>
      <td>${c.tecnico_id ? esc(nome(c.tecnico_id)) : "—"}</td><td>${esc(fmt(c.prazo_sla))}</td>
      <td><div class="acoes">${acoes(c, tecnicos)}</div></td></tr>`;
  }).join("") || `<tr><td colspan="7"><small>Nenhum chamado.</small></td></tr>`;
  const recentes = avisos.slice().reverse().slice(0, 6);
  $("avisos").innerHTML = recentes.map((a) =>
    `<article class="aviso"><div><b>${esc(a.tipo)}</b><div class="aviso-mensagem">${esc(a.mensagem)}</div><small>${esc(fmt(a.criada_em))}</small></div></article>`).join("") || "<p class=\"empty-state\">Nenhuma notificação por enquanto.</p>";
  $("nav-notification-count").textContent = String(avisos.length);
  $("nav-notification-count").hidden = avisos.length === 0;
  $("erro").textContent = [...new Set(avisosDeFalha)].join(" ");
  $("ativo").innerHTML = `<option value="">Nenhum</option>` + ativos.map((a) => `<option value="${esc(a.id)}">${esc(a.patrimonio)} · ${esc(a.descricao)}</option>`).join("");
  filtrarChamados();
}

function filtrarChamados() {
  const termo = $("filtro-chamados").value.trim().toLocaleLowerCase("pt-BR");
  const linhas = [...$("lista").querySelectorAll("tr[data-search]")];
  let encontrados = 0;
  const contagens = { all: linhas.length, aberto: 0, em_atendimento: 0, concluidos: 0 };
  linhas.forEach((linha) => {
    const status = linha.dataset.status;
    if (status === "aberto" || status === "em_atendimento") contagens[status] += 1;
    else if (status === "resolvido" || status === "fechado") contagens.concluidos += 1;
  });
  document.querySelectorAll("[data-filter-count]").forEach((contador) => {
    contador.textContent = String(contagens[contador.dataset.filterCount] || 0);
  });
  linhas.forEach((linha) => {
    const statusCorresponde = filtroStatus === "all" ||
      linha.dataset.status === filtroStatus ||
      (filtroStatus === "concluidos" && ["resolvido", "fechado"].includes(linha.dataset.status));
    const corresponde = statusCorresponde && linha.dataset.search.includes(termo);
    linha.hidden = !corresponde;
    if (corresponde) encontrados += 1;
  });
  $("contagem-chamados").textContent = `${encontrados} ${encontrados === 1 ? "chamado" : "chamados"}`;
  $("sem-resultados").hidden = encontrados > 0 || linhas.length === 0;
}

function renderizarInventario() {
  const tipos = { computador: "Computador", notebook: "Notebook", impressora: "Impressora", rede: "Rede", outro: "Outro" };
  const notebooks = ativos.filter((a) => a.tipo === "notebook").length;
  const setores = new Set(ativos.map((a) => a.setor)).size;
  $("resumo-inventario").innerHTML = [
    ["Equipamentos", ativos.length, "ativos cadastrados"],
    ["Setores", setores, "áreas atendidas"],
    ["Notebooks", notebooks, "equipamentos móveis"],
  ].map(([titulo, valor, detalhe]) =>
    `<article class="inventory-stat"><span>${esc(titulo)}</span><b>${esc(valor)}</b><small>${esc(detalhe)}</small></article>`
  ).join("");
  $("lista-ativos").innerHTML = ativos.map((a) => {
    const tipo = tipos[a.tipo] || tipos.outro;
    const busca = [a.patrimonio, tipo, a.descricao, a.setor].join(" ").toLocaleLowerCase("pt-BR");
    return `<article class="asset-card" data-search="${esc(busca)}">
      <div class="asset-card-top"><span class="asset-type-icon" aria-hidden="true">${esc(tipo.slice(0, 2).toUpperCase())}</span><span class="asset-type">${esc(tipo)}</span></div>
      <p class="asset-tag">PATRIMÔNIO</p><h3>${esc(a.patrimonio)}</h3>
      <p class="asset-description">${esc(a.descricao)}</p>
      <div class="asset-card-bottom"><span><small>Setor</small><b>${esc(a.setor)}</b></span>
        <button type="button" class="asset-action" data-report-asset="${esc(a.id)}">Abrir chamado <span aria-hidden="true">→</span></button>
      </div>
    </article>`;
  }).join("");
  filtrarInventario();
}

function renderizarDestaques(chamados) {
  const ativos = chamados
    .filter((chamado) => chamado.status === "aberto" || chamado.status === "em_atendimento")
    .sort((a, b) => new Date(a.prazo_sla) - new Date(b.prazo_sla));
  const abertos = ativos.filter((chamado) => chamado.status === "aberto").length;
  $("overview-active-count").textContent = String(ativos.length);
  $("overview-open-count").textContent = String(abertos);
  $("overview-working-count").textContent = String(ativos.length - abertos);
  $("chamados-em-foco").innerHTML = ativos.slice(0, 4).map((chamado) => {
    const atrasado = new Date(chamado.prazo_sla).getTime() < Date.now();
    return `<button type="button" class="focus-ticket" data-foco-id="${esc(chamado.id)}" aria-label="Abrir detalhes do chamado #${esc(chamado.id)}">
      <span class="focus-priority p-${esc(chamado.prioridade)}" aria-hidden="true"></span>
      <span class="focus-ticket-copy"><b>${esc(chamado.titulo)}</b><small>#${esc(chamado.id)} · ${esc(nome(chamado.solicitante_id))}</small></span>
      <span class="focus-ticket-meta"><span class="pill s-${esc(chamado.status)}">${esc(ROTULO[chamado.status])}</span><small class="${atrasado ? "focus-overdue" : ""}">${atrasado ? "SLA vencido" : "SLA"} · ${esc(fmt(chamado.prazo_sla))}</small></span>
      <span class="focus-ticket-arrow" aria-hidden="true">↗</span>
    </button>`;
  }).join("") || `<p class="focus-empty">Tudo em dia. Não há chamados ativos para acompanhar.</p>`;
}

function filtrarInventario() {
  const termo = $("filtro-inventario").value.trim().toLocaleLowerCase("pt-BR");
  const cards = [...$("lista-ativos").querySelectorAll(".asset-card")];
  let encontrados = 0;
  cards.forEach((card) => {
    const corresponde = card.dataset.search.includes(termo);
    card.hidden = !corresponde;
    if (corresponde) encontrados += 1;
  });
  $("sem-ativos").textContent = ativos.length === 0
    ? "Nenhum equipamento cadastrado."
    : "Nenhum equipamento corresponde à busca.";
  $("sem-ativos").hidden = ativos.length > 0 && encontrados > 0;
}

function acoes(c, tecnicos) {
  const botao = (acao, texto, extra = "") => `<button type="button" data-acao="${acao}" data-id="${esc(c.id)}" ${extra}>${esc(texto)}</button>`;
  let controles = "";
  if (equipe() && c.status === "aberto")
    controles = `<select id="t${esc(c.id)}" aria-label="Técnico">${tecnicos.map((t) => `<option value="${esc(t.id)}">${esc(t.nome)}</option>`).join("")}</select>` + botao("atribuir", "Atribuir");
  else if (equipe() && c.status === "em_atendimento") controles = botao("resolvido", "Resolver");
  else if (c.status === "resolvido" && (equipe() || c.solicitante_id === eu.id))
    controles = botao("fechado", "Fechar") + botao("em_atendimento", "Reabrir", 'class="sec"');
  return botao("detalhes", "Detalhes", 'class="sec"') + controles;
}

function renderizarDetalhe(chamado) {
  const status = ROTULO[chamado.status] || chamado.status;
  const ativo = ativos.find((a) => a.id === chamado.ativo_id);
  $("detalhe-chamado-conteudo").innerHTML = `
    <div class="ticket-detail-title">
      <div><p class="eyebrow">CHAMADO #${esc(chamado.id)}</p><h3>${esc(chamado.titulo)}</h3></div>
      <span class="pill s-${esc(chamado.status)}">${esc(status)}</span>
    </div>
    <div class="ticket-detail-grid">
      <div><small>Solicitante</small><b>${esc(nome(chamado.solicitante_id))}</b></div>
      <div><small>Técnico responsável</small><b>${esc(nome(chamado.tecnico_id))}</b></div>
      <div><small>Prioridade</small><b class="p-${esc(chamado.prioridade)}">${esc(chamado.prioridade)}</b></div>
      <div><small>Prazo de SLA</small><b>${esc(fmt(chamado.prazo_sla))}</b></div>
      <div><small>Equipamento</small><b>${esc(ativo ? `${ativo.patrimonio} · ${ativo.descricao}` : "Não informado")}</b></div>
      <div><small>Aberto em</small><b>${esc(fmt(chamado.criado_em))}</b></div>
    </div>
    <div class="ticket-description"><h4>Descrição</h4><p>${esc(chamado.descricao).replace(/\n/g, "<br>")}</p></div>`;
  const comentarios = chamado.comentarios || [];
  $("lista-comentarios").innerHTML = comentarios.map((comentario) =>
    `<article class="comment-item"><div class="comment-meta"><b>${esc(nome(comentario.autor_id))}</b><time>${esc(fmt(comentario.criado_em))}</time></div><p>${esc(comentario.texto).replace(/\n/g, "<br>")}</p></article>`
  ).join("") || `<p class="empty-state">Nenhum comentário ainda. Use este espaço para acompanhar a solicitação.</p>`;
  $("novo-comentario").hidden = chamado.status === "fechado";
  $("comentario-fechado").hidden = chamado.status !== "fechado";
  $("erro-comentario").textContent = "";
}

async function abrirDetalhe(chamadoId) {
  const chamado = await req("GET", `/chamados/${chamadoId}`);
  chamadoAtivo = chamado.id;
  renderizarDetalhe(chamado);
  if (!$("detalhe-chamado").open) $("detalhe-chamado").showModal();
}

async function acao(f) { try { await f(); await carregar(); } catch (e) { $("erro").textContent = e.message; } }

$("lista").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-acao]");
  if (!b) return;
  const id = Number(b.dataset.id);
  if (b.dataset.acao === "detalhes") abrirDetalhe(id).catch((erro) => { $("erro").textContent = erro.message; });
  else if (b.dataset.acao === "atribuir") acao(() => req("PATCH", `/chamados/${id}/atribuir`, { tecnico_id: Number($("t" + id).value) }));
  else acao(() => req("PATCH", `/chamados/${id}/status`, { status: b.dataset.acao }));
});

$("novo").addEventListener("submit", (e) => {
  e.preventDefault();
  acao(async () => {
    await req("POST", "/chamados", {
    titulo: $("titulo").value, descricao: $("descricao").value, prioridade: $("prioridade").value,
    ativo_id: $("ativo").value ? Number($("ativo").value) : null,
    });
    mudarPagina("tickets");
  });
});

$("filtro-chamados").addEventListener("input", filtrarChamados);
document.querySelector(".main-nav").addEventListener("click", (e) => {
  const link = e.target.closest("button[data-view]");
  if (link) mudarPagina(link.dataset.view);
});
document.querySelector(".ticket-filters").addEventListener("click", (e) => {
  const filtro = e.target.closest("button[data-ticket-filter]");
  if (!filtro) return;
  filtroStatus = filtro.dataset.ticketFilter;
  document.querySelectorAll(".ticket-filter").forEach((botao) => {
    botao.setAttribute("aria-pressed", String(botao === filtro));
  });
  filtrarChamados();
});
document.querySelector(".asset-grid").addEventListener("click", (e) => {
  const botao = e.target.closest("button[data-report-asset]");
  if (!botao) return;
  $("ativo").value = botao.dataset.reportAsset;
  mudarPagina("create");
  $("titulo").focus();
});
$("chamados-em-foco").addEventListener("click", (e) => {
  const botao = e.target.closest("button[data-foco-id]");
  if (botao) abrirDetalhe(Number(botao.dataset.focoId)).catch((erro) => { $("erro").textContent = erro.message; });
});
document.addEventListener("click", (e) => {
  const atalho = e.target.closest("button[data-go-view]");
  if (atalho) mudarPagina(atalho.dataset.goView);
});

$("filtro-inventario").addEventListener("input", filtrarInventario);
$("fechar-detalhe").addEventListener("click", () => $("detalhe-chamado").close());
$("detalhe-chamado").addEventListener("close", () => { chamadoAtivo = null; });
$("novo-comentario").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (chamadoAtivo === null) return;
  const chamadoId = chamadoAtivo;
  const botao = e.currentTarget.querySelector('button[type="submit"]');
  botao.disabled = true;
  $("erro-comentario").textContent = "";
  try {
    await req("POST", `/chamados/${chamadoId}/comentarios`, { texto: $("texto-comentario").value });
    $("texto-comentario").value = "";
    await carregar();
    if ($("detalhe-chamado").open) await abrirDetalhe(chamadoId);
  } catch (erro) { $("erro-comentario").textContent = erro.message; }
  finally { botao.disabled = false; }
});
$("atualizar").addEventListener("click", async () => {
  const botao = $("atualizar");
  botao.disabled = true;
  botao.classList.add("is-refreshing");
  try { await carregar(); }
  catch (e) { $("erro").textContent = e.message; $("erro-inventario").textContent = e.message; }
  finally { botao.disabled = false; botao.classList.remove("is-refreshing"); }
});
$("tela-login").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("erro-login").textContent = "";
  try {
    const r = await req("POST", "/auth/login", { email: $("email").value, senha: $("senha").value });
    guardarToken(r.access_token); $("senha").value = "";
    mostrar(true); await carregar();
  } catch (err) { $("erro-login").textContent = err.message; }
});

$("sair").addEventListener("click", sair);

if (token) { mostrar(true); carregar().catch((e) => { $("erro").textContent = e.message; }); } else { mostrar(false); }
