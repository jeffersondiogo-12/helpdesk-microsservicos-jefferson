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
  create: { eyebrow: "CENTRAL DE SUPORTE", title: "Abrir chamado", description: "Conte para a equipe o que precisa de atenção." },
  notifications: { eyebrow: "CENTRAL DE SUPORTE", title: "Notificações", description: "Acompanhe as atualizações mais recentes dos seus chamados." },
};

let token = null, eu = null, usuarios = [];
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
function sair() { guardarToken(null); eu = null; mostrar(false); }
function mostrar(logado) {
  $("tela-login-wrapper").hidden = logado; $("tela-sistema").hidden = !logado; $("barra").hidden = !logado;
  if (logado) mudarPagina("overview");
}
const nome = (id) => (usuarios.find((u) => u.id === id) || {}).nome || "—";
const equipe = () => eu && (eu.perfil === "tecnico" || eu.perfil === "admin");

function mudarPagina(pagina) {
  const detalhes = PAGINAS[pagina];
  if (!detalhes) return;
  document.querySelectorAll("[data-view-panel]").forEach((painel) => {
    painel.hidden = painel.dataset.viewPanel !== pagina;
  });
  document.querySelectorAll(".nav-link").forEach((link) => {
    if (link.dataset.view === pagina) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
  $("page-eyebrow").textContent = detalhes.eyebrow;
  $("page-title").textContent = detalhes.title;
  $("page-description").textContent = detalhes.description;
}

async function carregar() {
  $("erro").textContent = "";
  eu = await req("GET", "/auth/eu");
  $("quem").textContent = eu.nome + " (" + eu.perfil + ")";
  $("avatar").textContent = eu.nome.trim().charAt(0).toUpperCase();
  $("bem-vindo").textContent = eu.nome.trim().split(/\s+/)[0];
  // Cada parte da tela carrega separada: se um serviço cair, o resto continua aparecendo
  const avisosDeFalha = [];
  const tentar = (caminho, padrao) => req("GET", caminho).catch((e) => { avisosDeFalha.push(e.message); return padrao; });
  const [lista, ativos, chamados, painel, avisos] = await Promise.all([
    tentar("/usuarios", []), tentar("/ativos", []), tentar("/chamados", []),
    tentar("/chamados/painel", { total: 0, por_status: {}, atrasados: 0 }), tentar("/notificacoes", []),
  ]);
  usuarios = lista;
  const ps = painel.por_status;
  $("kpis").innerHTML = [["Total", painel.total], ["Abertos", ps.aberto || 0], ["Em atendimento", ps.em_atendimento || 0],
    ["Resolvidos", (ps.resolvido || 0) + (ps.fechado || 0)], ["Atrasados", painel.atrasados]]
    .map(([t, v]) => `<article class="kpi"><small>${esc(t)}</small><b>${esc(v)}</b></article>`).join("");
  const tecnicos = usuarios.filter((u) => u.perfil === "tecnico");
  $("lista").innerHTML = chamados.map((c) => {
    const busca = [c.id, c.titulo, nome(c.solicitante_id), nome(c.tecnico_id), c.prioridade, ROTULO[c.status]].join(" ").toLocaleLowerCase("pt-BR");
    return `<tr data-search="${esc(busca)}">
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
  linhas.forEach((linha) => {
    const corresponde = linha.dataset.search.includes(termo);
    linha.hidden = !corresponde;
    if (corresponde) encontrados += 1;
  });
  $("contagem-chamados").textContent = `${encontrados} ${encontrados === 1 ? "chamado" : "chamados"}`;
  $("sem-resultados").hidden = !termo || encontrados > 0 || linhas.length === 0;
}

function acoes(c, tecnicos) {
  const botao = (acao, texto, extra = "") => `<button type="button" data-acao="${acao}" data-id="${esc(c.id)}" ${extra}>${esc(texto)}</button>`;
  if (equipe() && c.status === "aberto")
    return `<select id="t${esc(c.id)}" aria-label="Técnico">${tecnicos.map((t) => `<option value="${esc(t.id)}">${esc(t.nome)}</option>`).join("")}</select>` + botao("atribuir", "Atribuir");
  if (equipe() && c.status === "em_atendimento") return botao("resolvido", "Resolver");
  if (c.status === "resolvido" && (equipe() || c.solicitante_id === eu.id))
    return botao("fechado", "Fechar") + botao("em_atendimento", "Reabrir", 'class="sec"');
  return "";
}

async function acao(f) { try { await f(); await carregar(); } catch (e) { $("erro").textContent = e.message; } }

$("lista").addEventListener("click", (e) => {
  const b = e.target.closest("button[data-acao]");
  if (!b) return;
  const id = Number(b.dataset.id);
  if (b.dataset.acao === "atribuir") acao(() => req("PATCH", `/chamados/${id}/atribuir`, { tecnico_id: Number($("t" + id).value) }));
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
document.addEventListener("click", (e) => {
  const atalho = e.target.closest("button[data-go-view]");
  if (atalho) mudarPagina(atalho.dataset.goView);
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
