"use strict";

const $ = (id) => document.getElementById(id);
const corpo = document.body;
const campo = $("q"), lista = $("sugestoes"), statusEl = $("status");
const secArtista = $("artista"), inicio = $("inicio"), parede = $("parede");
const filtrosEl = $("filtros"), ordemBtn = $("ordem"), dialogo = $("detalhe");
const vitrine = $("vitrine"), fundo = $("fundo"), numerosEl = $("numeros");
const compactoBtn = $("compacto"), copiarBtn = $("copiar");

const EXEMPLOS = ["Kanye West", "Radiohead", "Beyoncé", "Racionais MC's", "Pink Floyd", "Taylor Swift"];
const TIPOS = [
  ["album", "Álbuns", "Álbum"], ["ep", "EPs", "EP"], ["single", "Singles", "Single"],
  ["ao-vivo", "Ao vivo", "Ao vivo"], ["coletanea", "Coletâneas", "Coletânea"],
];
const NOME_TIPO = Object.fromEntries(TIPOS.map(([k, , s]) => [k, s]));

const estado = { dados: null, filtro: "album", recentes: false, compacto: false, pedido: 0 };

function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos) if (f != null) n.append(f);
  return n;
}

async function api(caminho) {
  let r;
  try { r = await fetch(caminho); }
  catch { throw new Error("Sem conexão com o servidor. Ele está rodando?"); }
  if (!r.ok) {
    let msg = "Algo deu errado. Tente de novo em instantes.";
    try { const j = await r.json(); if (typeof j.detail === "string") msg = j.detail; } catch { /* mantém */ }
    throw new Error(msg);
  }
  return r.json();
}

function aviso(texto, erro = false) {
  statusEl.hidden = !texto;
  statusEl.textContent = texto || "";
  statusEl.classList.toggle("erro", erro);
}

const formatarData = (iso) => {
  if (!iso) return "Sem data";
  const [a, m, d] = iso.split("-").map(Number);
  if (!m || !d) return String(a);
  return new Date(a, m - 1, d).toLocaleDateString("pt-BR", { day: "numeric", month: "long", year: "numeric" });
};
const duracao = (s) => {
  if (!s) return "";
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), seg = s % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}min` : `${m}:${String(seg).padStart(2, "0")}`;
};

/* ---------- busca ---------- */
let timer, ativo = -1, resultados = [];

function fecharSugestoes() { lista.hidden = true; lista.replaceChildren(); ativo = -1; campo.removeAttribute("aria-activedescendant"); }

function mostrarSugestoes(itens, msg) {
  resultados = itens;
  lista.replaceChildren();
  if (msg) lista.append(el("li", { class: "aviso" }, msg));
  itens.forEach((a, i) => {
    const foto = a.foto ? el("img", { src: a.foto, alt: "", width: 40, height: 40, loading: "lazy" }) : el("span", { class: "sem-foto" });
    const li = el("li", { role: "option", id: `sug-${i}`, onmousedown: (e) => { e.preventDefault(); escolher(a); } },
      foto, el("span", {}, el("strong", {}, a.nome), a.fas ? el("small", {}, `${a.fas.toLocaleString("pt-BR")} fãs`) : null));
    lista.append(li);
  });
  lista.hidden = false;
  ativo = -1;
}

async function buscar() {
  const q = campo.value.trim();
  if (q.length < 2) return fecharSugestoes();
  const meu = ++estado.pedido;
  try {
    const itens = await api(`/api/artistas?q=${encodeURIComponent(q)}`);
    if (meu !== estado.pedido) return;
    mostrarSugestoes(itens, itens.length ? null : "Nenhum artista encontrado.");
  } catch (e) {
    if (meu === estado.pedido) mostrarSugestoes([], e.message);
  }
}

campo.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(buscar, 250); });
campo.addEventListener("blur", () => setTimeout(fecharSugestoes, 120));
campo.addEventListener("keydown", (e) => {
  const itens = [...lista.querySelectorAll("li[role=option]")];
  if (e.key === "Escape") return fecharSugestoes();
  if (e.key === "Enter") {
    e.preventDefault();
    if (lista.hidden) { clearTimeout(timer); return buscar(); }
    const a = resultados[ativo >= 0 ? ativo : 0];
    return a && escolher(a);
  }
  if ((e.key === "ArrowDown" || e.key === "ArrowUp") && itens.length) {
    e.preventDefault();
    ativo = (ativo + (e.key === "ArrowDown" ? 1 : -1) + itens.length) % itens.length;
    itens.forEach((li, i) => li.classList.toggle("ativo", i === ativo));
    campo.setAttribute("aria-activedescendant", itens[ativo].id);
  }
});

/* ---------- artista ---------- */
function mostrarInicio(sim) {
  inicio.hidden = !sim;
  vitrine.hidden = !sim || !vitrine.childElementCount;
}

function irParaInicio(empurrar = true) {
  estado.pedido++;
  corpo.classList.add("home");
  secArtista.hidden = true; mostrarInicio(true); aviso("");
  campo.value = ""; fecharSugestoes();
  document.title = "álbuns · discografia";
  if (empurrar && location.pathname !== "/") history.pushState(null, "", "/");
  window.scrollTo(0, 0);
}
$("marca").addEventListener("click", (e) => { e.preventDefault(); irParaInicio(); });

function esqueleto() {
  const grupo = el("section", { class: "decada", "aria-hidden": "true" },
    el("span", { class: "sk-nome" }),
    el("ul", { class: "capas" }, ...Array.from({ length: 10 }, () =>
      el("li", {}, el("span", { class: "sk-capa" }), el("span", { class: "sk-linha" }), el("span", { class: "sk-linha curta" })))));
  parede.replaceChildren(grupo);
}

function poeFoto(a) {
  const url = a.foto_grande || a.foto;
  for (const img of [$("foto"), fundo]) {
    img.hidden = !url;
    if (url) img.src = url; else img.removeAttribute("src");
  }
}

async function escolher(a, { empurrar = true } = {}) {
  fecharSugestoes();
  campo.blur();
  const meu = ++estado.pedido;
  pararPrevia();

  corpo.classList.remove("home");
  mostrarInicio(false); aviso("");
  secArtista.hidden = false;
  if (a.nome) campo.value = a.nome;
  $("nome").textContent = a.nome || "";
  $("resumo").textContent = "Buscando a discografia…";
  poeFoto(a);
  numerosEl.hidden = true;
  filtrosEl.replaceChildren(); ordemBtn.hidden = true; compactoBtn.hidden = true;
  esqueleto();
  window.scrollTo(0, 0);
  if (empurrar) history.pushState(null, "", `/artista/${a.id}`);

  try {
    const dados = await api(`/api/artistas/${a.id}`);
    if (meu !== estado.pedido) return;
    estado.dados = dados;
    estado.recentes = false;
    estado.compacto = false;
    const c = dados.contagens || {};
    estado.filtro = c.album ? "album" : "todos";
    campo.value = dados.artista.nome;
    poeFoto(dados.artista);
    document.title = `${dados.artista.nome} · álbuns`;
    desenhar();
  } catch (e) {
    if (meu !== estado.pedido) return;
    secArtista.hidden = true;
    aviso(e.message, true);
  }
}

/* o endereço é o app: /artista/230 abre direto, e o botão voltar do navegador funciona */
function abrirPeloEndereco() {
  const m = location.pathname.match(/^\/artista\/(\d{1,12})\/?$/);
  if (m) escolher({ id: m[1] }, { empurrar: false });
  else if (!corpo.classList.contains("home")) irParaInicio(false);
}
window.addEventListener("popstate", () => { if (dialogo.open) dialogo.close(); abrirPeloEndereco(); });

function visiveis() {
  const todos = estado.dados.lancamentos;
  return estado.filtro === "todos" ? todos : todos.filter((l) => l.tipo === estado.filtro);
}

function desenhar() {
  const { artista, contagens } = estado.dados;
  $("nome").textContent = artista.nome;
  const total = estado.dados.lancamentos.length;

  // filtros: só os tipos que existem
  const chips = [];
  for (const [chave, rotulo] of TIPOS) {
    const n = contagens[chave];
    if (n) chips.push([chave, rotulo, n]);
  }
  if (chips.length > 1) chips.push(["todos", "Todos", total]);
  filtrosEl.replaceChildren(...chips.map(([chave, rotulo, n]) =>
    el("button", {
      class: "filtro", type: "button", "aria-pressed": String(estado.filtro === chave),
      onclick: () => { estado.filtro = chave; desenhar(); },
    }, rotulo, el("small", {}, String(n)))));

  const itens = visiveis();
  const comData = itens.filter((l) => l.ano);
  const anos = comData.map((l) => l.ano);
  const nomeFiltro = (TIPOS.find(([k]) => k === estado.filtro) || [, "lançamentos"])[1].toLowerCase();
  $("resumo").textContent = itens.length
    ? `${itens.length} ${estado.filtro === "todos" ? "lançamentos" : nomeFiltro}` +
      (anos.length ? `, de ${Math.min(...anos)} a ${Math.max(...anos)}` : "")
    : "Nada encontrado para este artista.";

  ordemBtn.hidden = itens.length < 2;
  ordemBtn.textContent = estado.recentes ? "Do mais recente ao mais antigo" : "Do mais antigo ao mais recente";
  ordemBtn.onclick = () => { estado.recentes = !estado.recentes; desenhar(); };

  compactoBtn.hidden = itens.length < 24;
  compactoBtn.setAttribute("aria-pressed", String(estado.compacto));
  compactoBtn.onclick = () => { estado.compacto = !estado.compacto; desenhar(); };
  parede.classList.toggle("compacto", estado.compacto && itens.length >= 24);

  desenharNumeros();
  parede.replaceChildren(...grupos(itens));
}

function desenharNumeros() {
  const base = estado.dados.lancamentos.filter((l) => l.tipo === "album" && l.ano);
  const anos = base.map((l) => l.ano);
  const blocos = [];
  if (base.length >= 3) {
    const ini = Math.min(...anos), fim = Math.max(...anos);
    if (fim > ini) blocos.push([`${fim - ini}`, "anos entre o primeiro e o último álbum"]);
    if (fim > ini) {
      const media = (fim - ini) / (base.length - 1);
      blocos.push([media.toLocaleString("pt-BR", { maximumFractionDigits: 1 }), "anos entre um álbum e outro, em média"]);
    }
    const porDec = {};
    for (const a of anos) { const d = Math.floor(a / 10) * 10; porDec[d] = (porDec[d] || 0) + 1; }
    const [dec, n] = Object.entries(porDec).sort((x, y) => y[1] - x[1] || x[0] - y[0])[0];
    blocos.push([`${dec}s`, `década com mais álbuns (${n})`]);
  }
  numerosEl.hidden = !blocos.length;
  numerosEl.replaceChildren(...blocos.map(([v, r]) => el("div", {}, el("dt", {}, r), el("dd", {}, v))));
}

function grupos(itens) {
  if (!itens.length) return [el("p", { class: "vazio" }, "Nenhum lançamento nesse filtro.")];
  const porDecada = new Map(), semData = [];
  for (const l of itens) {
    if (!l.ano) { semData.push(l); continue; }
    const d = Math.floor(l.ano / 10) * 10;
    if (!porDecada.has(d)) porDecada.set(d, []);
    porDecada.get(d).push(l);
  }
  const decadas = [...porDecada.keys()].sort((a, b) => (estado.recentes ? b - a : a - b));
  const sec = decadas.map((d) => {
    const ls = porDecada.get(d).sort((a, b) => (a.data || "").localeCompare(b.data || "") * (estado.recentes ? -1 : 1));
    return grupo(`${d}s`, ls, false);
  });
  if (semData.length) sec.push(grupo("Sem data", semData, true));
  return sec;
}

function grupo(nome, ls, pequeno) {
  return el("section", { class: "decada", "aria-label": nome },
    el("h3", { class: "decada-nome" + (pequeno ? " pequeno" : "") }, nome),
    el("ul", { class: "capas" }, ...ls.map(cartao)));
}

/* ---------- capas ---------- */
function capaImg(l, classe) {
  if (!l.capa) return el("span", { class: `cover cover-empty ${classe || ""}`, "aria-hidden": "true" }, el("span", {}, l.titulo));
  const img = el("img", {
    class: `cover ${classe || ""}`, src: l.capa, alt: "", width: 250, height: 250, loading: "lazy", decoding: "async",
    srcset: l.capa2x ? `${l.capa} 1x, ${l.capa2x} 2x` : null,
  });
  const ok = () => img.classList.add("pronto");
  if (img.complete && img.naturalWidth) ok(); else img.addEventListener("load", ok);
  img.addEventListener("error", () => {
    const vazio = capaImg({ ...l, capa: null }, classe);
    img.replaceWith(vazio);
  });
  return img;
}

function cartao(l) {
  const abrirEste = () => abrir(l);
  const botao = el("button", { class: "capa", type: "button", "aria-label": `Abrir ${l.titulo}`, onclick: abrirEste },
    el("span", { class: "frame" }, el("span", { class: "lift" }, capaImg(l), el("span", { class: "glare" }))));
  const meta = el("span", { class: "album-meta" },
    l.ano ? el("span", {}, String(l.ano)) : null,
    estado.filtro === "todos" && l.tipo !== "album" ? el("span", { class: "tipo" }, NOME_TIPO[l.tipo] || l.tipo) : null,
    l.explicito ? el("span", { class: "explicito", title: "Conteúdo explícito" }, "E") : null);
  return el("li", { class: "album" }, botao,
    el("span", { class: "album-info" },
      el("button", { class: "album-titulo", type: "button", onclick: abrirEste }, l.titulo), meta));
}

/* inclinação 3D que acompanha o mouse */
parede.addEventListener("pointermove", (e) => {
  if (e.pointerType !== "mouse") return;
  const capa = e.target.closest(".capa");
  if (!capa) return;
  const r = capa.querySelector(".frame").getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
  capa.style.setProperty("--ry", `${((x - .5) * 14).toFixed(2)}deg`);
  capa.style.setProperty("--rx", `${((.5 - y) * 14).toFixed(2)}deg`);
  capa.style.setProperty("--mx", `${(x * 100).toFixed(1)}%`);
  capa.style.setProperty("--my", `${(y * 100).toFixed(1)}%`);
});
parede.addEventListener("pointerout", (e) => {
  const capa = e.target.closest && e.target.closest(".capa");
  if (capa && !capa.contains(e.relatedTarget)) ["--rx", "--ry"].forEach((p) => capa.style.removeProperty(p));
});

/* ---------- prévia de 30 s ---------- */
const audio = new Audio();
audio.preload = "none";
let linhaTocando = null;

function pararPrevia() {
  audio.pause();
  if (linhaTocando) { linhaTocando.classList.remove("tocando"); linhaTocando.style.removeProperty("--p"); }
  linhaTocando = null;
}
audio.addEventListener("ended", pararPrevia);
audio.addEventListener("timeupdate", () => {
  if (linhaTocando && audio.duration) linhaTocando.style.setProperty("--p", (audio.currentTime / audio.duration).toFixed(3));
});

function alternarPrevia(linha, url) {
  if (linhaTocando === linha) return pararPrevia();
  pararPrevia();
  audio.src = url;
  linhaTocando = linha;
  linha.classList.add("tocando");
  audio.play().catch(() => pararPrevia());
}

const SVG = "http://www.w3.org/2000/svg";
function icone(classe, d) {
  const svg = document.createElementNS(SVG, "svg");
  svg.setAttribute("viewBox", "0 0 16 16"); svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("class", `ic ${classe}`);
  const p = document.createElementNS(SVG, "path"); p.setAttribute("d", d); svg.append(p);
  return svg;
}

function celulaNumero(f, linha) {
  if (!f.previa) return el("span", { class: "n" }, String(f.n));
  const b = el("button", {
    class: "tocar", type: "button", "aria-label": `Ouvir prévia de ${f.titulo}`,
    onclick: () => alternarPrevia(linha, f.previa),
  }, el("span", { class: "num" }, String(f.n)),
    icone("play", "M3 1.5v13l11-6.5z"), icone("pausa", "M3 2h3.5v12H3zM9.5 2H13v12H9.5z"));
  return el("span", { class: "n" }, b);
}

/* tom médio da capa, para tingir o fundo da ficha (se o navegador não deixar ler a imagem, fica sem) */
function tomDaCapa(url) {
  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      try {
        const c = document.createElement("canvas"); c.width = c.height = 8;
        const x = c.getContext("2d"); x.drawImage(img, 0, 0, 8, 8);
        const d = x.getImageData(0, 0, 8, 8).data;
        let r = 0, g = 0, b = 0;
        for (let i = 0; i < d.length; i += 4) { r += d[i]; g += d[i + 1]; b += d[i + 2]; }
        const n = d.length / 4; r /= n; g /= n; b /= n;
        const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
        const k = lum > .55 ? .55 / lum : 1;
        resolve([r * k, g * k, b * k].map(Math.round));
      } catch { resolve(null); }
    };
    img.onerror = () => resolve(null);
    img.src = url;
  });
}

/* ---------- detalhe ---------- */
let pedidoAlbum = 0, ultimoFoco = null;

function fato(rotulo, valor) { return valor ? [el("dt", {}, rotulo), el("dd", {}, valor)] : []; }

function abrir(l) {
  ultimoFoco = document.activeElement;
  const meu = ++pedidoAlbum;
  const artistaNome = estado.dados.artista.nome;

  const faixasBox = el("div", {}, el("p", { class: "faixas-aviso" }, "Carregando faixas…"));
  const fatos = el("dl", { class: "facts" },
    ...fato("Lançamento", l.data ? formatarData(l.data) : null),
    ...fato("Tipo", NOME_TIPO[l.tipo]));
  const ctaBox = el("div", {});

  const sheet = el("div", { class: "sheet-inner" },
    el("div", { class: "sheet-bar" },
      el("button", { class: "back", type: "button", onclick: () => dialogo.close() }, "‹ Voltar")),
    el("div", { class: "sheet-grid" },
      el("div", { class: "sheet-cover-wrap" }, capaImg({ ...l, capa: l.capa2x || l.capa }, "sheet-cover")),
      el("div", {},
        el("h2", { class: "sheet-title" }, l.titulo),
        el("p", { class: "sheet-by" }, artistaNome),
        fatos, ctaBox, faixasBox)));
  dialogo.replaceChildren(sheet);
  dialogo.classList.remove("tom");
  if (l.capa) tomDaCapa(l.capa2x || l.capa).then((rgb) => {
    if (rgb && meu === pedidoAlbum) { dialogo.style.setProperty("--tom", `rgb(${rgb})`); dialogo.classList.add("tom"); }
  });
  dialogo.showModal();
  corpo.classList.add("sheet-open");
  dialogo.scrollTop = 0;

  api(`/api/albuns/${l.id}`).then((d) => {
    if (meu !== pedidoAlbum) return;
    if (d.generos && d.generos.length) sheet.querySelector(".sheet-by").after(el("p", { class: "sheet-genre" }, d.generos.join(", ")));
    fatos.replaceChildren(
      ...fato("Lançamento", d.data ? formatarData(d.data) : null),
      ...fato("Tipo", NOME_TIPO[l.tipo]),
      ...fato("Faixas", d.num_faixas ? String(d.num_faixas) : null),
      ...fato("Duração", duracao(d.duracao)),
      ...fato("Gravadora", d.gravadora));
    if (d.link) ctaBox.append(el("a", { class: "cta", href: d.link, target: "_blank", rel: "noopener" }, "Ouvir no Deezer"));
    if (d.faixas && d.faixas.length) {
      faixasBox.replaceChildren(
        el("h3", { class: "faixas-t" }, "Faixas"),
        el("ol", { class: "faixas" }, ...d.faixas.map((f) => {
          const linha = el("li", { class: "faixa" });
          linha.append(celulaNumero(f, linha),
            el("span", { class: "t" }, f.titulo, f.explicito ? el("span", { class: "explicito" }, "E") : null),
            el("span", { class: "d" }, duracao(f.duracao)));
          return linha;
        })));
    } else {
      faixasBox.replaceChildren(el("p", { class: "faixas-aviso" }, "Lista de faixas indisponível."));
    }
  }).catch((e) => {
    if (meu === pedidoAlbum) faixasBox.replaceChildren(el("p", { class: "faixas-aviso" }, e.message));
  });
}

dialogo.addEventListener("close", () => {
  pararPrevia();
  corpo.classList.remove("sheet-open");
  pedidoAlbum++;
  if (ultimoFoco && document.contains(ultimoFoco)) ultimoFoco.focus();
});
dialogo.addEventListener("click", (e) => { if (e.target === dialogo) dialogo.close(); });

/* ---------- início ---------- */
$("exemplos").append(...EXEMPLOS.map((nome) =>
  el("button", {
    class: "exemplo", type: "button",
    onclick: async () => {
      campo.value = nome;
      try {
        const r = await api(`/api/artistas?q=${encodeURIComponent(nome)}`);
        if (r.length) escolher(r[0]); else aviso("Artista não encontrado.", true);
      } catch (e) { aviso(e.message, true); }
    },
  }, nome)));

copiarBtn.addEventListener("click", async () => {
  const url = location.href;
  try { await navigator.clipboard.writeText(url); }
  catch {
    const t = el("textarea", { style: "position:fixed;opacity:0" }); t.value = url;
    document.body.append(t); t.select(); try { document.execCommand("copy"); } catch { /* sem jeito */ }
    t.remove();
  }
  copiarBtn.textContent = "Link copiado";
  setTimeout(() => { copiarBtn.textContent = "Copiar link"; }, 2000);
});

/* ---------- vitrine ---------- */
async function carregarVitrine() {
  try {
    const itens = await api("/api/destaques");
    if (itens.length < 6) return;
    const linhas = itens.length >= 24 ? 3 : itens.length >= 12 ? 2 : 1;
    const grupos = Array.from({ length: linhas }, (_, k) => itens.filter((_, i) => i % linhas === k));
    vitrine.replaceChildren(...grupos.map((g, k) => {
      const botao = (it, copia) => el("button", {
        class: "vit", type: "button", tabindex: copia ? "-1" : null, "aria-hidden": copia ? "true" : null,
        "aria-label": copia ? null : `${it.artista}, ${it.titulo}`,
        onclick: () => escolher({ id: it.artista_id, nome: it.artista }),
      }, capaImg({ titulo: it.titulo, capa: it.capa, capa2x: it.capa2x }),
        el("span", { class: "vit-rotulo" }, el("strong", {}, it.titulo), el("small", {}, it.artista)));
      const fila = el("div", { class: "fila" + (k % 2 ? " volta" : ""), style: `--tempo:${g.length * 7}s` },
        ...g.map((it) => botao(it, false)), ...g.map((it) => botao(it, true)));
      return fila;
    }));
    vitrine.hidden = inicio.hidden;
  } catch { /* sem vitrine, o resto funciona igual */ }
}
carregarVitrine();
abrirPeloEndereco();
