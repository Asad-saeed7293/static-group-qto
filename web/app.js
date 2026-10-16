/* Static Group · Automated QTO & Project Intelligence — single page app (no build step).
   UI layer only: every number shown comes from the backend API (deterministic engine, stored runs). */
const S = { pid: localStorage.getItem("pid") || null, projects: [], cache: {}, user: "", chat: [] };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = v => (v === null || v === undefined) ? "" : String(v).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const n3 = v => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
const n2 = v => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const n0 = v => (v === null || v === undefined) ? "—" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 });
const pct = v => (v === null || v === undefined) ? "—" : (v > 0 ? "+" : "") + Number(v).toFixed(1) + " %";
const UNIT = u => ({ m3: "m³", m2: "m²", m: "m", lm: "lm", nr: "nr", item: "item" }[u] || u || "");
const TYPES = { footing: "Footing", raft: "Raft", blinding: "Blinding", column: "Column", wall: "RC wall", beam: "Beam", slab: "Slab", pedestal: "Pedestal" };
const shortName = n => (n || "").replace(/^Mr\.?\s+|^Mrs\.?\s+/, "").split(" Villa")[0].split(" (")[0];

/* ---------------- icons ---------------- */
const IC = {
  home: "M3 10.5 12 3l9 7.5|M5 9v11h14V9|M10 20v-6h4v6",
  projects: "M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z",
  overview: "M4 4h7v7H4z|M13 4h7v4h-7z|M13 10h7v10h-7z|M4 13h7v7H4z",
  boq: "M9 6h11|M9 12h11|M9 18h11|M4 6h.01|M4 12h.01|M4 18h.01",
  drawings: "M12 3 2 8l10 5 10-5z|M2 16l10 5 10-5|M2 12l10 5 10-5",
  review: "M9 11l3 3 8-8|M20 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11",
  bench: "M4 20V11|M10 20V5|M16 20v-8|M21 20H3",
  rules: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z|M9 12l2 2 4-4",
  knowledge: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z|M4 19.5A2.5 2.5 0 0 0 6.5 22H20v-5",
  assistant: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z|M8.5 12h.01|M12 12h.01|M15.5 12h.01",
  report: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z|M14 3v6h6|M8 13h8|M8 17h5",
  audit: "M3 12a9 9 0 1 0 3-6.7L3 8|M3 3v5h5|M12 7v5l3 2",
  settings: "M4 21v-7|M4 10V3|M12 21v-9|M12 8V3|M20 21v-5|M20 12V3|M1 14h6|M9 8h6|M17 16h6",
  export: "M12 3v12|M8 11l4 4 4-4|M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  play: "M7 4l13 8-13 8z", plus: "M12 5v14|M5 12h14", arrow: "M5 12h14|M13 6l6 6-6 6", back: "M19 12H5|M11 6l-6 6 6 6",
  fit: "M4 9V4h5|M20 9V4h-5|M4 15v5h5|M20 15v5h-5", zin: "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0|M21 21l-4.3-4.3|M11 8v6|M8 11h6", zout: "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0|M21 21l-4.3-4.3|M8 11h6",
  info: "M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0-18 0|M12 8h.01|M11 12h1v5h1", alert: "M12 3 2 20h20z|M12 10v4|M12 17h.01",
  locate: "M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0|M12 2v4|M12 18v4|M2 12h4|M18 12h4", check: "M5 12l5 5L20 7", x: "M6 6l12 12|M18 6 6 18",
  note: "M4 20h4L19 9l-4-4L4 16z", changes: "M6 3v12|M18 9v12|M6 18m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0|M18 6m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  inputs: "M4 4h16v16H4z|M8 9h8|M8 13h8|M8 17h4", print: "M6 9V3h12v6|M6 18H4v-7h16v7h-2|M8 14h8v7H8z", elements: "M12 2l9 5v10l-9 5-9-5V7z|M12 22V12|M21 7l-9 5-9-5",
  doc: "M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z|M14 3v6h6", eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z|M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
  send: "M22 2 11 13|M22 2l-7 20-4-9-9-4z", search: "M11 11m-7 0a7 7 0 1 0 14 0a7 7 0 1 0-14 0|M21 21l-4.3-4.3",
};
const icon = (n, cls = "") => `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${(IC[n] || "").split("|").map(d => `<path d="${d}"/>`).join("")}</svg>`;

/* ---------------- status vocabulary ---------------- */
const DS = { "Calculated": ["b-success", "#1d7048"], "Estimated": ["b-info", "#2b5a8a"], "Needs Review": ["b-warning", "#c98a1a"], "Missing": ["b-error", "#b42318"], "Lump Sum": ["b-neutral", "#9aa1a9"], "Excluded": ["b-neutral", "#c9cdd2"] };
const RAW2DS = { "Automatically Calculated": "Calculated", "Calculated With Assumption": "Estimated", "Requires Input": "Missing", "Not Available From Drawing": "Missing", "Requires Engineer Review": "Needs Review", "Lump Sum": "Lump Sum", "Not Applicable": "Excluded" };
const dsBadge = s => `<span class="badge ${(DS[s] || ["b-neutral"])[0]}">${esc(s)}</span>`;
const RS = { CONFIRMED: "b-success", INFERRED: "b-info", ASSUMED: "b-warning", UNKNOWN: "b-error" };
const ruleBadge = s => `<span class="badge ${RS[s] || "b-neutral"}">${esc(s)}</span>`;
const STATUS_COLORS = { "Verified": "#1d7048", "OK": "#5c9c7a", "Check": "#c98a1a", "Review Required": "#b42318", "Missing Data": "#8a929b", "BOQ not provided": "#c9cdd2" };
const ELB = { "Verified": "b-success", "OK": "b-success", "Check": "b-warning", "Review Required": "b-error", "Missing Data": "b-neutral", "BOQ not provided": "b-neutral", "Accepted": "b-success", "Resolved": "b-success", "Rejected": "b-neutral", "Open": "b-outline" };
function badge(s) { return s ? `<span class="badge ${ELB[s] || "b-neutral"}">${esc(s)}</span>` : ""; }
const SEV = { critical: ["#b42318", "Critical"], attention: ["#c98a1a", "Attention"], info: ["#8a929b", "Info"] };

/* ---------------- infrastructure ---------------- */
function toast(m, ms = 3200, kind = "") { const t = $("#toast"); t.className = kind; t.innerHTML = esc(m); clearTimeout(t._h); t._h = setTimeout(() => t.classList.add("hidden"), ms); }
/* Navigation guard: a page load superseded by a newer navigation must not render over it.
   GET responses that arrive after the user navigated away raise StaleNav, which route() and the
   global handler ignore. Writes (POST) are never cancelled. */
class StaleNav extends Error { constructor() { super("superseded navigation"); this.name = "StaleNav"; } }
window.addEventListener("unhandledrejection", e => { if (e.reason instanceof StaleNav) e.preventDefault(); });
S.nav = 0; S.raw = 0;
async function api(path, opts = {}) {
  const tok = S.raw ? null : S.nav;
  const r = await rawApi(path, opts);
  if (!opts.method && tok !== null && tok !== S.nav) throw new StaleNav();
  return r;
}
async function rawApi(path, opts = {}) {
  const o = { ...opts }; if (o.body && !(o.body instanceof FormData)) { o.headers = { "Content-Type": "application/json" }; o.body = JSON.stringify(o.body); }
  const r = await fetch(path, o); if (!r.ok) { let d = ""; try { d = (await r.json()).detail } catch (e) { } throw new Error(d || r.statusText); }
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
}
const P = p => `/api/projects/${S.pid}${p}`;
function invalidate() { S.cache = {}; }
async function cached(k, f) {
  const tok = S.nav;
  if (!S.cache[k]) { S.raw++; try { S.cache[k] = f(); } finally { S.raw--; } }   // shared promise: never cancelled itself
  let v; try { v = await S.cache[k]; } catch (e) { delete S.cache[k]; throw e; }
  if (tok !== S.nav) throw new StaleNav();
  return v;
}
const cur = () => S.projects.find(p => p.id === S.pid) || {};
const fmtRun = rid => { if (!rid) return "Not processed"; const m = /^(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})/.exec(rid); if (!m) return rid; const d = new Date(+m[1], +m[2] - 1, +m[3], +m[4], +m[5]); return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) + ", " + m[4] + ":" + m[5]; };
const fmtIso = s => { if (!s) return "—"; const d = new Date(s); return isNaN(d) ? s : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) + ", " + d.toTimeString().slice(0, 5); };
function confirmDialog(title, text, ok = "Confirm", danger = false) {
  const d = $("#dlg"); $("#dlgTitle").textContent = title; $("#dlgText").innerHTML = text; $("#dlgOk").textContent = ok; $("#dlgOk").className = danger ? "danger" : "";
  d.returnValue = ""; d.showModal(); return new Promise(res => d.addEventListener("close", () => res(d.returnValue === "ok"), { once: true }));
}
function openSheet(html, narrow = false) { const d = $("#drawer"); d.classList.toggle("narrow", narrow); d.classList.remove("hidden"); $("#drawerBody").innerHTML = html; $(".drawer-inner").scrollTop = 0; setTimeout(() => $(".drawer-inner .close")?.focus(), 30); }
function closeDrawer() { $("#drawer").classList.add("hidden"); $$("tr.sel").forEach(t => t.classList.remove("sel")); }
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#drawer").classList.contains("hidden") && !$("#dlg").open) closeDrawer(); });
$("#drawer").addEventListener("click", ev => { if (ev.target.id === "drawer") closeDrawer(); });
const skeleton = (n = 3) => `<div class="skel-page"><div class="skel" style="height:26px;width:280px"></div><div class="skel" style="height:14px;width:460px;margin-bottom:22px"></div><div class="grid g4" style="margin-bottom:16px">${"<div class='skel' style='height:92px'></div>".repeat(4)}</div>${"<div class='skel' style='height:120px'></div>".repeat(n)}</div>`;
const emptyState = (ic, title, text, action = "") => `<div class="card"><div class="empty-state">${icon(ic)}<h3>${esc(title)}</h3><p>${text}</p>${action}</div></div>`;
function pageHead(title, sub = "", actions = "", eyebrow = "") { return `<div class="page-head"><div>${eyebrow ? `<div class="eyebrow">${eyebrow}</div>` : ""}<h1 class="page-title">${title}</h1>${sub ? `<div class="page-sub">${sub}</div>` : ""}</div>${actions ? `<div class="row wrap">${actions}</div>` : ""}</div>`; }
function setCrumb(...parts) { $("#crumb").innerHTML = parts.filter(Boolean).map((p, i, a) => i === a.length - 1 ? `<b>${esc(p)}</b>` : esc(p)).join(' <span style="color:var(--faint)">/</span> '); }
function kpi(label, value, sub = "", opts = {}) { return `<div class="card kpi ${opts.cls || ""} ${opts.href ? "link" : ""}" ${opts.href ? `onclick="location.hash='${opts.href}'" role="link" tabindex="0"` : ""}><div class="l">${label}</div><div class="v">${value}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div>`; }
function stackBar(counts, colors, thin = false) {
  const tot = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  return `<div class="stack ${thin ? "thin" : ""}">${Object.keys(colors).filter(k => counts[k]).map(k => `<div title="${esc(k)}: ${counts[k]}" style="width:${counts[k] / tot * 100}%;background:${colors[k]}"></div>`).join("")}</div>`;
}
function legend(counts, colors) { return `<div class="legend">${Object.keys(colors).filter(k => counts[k]).map(k => `<span><i style="background:${colors[k]}"></i>${esc(k)}<b>${counts[k]}</b></span>`).join("")}</div>`; }
const DSC = Object.fromEntries(Object.entries(DS).map(([k, v]) => [k, v[1]]));
function stack(counts) { return stackBar(counts, STATUS_COLORS) + legend(counts, STATUS_COLORS); }
function bars(rows, fmt = n3, unit = "") {
  const max = Math.max(...rows.map(r => Math.abs(r[1] || 0)), 1e-9);
  return `<div class="bars">${rows.map(([l, v, c]) => `<div class="row"><div>${esc(l)}</div><div class="track"><div class="fill" style="width:${Math.abs(v || 0) / max * 100}%;${c ? "background:" + c : ""}"></div></div><div class="num" style="text-align:right">${fmt(v)} ${unit}</div></div>`).join("")}</div>`;
}
function table(cols, rows, { onclick, id } = {}) {
  const tid = id || "t" + Math.random().toString(36).slice(2, 8);
  const html = `<div class="tablewrap"><table id="${tid}"><thead><tr>${cols.map((c, i) => `<th data-i="${i}" class="${c.num ? "num" : ""}" scope="col">${c.t}</th>`).join("")}</tr></thead><tbody></tbody></table></div>`;
  setTimeout(() => {
    const t = document.getElementById(tid); if (!t) return; let sortI = null, asc = true;
    const draw = () => {
      let rs = rows.slice();
      if (sortI !== null) { const c = cols[sortI]; rs.sort((a, b) => { const x = c.sv ? c.sv(a) : a[c.k], y = c.sv ? c.sv(b) : b[c.k]; return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1); }); }
      t.tBodies[0].innerHTML = rs.map(r => `<tr class="${onclick ? "click" : ""}" data-ri="${rows.indexOf(r)}" ${onclick ? 'tabindex="0"' : ""}>${cols.map(c => `<td class="${c.num ? "num" : ""}">${c.f ? c.f(r) : esc(r[c.k])}</td>`).join("")}</tr>`).join("") || `<tr><td colspan="${cols.length}" class="empty">No rows match the current filter</td></tr>`;
      if (onclick) t.tBodies[0].querySelectorAll("tr[data-ri]").forEach(tr => { const go = () => { $$("tr.sel", t).forEach(x => x.classList.remove("sel")); tr.classList.add("sel"); onclick(rows[+tr.dataset.ri]); }; tr.onclick = go; tr.onkeydown = e => { if (e.key === "Enter") go(); }; });
      t.tHead.querySelectorAll("th").forEach((th, i) => { th.classList.toggle("sorted", i === sortI); th.classList.toggle("desc", i === sortI && !asc); });
    };
    t.tHead.querySelectorAll("th").forEach(th => th.onclick = () => { const i = +th.dataset.i; asc = sortI === i ? !asc : true; sortI = i; draw(); });
    draw();
  });
  return html;
}
function seg(id, opts, on) { return `<div class="seg" id="${id}" role="tablist">${opts.map(([v, l, n]) => `<button type="button" role="tab" data-v="${esc(v)}" class="${v === on ? "on" : ""}" aria-selected="${v === on}">${l}${n !== undefined ? `<span class="n">${n}</span>` : ""}</button>`).join("")}</div>`; }
function bindSeg(id, fn) { $$(`#${id} button`).forEach(b => b.onclick = () => { $$(`#${id} button`).forEach(x => { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); }); fn(b.dataset.v); }); }

/* ---------------- navigation ---------------- */
const NAV = [
  ["Workspace", [["home", "Dashboard", "home"], ["projects", "Projects", "projects"]]],
  ["Current project", [["project/overview", "Overview", "overview"], ["project/boq", "BOQ", "boq"], ["project/drawings", "Drawings", "drawings"], ["project/reviews", "Reviews", "review", "reviewBadge"]]],
  ["Methodology", [["rules", "Rule Approval", "rules", "rulesBadge"], ["benchmark", "Benchmarks", "bench"], ["costs", "Cost Benchmarking", "bench"], ["knowledge", "Knowledge", "knowledge"]]],
  ["Intelligence", [["assistant", "Assistant", "assistant"], ["report", "Daily Report", "report"]]],
  ["System", [["reports", "Reports & Audit", "audit"], ["settings", "Settings", "settings"]]],
];
function buildNav() {
  $("#nav").innerHTML = NAV.map(([g, items]) => `<div class="nav-group">${g}</div>` + items.map(([r, l, ic, b]) => `<a href="#/${r}" data-r="${r}">${icon(ic)}<span>${l}</span>${b ? `<span class="nav-badge" id="${b}"></span>` : ""}</a>`).join("")).join("");
}
const REDIRECT = { ceo: "home", dashboard: "project/overview", sboq: "project/boq", drawings: "project/drawings", review: "project/reviews", elements: "project/elements", takeoff: "project/takeoff", changes: "project/changes", inputs: "project/inputs", boq: "project/clientboq", variance: "project/variance" };
const ROUTES = { home, projects, project, processing, viewer, benchmark, costs, knowledge, rules, assistant, report, reports, settings, newproject };
async function route() {
  const raw = location.hash.slice(2) || "home";
  const [path, qs] = raw.split("?");
  let [name, arg] = path.split("/");
  if (REDIRECT[name]) { const [n2_, a2] = REDIRECT[name].split("/"); if (name === "drawings" || !arg) { location.replace("#/" + REDIRECT[name] + (qs ? "?" + qs : "")); return; } name = n2_; arg = a2; }
  const params = Object.fromEntries(new URLSearchParams(qs || ""));
  closeDrawer();
  const key = name === "project" ? `project/${arg || "overview"}` : name;
  $$("#nav a").forEach(a => { const on = a.dataset.r === key || (name === "project" && a.dataset.r === "project/overview" && !$$("#nav a").some(x => x.dataset.r === key)) || (name === "viewer" && a.dataset.r === "project/drawings") || (name === "newproject" && a.dataset.r === "projects") || (name === "processing" && a.dataset.r === "project/overview"); a.classList.toggle("active", on); a.toggleAttribute("aria-current", on); });
  const main = $("#main"); main.innerHTML = skeleton();
  const tok = ++S.nav;
  try { await (ROUTES[name] || home)(main, arg, params); }
  catch (e) {
    if (e instanceof StaleNav || tok !== S.nav) return;   // a newer navigation owns the page
    if (String(e.message).includes("not been processed")) main.innerHTML = emptyState("play", "This project has not been processed yet", "Run processing to read the project's DXF drawings, extract elements and calculate quantities.", `<a class="btn" href="#/processing">${icon("play")}Process drawings</a>`);
    else main.innerHTML = emptyState("alert", "Something went wrong loading this page", esc(e.message), `<button class="sec" onclick="route()">Try again</button>`);
  }
  main.focus({ preventScroll: true });
}
window.addEventListener("hashchange", route);

async function init() {
  buildNav();
  const [projs, me] = await Promise.all([api("/api/projects"), api("/api/me").catch(() => ({ user: "" }))]);
  S.projects = projs; S.user = me.user || "";
  $("#userName").textContent = S.user; $("#avatar").textContent = (S.user || "SG").slice(0, 2).toUpperCase(); $("#user").title = "Signed in as " + S.user;
  if (!S.pid || !S.projects.find(p => p.id === S.pid)) S.pid = S.projects[0]?.id;
  const sel = $("#projectSelect");
  sel.innerHTML = S.projects.map(p => `<option value="${p.id}">${esc(shortName(p.name))}</option>`).join("");
  sel.value = S.pid; sel.onchange = () => selectProject(sel.value);
  setupSearch(); refreshChrome(); route();
}
function selectProject(pid) { S.pid = pid; localStorage.setItem("pid", pid); $("#projectSelect").value = pid; invalidate(); refreshChrome(); route(); }
async function refreshChrome() {
  const p = cur();
  $("#runInfo").textContent = p?.latest_run ? `Run ${p.latest_run}` : "Not processed";
  try { const q = await cached("review", () => api(P("/review"))); const n = q.filter(i => i.decision.state === "Open").length; $("#reviewBadge").textContent = n || ""; } catch (e) { $("#reviewBadge").textContent = ""; }
  try { const r = await cached("rules", () => api("/api/rules")); const n = r.filter(x => x.status !== "CONFIRMED").length; $("#rulesBadge").textContent = n || ""; $("#rulesBadge").classList.toggle("alert", n > 0); } catch (e) { }
}

/* ================= EXECUTIVE DASHBOARD ================= */
async function home(main) {
  setCrumb("Workspace", "Dashboard");
  const d = await api("/api/ceo");
  const live = d.projects.filter(p => p.processed);
  const sum = k => live.reduce((a, p) => a + (p[k] || 0), 0);
  const pend = d.rules.total - (d.rules.by_status.CONFIRMED || 0);
  const disp = p => { const c = {}; Object.entries(p.items_by_status || {}).forEach(([k, v]) => { const s = RAW2DS[k] || k; c[s] = (c[s] || 0) + v; }); return c; };
  const status = p => !p.processed ? ["Not processed", "b-outline"] : p.critical_review_items || p.items_needing_review ? ["In review", "b-warning"] : ["Ready", "b-success"];
  const att = d.attention || [];
  main.innerHTML = pageHead("Static Group Project Intelligence", "Automated Quantity Takeoff, BOQ &amp; Project Intelligence", `<a class="btn sec" href="#/report">${icon("report")}Daily report</a><a class="btn" href="#/assistant">${icon("assistant")}Ask the assistant</a>`) + `
  <div class="grid g5">
    ${kpi("Projects", d.projects.length, `${live.length} processed`, { href: "#/projects" })}
    ${kpi("BOQ lines", n0(sum("boq_items")), `${live.reduce((x, p) => x + (p.readiness?.final || 0), 0)} calculated / estimated · ${live.reduce((x, p) => x + (p.readiness?.lump_excluded || 0), 0)} lump sum / excluded (no measurement)`)}
    ${kpi("Items requiring review", n0(sum("items_needing_review")), "Candidate quantities, missing dimensions and unresolved methodology decisions", { cls: "accent-warning" })}
    ${kpi("Missing information", n0(sum("items_missing_input")), "lines without required inputs", { cls: "accent-error" })}
    ${kpi("Pending rules", pend, `${d.rules.by_status.CONFIRMED || 0} confirmed · ${d.rules.by_status.INFERRED || 0} inferred · ${d.rules.by_status.ASSUMED || 0} assumed · ${d.rules.by_status.UNKNOWN || 0} unknown · ${d.rules.reviewed || 0} reviewed`, { href: "#/rules" })}
  </div>
  <div class="split" style="margin-top:20px">
    <div class="card flush"><div class="card-head"><h3>Project overview</h3><a class="small" href="#/projects">All projects →</a></div>
      <div class="tablewrap" style="max-height:none"><table><thead><tr><th scope="col">Project</th><th scope="col">Status</th><th class="num" scope="col">Drawings</th><th scope="col" style="min-width:140px">BOQ progress</th><th class="num" scope="col">Review items</th><th scope="col">Last processed</th></tr></thead><tbody>
      ${d.projects.map(p => { const c = disp(p); const [st, cls] = status(p); const pr = S.projects.find(x => x.id === p.id) || {};
        return `<tr class="click" tabindex="0" data-pid="${p.id}"><td><b>${esc(shortName(p.name))}</b><div class="small">${pr.historical_boq ? "Reference project · historical BOQ" : esc((p.role || "").split(" (")[0].replace(/^./, c => c.toUpperCase()))}</div></td><td><span class="badge ${cls}">${st}</span></td>
        <td class="num">${pr.counts ? n0(pr.counts.drawings) : "—"}</td>
        <td>${p.processed ? `${stackBar(c, DSC, true)}<div class="small">${p.boq_items} lines · ${(c["Needs Review"] || 0)} review · ${(c["Missing"] || 0)} missing</div>` : '<span class="small">—</span>'}</td>
        <td class="num">${p.processed ? `${n0(p.open_review_items)}<div class="small">${p.critical_review_items} critical</div>` : "—"}</td>
        <td class="small" style="white-space:nowrap" title="${esc(fmtIso(p.finished))}">${p.finished ? fmtIso(p.finished).split(",")[0] : "—"}</td></tr>`; }).join("")}
      </tbody></table></div>
      <div class="card-body" style="border-top:1px solid var(--border)">${legend(Object.fromEntries(Object.keys(DS).map(k => [k, live.reduce((a, p) => a + (disp(p)[k] || 0), 0)])), DSC)}</div></div>
    <div class="card flush"><div class="card-head"><h3>Attention required</h3><span class="small">${att.length} items · most important first</span></div>
      <div id="attn">${att.slice(0, 9).map(a => `<div class="attn" tabindex="0" data-url="${esc(a.url)}" data-pid="${esc(a.pid || "")}"><span class="sev" style="background:${SEV[a.severity][0]}"></span><div style="flex:1;min-width:0"><div class="t">${esc(a.title)}</div><div class="d">${esc(a.detail)}</div></div>${a.project ? `<span class="proj">${esc(shortName(a.project))}</span>` : ""}</div>`).join("") || `<div class="empty">Nothing needs attention.</div>`}</div>
      ${att.length > 9 ? `<div class="card-body" style="border-top:1px solid var(--border)"><button class="ghost small" id="attmore">Show ${att.length - 9} more</button></div>` : ""}</div>
  </div>
  ${readinessCard(live, pend)}
  <div class="banner info" style="margin-top:20px">${icon("info")}<div>Every figure on this page is read from stored processing runs, review queues, benchmarks and methodology rules. ${esc(d.not_measured.join(" "))} Assistant mode: <b>${esc(d.ai_mode)}</b>.</div></div>`;
  $$("tr[data-pid]").forEach(tr => { const go = () => { selectProjectQuiet(tr.dataset.pid); location.hash = "#/project/overview"; }; tr.onclick = go; tr.onkeydown = e => e.key === "Enter" && go(); });
  const bindAttn = () => $$(".attn").forEach(el => { const go = () => { if (el.dataset.pid) selectProjectQuiet(el.dataset.pid); location.hash = el.dataset.url; }; el.onclick = go; el.onkeydown = e => e.key === "Enter" && go(); });
  bindAttn();
  if ($("#attmore")) $("#attmore").onclick = () => { $("#attn").innerHTML = att.map(a => `<div class="attn" tabindex="0" data-url="${esc(a.url)}" data-pid="${esc(a.pid || "")}"><span class="sev" style="background:${SEV[a.severity][0]}"></span><div style="flex:1;min-width:0"><div class="t">${esc(a.title)}</div><div class="d">${esc(a.detail)}</div></div>${a.project ? `<span class="proj">${esc(shortName(a.project))}</span>` : ""}</div>`).join(""); $("#attmore").parentElement.remove(); bindAttn(); };
}
const RD = [["final", "Calculated / Estimated", "#1d7048", "Quantity with an approved (Calculated) or inferred / assumed (Estimated) rule"], ["lump_excluded", "Lump Sum / Excluded", "#9aa1a9", "No measurement required"],
  ["measured_review", "Measured, needs review", "#c98a1a", "A measured value exists but needs validation (e.g. elements missing a dimension)"],
  ["candidates", "Candidate quantities", "#2b5a8a", "One quantity per option - the methodology rule is not yet approved"], ["not_automated", "No quantity yet", "#d9c08a", "Needs review: extraction not automated or incomplete"], ["missing", "Missing information", "#b42318", "Required project input or drawing data is absent"]];
function readinessCard(live, pend) {
  const withR = live.filter(p => p.readiness);
  if (!withR.length) return "";
  const tot = k => withR.reduce((a, p) => a + (p.readiness[k] || 0), 0);
  const colors = Object.fromEntries(RD.map(([k, , c]) => [k, c]));
  return `<div class="card flush" style="margin-top:20px"><div class="card-head"><div><h3>Automation readiness</h3><div class="small">Why quantities are not final yet — current BOQ line states from the latest runs. This is not an accuracy measure.</div></div>
    <a class="btn sec small" href="#/rules">${icon("rules")}${pend} methodology decisions pending</a></div>
    <div class="tablewrap" style="max-height:none;border:0;border-radius:0"><table><thead><tr><th>Project</th>${RD.map(([, l, c]) => `<th class="num"><span class="dot-s" style="background:${c}"></span>${l}</th>`).join("")}<th class="num">Lines</th></tr></thead><tbody>
    ${withR.map(p => `<tr><td><b>${esc(shortName(p.name))}</b><div style="max-width:220px">${stackBar(p.readiness, colors, true)}</div></td>${RD.map(([k]) => `<td class="num">${p.readiness[k]}</td>`).join("")}<td class="num"><b>${p.boq_items}</b></td></tr>`).join("")}
    <tr><td><b>All projects</b></td>${RD.map(([k]) => `<td class="num"><b>${tot(k)}</b></td>`).join("")}<td class="num"><b>${withR.reduce((a, p) => a + p.boq_items, 0)}</b></td></tr></tbody></table></div>
    <div class="card-body small" style="border-top:1px solid var(--border)">Lines carrying candidate quantities in total: ${withR.map(p => `${esc(shortName(p.name))} ${p.readiness.lines_with_candidates}`).join(" · ")} (includes ${tot("missing_with_candidates")} Missing lines whose candidates also need an input, e.g. ground level). Lines become Estimated or Calculated only when their methodology rule is approved and required inputs are provided.</div></div>`;
}
function selectProjectQuiet(pid) { if (pid && pid !== S.pid) { S.pid = pid; localStorage.setItem("pid", pid); $("#projectSelect").value = pid; invalidate(); refreshChrome(); } }

/* ================= PROJECTS ================= */
async function projects(main) {
  setCrumb("Workspace", "Projects");
  const d = await api("/api/ceo");
  const by = Object.fromEntries(d.projects.map(p => [p.id, p]));
  const archived = await api("/api/projects-archived").catch(() => []);
  main.innerHTML = pageHead("Projects", "Reference projects with Static Group's historical BOQs, and new projects processed from their own drawings.", `<a class="btn" href="#/newproject">${icon("plus")}New project</a>`) +
    `<div class="grid g3">${S.projects.map(p => { const s = by[p.id] || {}; const c = {}; Object.entries(s.items_by_status || {}).forEach(([k, v]) => { const x = RAW2DS[k] || k; c[x] = (c[x] || 0) + v; });
      return `<div class="card" style="display:flex;flex-direction:column;gap:12px">
        <div class="row" style="align-items:flex-start"><div style="flex:1;min-width:0"><div class="eyebrow">${p.historical_boq ? "Reference project" : esc(p.role || "Project")}</div><h3 style="margin:0;font-size:15px">${esc(shortName(p.name))}</h3><div class="small" title="${esc(p.name)}">${esc(p.name)}</div></div>
        ${p.latest_run ? '<span class="badge b-warning">In review</span>' : '<span class="badge b-outline">Not processed</span>'}</div>
        <div class="kv tight small"><div>Drawings</div><div>${p.counts ? `${n0(p.counts.drawings)} (${p.counts.processed} measured)` : "—"}</div><div>Elements</div><div>${p.counts ? n0(p.counts.elements) : "—"}</div>
        <div>BOQ lines</div><div>${s.boq_items ?? "—"}</div><div>Historical BOQ</div><div>${p.historical_boq ? "Available — benchmarked" : "None"}</div><div>Last processed</div><div>${fmtRun(p.latest_run)}</div></div>
        ${s.processed ? stackBar(c, DSC, true) : ""}
        <div class="row" style="margin-top:auto"><button class="sec small" data-open="${p.id}">Open project ${icon("arrow")}</button><button class="ghost small" data-proc="${p.id}">${icon("play")}Process</button>${p.historical_boq || p.id === "ramzi-villa" ? "" : `<span class="spacer"></span><button class="ghost small" data-arch="${p.id}" title="Hide from KPIs, reports and the assistant (reversible; data kept)">Archive</button>`}</div></div>`; }).join("")}</div>${archived.length ? `<details style="margin-top:20px"><summary>Archived projects (${archived.length}) — excluded from KPIs, reports and the assistant</summary>${archived.map(a => `<div class="row small" style="margin-top:8px"><b>${esc(a.name)}</b><span>archived ${fmtIso(a.archived_at)} by ${esc(a.archived_by || "")} — ${esc(a.archived_reason || "")}</span><button class="ghost small" data-restore="${a.id}">Restore</button></div>`).join("")}</details>` : ""}`;
  $$("[data-open]").forEach(b => b.onclick = () => { selectProjectQuiet(b.dataset.open); location.hash = "#/project/overview"; });
  $$("[data-proc]").forEach(b => b.onclick = () => { selectProjectQuiet(b.dataset.proc); location.hash = "#/processing"; });
  $$("[data-arch]").forEach(b => b.onclick = async () => { const pr = S.projects.find(x => x.id === b.dataset.arch);
    if (!(await confirmDialog(`Archive “${pr.name}”?`, "It is hidden from KPIs, reports, the daily report and the assistant. Its data stays on disk and it can be restored. The action is audited.", "Archive"))) return;
    await api(`/api/projects/${pr.id}/archive`, { method: "POST", body: { archived: true, reason: pr.latest_run ? "Archived by user" : "Test / non-production project (no drawings processed)" } }); toast("Project archived"); if (S.pid === pr.id) S.pid = null; await init(); location.hash = "#/projects"; });
  $$("[data-restore]").forEach(b => b.onclick = async () => { await api(`/api/projects/${b.dataset.restore}/archive`, { method: "POST", body: { archived: false } }); toast("Project restored"); await init(); location.hash = "#/projects"; });
}

/* ================= PROJECT WORKSPACE ================= */
const PTABS = [["overview", "Overview"], ["boq", "BOQ"], ["drawings", "Drawings"], ["elements", "Elements"], ["reviews", "Reviews"], ["changes", "Changes"], ["inputs", "Inputs"], ["validation", "Validation"], ["clientboq", "Client BOQ"], ["pilot", "Pilot"], ["audit", "Audit"]];
const PTAB_FN = { overview: projOverview, boq: sboq, drawings, elements, takeoff, reviews: review, changes, inputs, clientboq: boq, variance, validation: liveTab, pilot: pilotTab, audit: reports };
async function project(main, tab = "overview", params = {}) {
  tab = PTAB_FN[tab] ? tab : "overview";
  const p = cur();
  const label = (PTABS.find(t => t[0] === tab) || [0, tab === "takeoff" ? "Quantity takeoff" : tab === "variance" ? "Variance analysis" : tab])[1];
  setCrumb("Projects", shortName(p.name), label);
  const processed = !!p.latest_run;
  main.innerHTML = `<div class="page-head" style="margin-bottom:6px"><div style="min-width:0"><div class="eyebrow">${p.historical_boq ? "Reference project" : esc(p.role || "Project")}</div>
    <h1 class="page-title">${esc(p.name)}</h1>
    <div class="row wrap" style="margin-top:8px">${processed ? '<span class="badge b-warning">In review</span>' : '<span class="badge b-outline">Not processed</span>'}<span class="small">Last processed ${fmtRun(p.latest_run)}</span>${p.counts ? `<span class="small">· ${n0(p.counts.drawings)} drawings · ${n0(p.counts.elements)} elements</span>` : ""}</div></div>
    <div class="row wrap"><a class="btn sec" href="#/processing">${icon("play")}Process</a><a class="btn sec" href="#/project/reviews">${icon("review")}Review</a><a class="btn sec" href="#/project/boq">${icon("boq")}Generate BOQ</a>${processed ? `<button class="btn sec" id="hdpv">${icon("eye")}Preview BOQ</button><a class="btn" href="${P("/export/static-boq")}">${icon("export")}Export BOQ</a>` : ""}</div></div>
    <nav class="tabs" aria-label="Project sections">${PTABS.map(([k, l]) => `<a href="#/project/${k}" class="${k === tab || (tab === "takeoff" && k === "elements") || (tab === "variance" && k === "clientboq") ? "on" : ""}">${l}</a>`).join("")}</nav><div id="tabbody">${skeleton(2)}</div>`;
  if ($("#hdpv")) $("#hdpv").onclick = previewStaticBoq;
  const body = $("#tabbody");
  if (!processed && !["inputs", "audit"].includes(tab)) { body.innerHTML = emptyState("play", "This project has not been processed yet", "Upload or point to the project's drawings, then run processing to extract elements and calculate quantities.", `<a class="btn" href="#/processing">${icon("play")}Process drawings</a> <a class="btn sec" href="#/newproject">Upload documents</a>`); return; }
  try { await PTAB_FN[tab](body, undefined, params); }
  catch (e) { body.innerHTML = String(e.message).includes("not been processed") ? emptyState("play", "Not processed yet", "Run processing first.", `<a class="btn" href="#/processing">Process drawings</a>`) : emptyState("alert", "Could not load this section", esc(e.message)); }
}

async function projOverview(main) {
  const [d, b] = await Promise.all([cached("dash", () => api(P("/dashboard"))), cached("sboq", () => api(P("/static-boq")))]);
  const sm = b.available ? b.summary : {};
  const final = (sm.Calculated || 0) + (sm.Estimated || 0);
  const sections = {};
  (b.lines || []).filter(l => !l.is_group_header).forEach(l => { const k = l.section_title || l.section; (sections[k] = sections[k] || {})[l.display_status] = ((sections[k] || {})[l.display_status] || 0) + 1; });
  const typeRows = Object.entries(d.quantities.by_type).map(([k, v]) => [`${TYPES[k] || k} (${v.count})`, v.quantity]);
  main.innerHTML = `<div class="grid g4">
    ${kpi("Drawings", n0(d.drawings.total), `${d.drawings.processed} measured · ${d.drawings.inventoried} inventoried · ${d.drawings.failed} failed`, { href: "#/project/drawings" })}
    ${kpi("Elements detected", n0(d.elements.total), Object.entries(d.elements.by_type).map(([k, v]) => `${v} ${(TYPES[k] || k).toLowerCase()}`).join(" · "), { href: "#/project/elements" })}
    ${kpi("BOQ lines", (b.lines || []).filter(l => !l.is_group_header).length, `${final} with a final quantity · ${(sm["Lump Sum"] || 0) + (sm.Excluded || 0)} lump sum / excluded`, { href: "#/project/boq" })}
    ${kpi("Open review items", n0(d.review.open), `${d.review.by_impact["Review Required"] || 0} need a decision · ${d.review.by_impact["Missing Data"] || 0} missing data`, { href: "#/project/reviews" })}
  </div>
  <div class="card" style="margin-top:16px"><div class="row" style="margin-bottom:6px"><h3 style="margin:0">BOQ status</h3><span class="spacer"></span><span class="small">Lines move to Estimated or Calculated as rules are approved and inputs provided</span></div>
    <div class="grid g5" style="margin:10px 0 14px">${["Calculated", "Estimated", "Needs Review", "Missing"].map(k => `<div><div class="small"><span class="dot-s" style="background:${DSC[k]}"></span>${k}</div><div style="font-size:22px;font-weight:600">${sm[k] || 0}</div></div>`).join("")}<div><div class="small"><span class="dot-s" style="background:${DSC["Lump Sum"]}"></span>Lump Sum / Excluded</div><div style="font-size:22px;font-weight:600">${(sm["Lump Sum"] || 0) + (sm.Excluded || 0)}</div></div></div>
    ${stackBar(sm, DSC)}</div>
  <div class="grid g2" style="margin-top:16px">
    <div class="card"><h3>BOQ status by section</h3>${Object.entries(sections).map(([k, c]) => `<div style="margin:10px 0"><div class="row small"><span style="color:var(--text-primary)">${esc(k)}</span><span class="spacer"></span>${Object.values(c).reduce((a, x) => a + x, 0)} lines</div>${stackBar(c, DSC, true)}</div>`).join("")}</div>
    <div class="stackv"><div class="card"><h3>Calculated concrete by element type</h3>${bars(typeRows, n2, "m³")}<div class="small" style="margin-top:8px">Element-level measurement: ${n2(d.quantities.total_concrete_m3)} m³ concrete + ${n2(d.quantities.total_blinding_m3)} m³ blinding from ${d.quantities.quantified} of ${d.quantities.quantified + d.quantities.not_quantified} elements (the rest lack a dimension and are never guessed).</div></div>
    <div class="card"><h3>Storey heights used</h3><table class="plain"><thead><tr><th>Floor</th><th class="num">Height</th><th>Status</th></tr></thead><tbody>${Object.entries(d.storey_heights).map(([k, s]) => `<tr><td>${esc(k)}</td><td class="num">${s.height == null ? "—" : n3(s.height) + " m"}</td><td>${s.height == null ? badge("Missing Data") : s.confirmed ? badge("OK") : badge("Check")}</td></tr>`).join("")}</tbody></table><div class="small" style="margin-top:8px">Derived from level tags; confirm in <a href="#/settings">Settings</a>.</div></div></div>
  </div>`;
}

/* ================= STATIC GROUP BOQ ================= */
async function sboq(main) {
  const b = await cached("sboq", () => api(P("/static-boq")));
  if (!b.available) { main.innerHTML = emptyState("boq", "BOQ not available", esc(b.reason), `<a class="btn" href="#/processing">Reprocess project</a>`); return; }
  const lines = b.lines, sm = b.summary;
  let filt = "", q = "";
  const lineCount = lines.filter(l => !l.is_group_header).length;
  const opts = [["", "All", lineCount], ...["Calculated", "Estimated", "Needs Review", "Missing"].map(k => [k, k, sm[k] || 0]), ["LSX", "Lump Sum / Excluded", (sm["Lump Sum"] || 0) + (sm.Excluded || 0)]];
  main.innerHTML = `<div class="card" style="margin-bottom:14px"><div class="row wrap"><div style="flex:1;min-width:280px">${stackBar(sm, DSC)}${legend(sm, DSC)}</div>
    <div class="row"><a class="btn sec" href="#/rules">${icon("rules")}Resolve rules</a><a class="btn sec" href="#/project/inputs">${icon("inputs")}Enter inputs</a><button class="sec" id="bqpv">${icon("eye")}Preview</button><a class="btn sec" href="${P("/export/tender-pdf")}" title="Client-ready PDF — same sheets and numbering as the Excel export, Rate/Amount left for Static Group to price">${icon("doc")}Tender PDF</a><a class="btn" href="${P("/export/static-boq")}">${icon("export")}Export Excel</a></div></div></div>
  ${(b.new_items || []).length ? `<div class="banner warn">${icon("alert")}<div><b>${b.new_items.length} new BOQ items detected</b> in the client BOQ that match no Static Group knowledge-model item. <a href="#" id="shownew">Review them</a>.</div></div>` : ""}
  <div class="toolbar">${seg("bf", opts, "")}<span class="spacer"></span><div class="search">${icon("search")}<input id="bq" placeholder="Filter by code or description" style="width:260px" aria-label="Filter BOQ lines"></div></div>
  <div class="tablewrap" style="max-height:calc(100vh - 330px)"><table id="sbt"><thead><tr><th scope="col">Code</th><th scope="col">Description</th><th scope="col">Unit</th><th class="num" scope="col">Quantity</th><th scope="col">Status</th><th class="num" scope="col">Confidence</th><th scope="col">Source</th><th scope="col">Review</th></tr></thead><tbody></tbody></table></div>
  <div class="small" style="margin-top:10px">Calculated = rule confirmed · Estimated = inferred or assumed rule · Needs Review = rule undecided (candidates shown) or value to validate · Missing = input or drawing data absent. Select a line to see its calculation evidence.</div>`;
  const draw = () => {
    // "code" (1, 1.1, 2 ...) matches Static Group's own numbering and resets per section, so it repeats
    // across the BOQ by design - "key" (item_id + variant) is what's unique and used for lookups.
    const rows = lines.filter(l => l.is_group_header || ((!filt || (filt === "LSX" ? ["Lump Sum", "Excluded"].includes(l.display_status) : l.display_status === filt)) && (!q || (l.code + " " + l.description + " " + l.variant).toLowerCase().includes(q))));
    let sec = null, html = "";
    rows.forEach(l => {
      const st = l.subsection_title || l.section_title;
      if (st !== sec) { sec = st; html += `<tr class="group"><td colspan="8">${esc(l.section)} · ${esc(l.section_title)}${l.subsection_title ? ` <span class="small">/ ${esc(l.subsection_title)}</span>` : ""}</td></tr>`; }
      if (l.is_group_header) { html += `<tr class="group"><td colspan="8" style="padding-left:28px">${esc(l.code)} · ${esc(l.description)}</td></tr>`; return; }
      const nc = Object.values(l.candidates || {}).filter(v => v != null).length;
      html += `<tr class="click" tabindex="0" data-key="${esc(l.key)}"><td class="mono">${esc(l.code)}</td><td>${esc(l.description)}${l.variant && !l.description.includes(l.variant) ? ` <span class="small">${esc(l.variant)}</span>` : ""}</td><td>${esc(UNIT(l.unit))}</td>
        <td class="num">${l.quantity != null ? `<b>${n2(l.quantity)}</b>` : nc ? `<span class="small">${nc} candidate${nc > 1 ? "s" : ""}</span>` : '<span class="small">—</span>'}</td><td>${dsBadge(l.display_status)}</td>
        <td class="num">${l.confidence != null ? Math.round(l.confidence * 100) + " %" : '<span class="small">—</span>'}</td><td class="small" style="max-width:280px">${esc((l.source || "").split(";")[0]).slice(0, 80)}</td><td>${l.review_status === "Open" ? '<span class="badge b-outline plain">Open</span>' : '<span class="small">—</span>'}</td></tr>`;
    });
    $("#sbt tbody").innerHTML = html || `<tr><td colspan="8" class="empty">No BOQ lines match this filter</td></tr>`;
    $$("#sbt tr[data-key]").forEach(tr => { const go = () => { $$("#sbt tr.sel").forEach(x => x.classList.remove("sel")); tr.classList.add("sel"); boqLineDetail(lines.find(l => l.key === tr.dataset.key)); }; tr.onclick = go; tr.onkeydown = e => e.key === "Enter" && go(); });
  };
  bindSeg("bf", v => { filt = v; draw(); });
  $("#bq").oninput = e => { q = e.target.value.toLowerCase(); draw(); };
  $("#bqpv").onclick = previewStaticBoq;
  if ($("#shownew")) $("#shownew").onclick = e => { e.preventDefault(); openSheet(`<div class="sheet-head"><div class="eyebrow">Client BOQ</div><h2>New BOQ items detected</h2><div class="small">These lines match no item of the Static Group knowledge model. An estimator should create a model item and rule for each.</div></div>${table([{ k: "row", t: "Row" }, { k: "description", t: "Description" }, { k: "unit", t: "Unit" }, { t: "Qty", num: 1, f: x => n3(x.quantity) }], b.new_items)}`, true); };
  draw();
}
async function boqLineDetail(l) {
  openSheet(`<div class="sheet-head"><div class="eyebrow">${esc(l.code)} · ${esc(l.subsection_title || l.section_title)}</div><h2>${esc(l.description)}</h2></div>${skeleton(1)}`, true);
  const [items, els] = await Promise.all([cached("items", () => api(P("/items"))), cached("elements", () => api(P("/elements")))]);
  const it = items.find(i => i.item_id === l.item_id && (i.variant || "") === (l.variant || "")) || {};
  const byUid = Object.fromEntries(els.map(e => [e.uid, e]));
  const myEls = (it.element_uids || []).map(u => byUid[u]).filter(Boolean).sort((a, b) => (a.quantity == null ? 0 : 1) - (b.quantity == null ? 0 : 1));
  const cands = Object.entries(it.candidates || l.candidates || {}).filter(([k, v]) => v != null);
  const inputs = Object.entries(it.inputs || {}).filter(([k, v]) => v !== null && typeof v !== "object");
  const reasons = [...(l.missing || []), ...(it.rules || []).filter(r => r.selected == null).map(r => `Methodology rule "${r.title}" is ${r.status} — no option approved`)];
  $("#drawerBody").innerHTML = `<div class="sheet-head"><div class="eyebrow">${esc(l.code)} · ${esc(l.subsection_title || l.section_title)}</div><h2>${esc(l.description)}</h2>
    <div class="row wrap" style="margin-top:8px">${dsBadge(l.display_status)}<span class="small">${esc(l.calculation_status)}</span>${l.review_status === "Open" ? '<span class="badge b-outline plain">Review open</span>' : ""}</div></div>
  <div class="sheet-section"><div class="qty-hero"><div><div class="small">Quantity</div><div class="v">${l.quantity != null ? n2(l.quantity) : "—"}<span class="u">${esc(UNIT(l.unit))}</span></div></div>
    <div><div class="small">Confidence</div><div style="font-size:18px;font-weight:600">${l.confidence != null ? Math.round(l.confidence * 100) + " %" : "—"}</div></div>
    <div><div class="small">Item</div><div class="mono">${esc(l.item_id)}${l.variant ? " · " + esc(l.variant) : ""}</div></div></div>
    ${l.quantity == null ? `<div class="small" style="margin-top:10px">${cands.length ? "No quantity is final: the governing methodology rule has not been approved. Candidate quantities per option are listed below." : "No quantity: required information is missing (see reasons)."}</div>` : ""}</div>
  ${cands.length ? `<div class="sheet-section"><h4>Candidate quantities (one per methodology option)</h4><table class="plain"><tbody>${cands.map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num"><b>${n2(v)}</b> ${esc(UNIT(l.unit))}</td></tr>`).join("")}</tbody></table></div>` : ""}
  ${reasons.length ? `<div class="sheet-section"><h4>Reason</h4>${reasons.map(r => `<div class="flag ${r.startsWith("Methodology") ? "info" : "Missing"}">${esc(r)}</div>`).join("")}</div>` : ""}
  <div class="sheet-section"><h4>Calculation evidence</h4><div class="kv tight">
    <div>Formula</div><div class="mono">${esc(it.formula || "—")}</div>
    ${(it.rules || []).map(r => `<div>Rule</div><div>${ruleBadge(r.status)} ${esc(r.title)} <span class="small">· ${r.selected ? "option " + esc(r.selected) : "no option approved"}</span> <a class="small" href="#/rules" onclick="closeDrawer()">open</a></div>`).join("")}
    ${inputs.map(([k, v]) => `<div>${esc(k.replace(/_/g, " "))}</div><div>${typeof v === "number" ? n3(v) : esc(v)}</div>`).join("")}
    <div>Source</div><div>${(it.evidence || [l.source]).map(e => esc(e)).join("<br>")}</div></div></div>
  ${myEls.length ? `<div class="sheet-section"><h4>Measured elements (${myEls.length})</h4>${myEls.slice(0, 25).map(e => `<div class="ev-el"><div><b>${esc(e.mark || "unidentified")}</b> <span class="small">${esc(TYPES[e.element_type] || e.element_type)} · ${esc(e.floor)}</span><div class="small">${dimsShort(e)} m · ${esc(e.formula || "")}</div><div class="small">${esc(e.drawing)} · ${esc(e.layer)}</div></div>
      <div style="text-align:right"><div class="tnum"><b>${e.quantity == null ? "n/a" : n3(e.quantity)}</b> ${esc(UNIT(e.unit))}</div><div class="row" style="justify-content:flex-end;margin-top:4px"><a class="btn ghost small" href="#/viewer/${e.drawing_id}?el=${encodeURIComponent(e.uid)}" onclick="closeDrawer()" title="Open the drawing and highlight this element">${icon("locate")}Drawing</a><button class="ghost small" data-ev="${esc(e.uid)}">${icon("eye")}Evidence</button></div></div></div>`).join("")}
    ${myEls.length > 25 ? `<div class="small">+ ${myEls.length - 25} more elements</div>` : ""}</div>` : ""}`;
  $$("[data-ev]").forEach(bn => bn.onclick = () => openEvidence(bn.dataset.ev, () => boqLineDetail(l)));
}

async function previewStaticBoq() {
  openSheet(`<div class="sheet-head"><div class="eyebrow">Preview</div><h2>BOQ preview — Static Group format</h2></div>${skeleton(1)}`);
  const b = await api(P("/static-boq/preview"));
  if (!b.available) { $("#drawerBody").innerHTML = emptyState("boq", "Preview not available", esc(b.reason)); return; }
  const tabs = [...b.sheet_order, "Summary"];
  let tab = tabs[0];
  const rowsFor = sh => {
    if (sh === "Summary") {
      return b.summary.map(s => `<tr class="group"><td class="mono">${esc(s.code)}</td><td colspan="4">${esc(s.title)}</td><td class="num small">—</td></tr>`).join("")
        || `<tr><td colspan="6" class="empty">No sections to carry to Summary yet</td></tr>`;
    }
    const rows = b.sheets[sh] || [];
    if (!rows.length) return `<tr><td colspan="6" class="empty">No lines in this sheet</td></tr>`;
    return rows.map(r => {
      if (r.row === "section" || r.row === "subsection") return `<tr class="group"><td class="mono">${esc(r.code)}</td><td colspan="5">${esc(r.title)}</td></tr>`;
      if (r.row === "group") return `<tr class="group"><td class="mono" style="padding-left:24px">${esc(r.code)}</td><td colspan="5">${esc(r.title)}</td></tr>`;
      if (r.row === "subtotal") return `<tr class="boq-total"><td></td><td colspan="4">TOTAL CARRIED TO SUMMARY</td><td class="num">—</td></tr>`;
      const sug = r.suggested_rate != null;
      const rateCell = sug ? `<span style="color:#946F00;font-style:italic" title="Suggested from rate memory — ${esc(r.suggested_rate_source || "a past priced BOQ")}. Not confirmed.">${n2(r.suggested_rate)}*</span>` : "—";
      const amtCell = sug && r.quantity != null ? `<span style="color:#946F00;font-style:italic">${n2(r.suggested_rate * r.quantity)}*</span>` : "—";
      return `<tr><td class="mono">${esc(r.code)}</td><td>${esc(r.description)}</td><td class="num">${r.quantity != null ? n2(r.quantity) : "—"}</td><td>${esc(UNIT(r.unit))}</td><td class="num small">${rateCell}</td><td class="num small">${amtCell}</td></tr>`;
    }).join("");
  };
  const draw = () => {
    const hasSug = Object.values(b.sheets).some(rows => rows.some(r => r.suggested_rate != null));
    $("#drawerBody").innerHTML = `<div class="sheet-head"><div class="eyebrow">Preview · matches Export Excel exactly</div><h2>${esc(b.title)}</h2><div class="small">RATE and AMOUNT are blank here — Static Group prices them after export${hasSug ? ', except lines marked with <span style="color:#946F00;font-style:italic">amber italics and *</span>, which show a suggested rate from a past priced BOQ (not confirmed)' : ""}. Everything else (sheets, headings, numbering) is exactly what the download will contain.</div></div>
    <div class="kv tight" style="margin-bottom:12px"><div>Project</div><div>${esc(b.project.name)}</div><div>Client</div><div>${esc(b.project.client || "—")}</div><div>Location</div><div>${esc(b.project.location || "—")}</div><div>Ref.No / Date</div><div>${b.boq_meta.ref ? esc(b.boq_meta.ref) : "—"}${b.boq_meta.date ? " · " + esc(b.boq_meta.date) : ""}</div></div>
    <div class="toolbar" style="margin-bottom:8px">${seg("pvtab", tabs.map(s => [s, s]), tab)}</div>
    <div class="tablewrap" style="max-height:420px"><table><thead><tr><th>ITEM</th><th>DESCRIPTION</th><th class="num">QTY</th><th>UNIT</th><th class="num">RATE</th><th class="num">AMOUNT (QR)</th></tr></thead><tbody>${rowsFor(tab)}</tbody></table></div>
    <div class="row" style="margin-top:14px"><a class="btn" href="${P("/export/static-boq")}">${icon("export")}Export Excel</a></div>`;
    bindSeg("pvtab", v => { tab = v; draw(); });
  };
  draw();
}

/* ================= PROCESSING ================= */
let pollH = null;
async function processing(main) {
  const p = cur();
  setCrumb("Projects", shortName(p.name), "Processing");
  const runs = await api(P("/runs")).catch(() => []);
  main.innerHTML = pageHead("Process drawings", esc(p.name), `<a class="btn sec" href="#/project/overview">${icon("back")}Back to project</a>`, "Processing") + `
  <div class="grid g2"><div class="card"><h3>Run processing</h3><div class="kv"><div>Source folder</div><div class="mono">${esc(p.source_folder)}</div><div>Folder found</div><div>${p.folder_exists ? "Yes" : "<b style='color:var(--error)'>No</b>"}</div><div>CAD standard (rules)</div><div class="mono">config/${esc(p.rules_file)}</div></div>
   <div class="toolbar" style="margin-top:14px"><select id="scope" aria-label="Scope"><option value="all">All DXF files (every discipline)</option><option value="structural">Structural drawings only (faster)</option></select>
   <button id="go">${icon("play")}Run processing</button><button class="sec" id="rc">Recalculate from last scan</button></div>
   <p class="small">Every DXF is opened, blocks and xrefs flattened, entities classified with the rules file, schedules and levels read, elements measured and quantities calculated. Progress below is reported by the server as each step completes.</p></div>
   <div class="card"><h3>Previous runs</h3>${runs.length ? table([{ k: "run_id", t: "Run" }, { k: "kind", t: "Kind" }, { t: "Finished", f: r => fmtIso(r.finished) }, { t: "Elements", f: r => r.counts?.elements ?? "", num: 1 }, { t: "Drawings", f: r => r.counts?.drawings ?? "", num: 1 }], runs) : "<div class='empty'>No runs yet</div>"}</div></div>
  <div class="section-title">Processing status</div><div id="stages" class="stages"></div>
  <div class="small" id="fileinfo" style="margin:10px 0"></div><div class="log" id="log" aria-live="polite"></div>`;
  $("#go").onclick = async () => { try { await api(P("/run"), { method: "POST", body: { scope: $("#scope").value } }); toast("Processing started"); poll(); } catch (e) { toast(e.message, 5000, "error"); } };
  $("#rc").onclick = async () => { $("#rc").disabled = true; try { const r = await api(P("/recalc"), { method: "POST" }); invalidate(); toast("Recalculated: run " + r.run_id); S.projects = await api("/api/projects"); refreshChrome(); route(); } catch (e) { toast(e.message, 5000, "error"); $("#rc").disabled = false; } };
  poll();
}
async function poll() {
  clearTimeout(pollH);
  const st = await api(P("/progress"));
  const el = $("#stages"); if (!el) return;
  const stages = st.stages.length ? st.stages : ["Select project", "Load drawings", "Scan DXF files", "Detect layers and elements", "Extract dimensions", "Calculate quantities", "Generate BOQ", "Run validation", "Results"].map(n => ({ name: n, status: "pending", detail: "" }));
  el.innerHTML = stages.map((s, i) => `<div class="stage"><div class="dot ${s.status}"></div><div><b>${i + 1}. ${esc(s.name)}</b></div><div class="small">${s.seconds != null ? s.seconds + " s" : s.status}</div><div class="small">${esc(s.detail)}</div></div>`).join("");
  $("#fileinfo").textContent = st.running && st.file_total ? `Scanning file ${st.file_index} of ${st.file_total}: ${st.current_file}` : (st.error ? "Processing failed: " + st.error : "");
  $("#log").innerHTML = (st.log || []).slice(-120).map(l => `${esc(l.t.slice(11))}  ${esc(l.msg)}`).join("<br>") || "Idle — no processing running.";
  $("#log").scrollTop = 1e9;
  if (st.running) pollH = setTimeout(poll, 800);
  else if (st.run_id && !st._seen) { invalidate(); S.projects = await api("/api/projects"); refreshChrome(); }
}

/* ================= DRAWINGS & VIEWER ================= */
async function drawings(main) {
  const ds = await cached("drawings", () => api(P("/drawings")));
  const disc = [...new Set(ds.map(d => d.discipline))];
  main.innerHTML = `<div class="toolbar"><select id="fd" aria-label="Discipline"><option value="">All disciplines (${ds.length})</option>${disc.map(x => `<option>${esc(x)}</option>`).join("")}</select>
  <label class="small"><input type="checkbox" id="fr"> Only drawings used for quantities</label><span class="spacer"></span><span class="small">Select a drawing to open it in the viewer</span></div><div id="dt"></div>`;
  const draw = () => {
    const f = $("#fd").value, r = $("#fr").checked;
    const rows = ds.filter(d => (!f || d.discipline === f) && (!r || d.status === "processed"));
    $("#dt").innerHTML = table([{ t: "Drawing", f: d => `<b>${esc(d.file)}</b>` , sv: d => d.file }, { k: "discipline", t: "Discipline" }, { t: "Role", f: d => d.role_title ? `<span class="pill">${esc(d.role_title)}</span>` : "<span class='small'>inventory only</span>" },
    { t: "Status", f: d => d.status === "processed" ? '<span class="badge b-success">Measured</span>' : d.status === "error" ? '<span class="badge b-error">Failed</span>' : '<span class="badge b-neutral">Inventoried</span>', sv: d => d.status }, { k: "units", t: "Units" }, { k: "entities", t: "Entities", num: 1 }, { k: "layers", t: "Layers", num: 1 },
    { t: "Elements extracted", f: d => Object.entries(d.elements).map(([k, v]) => `<span class="chip">${v} ${TYPES[k] || k}</span>`).join("") }], rows, { onclick: d => location.hash = `#/viewer/${d.drawing_id}` });
  };
  $("#fd").onchange = draw; $("#fr").onchange = draw; draw();
}
const ACI = { 1: "#c62828", 2: "#a58f00", 3: "#2e7d32", 4: "#00838f", 5: "#1f4fd1", 6: "#8e24aa", 7: "#2b2d31", 8: "#8a8f96", 9: "#b0b4ba" };
const ELC = { footing: "#1f5fa8", raft: "#138496", blinding: "#8a8f1f", column: "#c0392b", wall: "#7b4f2c", beam: "#d4780f", slab: "#2e8b57", pedestal: "#7d4fa8" };
async function viewer(main, did, params) {
  main.innerHTML = `<div class="empty"><span class="spinner dark"></span> Loading drawing geometry — the first open of a large drawing can take a few seconds…</div>`;
  const [info, geo, els] = await Promise.all([api(P(`/drawings/${did}`)), api(P(`/drawings/${did}/geometry`)), api(P(`/elements?drawing_id=${did}`))]);
  setCrumb("Projects", shortName(cur().name), "Drawings", info.file);
  main.innerHTML = `<div class="page-head" style="margin-bottom:12px"><div><div class="eyebrow">Drawing viewer</div><h1 class="page-title">${esc(info.file)}</h1><div class="page-sub">${esc(info.rel_path)} · ${esc(info.meta?.units)} · ${geo.items.length.toLocaleString()} entities${geo.truncated ? " (display truncated)" : ""} · ${els.length} extracted elements</div></div>
    <div class="row"><a class="btn sec" href="#/project/drawings">${icon("back")}All drawings</a></div></div>
    <div class="viewer"><div class="panel"><h4>Display</h4><label class="layer"><input type="checkbox" id="showEl" checked> Extracted elements (${els.length})</label><label class="layer"><input type="checkbox" id="showTx" checked> Text</label>
    <div class="legend" style="margin:8px 0 4px">${[...new Set(els.map(e => e.element_type))].map(t => `<span><i style="background:${ELC[t] || "#000"}"></i>${TYPES[t] || t}</span>`).join("")}</div>
    <h4 style="margin-top:14px">Layers</h4><div class="row" style="margin-bottom:6px"><button class="sec small" id="lAll">All</button><button class="sec small" id="lNone">None</button></div><div id="layers"></div></div>
    <div class="minimap"><canvas id="cv" aria-label="Drawing canvas: scroll to zoom, drag to pan, click an element to select"></canvas>
    <div class="vtools"><button id="fit" title="Fit to screen" aria-label="Fit to screen">${icon("fit")}</button><button id="zin" title="Zoom in" aria-label="Zoom in">${icon("zin")}</button><button id="zout" title="Zoom out" aria-label="Zoom out">${icon("zout")}</button></div><div class="vstatus" id="vst">Scroll to zoom · drag to pan · click an element</div></div>
    <div class="panel" id="vinfo"><h4>Selected element</h4><p class="small">Click a highlighted element on the drawing to see its measurement, or open a drawing from a BOQ line's evidence to locate an element automatically.</p></div></div>`;
  const cv = $("#cv"), ctx = cv.getContext("2d");
  const L = geo.layers.map(l => ({ ...l, on: true }));
  const polys = els.filter(e => e.geometry && e.geometry.length > 2);
  let view = { s: 1, ox: 0, oy: 0 }, sel = params.el || null;
  function resize() { const r = cv.getBoundingClientRect(); cv.width = r.width * devicePixelRatio; cv.height = r.height * devicePixelRatio; }
  function fit(b) { const [x0, y0, x1, y1] = b; const W = cv.width, H = cv.height; view.s = Math.min(W / (x1 - x0 || 1), H / (y1 - y0 || 1)) * 0.92; view.ox = W / 2 - (x0 + x1) / 2 * view.s; view.oy = H / 2 + (y0 + y1) / 2 * view.s; }
  const X = x => x * view.s + view.ox, Y = y => -y * view.s + view.oy;
  let raf = null; const redraw = () => { if (!raf) raf = requestAnimationFrame(() => { raf = null; draw(); }); };
  function draw() {
    if (!document.body.contains(cv)) return;   // page left while a redraw was pending
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, cv.width, cv.height); ctx.lineWidth = 1;
    const showTx = $("#showTx").checked;
    for (const it of geo.items) {
      const l = L[it.l]; if (!l.on) continue;
      ctx.strokeStyle = ACI[l.color] || "#555"; ctx.fillStyle = ctx.strokeStyle;
      if (it.t === "p") { const p = it.p; ctx.beginPath(); ctx.moveTo(X(p[0]), Y(p[1])); for (let i = 2; i < p.length; i += 2) ctx.lineTo(X(p[i]), Y(p[i + 1])); if (it.c) ctx.closePath(); ctx.stroke(); }
      else if (showTx) { const h = it.hgt * view.s; if (h < 4) continue; ctx.save(); ctx.translate(X(it.x), Y(it.y)); ctx.rotate(-it.r * Math.PI / 180); ctx.font = `${h}px Arial`; ctx.textBaseline = it.m ? "top" : "alphabetic"; ctx.fillText(it.s.split("\n")[0], 0, 0); ctx.restore(); }
    }
    if ($("#showEl").checked) for (const e of polys) {
      const rings = [e.geometry, ...(e.extra_rings || [])]; const c = ELC[e.element_type] || "#000"; const on = e.uid === sel;
      for (const g of rings) { ctx.beginPath(); g.forEach((p, i) => i ? ctx.lineTo(X(p[0]), Y(p[1])) : ctx.moveTo(X(p[0]), Y(p[1]))); ctx.closePath();
        ctx.fillStyle = c + (on ? "66" : "26"); ctx.fill(); ctx.strokeStyle = on ? "#111214" : c; ctx.lineWidth = on ? 3 * devicePixelRatio : 1.2; ctx.stroke(); }
      if (on) { const xs = e.geometry.map(p => X(p[0])), ys = e.geometry.map(p => Y(p[1])); const pad = 10 * devicePixelRatio; ctx.setLineDash([6, 4]); ctx.strokeStyle = "#111214"; ctx.lineWidth = 1.5; ctx.strokeRect(Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) - Math.min(...xs) + 2 * pad, Math.max(...ys) - Math.min(...ys) + 2 * pad); ctx.setLineDash([]); }
    }
    if (params.pt) { const [px, py] = params.pt.split(",").map(Number); ctx.strokeStyle = "#b42318"; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(X(px), Y(py), 18, 0, 7); ctx.stroke(); }
    $("#vst").textContent = `Scale ${(view.s / devicePixelRatio).toFixed(1)} px/m${sel ? " · selected " + sel : ""}`;
  }
  function inPoly(x, y, g) { let c = false; for (let i = 0, j = g.length - 1; i < g.length; j = i++) { const [xi, yi] = g[i], [xj, yj] = g[j]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) c = !c; } return c; }
  function area(g) { let a = 0; for (let i = 0, j = g.length - 1; i < g.length; j = i++) a += (g[j][0] + g[i][0]) * (g[j][1] - g[i][1]); return Math.abs(a / 2); }
  function showInfo(uid) {
    sel = uid; redraw(); const e = els.find(x => x.uid === uid); if (!e) return;
    $("#vinfo").innerHTML = `<h4>Selected element</h4><div style="font-size:14px;font-weight:600">${esc(e.description)}</div><div class="small mono">${esc(e.uid)}</div><div style="margin:8px 0">${badge(e.status)}</div>
      <h4 style="margin-top:12px">Measurement</h4><div class="kv tight">${Object.entries(e.dims).map(([k, v]) => `<div>${esc(k.replace(/_/g, " "))}</div><div class="tnum">${v == null ? "<i style='color:var(--error)'>not available</i>" : n3(v)}</div>`).join("")}
      <div>Quantity</div><div><b class="tnum">${n3(e.quantity)} ${esc(UNIT(e.unit))}</b></div><div>Formula</div><div class="mono">${esc(e.formula)}</div><div>Layer</div><div class="mono">${esc(e.layer)}</div><div>Floor</div><div>${esc(e.floor)}</div></div>
      ${e.flags.length ? `<h4 style="margin-top:12px">Flags</h4><div>${e.flags.map(f => `<span class="chip">${esc(f)}</span>`).join("")}</div>` : ""}<div style="margin-top:12px"><button class="small" onclick="openEvidence('${esc(e.uid)}')">${icon("eye")}Full evidence</button></div>`;
  }
  const groups = {}; L.forEach(l => (groups[l.base] = groups[l.base] || []).push(l));
  $("#layers").innerHTML = Object.entries(groups).sort((a, b) => b[1].reduce((s, l) => s + l.n, 0) - a[1].reduce((s, l) => s + l.n, 0)).map(([b, ls]) =>
    `<label class="layer"><input type="checkbox" checked data-b="${esc(b)}"><i style="background:${ACI[ls[0].color] || "#555"}"></i><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(b)}</span><span class="small">${ls.reduce((s, l) => s + l.n, 0)}</span></label>`).join("");
  $("#layers").onchange = ev => { const b = ev.target.dataset.b; L.forEach(l => { if (l.base === b) l.on = ev.target.checked; }); redraw(); };
  $("#lAll").onclick = () => { L.forEach(l => l.on = true); $$("#layers input").forEach(i => i.checked = true); redraw(); };
  $("#lNone").onclick = () => { L.forEach(l => l.on = false); $$("#layers input").forEach(i => i.checked = false); redraw(); };
  $("#showEl").onchange = redraw; $("#showTx").onchange = redraw;
  resize();
  const focus = sel && polys.find(e => e.uid === sel);
  if (focus) { const xs = focus.geometry.map(p => p[0]), ys = focus.geometry.map(p => p[1]); const pad = Math.max(Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys), 2) * 2; fit([Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad]); showInfo(sel); }
  else if (sel) { toast("This element has no outline on this drawing; showing the whole sheet"); fit(geo.bounds); }
  else if (params.pt) { const [px, py] = params.pt.split(",").map(Number); fit([px - 4, py - 4, px + 4, py + 4]); }
  else if (polys.length) { const xs = polys.flatMap(e => e.geometry.map(p => p[0])), ys = polys.flatMap(e => e.geometry.map(p => p[1])); fit([Math.min(...xs) - 2, Math.min(...ys) - 2, Math.max(...xs) + 2, Math.max(...ys) + 2]); }
  else fit(geo.bounds);
  draw();
  $("#fit").onclick = () => { fit(geo.bounds); draw(); };
  const zoom = (f, cx = cv.width / 2, cy = cv.height / 2) => { view.ox = cx - (cx - view.ox) * f; view.oy = cy - (cy - view.oy) * f; view.s *= f; redraw(); };
  $("#zin").onclick = () => zoom(1.4); $("#zout").onclick = () => zoom(1 / 1.4);
  cv.onwheel = ev => { ev.preventDefault(); const r = cv.getBoundingClientRect(); zoom(ev.deltaY < 0 ? 1.2 : 1 / 1.2, (ev.clientX - r.left) * devicePixelRatio, (ev.clientY - r.top) * devicePixelRatio); };
  let drag = null;
  cv.onmousedown = ev => { drag = { x: ev.clientX, y: ev.clientY, ox: view.ox, oy: view.oy, moved: false }; cv.style.cursor = "grabbing"; };
  window.onmouseup = ev => {
    if (!drag) return; cv.style.cursor = "grab";
    if (!drag.moved && ev.target === cv) {
      const r = cv.getBoundingClientRect(); const wx = ((ev.clientX - r.left) * devicePixelRatio - view.ox) / view.s, wy = -((ev.clientY - r.top) * devicePixelRatio - view.oy) / view.s;
      const hits = polys.filter(e => [e.geometry, ...(e.extra_rings || [])].some(g => inPoly(wx, wy, g))).sort((a, b) => area(a.geometry) - area(b.geometry));
      if (hits.length) showInfo(hits[0].uid);
    }
    drag = null;
  };
  window.onmousemove = ev => { if (!drag) return; const dx = (ev.clientX - drag.x) * devicePixelRatio, dy = (ev.clientY - drag.y) * devicePixelRatio; if (Math.abs(dx) + Math.abs(dy) > 3) drag.moved = true; view.ox = drag.ox + dx; view.oy = drag.oy + dy; redraw(); };
  window.onresize = () => { if (!document.body.contains(cv)) return; resize(); redraw(); };
}

/* ================= ELEMENTS & TAKEOFF ================= */
const elSwitch = on => `<div class="toolbar">${seg("elsw", [["elements", "Element list"], ["takeoff", "Quantity takeoff"]], on)}</div>`;
async function elements(main, arg, params = {}) {
  const els = await cached("elements", () => api(P("/elements")));
  main.innerHTML = elSwitch("elements") + `<div class="toolbar"><select id="ft" aria-label="Type"><option value="">All types</option>${Object.keys(TYPES).map(t => `<option value="${t}" ${params.type === t ? "selected" : ""}>${TYPES[t]}</option>`).join("")}</select>
  <select id="ff" aria-label="Floor"><option value="">All floors</option>${["FDN", "BS", "GR", "L1", "PH", "TOR"].map(f => `<option>${f}</option>`).join("")}</select>
  <select id="fs" aria-label="Status"><option value="">All statuses</option>${Object.keys(STATUS_COLORS).slice(0, 5).map(s => `<option>${s}</option>`).join("")}</select>
  <input id="fq" placeholder="Filter by ID or description" aria-label="Filter elements"><span class="small" id="cnt"></span></div><div id="et"></div>`;
  bindSeg("elsw", v => location.hash = "#/project/" + v);
  const draw = () => {
    const t = $("#ft").value, f = $("#ff").value, s = $("#fs").value, q = $("#fq").value.toLowerCase();
    const rows = els.filter(e => (!t || e.element_type === t) && (!f || e.floor === f) && (!s || e.status === s) && (!q || (e.mark + e.uid + e.description).toLowerCase().includes(q)));
    $("#cnt").textContent = `${rows.length} elements`;
    $("#et").innerHTML = table([{ t: "Element", f: e => e.mark ? `<b>${esc(e.mark)}</b><div class="small mono">${esc(e.uid)}</div>` : `<i class='small'>unidentified</i><div class="small mono">${esc(e.uid)}</div>`, sv: e => e.mark }, { t: "Type", f: e => TYPES[e.element_type] }, { k: "floor", t: "Floor" },
    { t: "Key dimensions (m)", f: e => `<span class="tnum">${dimsShort(e)}</span>` }, { t: "Quantity", num: 1, f: e => e.quantity == null ? "<i class='small'>n/a</i>" : n3(e.quantity) + " " + UNIT(e.unit), sv: e => e.quantity ?? -1 },
    { t: "Cross-checks", f: e => e.cross_checks ? `${e.cross_checks_passed}/${e.cross_checks}` : "—" }, { t: "Status", f: e => badge(e.status), sv: e => e.status }, { k: "drawing", t: "Drawing" }, { t: "Confidence", num: 1, f: e => Math.round(e.confidence * 100) + " %", sv: e => e.confidence }], rows, { onclick: e => openEvidence(e.uid) });
  };
  ["#ft", "#ff", "#fs"].forEach(s => $(s).onchange = draw); $("#fq").oninput = draw; draw();
}
function dimsShort(e) {
  const d = e.dims, m = v => v == null ? "?" : (+v).toFixed(3);
  switch (e.element_type) {
    case "footing": case "raft": return d.length ? `${m(d.length)} × ${m(d.width)} × ${m(d.depth)}` : `A ${m(d.plan_area)} m² × ${m(d.depth)}`;
    case "column": return `${m(d.width)} × ${m(d.depth)} × H ${m(d.height)}`;
    case "beam": return `L ${m(d.length)} × ${m(d.width)} × ${m(d.depth)}${d.slab_deduction ? " (−" + m(d.slab_deduction) + ")" : ""}`;
    case "slab": return `A ${m(d.net_area)} m² × ${m(d.thickness)}`;
    case "wall": return `A ${m(d.plan_area)} m² × H ${m(d.height)}`;
    case "pedestal": return `${m(d.length)} × ${m(d.width)} × ${m(d.height)}`;
    case "blinding": return `A ${m(d.plan_area)} m² × ${m(d.thickness)}`;
  } return "";
}
async function takeoff(main) {
  const els = await cached("elements", () => api(P("/elements")));
  const types = Object.keys(TYPES).filter(t => els.some(e => e.element_type === t));
  let curT = types[0];
  main.innerHTML = elSwitch("takeoff") + `<div class="sub">Every quantity is calculated by the deterministic engine from measured CAD geometry, schedules and tags. Select a row for its full evidence.</div><div class="tabs" id="ttabs" style="margin-bottom:12px"></div><div id="sum" class="small" style="margin-bottom:10px"></div><div id="tt"></div>`;
  bindSeg("elsw", v => location.hash = "#/project/" + v);
  const draw = () => {
    $("#ttabs").innerHTML = types.map(t => `<button class="${t === curT ? "on" : ""}" data-t="${t}">${TYPES[t]}<span class="n">${els.filter(e => e.element_type === t).length}</span></button>`).join("");
    $$("#ttabs button").forEach(b => b.onclick = () => { curT = b.dataset.t; draw(); });
    const rows = els.filter(e => e.element_type === curT);
    const tot = rows.reduce((s, e) => s + (e.quantity || 0), 0), miss = rows.filter(e => e.quantity == null).length;
    $("#sum").innerHTML = `Total ${TYPES[curT].toLowerCase()}: <b style="color:var(--text-primary)">${n3(tot)} m³</b> from ${rows.length - miss} quantified elements${miss ? ` · <b style="color:var(--error)">${miss} not calculable (missing data — never guessed)</b>` : ""}`;
    const D = k => ({ t: k.replace(/_/g, " "), num: 1, f: e => e.dims[k] == null ? (k in e.dims ? "<b style='color:var(--error)'>n/a</b>" : "") : n3(e.dims[k]), sv: e => e.dims[k] ?? -1 });
    const dimcols = { footing: ["length", "width", "plan_area", "depth"], raft: ["length", "width", "plan_area", "depth"], blinding: ["plan_area", "thickness"], column: ["width", "depth", "height"], wall: ["plan_area", "height"], beam: ["length", "width", "depth", "slab_deduction"], slab: ["gross_area", "openings_area", "net_area", "thickness"], pedestal: ["length", "width", "height"] }[curT];
    $("#tt").innerHTML = table([{ t: "Element", f: e => e.mark ? `<b>${esc(e.mark)}</b>` : "<i class='small'>unidentified</i>", sv: e => e.mark }, { k: "floor", t: "Floor" }, ...dimcols.map(D),
    { t: "Formula", f: e => `<span class="mono small">${esc(e.formula)}</span>` }, { t: "Quantity (m³)", num: 1, f: e => e.quantity == null ? "<b style='color:var(--error)'>n/a</b>" : `<b>${n3(e.quantity)}</b>`, sv: e => e.quantity ?? -1 },
    { t: "Status", f: e => badge(e.status), sv: e => e.status }, { t: "Source", f: e => `<span class="small">${esc(e.drawing)} · ${esc(e.layer)}</span>` }], rows, { onclick: e => openEvidence(e.uid) });
  };
  draw();
}

/* ================= ELEMENT EVIDENCE ================= */
async function openEvidence(uid, back) {
  openSheet(`<div class="sheet-head"><div class="eyebrow">Evidence</div><h2>${esc(uid)}</h2></div>${skeleton(1)}`);
  const r = await api(P(`/elements/${encodeURIComponent(uid)}`)); const e = r.element;
  const vol = r.quantities.find(q => q.quantity_type.endsWith("volume")) || r.quantities[0];
  const c = r.comparison;
  $("#drawerBody").innerHTML = `${back ? `<button class="ghost small" id="evback" style="margin-bottom:10px">${icon("back")}Back to BOQ line</button>` : ""}
   <div class="sheet-head"><div class="eyebrow">Element evidence · ${esc(e.uid)}</div><h2>${esc(e.description)}</h2>
   <div class="row wrap" style="margin-top:8px">${badge(r.status)}<span class="small">Confidence ${Math.round(e.confidence * 100)} % — ${esc(e.confidence_reason)}</span><span class="spacer"></span><a class="btn sec small" href="#/viewer/${e.drawing_id}?el=${encodeURIComponent(e.uid)}" onclick="closeDrawer()">${icon("locate")}Show on drawing</a></div></div>
   <div class="grid g2">
    <div class="card"><h3>Identification</h3><div class="kv tight">
      <div>Element type</div><div>${TYPES[e.element_type] || e.element_type}</div><div>Element ID</div><div><b>${esc(e.mark) || "<i>not identified on drawing</i>"}</b> ${e.attributes.id_note ? `<div class="small">${esc(e.attributes.id_note)}</div>` : ""}</div>
      <div>Floor</div><div>${esc(e.floor)}</div><div>Drawing</div><div>${esc(e.drawing)}</div><div>Layer</div><div class="mono">${esc(e.layer)}</div>
      <div>CAD entity</div><div class="mono">${esc(e.sources[0]?.entity_type)} #${esc(e.sources[0]?.handle)} ${e.sources[0]?.block ? "in " + esc(e.sources[0].block) : ""}</div>
      ${e.attributes.shape ? `<div>Shape</div><div>${esc(e.attributes.shape)}</div>` : ""}</div></div>
    <div class="card"><h3>Calculation</h3>${vol ? `<div class="formula">${esc(vol.formula)}<br>= ${esc(vol.substitution)}<br>= <b>${n3(vol.value)} ${esc(UNIT(vol.unit))}</b></div>
      ${vol.assumptions.map(a => `<div class="small">Assumption: ${esc(a)}</div>`).join("")}${vol.notes.map(a => `<div class="small">${esc(a)}</div>`).join("")}` : "<div class='small'>No quantity — required dimensions are missing.</div>"}
      ${r.quantities.filter(q => q !== vol).map(q => `<div class="small">${esc(q.quantity_type)}: ${n3(q.value)} ${esc(UNIT(q.unit))} (${esc(q.formula)})</div>`).join("")}</div>
   </div>
   <div class="card" style="margin-top:14px"><h3>Extracted dimensions — where each number came from</h3>
    <table class="plain"><thead><tr><th>Dimension</th><th class="num">Value</th><th>Source</th><th>Evidence</th><th>CAD reference</th></tr></thead><tbody>
    ${Object.entries(e.dims).map(([k, m]) => `<tr><td>${esc(k.replace(/_/g, " "))}${m.is_assumption ? ' <span class="badge b-warning">assumption</span>' : ""}</td><td class="num">${m.value == null ? "<b style='color:var(--error)'>Not available</b>" : n3(m.value) + " " + esc(m.unit)}</td><td>${esc(m.source)}</td><td class="small">${esc(m.detail)}</td><td class="mono small">${m.ref ? esc(m.ref.drawing + " · " + m.ref.layer + " · #" + m.ref.handle) : ""}</td></tr>`).join("")}</tbody></table></div>
   ${e.cross_checks.length ? `<div class="card" style="margin-top:14px"><h3>Independent cross-checks</h3><table class="plain"><thead><tr><th>Check</th><th>Expected</th><th>Drawn / found</th><th>Result</th></tr></thead><tbody>${e.cross_checks.map(c => `<tr><td>${esc(c.name)}<div class="small">${esc(c.detail)}</div></td><td class="mono">${esc(c.expected)}</td><td class="mono">${esc(c.actual)}</td><td class="${c.passed ? "cc-pass" : "cc-fail"}">${c.passed ? "Pass" : "Fail"}</td></tr>`).join("")}</tbody></table></div>` : ""}
   ${r.boq_line || c ? `<div class="card" style="margin-top:14px"><h3>BOQ comparison</h3><div class="kv">${r.boq_line ? `<div>Generated BOQ item</div><div><b>${esc(r.boq_line.item_no)}</b> ${esc(r.boq_line.description)}</div><div>Line total (${r.boq_line.count} instance${r.boq_line.count > 1 ? "s" : ""})</div><div>${n3(r.boq_line.quantity)} m³</div>` : ""}
    ${c ? `<div>BOQ quantity</div><div>${c.boq_quantity == null ? "—" : n3(c.boq_quantity) + " " + esc(c.boq_unit || "")} ${c.boq_item_no ? "(BOQ item " + esc(c.boq_item_no) + ")" : ""}</div><div>Variance</div><div>${n3(c.variance)} m³ (${pct(c.variance_pct)})</div><div>Comparison status</div><div>${badge(c.status)}</div><div>Reason</div><div>${esc(c.reasons.join("; "))}</div>` : ""}</div></div>` : ""}
   ${e.flags.length ? `<div class="card" style="margin-top:14px"><h3>Why this element was flagged</h3>${e.flags.map(f => `<div class="flag ${f.status_impact.split(" ")[0]}"><b>${esc(f.title)}</b> ${badge(f.status_impact)}<div class="small">${esc(f.detail)}</div></div>`).join("")}</div>` : ""}
   <div class="card" style="margin-top:14px"><h3>All CAD sources</h3><table class="plain"><thead><tr><th>Drawing</th><th>Layer</th><th>Type</th><th>Handle</th><th>Note</th></tr></thead><tbody>${e.sources.map(s => `<tr><td>${esc(s.drawing)}</td><td class="mono">${esc(s.layer)}</td><td>${esc(s.entity_type)}</td><td class="mono">${esc(s.handle)}</td><td class="small">${esc(s.note)}</td></tr>`).join("")}</tbody></table></div>
   <div class="card" style="margin-top:14px"><h3>Plain-English explanation</h3><p style="margin:0">${esc(r.explanation.text)}</p>${r.explanation.ai_rewrite?.text ? `<p><i>AI summary (${esc(r.explanation.ai_rewrite.model)}):</i> ${esc(r.explanation.ai_rewrite.text)}</p>` : ""}<div class="small" style="margin-top:6px">Generated deterministically from the evidence above.</div></div>`;
  if (back) $("#evback").onclick = back;
}

/* ================= CLIENT BOQ & VARIANCE ================= */
async function boq(main) {
  const [lines, imports] = await Promise.all([cached("boq", () => api(P("/boq"))), api(P("/boq/imports"))]);
  const act = imports.find(i => i.active);
  main.innerHTML = `<div class="grid g2"><div class="card"><h3>Element BOQ generated from drawings</h3><div class="kv tight"><div>BOQ lines</div><div>${lines.length}</div><div>Total concrete</div><div>${n3(lines.reduce((s, l) => s + (l.quantity || 0), 0))} m³</div><div>Lines with missing data</div><div>${lines.filter(l => l.count_missing).length}</div></div>
   <div class="toolbar" style="margin-top:12px;margin-bottom:0"><a class="btn sec" href="${P("/export/boq")}">${icon("export")}Export element BOQ</a><a class="btn sec" href="#/project/variance">Variance analysis ${icon("arrow")}</a></div></div>
   <div class="card"><h3>Client / existing BOQ for comparison</h3>${act ? `<div class="banner ${act.is_test ? "test" : "info"}">${act.is_test ? "TEST BOQ (synthetic, not Static Group data): " : "Active BOQ: "}${esc(act.name)} · ${act.row_count} rows</div>` : `<div class="banner info">${icon("info")}<div>No client BOQ imported for this project.</div></div>`}
    <div class="toolbar"><input type="file" id="bf" accept=".xlsx,.csv" aria-label="BOQ file"><button id="bu">Upload &amp; map columns</button></div>
    ${imports.length ? `<div class="small">Previous imports: ${imports.map(i => `<a href="#" data-i="${i.import_id}" class="actv">${esc(i.name)}${i.is_test ? " [TEST]" : ""}${i.active ? " (active)" : ""}</a>`).join(" · ")} · <a href="#" class="actv" data-i="">Deactivate</a></div>` : ""}
    <div id="mapper"></div></div></div>
   <div class="section-title">Element BOQ lines <span class="count">${lines.length}</span></div><div id="bt"></div>`;
  $("#bt").innerHTML = table([{ k: "item_no", t: "Item" }, { k: "category", t: "Category" }, { k: "description", t: "Description" }, { t: "Element ID", f: l => esc(l.element_id) || "<i>unidentified</i>" }, { k: "floor_name", t: "Floor" }, { k: "unit", t: "Unit" },
  { k: "count", t: "No.", num: 1 }, { t: "Calculated qty", num: 1, f: l => l.quantity == null ? "<b style='color:var(--error)'>n/a</b>" : n3(l.quantity), sv: l => l.quantity ?? -1 }, { t: "Status", f: l => badge(l.status), sv: l => l.status }, { t: "Source", f: l => `<span class="small">${esc(l.drawings.join(", "))}</span>` }],
    lines, { onclick: l => openEvidence(l.element_uids[0]) });
  $$(".actv").forEach(a => a.onclick = async ev => { ev.preventDefault(); await api(P("/boq/activate"), { method: "POST", body: { import_id: a.dataset.i || null } }); invalidate(); refreshChrome(); route(); });
  $("#bu").onclick = async () => {
    const f = $("#bf").files[0]; if (!f) return toast("Choose an .xlsx or .csv file first");
    const fd = new FormData(); fd.append("file", f);
    try { const pv = await api(P("/boq/preview"), { method: "POST", body: fd }); showMapper(pv); } catch (e) { toast(e.message, 5000, "error"); }
  };
}
function showMapper(pv) {
  const opt = sel => `<option value="">— not mapped —</option>` + pv.header.map((h, i) => `<option value="${i}" ${sel === i ? "selected" : ""}>${esc(h || "(column " + (i + 1) + ")")}</option>`).join("");
  const LBL = { item_no: "BOQ item no.", description: "Description", element: "Element / mark", floor: "Floor / level", quantity: "Quantity *", unit: "Unit", rate: "Rate (optional — a priced BOQ builds rate memory for future suggestions)" };
  $("#mapper").innerHTML = `<h3 style="margin-top:14px">Map columns — ${esc(pv.filename)}</h3>
   ${pv.title_rows.length ? `<div class="small">Title rows detected above header: ${esc(pv.title_rows.join(" | "))}</div>` : ""}
   <div class="mapping">${pv.fields.map(f => `<label>${LBL[f]}</label><select data-f="${f}">${opt(pv.suggested_mapping[f])}</select>`).join("")}
   <label>Header row</label><input id="hr" type="number" value="${pv.header_row}" min="0">
   <label>Name</label><input id="bn" value="${esc(pv.filename)}">
   <label>Data source</label><label class="small"><input type="checkbox" id="istest" ${pv.looks_like_test ? "checked" : ""}> TEST / synthetic BOQ (labelled everywhere)</label></div>
   <div class="small" style="margin:10px 0">Preview (${pv.row_count} rows):</div>
   <div class="tablewrap" style="max-height:200px"><table><thead><tr>${pv.header.map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead><tbody>${pv.sample.map(r => `<tr>${r.map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
   <div class="toolbar" style="margin-top:12px"><button id="imp">Import &amp; compare</button></div>`;
  $("#imp").onclick = async () => {
    const mapping = {}; $$("#mapper select[data-f]").forEach(s => { if (s.value !== "") mapping[s.dataset.f] = +s.value; });
    try {
      const r = await api(P("/boq/import"), { method: "POST", body: { token: pv.token, mapping, header_row: +$("#hr").value, sheet: pv.sheet, name: $("#bn").value, filename: pv.filename, is_test: $("#istest").checked } });
      toast(`Imported ${r.row_count} BOQ rows` + (r.rates_recorded ? ` — captured ${r.rates_recorded} rate(s) for future suggestions` : ""), 6000); invalidate(); refreshChrome(); location.hash = "#/project/variance";
    } catch (e) { toast(e.message, 6000, "error"); }
  };
}
async function variance(main) {
  const c = await cached("cmp", () => api(P("/comparison")));
  const mappingData = c.boq ? await cached("boq-mappings", () => api(P("/boq/mappings"))) : { targets: [] };
  const s = await api(P("/settings"));
  const tol = s.settings.tolerances.map(b => `≤ ${b.max_abs_pct}% → ${b.status}`).join(" · ") + ` · above → ${s.settings.tolerance_above_status}`;
  const banner = !c.boq ? `<div class="banner info">${icon("info")}<div>No client BOQ imported — showing drawing quantities only. Import one on the <a href="#/project/clientboq">Client BOQ</a> tab.</div></div>`
    : c.boq.is_test ? `<div class="banner test">TEST BOQ — "${esc(c.boq.name)}" is synthetic data created to demonstrate the comparison logic. It is NOT Static Group data.</div>` : `<div class="banner info">${icon("info")}<div>Compared with BOQ: ${esc(c.boq.name)}</div></div>`;
  main.innerHTML = `<div class="toolbar"><a class="btn ghost small" href="#/project/clientboq">${icon("back")}Client BOQ</a></div>${banner}<div class="grid g2"><div class="card"><h3>Status</h3>${stack(c.summary.by_status)}<div class="small" style="margin-top:8px">Tolerance bands (Settings): ${esc(tol)}<br>Variance = Drawing − BOQ; Variance % = Variance ÷ BOQ × 100 (undefined when BOQ = 0 or missing).</div></div>
  <div class="card"><h3>By category</h3><table class="plain"><thead><tr><th>Category</th><th class="num">Drawing</th><th class="num">BOQ</th><th class="num">Variance</th><th class="num">%</th></tr></thead><tbody>${Object.entries(c.summary.by_category).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${n3(v.drawing)}</td><td class="num">${n3(v.boq)}</td><td class="num">${n3(v.variance)}</td><td class="num">${pct(v.variance_pct)}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="toolbar" style="margin-top:16px"><select id="vs" aria-label="Status"><option value="">All statuses</option>${Object.keys(STATUS_COLORS).map(k => `<option>${k}</option>`).join("")}</select><a class="btn sec" href="${P("/export/variance")}">${icon("export")}Export variance report</a></div><div id="vt"></div>`;
  const draw = () => {
    const f = $("#vs").value; const rows = c.rows.filter(r => !f || r.status === f);
    $("#vt").innerHTML = table([{ t: "BOQ item", f: r => esc(r.boq_item_no) || "<i class='small'>—</i>" }, { t: "BOQ description", f: r => esc(r.boq_description) || "<i class='small'>(no BOQ row)</i>" }, { k: "boq_element", t: "BOQ element" },
    { t: "Drawing item", f: r => `${esc(r.matched_items.join(", "))}<div class="small">${esc((r.drawing_description || "").slice(0, 70))}</div>` }, { t: "Drawing qty", num: 1, f: r => n3(r.drawing_quantity), sv: r => r.drawing_quantity ?? -1 }, { t: "BOQ qty", num: 1, f: r => n3(r.boq_quantity) + (r.boq_unit ? " " + esc(r.boq_unit) : ""), sv: r => r.boq_quantity ?? -1 },
    { t: "Variance", num: 1, f: r => n3(r.variance), sv: r => r.variance ?? 0 }, { t: "Var %", num: 1, f: r => pct(r.variance_pct), sv: r => Math.abs(r.variance_pct ?? 0) }, { t: "Status", f: r => badge(r.status), sv: r => r.status },
    { t: "Mapping decision", f: r => {
      if (r.boq_source_row == null) return "";
      const suggestedKey = r.candidate_refs?.length === 1 ? r.candidate_refs[0].match_key : null;
      const selectedTarget = r.mapping_target_type && r.mapping_target_key
        ? `${r.mapping_target_type}|${r.mapping_target_key}` : suggestedKey ? `calculated|${suggestedKey}` : "";
      const options = (mappingData.targets || []).map(t => {
        const value = `${t.target_type}|${t.target_id}`;
        const detail = t.target_type === "canonical" ? "canonical item; no measured quantity" : `calculated · ${t.evidence_status || "status unknown"}`;
        const score = t.target_type === "calculated" ? r.candidate_scores?.find(c => c.item_no === t.item_no) : null;
        return `<option value="${esc(value)}" ${selectedTarget === value ? "selected" : ""}>${esc(t.item_no)} — ${esc(t.description)} (${esc(t.unit)}; ${detail}${score ? `; description similarity ${Math.round(score.score * 100)}%` : ""})</option>`;
      }).join("");
      const state = r.mapping_status ? `${esc(r.mapping_status)}${r.mapping_version ? ` v${r.mapping_version}` : ""}` : "No saved decision";
      const sourceIdentity = r.mapping_source_identity || {};
      const history = (r.mapping_history || []).map(h => `<li>v${h.version}: ${esc(h.action)}${h.target_id ? ` → ${esc(h.target_id)}` : ""} · ${esc(h.reviewer || "reviewer unavailable")} · ${esc(fmtIso(h.timestamp))}${h.comment ? `<br>${esc(h.comment)}` : ""}</li>`).join("");
      const sourceDetails = `${esc(r.boq_source_file || sourceIdentity.source_file || "")} · ${esc(r.boq_sheet || sourceIdentity.source_sheet || "")} row ${esc(r.boq_source_row)} · ${esc(r.boq_item_no)} · ${esc(r.boq_unit || "")} · qty ${n3(r.boq_quantity)}`;
      const suggestions = (r.candidate_scores || []).map(c => `${c.item_no}: description similarity ${Math.round(c.score * 100)}%`).join("; ");
      return `<div class="small">${state}${r.mapping_target_type ? ` · ${esc(r.mapping_target_type)}: ${esc(r.mapping_target_code || r.mapping_target_id || "")}` : ""}</div>
        <details><summary>Source, suggestions &amp; history</summary><div class="small">${sourceDetails}<br>${esc(suggestions || "No suggested calculated target")}${sourceIdentity.source_fingerprint ? `<br>Source fingerprint: ${esc(sourceIdentity.source_fingerprint)}` : ""}</div>${history ? `<ol class="small">${history}</ol>` : '<div class="small">No prior mapping decisions.</div>'}</details>
        <select data-map-target aria-label="Mapping target"><option value="">Select target…</option>${options}</select>
        <select data-map-action aria-label="Mapping decision"><option value="approve">Approve selected target</option><option value="reject">Reject selected candidate</option><option value="unresolved">Leave unresolved</option></select>
        <button type="button" class="sec small" data-map-apply>Preview decision</button>`;
    } },
    { t: "Reason", f: r => `<span class="small">${esc(r.reasons.join("; "))}</span>` }], rows, { onclick: r => r.element_uids.length ? openEvidence(r.element_uids[0]) : toast("This BOQ row has no matching drawing element") });
    setTimeout(() => {
      const tableEl = $("#vt table");
      if (!tableEl) return;
      tableEl.querySelectorAll("[data-map-target], [data-map-action], [data-map-apply], details, summary").forEach(el => {
        el.addEventListener("click", e => e.stopPropagation());
        el.addEventListener("keydown", e => e.stopPropagation());
      });
      tableEl.querySelectorAll("[data-map-apply]").forEach(button => button.onclick = async e => {
        e.stopPropagation();
        const tr = button.closest("tr");
        const row = rows[+tr.dataset.ri];
        const action = tr.querySelector("[data-map-action]").value;
        const selected = tr.querySelector("[data-map-target]").value || "";
        const [targetType, targetId] = selected ? selected.split("|", 2) : [null, null];
        if (action !== "unresolved" && !targetId) return toast("Select a target or candidate first", 5000, "error");
        const expectedVersion = row.mapping_version || 0;
        const originalLabel = button.textContent;
        button.disabled = true;
        button.textContent = "Preparing preview…";
        try {
          const preview = await api(P("/boq/mappings/preview"), { method: "POST", body: {
            source_row: row.boq_source_row, action, target_id: action === "unresolved" ? null : targetId,
            target_type: action === "unresolved" ? null : targetType,
            expected_version: expectedVersion
          } });
          const before = preview.before;
          const after = preview.after;
          const quantityNote = preview.after.target_type === "canonical" ? "<br>Canonical target is a classification only; no calculated quantity is being approved." : "";
          const message = `BOQ row ${preview.source_row}: <b>${esc(preview.source_description)}</b><br>
            Current: ${esc(before.decision)} · drawing qty ${n3(before.drawing_quantity)} · variance ${n3(before.variance)}<br>
            Proposed: ${esc(after.decision)}${after.target_description ? ` → ${esc(after.target_description)}` : ""}
            · drawing qty ${n3(after.drawing_quantity)} · variance ${n3(after.variance)}${quantityNote}<br>
            Run ${esc(preview.run_id || "not available")} · import ${esc(preview.import_id)}. Historical runs are unchanged. Preview expires in ${preview.expires_in_seconds}s.
            <label for="boqMapComment">Estimator comment (optional)</label><textarea id="boqMapComment" rows="3" aria-label="Estimator comment"></textarea>`;
          if (!(await confirmDialog("Preview BOQ mapping decision", message, "Apply decision", action === "reject"))) {
            button.disabled = false;
            button.textContent = originalLabel;
            return;
          }
          const comment = $("#boqMapComment")?.value.trim() || "";
          button.textContent = "Applying decision…";
          await api(P("/boq/mappings"), { method: "POST", body: {
            source_row: row.boq_source_row, action, target_id: action === "unresolved" ? null : targetId,
            target_type: action === "unresolved" ? null : targetType,
            expected_version: expectedVersion, preview_token: preview.preview_token, comment
          } });
          invalidate(); toast("BOQ mapping decision saved"); await variance(main);
        } catch (err) {
          toast(err.message, 6000, "error"); button.disabled = false; button.textContent = originalLabel;
          if (/stale|version changed|expired/i.test(err.message)) { invalidate(); await variance(main); }
        }
      });
    }, 0);
  };
  $("#vs").onchange = draw; draw();
}

/* ================= REVIEW WORKSPACE ================= */
const RQ_CAT = [
  ["missing", "Missing dimensions", i => i.status_impact === "Missing Data"],
  ["conflict", "Drawing conflicts", i => i.status_impact === "Review Required" && !["LARGE_VARIANCE", "BOQ_ITEM_NOT_IN_DRAWINGS", "DRAWING_ITEM_NOT_IN_BOQ", "BOQ_QTY_ZERO", "UNIT_MISMATCH"].includes(i.code)],
  ["inputs", "Missing project inputs", null],
  ["variance", "Large BOQ variances", i => ["LARGE_VARIANCE", "BOQ_ITEM_NOT_IN_DRAWINGS", "DRAWING_ITEM_NOT_IN_BOQ", "BOQ_QTY_ZERO", "UNIT_MISMATCH", "VARIANCE_CHECK"].includes(i.code)],
  ["rules", "Unconfirmed methodology rules", null],
  ["checks", "Other checks", i => i.status_impact === "Check" && i.code !== "VARIANCE_CHECK"],
];
async function review(main) {
  const p = cur();
  const [q, items, rulesL, bm] = await Promise.all([cached("review", () => api(P("/review"))), cached("items", () => api(P("/items"))), cached("rules", () => api("/api/rules")),
    p.historical_boq ? cached("bench", () => api(P("/benchmark"))) : Promise.resolve(null)]);
  let state = "Open", catKey = null;
  const inputItems = items.filter(i => i.status === "Requires Input");
  const bmRows = bm && bm.available ? bm.rows.filter(r => r.kind === "measured" && r.diff_pct != null && Math.abs(r.diff_pct) >= 20) : [];
  const pend = rulesL.filter(r => r.status !== "CONFIRMED" && (r.items || []).some(id => items.some(i => i.item_id === id)));
  const qOf = (fn) => q.filter(i => (!state || i.decision.state === state) && fn(i));
  const count = k => { const c = RQ_CAT.find(x => x[0] === k); if (k === "inputs") return inputItems.length; if (k === "rules") return pend.length; return qOf(c[2]).length + (k === "variance" ? bmRows.length : 0); };
  catKey = RQ_CAT.map(c => c[0]).find(k => count(k)) || "missing";
  const render = () => {
    main.innerHTML = `<div class="toolbar">${seg("rqc", RQ_CAT.map(([k, l], i) => [k, `${i + 1}. ${l}`, count(k)]), catKey)}<span class="spacer"></span>
      <select id="rqs" aria-label="Decision state"><option value="Open">Open items</option><option value="">All decisions</option><option>Accepted</option><option>Resolved</option><option>Rejected</option></select>
      <a class="btn sec small" href="${P("/export/review")}">${icon("export")}Export</a></div><div id="rqb"></div>`;
    $("#rqs").value = state;
    bindSeg("rqc", v => { catKey = v; body(); });
    $("#rqs").onchange = e => { state = e.target.value; render(); };
    body();
  };
  const body = () => {
    const el = $("#rqb");
    if (catKey === "inputs") {
      el.innerHTML = `<div class="sub">BOQ lines that cannot be calculated until the project information is entered. Values entered on the Inputs tab are labelled "User input" on every quantity and audited.</div>` + table([
        { t: "Issue", f: i => `<b>${esc(i.missing[0] || "Input required")}</b>` }, { t: "BOQ item", f: i => `${esc(i.description)}<div class="small mono">${esc(i.item_id)}${i.variant ? " · " + esc(i.variant) : ""}</div>` },
        { t: "Impact", f: () => dsBadge("Missing") }, { t: "Action", f: () => `<a class="btn sec small" href="#/project/inputs">${icon("inputs")}Enter input</a>` }], inputItems);
      return;
    }
    if (catKey === "rules") {
      el.innerHTML = `<div class="sub">Measurement conventions not yet confirmed by an estimator that affect this project's BOQ. Decide them on the Rule Approval page — every decision is versioned and audited.</div>` + table([
        { t: "Rule", f: r => `<b>${esc(r.title)}</b><div class="small">${esc(r.description)}</div>` }, { t: "Status", f: r => ruleBadge(r.status), sv: r => r.status },
        { t: "BOQ items", f: r => (r.items || []).map(x => `<span class="chip">${esc(x)}</span>`).join("") }, { t: "Evidence", f: r => `<span class="small">${esc(r.evidence || "")}</span>` },
        { t: "Action", f: r => `<a class="btn sec small" href="#/rules?r=${esc(r.rule_id)}">Decide</a>` }], pend);
      return;
    }
    const c = RQ_CAT.find(x => x[0] === catKey);
    const rows = qOf(c[2]);
    el.innerHTML = (catKey === "variance" && bmRows.length ? `<div class="section-title" style="margin-top:0">Historical benchmark differences ≥ 20 % <span class="count">${bmRows.length}</span></div>` + table([
      { t: "Issue", f: r => `<b>${esc(r.description)}</b><div class="small">${esc(r.sheet)} row ${r.row}</div>` }, { t: "Static Group", num: 1, f: r => n2(r.historical_qty) }, { t: "Engine", num: 1, f: r => n2(r.engine_qty) },
      { t: "Variance", num: 1, f: r => `<b style="color:var(--error)">${pct(r.diff_pct)}</b>` }, { t: "Reason", f: r => `<span class="small">${esc((r.diagnosis || [])[0]?.cause || "")}</span>` }, { t: "Action", f: () => '<span class="btn sec small">Reconcile</span>' }], bmRows, { onclick: openReconcile }) + `<div class="section-title">Element-level variance flags <span class="count">${rows.length}</span></div>` : "") +
      table([{ t: "Impact", f: i => badge(i.status_impact), sv: i => i.status_impact }, { t: "Issue", f: i => `<b>${esc(i.title)}</b><div class="small mono">${esc(i.code)}</div>` },
      { t: "Element", f: i => `${esc(TYPES[i.element_type] || i.element_type || "")} <b>${esc(i.mark)}</b> ${i.count > 1 ? `<span class="chip">${i.count} elements</span>` : ""}<div class="small">${esc(i.floor)} ${esc(i.drawing)}</div>` },
      { t: "Reason", f: i => `<span class="small">${esc(i.detail).slice(0, 260)}</span>` }, { t: "Decision", f: i => `${badge(i.decision.state)}${i.decision.comment ? `<div class="small">${esc(i.decision.comment)}</div>` : ""}`, sv: i => i.decision.state },
      { t: "Action", f: () => '<span class="btn sec small">Review</span>' }], rows, { onclick: openReview });
  };
  render();
}
function openReview(i) {
  const act = i.action;
  openSheet(`<div class="sheet-head"><div class="eyebrow">Review item · ${esc(i.code)}</div><h2>${esc(i.title)}</h2><div class="row wrap" style="margin-top:8px">${badge(i.status_impact)}${badge(i.decision.state)}<span class="small">source: ${esc(i.source)}</span></div></div>
   <div class="sheet-section"><h4>Reason</h4><p style="margin:0">${esc(i.detail)}</p>${i.variance_pct != null ? `<p>Variance: <b>${pct(i.variance_pct)}</b></p>` : ""}</div>
   <div class="sheet-section"><h4>Evidence — affected elements (${(i.element_uids || []).length})</h4>${(i.element_uids || []).map(u => `<a href="#" class="chip ev" data-u="${esc(u)}">${icon("eye")}${esc(u)}</a>`).join("") || "<span class='small'>None — drawing-level item</span>"}
    ${i.drawing_id && i.point ? `<div style="margin-top:10px"><a class="btn sec small" href="#/viewer/${i.drawing_id}?pt=${i.point.join(",")}" onclick="closeDrawer()">${icon("locate")}Show location on drawing</a></div>` : ""}</div>
   ${act ? `<div class="sheet-section"><h4>Correct</h4>${act.type === "slab_thickness" ? `<p class="small">Enter the slab thickness confirmed from sections/details. It is recorded as <b>User input</b>, kept separate from measured values and logged in the audit trail.</p><div class="row"><input id="av" type="number" value="${esc(act.value)}" placeholder="mm" style="width:120px" aria-label="Thickness in mm"> mm <button id="aa">Apply &amp; recalculate</button></div>` : `<p class="small">Enter the storey height in <a href="#/settings" onclick="closeDrawer()">Settings</a>.</p>`}</div>` : ""}
   <div class="sheet-section"><h4>Decision</h4><textarea id="dcm" rows="3" style="width:100%" placeholder="Comment — recorded with the decision in the audit log">${esc(i.decision.comment || "")}</textarea>
   <div class="row wrap" style="margin-top:10px"><button data-st="Accepted">${icon("check")}Approve</button><button class="sec" data-st="Resolved">Resolve</button><button class="danger" data-st="Rejected">Reject</button>${i.decision.state !== "Open" ? `<button class="ghost" data-st="Open">Reopen</button>` : ""}</div>
   ${i.decision.user ? `<div class="small" style="margin-top:8px">Last decision: ${esc(i.decision.state)} by ${esc(i.decision.user)} · ${fmtIso(i.decision.at)}</div>` : ""}</div>`, true);
  $$(".ev").forEach(a => a.onclick = ev => { ev.preventDefault(); openEvidence(a.dataset.u, () => openReview(i)); });
  $$("[data-st]").forEach(b => b.onclick = async () => { b.disabled = true; try { await api(P(`/review/${encodeURIComponent(i.id)}`), { method: "POST", body: { state: b.dataset.st, comment: $("#dcm").value } }); invalidate(); closeDrawer(); refreshChrome(); route(); toast(`Decision recorded: ${b.dataset.st}`); } catch (e) { toast(e.message, 5000, "error"); b.disabled = false; } });
  if ($("#aa")) $("#aa").onclick = async () => {
    const v = $("#av").value; if (!v) return toast("Enter a thickness");
    try {
      await api(P("/settings"), { method: "POST", body: { slab_thickness: { [act.uid]: v }, reason: `Review item ${i.id}` } });
      await api(P(`/review/${encodeURIComponent(i.id)}`), { method: "POST", body: { state: "Resolved", comment: `Thickness ${v} mm entered by engineer` } });
      invalidate(); closeDrawer(); refreshChrome(); route(); toast("Thickness applied and quantities recalculated");
    } catch (e) { toast("Could not apply: " + e.message, 6000, "error"); }
  };
}

/* ================= REPORTS & AUDIT / SETTINGS ================= */
async function reports(main) {
  const inProject = main.id === "tabbody";
  if (!inProject) setCrumb("System", "Reports & Audit");
  const [insp, audit, runs] = await Promise.all([cached("insp", () => api(P("/inspection"))).catch(() => null), api(P("/audit")), api(P("/runs"))]);
  main.innerHTML = (inProject ? "" : pageHead("Reports &amp; Audit", `Exports and the audit trail for ${esc(shortName(cur().name))}. Every decision, input and processing run is recorded.`)) + `<div class="grid g5">
   ${[["static-boq", "Static Group BOQ", "Company BOQ structure with status, rule status, source and confidence"], ["boq", "Element BOQ", "Element lines, formulas, CAD handles, assumptions"], ["variance", "Variance report", "Comparison against the active client BOQ"], ["review", "Review report", "Flagged items with reasons and decisions"], ["processing", "Processing summary", "Files, unsupported entities, warnings, audit log"]]
      .map(([k, t, d]) => `<div class="card" style="display:flex;flex-direction:column"><h3 style="margin-bottom:4px">${t}</h3><p class="small" style="flex:1;margin:0 0 12px">${d}</p><a class="btn sec small" href="${P("/export/" + k)}">${icon("export")}Download Excel</a></div>`).join("")}</div>
  <div class="grid g2" style="margin-top:16px"><div class="card"><h3>Audit trail</h3>${table([{ t: "When", f: a => `<span class="small">${fmtIso(a.at)}</span>`, sv: a => a.at }, { k: "user", t: "User" }, { k: "event", t: "Event" }, { t: "Details", f: a => `<span class="small mono">${esc(JSON.stringify(Object.fromEntries(Object.entries(a).filter(([k]) => !["at", "user", "event", "project"].includes(k))))).slice(0, 200)}</span>` }], audit)}</div>
   <div class="card"><h3>Processing runs</h3>${table([{ k: "run_id", t: "Run" }, { k: "kind", t: "Kind" }, { t: "Started", f: r => fmtIso(r.started) }, { k: "status", t: "Status" }, { t: "Elements", num: 1, f: r => r.counts?.elements }], runs)}</div></div>
  ${insp ? `<div class="card" style="margin-top:16px"><h3>Drawing inspection — what the files contain</h3>
   <div class="kv"><div>DXF files</div><div>${insp.files}</div><div>Units</div><div>${Object.entries(insp.units).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ")}</div><div>DXF versions</div><div>${Object.entries(insp.dxf_versions).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ")}</div>
   <div>ID patterns found</div><div>${Object.entries(insp.id_patterns).map(([k, v]) => `<span class="chip">${esc(k)} ×${v}</span>`).join("")}</div></div>
   <details style="margin-top:12px"><summary>Structural conventions derived from the files</summary><div class="kv" style="margin-top:8px">${Object.entries(insp.structural_findings).map(([k, v]) => `<div>${esc(k)}</div><div>${esc(v)}</div>`).join("")}</div></details>
   ${Object.entries(insp.by_discipline).map(([k, v]) => `<details><summary><b>${esc(k)}</b> — ${v.files} files, ${v.entities.toLocaleString()} entities, ${v.layer_count} layers</summary>
     <div class="small">Entity types: ${Object.entries(v.types).map(([a, b]) => `${esc(a)} ${b}`).join(", ")}</div><div class="small">Top layers: ${Object.entries(v.layers).map(([a, b]) => `<span class="chip">${esc(a)} ${b}</span>`).join("")}</div></details>`).join("")}</div>` : ""}`;
}
async function settings(main) {
  setCrumb("System", "Settings");
  const s = await api(P("/settings"));
  const st = s.design.storey_heights, lv = s.design.levels, ov = s.overrides;
  main.innerHTML = pageHead("Settings", `Tolerances, measurement conventions and storey heights for ${esc(shortName(cur().name))}. Every change is audited and triggers a recalculation.`) + `<div class="grid g2"><div class="card"><h3>Variance tolerance bands</h3><p class="small">Applied by the comparison engine; not hard-coded.</p>
   <div id="tols">${s.settings.tolerances.map((b, i) => `<div class="toolbar">≤ <input type="number" step="0.1" data-i="${i}" value="${b.max_abs_pct}" style="width:90px" aria-label="Band ${i + 1}"> % → <b>${esc(b.status)}</b></div>`).join("")}</div>
   <div class="small">Above the last band → ${esc(s.settings.tolerance_above_status)}</div><button id="svt" style="margin-top:10px">Save tolerances</button></div>
   <div class="card"><h3>Measurement conventions (development defaults)</h3><p class="small">Static Group's own conventions are decided on the <a href="#/rules">Rule Approval</a> page; an approved rule overrides these defaults.</p><div class="mapping"><label>Column height basis</label><select id="chb"><option value="to_slab_soffit">Top of slab to underside of slab above</option><option value="floor_to_floor">Floor to floor</option></select>
   <label>Beam depth basis</label><select id="bdb"><option value="below_slab">Below slab (slab thickness deducted)</option><option value="full_depth">Full depth</option></select></div><button id="svm" style="margin-top:10px">Save &amp; recalculate</button></div></div>
  <div class="card" style="margin-top:16px"><h3>Storey heights (columns and walls)</h3><p class="small">Derived from level tags in the drawings. Nothing is assumed silently: confirm each value or enter a corrected one.</p>
   <div class="tablewrap" style="max-height:none"><table><thead><tr><th>Floor</th><th>Base level</th><th>Top level</th><th>Slab at top</th><th>Derived height</th><th>Derivation</th><th>Override (m)</th><th>Confirmed</th></tr></thead><tbody>
   ${Object.entries(st).map(([k, v]) => `<tr><td><b>${k}</b></td><td>${v.base_level ?? "—"} (${esc(v.base_floor)})</td><td>${v.top_level ?? "—"} (${esc(v.top_floor)})</td><td>${v.slab_top ?? "—"}</td><td><b>${v.height ?? "Not available from drawing"}</b></td><td class="small">${esc(v.explanation)}</td>
     <td><input type="number" step="0.01" data-h="${k}" value="${ov.storey_heights?.[k] ?? ""}" style="width:90px" aria-label="Override ${k}"></td><td><input type="checkbox" data-c="${k}" ${ov.storey_heights_confirmed?.[k] ? "checked" : ""} aria-label="Confirm ${k}"></td></tr>`).join("")}</tbody></table></div>
   <div class="toolbar" style="margin-top:12px"><input id="why" placeholder="Reason for change (audit log)" style="flex:1"><button id="svh">Save heights &amp; recalculate</button></div>
   <details><summary>Levels found in drawings</summary><table class="plain" style="margin-top:8px"><thead><tr><th>Floor</th><th>Kind</th><th>Used</th><th>All values found (count)</th><th>Source</th></tr></thead><tbody>
   ${Object.entries(lv).map(([k, v]) => `<tr><td>${k}</td><td>${esc(v.kind)}</td><td>${v.value ?? "—"}${v.user_override ? " (user)" : ""}${v.tie ? ' <span class="badge b-warning">tie</span>' : ""}</td><td class="small">${(v.candidates || []).map(c => `${c.value} (${c.count})`).join(", ")}</td><td class="small">${esc(v.source?.drawing || "")}</td></tr>`).join("")}</tbody></table></details></div>
  <div class="card" style="margin-top:16px"><h3>Add a project from a drawing folder</h3><p class="small">Each project points at a folder of DXF drawings and a CAD-standard rules file in <span class="mono">config/</span>. To upload files instead, use <a href="#/newproject">New project</a>.</p>
   <div class="mapping"><label>Name</label><input id="pn"><label>DXF folder</label><input id="pf" placeholder="D:\\Projects\\..."><label>Rules file</label><input id="prf" value="${esc(s.rules_file)}"></div><button id="pa" style="margin-top:10px">Add project</button></div>`;
  $("#chb").value = s.settings.measurement.column_height_basis; $("#bdb").value = s.settings.measurement.beam_depth_basis;
  const save = async (body, msg) => { try { await api(P("/settings"), { method: "POST", body }); invalidate(); toast(msg); refreshChrome(); route(); } catch (e) { toast(e.message, 5000, "error"); } };
  $("#svt").onclick = () => save({ tolerances: s.settings.tolerances.map((b, i) => ({ ...b, max_abs_pct: +$(`#tols input[data-i="${i}"]`).value })) }, "Tolerances saved");
  $("#svm").onclick = () => save({ measurement: { column_height_basis: $("#chb").value, beam_depth_basis: $("#bdb").value } }, "Conventions saved, quantities recalculated");
  $("#svh").onclick = () => {
    const h = {}, c = {}; $$("input[data-h]").forEach(i => h[i.dataset.h] = i.value === "" ? null : +i.value); $$("input[data-c]").forEach(i => c[i.dataset.c] = i.checked);
    save({ storey_heights: h, storey_heights_confirmed: c, reason: $("#why").value }, "Storey heights saved, quantities recalculated");
  };
  $("#pa").onclick = async () => { try { await api("/api/projects", { method: "POST", body: { name: $("#pn").value, source_folder: $("#pf").value, rules_file: $("#prf").value } }); toast("Project added"); init(); } catch (e) { toast(e.message, 5000, "error"); } };
}

/* ================= HISTORICAL BENCHMARK ================= */
const BMS = { "Exact Match": ["Exact match", "b-success"], "Within Tolerance": ["Good match", "b-success"], "Difference": ["Difference", "b-warning"], "Candidates Only": ["Candidates only", "b-info"], "Unable to Calculate": ["Not automated", "b-neutral"], "Not Measured": ["Not measured", "b-neutral"] };
function bmLabel(r) { if (r.status === "Difference" && Math.abs(r.diff_pct || 0) >= 20) return ["Investigation required", "b-error"]; return BMS[r.status] || [r.status, "b-neutral"]; }
async function costs(main) {
  setCrumb("Methodology", "Cost Benchmarking");
  const rows = await api("/api/costs/benchmark");
  const anyPriced = rows.some(r => r.priced_lines > 0);
  main.innerHTML = pageHead("Cost benchmarking", "Built only from rate memory (real rates Static Group has entered into priced BOQs, re-imported back into the app) — never estimated or looked up externally. A project's \"indicative total\" is a partial sum: only the BOQ lines that have both a calculated quantity and a known rate are included, so it is exactly as complete as its coverage % says and nothing more.");
  if (!anyPriced) {
    main.innerHTML += emptyState("bench", "No rate history yet", "Import a priced BOQ (with a Rate column mapped) on any project's Client BOQ tab to start building rate memory. Once at least one item has a known rate, this page will show indicative cost and QR/m² per project.");
    return;
  }
  const withArea = rows.filter(r => r.qr_per_m2 != null).map(r => [shortName(r.project_name), r.qr_per_m2, r.coverage_pct >= 50 ? "#2e8b57" : "#d4780f"]);
  main.innerHTML += `
  ${withArea.length ? `<div class="card" style="margin-top:16px"><h3>QR / m² (built-up area)</h3><div class="small" style="margin-bottom:10px">Only projects with a known built-up area and at least one priced line. Darker bars have 50%+ of their calculable lines priced; lighter bars are low-coverage and should be read cautiously.</div>${bars(withArea, n2, "QR/m²")}</div>` : `<div class="banner info" style="margin-top:16px">${icon("info")}<div>No project yet has both a built-up area and a priced line — the chart will appear once one does. The table below still shows indicative totals without a per-m² figure.</div></div>`}
  <div class="card" style="margin-top:16px"><h3>All projects</h3>${table([
    { t: "Project", f: r => esc(shortName(r.project_name)), sv: r => r.project_name },
    { t: "Indicative total (QR)", num: 1, f: r => r.indicative_total != null ? n2(r.indicative_total) : "—", sv: r => r.indicative_total ?? -1 },
    { t: "Coverage", f: r => `${r.priced_lines} / ${r.eligible_lines} lines${r.coverage_pct != null ? ` (${r.coverage_pct}%)` : ""}`, sv: r => r.coverage_pct ?? -1 },
    { t: "Built-up area", num: 1, f: r => r.built_up_area_m2 != null ? n2(r.built_up_area_m2) + " m²" : "—", sv: r => r.built_up_area_m2 ?? -1 },
    { t: "QR / m²", num: 1, f: r => r.qr_per_m2 != null ? `<b>${n2(r.qr_per_m2)}</b>` : '<span class="small">—</span>', sv: r => r.qr_per_m2 ?? -1 },
  ], rows, { onclick: r => location.hash = `#/project/boq?pid=${r.project}` })}</div>`;
}
async function benchmark(main, arg, params) {
  setCrumb("Methodology", "Benchmarks");
  const refs = S.projects.filter(p => p.historical_boq);
  if (!refs.length) { main.innerHTML = emptyState("bench", "No reference project", "Benchmarks need a project with Static Group's historical BOQ."); return; }
  const bp = params.p && refs.find(p => p.id === params.p) ? params.p : (cur().historical_boq ? S.pid : refs[0].id);
  const b = await api(`/api/projects/${bp}/benchmark`);
  if (!b.available) { main.innerHTML = pageHead("Historical benchmark") + emptyState("bench", "No benchmark available", esc(b.reason)); return; }
  const s = b.summary, rows = b.rows.filter(r => r.kind === "measured"), st = s.by_status;
  const good = (st["Exact Match"] || 0) + (st["Within Tolerance"] || 0);
  const inv = rows.filter(r => bmLabel(r)[0] === "Investigation required").length;
  main.innerHTML = pageHead("Historical benchmark", `Engine quantities compared line by line with Static Group's own BOQ <b>${esc(b.boq_meta.ref)}</b> (${esc((b.boq_meta.date || "").slice(0, 10))}). Historical quantities validate the methodology only — they are never copied into new projects. Large variances are shown, not tuned away.`,
    seg("bpj", refs.map(p => [p.id, shortName(p.name)]), bp), "Reference project") + `
  <div class="grid g5">${kpi("Measured BOQ lines", s.measured_lines, `${s.boq_lines} lines in the BOQ`)}${kpi("Good match", good, "exact or within 5 %", { cls: "accent-success" })}${kpi("Investigation required", inv, "difference of 20 % or more", { cls: inv ? "accent-error" : "" })}${kpi("Candidates only", st["Candidates Only"] || 0, "methodology rule undecided")}${kpi("Not automated", st["Unable to Calculate"] || 0, "no calculator / data yet")}</div>
  <div class="toolbar" style="margin-top:20px"><select id="bc" aria-label="Category"><option value="">All categories</option>${[...new Set(rows.map(r => r.category))].map(c => `<option>${esc(c)}</option>`).join("")}</select>
   <select id="bs" aria-label="Result"><option value="">All results</option>${["Exact match", "Good match", "Difference", "Investigation required", "Candidates only", "Not automated"].map(k => `<option>${k}</option>`).join("")}</select><span class="small">Select a line to reconcile it.</span></div><div id="bt"></div>`;
  bindSeg("bpj", v => location.hash = "#/benchmark?p=" + v);
  const vb = r => { if (r.diff_pct == null) return '<span class="small">—</span>'; const v = Math.max(-100, Math.min(100, r.diff_pct)); const w = Math.abs(v) / 2; const col = Math.abs(r.diff_pct) <= 5 ? "var(--success)" : Math.abs(r.diff_pct) >= 20 ? "var(--error)" : "var(--warning)";
    return `<div class="row" style="gap:10px"><div class="vbar" style="flex:1"><span class="mid"></span><span class="fill" style="${v < 0 ? `right:50%` : `left:50%`};width:${w}%;background:${col}"></span></div><b class="tnum" style="min-width:64px;text-align:right;color:${col}">${pct(r.diff_pct)}</b></div>`; };
  const draw = () => {
    const c = $("#bc").value, s2 = $("#bs").value;
    const rs = rows.filter(r => (!c || r.category === c) && (!s2 || bmLabel(r)[0] === s2));
    $("#bt").innerHTML = table([{ t: "BOQ line", f: r => `<b>${esc(r.description)}</b><div class="small">${esc(r.category)} · ${esc(r.sheet)} row ${r.row} · <span class="mono">${esc(r.item_id || "—")}</span></div>`, sv: r => r.description }, { t: "Unit", f: r => esc(UNIT(r.unit)) },
      { t: "BOQ quantity", num: 1, f: r => n2(r.historical_qty), sv: r => r.historical_qty ?? -1 }, { t: "Engine quantity", num: 1, f: r => r.engine_qty != null ? `<b>${n2(r.engine_qty)}</b>` : '<span class="small">—</span>', sv: r => r.engine_qty ?? -1 },
      { t: "Variance", f: vb, sv: r => Math.abs(r.diff_pct ?? 999) }, { t: "Status", f: r => { const [l, cl] = bmLabel(r); return `<span class="badge ${cl}">${l}</span>`; }, sv: r => bmLabel(r)[0] },
      { t: "Reason", f: r => `<span class="small" style="color:var(--text-secondary)">${esc(((r.diagnosis || [])[0] || {}).cause || (r.status === "Unable to Calculate" ? "No calculator or source data yet" : ""))}</span>` }], rs, { onclick: openReconcile });
  };
  $("#bc").onchange = draw; $("#bs").onchange = draw; draw();
}
async function openReconcile(r) {
  openSheet(`<div class="sheet-head"><div class="eyebrow">Reconciliation</div><h2>${esc(r.description)}</h2></div>${skeleton(1)}`);
  const recs = await api(P("/reconciliations")).catch(() => []);
  const mine = recs.filter(x => x.sheet === r.sheet && x.row === r.row);
  const els = r.element_uids && r.element_uids.length ? (await cached("elements", () => api(P("/elements"))).catch(() => [])).filter(e => r.element_uids.includes(e.uid)) : [];
  const [lbl, cls] = bmLabel(r);
  $("#drawerBody").innerHTML = `<div class="sheet-head"><div class="eyebrow">Reconciliation · ${esc(r.sheet)} row ${r.row} · item ${esc(r.item)}</div><h2>${esc(r.description)}</h2><div class="row" style="margin-top:8px"><span class="badge ${cls}">${lbl}</span><span class="mono small">${esc(r.item_id || "")} ${esc(r.variant || "")}</span></div></div>
   <div class="grid g3">${kpi("Static Group BOQ", n2(r.historical_qty), esc(UNIT(r.unit)))}${kpi("Engine", n2(r.engine_qty), esc(r.engine_status || ""))}${kpi("Variance", r.diff == null ? "—" : n2(r.diff), pct(r.diff_pct))}</div>
   <div class="card" style="margin-top:14px"><h3>Why is this line different? <span class="small">— causes supported by data, not conclusions</span></h3>${(r.diagnosis || []).map(d => `<div class="flag info"><b>${esc(d.cause)}</b><div class="small">${esc(d.evidence)}</div></div>`).join("") || "<p class='small'>No difference to diagnose.</p>"}</div>
   ${Object.keys(r.candidates || {}).length ? `<div class="card" style="margin-top:14px"><h3>Candidate quantities per methodology option</h3><table class="plain"><thead><tr><th>Option</th><th class="num">Quantity</th><th class="num">vs BOQ</th></tr></thead><tbody>${Object.entries(r.candidates).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${n2(v)}</td><td class="num">${r.historical_qty && v != null ? pct((v - r.historical_qty) / r.historical_qty * 100) : "—"}</td></tr>`).join("")}</tbody></table></div>` : ""}
   <div class="card" style="margin-top:14px"><h3>Rules used</h3>${(r.rules || []).map(x => `<div style="margin:4px 0">${ruleBadge(x.status)} <b>${esc(x.title)}</b> <span class="small">· ${x.selected ? "option " + esc(x.selected) : "no option approved"}</span></div>`).join("") || "<span class='small'>None</span>"}
     <div class="small" style="margin-top:8px">Formula: <span class="mono">${esc(r.formula || "")}</span></div><div class="small">Evidence: ${esc(r.engine_detail || "")}</div>
     ${(r.missing || []).length ? `<div class="small" style="color:var(--error)">Missing: ${esc(r.missing.join("; "))}</div>` : ""}<div style="margin-top:10px"><a class="btn sec small" href="#/rules" onclick="closeDrawer()">${icon("rules")}Open rule approval</a></div></div>
   ${els.length ? `<div class="card" style="margin-top:14px"><h3>Elements measured by the engine (${els.length})</h3><div class="tablewrap" style="max-height:260px"><table><thead><tr><th>Element</th><th>Floor</th><th>Dimensions</th><th class="num">Qty</th></tr></thead><tbody>${els.map(e => `<tr class="click" data-u="${esc(e.uid)}"><td><b>${esc(e.mark || "—")}</b> <span class="small mono">${esc(e.uid)}</span></td><td>${esc(e.floor)}</td><td class="small">${dimsShort(e)}</td><td class="num">${n3(e.quantity)}</td></tr>`).join("")}</tbody></table></div></div>` : ""}
   <div class="card" style="margin-top:14px"><h3>Engineer reconciliation</h3><p class="small">Record what explains this difference. Notes are stored as Static Group knowledge (with user and date) and can become a methodology rule — they do not change quantities by themselves.</p>
     <div class="toolbar"><select id="rcat" aria-label="Category"><option>Unknown Static Group convention</option><option>Elements missing in engine</option><option>Extra elements in engine</option><option>Drawing / schedule error</option><option>Historical BOQ error / allowance</option><option>Other</option></select>
     <input id="rrule" placeholder="Related rule id (optional)" style="width:220px"></div><textarea id="rtxt" rows="3" style="width:100%" placeholder="What did Static Group include or measure differently?"></textarea>
     <div class="toolbar" style="margin-top:10px"><button id="rsave">Save reconciliation note</button></div>
     ${mine.map(x => `<div class="small">${fmtIso(x.at)} ${esc(x.user)} — <b>${esc(x.category)}</b>${x.rule_id ? " (" + esc(x.rule_id) + ")" : ""}: ${esc(x.text)}</div>`).join("")}</div>`;
  $$("#drawerBody tr[data-u]").forEach(tr => tr.onclick = () => openEvidence(tr.dataset.u, () => openReconcile(r)));
  $("#rsave").onclick = async () => {
    const body = { sheet: r.sheet, row: r.row, item_id: r.item_id, variant: r.variant, description: r.description, historical_qty: r.historical_qty, engine_qty: r.engine_qty, category: $("#rcat").value, rule_id: $("#rrule").value, text: $("#rtxt").value };
    if (!body.text.trim()) return toast("Write what explains the difference");
    await api(P("/reconciliations"), { method: "POST", body }); toast("Reconciliation recorded"); openReconcile(r);
  };
}

/* ================= KNOWLEDGE ================= */
const RCAT = r => { const it = (r.items || []).join(" "); return /TANK|BW-/.test(it) ? "Project Inputs" : /EW-/.test(it) ? "Earthworks" : /WP-/.test(it) ? "Waterproofing" : /BLK|PL-|LINTEL/.test(it) ? "Architectural" : /SRV/.test(it) ? "BOQ & Services" : "Structural"; };
const RCONF = { CONFIRMED: "High — estimator approved", INFERRED: "Medium — repeated in reference projects", ASSUMED: "Low — temporary assumption", UNKNOWN: "None — undecided" };
async function knowledge(main, arg, params) {
  setCrumb("Methodology", "Knowledge");
  const [m, rs] = await Promise.all([cached("knowledge", () => api("/api/knowledge")), cached("rules", () => api("/api/rules"))]);
  let tab = params.t || "methodology";
  main.innerHTML = pageHead("Static Group knowledge base", "How Static Group measures and structures its BOQs — methodology rules, the canonical BOQ item catalogue and the reference projects they were derived from. Quantities are never stored here.") +
    `<nav class="tabs">${[["methodology", "Static Group Methodology", rs.length], ["catalog", "BOQ Item Catalogue", m.items.length], ["refs", "Reference Projects", S.projects.filter(p => p.historical_boq).length]].map(([k, l, n]) => `<a href="#/knowledge?t=${k}" class="${k === tab ? "on" : ""}">${l}<span class="n">${n}</span></a>`).join("")}</nav><div id="kb"></div>`;
  const kb = $("#kb");
  if (tab === "methodology") {
    const cats = ["Structural", "Architectural", "Earthworks", "Waterproofing", "BOQ & Services", "Project Inputs"];
    kb.innerHTML = cats.map(c => { const rows = rs.filter(r => RCAT(r) === c); if (!rows.length) return "";
      return `<div class="section-title">${c} <span class="count">${rows.length} rules</span></div>` + table([{ t: "Rule", f: r => `<b>${esc(r.title)}</b><div class="small">${esc(r.description)}</div>`, sv: r => r.title }, { t: "Status", f: r => ruleBadge(r.status), sv: r => r.status },
        { t: "Source — historical evidence", f: r => `<span class="small">${esc(r.evidence || "")}</span>` }, { t: "Confidence", f: r => `<span class="small">${RCONF[r.status]}</span>` }, { t: "Version", f: r => `v${r.version}`, num: 1 },
        { t: "Last updated", f: r => `<span class="small">${r.history?.length ? fmtIso(r.history[r.history.length - 1].at) : "Seed definition"}</span>` }, { t: "Approved by", f: r => r.approved_by ? `${esc(r.approved_by)}<div class="small">${fmtIso(r.approved_at)}</div>` : '<span class="small">—</span>' }], rows, { onclick: r => location.hash = "#/rules?r=" + r.rule_id }); }).join("");
  } else if (tab === "catalog") {
    const cats = [...new Set(m.items.map(i => i.category))];
    kb.innerHTML = `<div class="toolbar"><select id="kc" aria-label="Category"><option value="">All categories</option>${cats.map(c => `<option>${esc(c)}</option>`).join("")}</select><select id="ka" aria-label="Automation"><option value="">All automation statuses</option>${m.statuses.map(s => `<option>${esc(s)}</option>`).join("")}</select><span class="small">${m.items.length} canonical items, model v${esc(m.version)}</span></div><div id="kt"></div>`;
    const draw = () => { const c = $("#kc").value, a = $("#ka").value; const rows = m.items.filter(i => (!c || i.category === c) && (!a || i.automation === a));
      $("#kt").innerHTML = table([{ t: "ID", f: i => `<span class="mono">${esc(i.id)}</span>`, sv: i => i.id }, { k: "category", t: "Category" }, { k: "description", t: "BOQ item" }, { t: "Unit", f: i => esc(UNIT(i.unit)) },
        { t: "Measurement method", f: i => `<span class="small">${esc(i.method || "")}</span>${i.formula ? `<div class="mono small">${esc(i.formula)}</div>` : ""}` },
        { t: "Drawing sources", f: i => `<span class="small">${esc((i.drawing_sources || []).join("; "))}</span>` }, { t: "Automation", f: i => `<span class="small">${esc(i.automation)}</span>` }], rows); };
    $("#kc").onchange = draw; $("#ka").onchange = draw; draw();
  } else {
    const refs = S.projects.filter(p => p.historical_boq);
    const bms = await Promise.all(refs.map(p => api(`/api/projects/${p.id}/benchmark`).catch(() => ({ available: false }))));
    kb.innerHTML = `<div class="sub">Reference projects are past Static Group projects with both drawings and a priced BOQ. They provide the historical evidence behind the methodology rules; their quantities are never reused.</div><div class="grid g2">${refs.map((p, i) => { const b = bms[i];
      return `<div class="card"><div class="eyebrow">Reference project</div><h3 style="font-size:15px;margin-bottom:10px">${esc(p.name)}</h3><div class="kv tight small"><div>Historical BOQ</div><div>${b.available ? esc(b.boq_meta.ref) + " · " + esc((b.boq_meta.date || "").slice(0, 10)) : "—"}</div><div>Drawings</div><div>${p.counts ? n0(p.counts.drawings) : "—"}</div>
        <div>BOQ lines</div><div>${b.available ? `${b.summary.boq_lines} (${b.summary.measured_lines} measured)` : "—"}</div></div>${b.available ? `<div style="margin-top:12px">${legend(Object.fromEntries(Object.entries(b.summary.by_status).map(([k, v]) => [BMS[k]?.[0] || k, v])), { "Exact match": "#1d7048", "Good match": "#5c9c7a", "Difference": "#c98a1a", "Candidates only": "#2b5a8a", "Not automated": "#9aa1a9" })}</div>` : ""}
        <div style="margin-top:12px"><a class="btn sec small" href="#/benchmark?p=${p.id}">${icon("bench")}Open benchmark</a></div></div>`; }).join("")}</div>`;
  }
}

/* ================= RULE APPROVAL ================= */
async function rules(main, arg, params) {
  setCrumb("Methodology", "Rule Approval");
  const rs = await api("/api/rules");
  S.cache.rules = Promise.resolve(rs);
  rs.forEach(r => { r._nItems = new Set(r.impact.map(m => m.item_id + m.variant)).size; r._nProj = new Set(r.impact.map(m => m.project)).size; });
  rs.sort((a, b) => { const au = a.status === "UNKNOWN" ? 0 : 1, bu = b.status === "UNKNOWN" ? 0 : 1; return au !== bu ? au - bu : b._nItems - a._nItems; });
  const topUnknown = rs.filter(r => r.status === "UNKNOWN" && r._nItems > 0)[0];
  const sessList = await api("/api/validation/sessions").catch(() => []);
  const sess = sessList.find(x => !x.finished);
  const inSess = new Set(sess ? sess.summary.reviewed : []);
  const reviewedEver = rs.filter(r => (r.notes || []).length || (r.history || []).length).length;
  const cnt = {}; rs.forEach(r => cnt[r.status] = (cnt[r.status] || 0) + 1);
  let f = params.r ? "" : "";
  main.innerHTML = pageHead("Methodology rule approval", "Each card is one Static Group measurement decision. Unknown rules never choose a value — the engine shows what every option would produce on each project. Approving an option makes it the versioned Static Group method and recalculates every project and benchmark.") +
    (topUnknown ? `<div class="banner info" style="margin-bottom:14px">${icon("alert")}<div><b>Biggest win available:</b> resolving “${esc(topUnknown.title)}” would settle ${topUnknown._nItems} open BOQ line${topUnknown._nItems === 1 ? "" : "s"} across ${topUnknown._nProj} project${topUnknown._nProj === 1 ? "" : "s"} — more than any other undecided rule. <a href="#rule-${esc(topUnknown.rule_id)}">Jump to it</a>. <span class="small">(Rules below are sorted by impact, undecided first — this is a priority hint only; nothing is approved automatically.)</span></div></div>` : "") +
    `<div class="grid g5" style="margin-bottom:14px">${kpi("Confirmed", cnt.CONFIRMED || 0, "approved by an estimator", { cls: cnt.CONFIRMED ? "accent-success" : "" })}${kpi("Inferred", cnt.INFERRED || 0, "from reference projects — not confirmed")}${kpi("Assumed", cnt.ASSUMED || 0, "temporary development assumption")}${kpi("Unknown", cnt.UNKNOWN || 0, "undecided — candidates only", { cls: "accent-warning" })}${kpi("Reviewed / remaining", `${reviewedEver} / ${rs.length - (cnt.CONFIRMED || 0)}`, "reviewed = has an estimator note or decision; remaining = not confirmed")}</div><div class="card" style="margin-bottom:14px" id="vsess">${sess ? `<div class="row wrap"><span class="badge b-dark plain">Validation session open</span><b>${esc(sess.estimator)}</b><span class="small">since ${fmtIso(sess.started)} · ${esc(sess.scope)}</span><span class="spacer"></span><span class="small">This session: ${sess.summary.reviewed.length} reviewed · ${sess.summary.confirmed.length} confirmed · ${sess.summary.rejected.length} rejected · ${sess.summary.kept_unconfirmed.length} kept unconfirmed · ${sess.summary.line_decisions || 0} BOQ line decisions · ${sess.summary.boq_lines_changed} BOQ lines changed by rules</span><button class="ghost small" id="vcancel" title="Close the session as cancelled (decisions already made stay recorded)">Cancel session</button><button class="sec small" id="vfinish">Finish session</button></div>` : `<div class="row wrap"><div style="flex:1;min-width:260px"><b>Estimator validation session</b><div class="small">Start a session before reviewing so every decision, note, recalculation and benchmark change is traced to the estimator and the session. The system never decides a rule.</div></div><input id="vest" value="${esc(S.user)}" aria-label="Estimator name" style="width:180px"><input id="vscope" value="All reference projects" aria-label="Scope" style="width:200px"><button id="vstart">Start validation session</button></div>`}${sessList.filter(x => x.finished).length ? `<details style="margin-top:10px"><summary>Completed sessions (${sessList.filter(x => x.finished).length})</summary>${sessList.filter(x => x.finished).map(x => `<div class="small" style="margin-top:6px"><span class="badge ${x.outcome === "cancelled" ? "b-neutral" : "b-success"} plain">${esc(x.outcome || "completed")}</span> <b>${esc(x.estimator)}</b> · ${fmtIso(x.started)} → ${fmtIso(x.finished)} · ${x.summary.line_decisions || 0} BOQ line decision(s) · reviewed ${x.summary.reviewed.length}, confirmed ${x.summary.confirmed.length} (${esc(x.summary.confirmed.join(", ") || "none")}), rejected ${x.summary.rejected.length}, kept unconfirmed ${x.summary.kept_unconfirmed.length}, unresolved ${x.summary.unresolved.length} · projects recalculated: ${esc(x.summary.recalculations.join(", ") || "none")} · ${x.summary.boq_lines_changed} BOQ lines changed${x.finish_note ? " · " + esc(x.finish_note) : ""}</div>`).join("")}</details>` : ""}</div><div class="toolbar">${seg("rf", [["", "All", rs.length], ...(sess ? [["__remaining", "Remaining in session", rs.filter(r => r.status !== "CONFIRMED" && !inSess.has(r.rule_id)).length]] : []), ...["UNKNOWN", "ASSUMED", "INFERRED", "CONFIRMED"].map(s => [s, s[0] + s.slice(1).toLowerCase(), cnt[s] || 0])], f)}</div><div id="rl"></div>`;
  const projNames = [...new Set(rs.flatMap(r => r.impact.map(m => m.project_name)))];
  const impactFor = (r, o) => projNames.map(pn => { const ms = r.impact.filter(m => m.project_name === pn); let tot = 0, any = false, hist = 0, hasH = false, unit = "";
    ms.forEach(m => { Object.entries(m.candidates || {}).forEach(([k, v]) => { if (k.includes(o) && v != null) { tot += v; any = true; } }); if (m.selected === o) { } if (m.historical != null) { hist += m.historical; hasH = true; } unit = m.unit; });
    if (!any) { const sel = ms.filter(m => r.selected === o && m.value != null); if (sel.length) { tot = sel.reduce((a, m) => a + m.value, 0); any = true; } }
    return any ? `<span>${esc(shortName(pn))}: <b>${n2(tot)}</b> ${esc(UNIT(unit))}${hasH ? ` <span class="small">(BOQ ${n2(hist)})</span>` : ""}</span>` : ""; }).filter(Boolean).join("") || '<span class="small">No computed quantity for this option on the current projects</span>';
  const draw = () => {
    $("#rl").innerHTML = rs.map((r, idx) => ({ r, idx })).filter(({ r }) => f === "__remaining" ? (r.status !== "CONFIRMED" && !inSess.has(r.rule_id)) : (!f || r.status === f)).map(({ r, idx }) => {
      const nItems = new Set(r.impact.map(m => m.item_id + m.variant)).size, nProj = new Set(r.impact.map(m => m.project)).size;
      return `<article class="rule-card" id="rule-${esc(r.rule_id)}"><div class="rc-head"><span class="rule-no">Rule ${String(idx + 1).padStart(2, "0")}</span><div style="flex:1;min-width:0"><h3>${esc(r.title)} <span class="mono small" style="font-weight:400">${esc(r.rule_id)}</span>${inSess.has(r.rule_id) ? ' <span class="badge b-outline plain">Reviewed in this session</span>' : ""}</h3><div class="q">${esc(r.description)}</div></div>
        <div style="text-align:right">${ruleBadge(r.status)}<div class="small" style="margin-top:4px">${{ CONFIRMED: "Confirmed by estimator", INFERRED: "Inferred from historical evidence", ASSUMED: "Assumed temporarily", UNKNOWN: "Undecided" }[r.status]}</div><div class="small">v${r.version}${r.approved_by ? ` · approved by ${esc(r.approved_by)}` : ""}</div></div></div>
        <div class="rc-grid"><div><div class="rc-label">Historical evidence</div><p style="margin:0 0 14px">${esc(r.evidence || "No historical evidence recorded.")}</p>
          <div class="rc-label">Why this matters</div><p style="margin:0 0 14px" class="small">Drives ${nItems} BOQ line${nItems === 1 ? "" : "s"} on ${nProj} project${nProj === 1 ? "" : "s"}: ${(r.items || []).map(x => `<span class="chip">${esc(x)}</span>`).join("")}. ${r.status === "UNKNOWN" ? "Until an option is approved these lines show candidate quantities only." : r.status === "CONFIRMED" ? "Approved — lines using it can be Calculated." : "Until confirmed, lines using it can be at most Estimated (they show Needs Review while other issues remain)."}</p>
          ${r.status !== "CONFIRMED" ? `<div class="rc-label">If it stays unconfirmed</div><p style="margin:0 0 14px" class="small">${r.status === "UNKNOWN" ? `No option is applied: ${nItems} line${nItems === 1 ? " keeps" : "s keep"} candidate quantities and ${nItems === 1 ? "stays" : "stay"} Needs Review (or Missing). No value is chosen for them.` : `Option <b>${esc(r.selected || "—")}</b> keeps being applied, but lines using it can never be Calculated — at best Estimated.`}</p>` : ""}<div class="rc-label">Current methodology</div><div>${r.selected ? `<b>${esc(r.selected)}</b> <span class="small">— ${esc(r.options[r.selected] || "")}</span>` : '<span style="color:var(--error);font-weight:550">No option selected</span>'}</div>
          ${(r.notes || []).length ? `<div class="rc-label" style="margin-top:14px">Notes</div>${r.notes.map(n => `<div class="small">${fmtIso(n.at)} · ${esc(n.user)}: ${esc(n.text)}</div>`).join("")}` : ""}
          ${(r.history || []).length ? `<details style="margin-top:10px"><summary>Version history (${r.history.length})</summary><div class="small">${r.history.map(h => `v${h.version} · ${fmtIso(h.at)} · ${esc(h.user)} · ${esc(h.action)}: ${esc(h.before.selected ?? "none")} → ${esc(h.after.selected ?? "none")} [${esc(h.before.status)} → ${esc(h.after.status)}] ${esc(h.note || "")}`).join("<br>")}</div></details>` : ""}</div>
        <div><div class="rc-label">Options &amp; impact on BOQ</div>${Object.entries(r.options).map(([o, d]) => `<label class="opt ${r.selected === o ? "on" : ""}"><input type="radio" name="opt-${esc(r.rule_id)}" value="${esc(o)}" ${r.selected === o ? "checked" : ""}><div><b class="mono" style="font-size:12.5px">${esc(o)}</b>${r.selected === o ? ' <span class="badge b-dark plain on-tag">Current</span>' : ""}<div class="small" style="color:var(--text-secondary)">${esc(d)}</div></div><div class="impact">${impactFor(r, o)}</div></label>`).join("")}
          ${(r.identical_options || []).map(t => `<div class="flag info small" style="margin-top:4px"><b>${esc(shortName(t.project_name))} · ${esc(t.item_id)}:</b> all options currently give ${n2(t.value)} because ${esc(t.reason)}.</div>`).join("")}</div></div>
        <div class="rc-foot"><input placeholder="Note or reason — recorded with the decision" data-note="${esc(r.rule_id)}" aria-label="Decision note">
          <button data-approve="${esc(r.rule_id)}" title="Make the selected option the CONFIRMED Static Group method and recalculate">${icon("check")}Approve rule</button>
          ${r.status !== "CONFIRMED" ? `<button class="sec" data-keep="${esc(r.rule_id)}" title="Records a review note only. The rule stays ${r.status} and no quantity changes.">Keep unconfirmed</button>` : ""}
          <button class="sec" data-act="note" data-rid="${esc(r.rule_id)}">${icon("note")}Add note</button>
          <button class="danger" data-act="reject" data-rid="${esc(r.rule_id)}" ${r.status === "UNKNOWN" ? "disabled title='Already undecided'" : "title='Return the rule to UNKNOWN: its lines show candidates only'"}>${r.status === "CONFIRMED" ? "Reopen (set UNKNOWN)" : "Reject"}</button>
          <a class="btn ghost" href="#/benchmark">${icon("bench")}View evidence</a>
          ${r.status !== "CONFIRMED" ? `<div class="small" style="flex-basis:100%">“Keep unconfirmed” only records a note — the rule stays <b>${r.status}</b>${r.status === "UNKNOWN" ? " (no option is used; candidates only)" : ` (option ${esc(r.selected || "—")} remains in use, lines stay Estimated)`}. Only “Approve rule” confirms a method.</div>` : ""}</div></article>`; }).join("") || emptyState("rules", "No rules with this status", "Choose another filter.");
    $$(".opt input").forEach(i => i.onchange = () => { const card = i.closest(".rule-card"); $$(".opt", card).forEach(o => o.classList.toggle("on", o.contains(i))); });
    const note = rid => $(`[data-note="${rid}"]`).value;
    const act = async (rid, body, msg, btn) => { btn.disabled = true; btn.innerHTML = `<span class="spinner${btn.classList.contains("sec") || btn.classList.contains("danger") ? " dark" : ""}"></span> Saving…`;
      try { const r = await api(`/api/rules/${rid}`, { method: "POST", body }); invalidate(); toast(`${msg}${r.recalculated?.length ? ` — recalculated ${r.recalculated.map(x => shortName((S.projects.find(p => p.id === x) || {}).name || x)).join(", ")}; ${(r.impact || []).filter(x => x.old_value !== x.new_value || x.old_status !== x.new_status).length} BOQ line(s) changed; ${Object.keys(r.benchmarks || {}).length} benchmark(s) refreshed` : ""}${r.session_id ? " · recorded in session " + r.session_id : ""}`, 9000); refreshChrome(); route(); } catch (e) { toast(e.message, 6000, "error"); route(); } };
    $$("[data-approve]").forEach(b => b.onclick = async () => { const rid = b.dataset.approve; const o = $(`input[name="opt-${rid}"]:checked`)?.value; if (!o) return toast("Select an option first");
      const r = rs.find(x => x.rule_id === rid);
      if (await confirmDialog(`Approve “${r.title}”?`, `Option <b>${esc(o)}</b> becomes the CONFIRMED Static Group method (version ${r.version + 1}). Every project and benchmark is recalculated and the decision is recorded in the audit log with your name.`, "Approve rule")) act(rid, { action: "approve", option: o, note: note(rid) }, "Rule approved", b); });
    $$("[data-keep]").forEach(b => b.onclick = () => { const rid = b.dataset.keep; const r = rs.find(x => x.rule_id === rid); act(rid, { action: "note", note: note(rid) || `Reviewed — kept unconfirmed (${r.status})`, recalculate: false }, `Note recorded — rule stays ${r.status}, no quantity changed`, b); });
    $$("[data-act]").forEach(b => b.onclick = async () => { const rid = b.dataset.rid;
      if (b.dataset.act === "note") { if (!note(rid).trim()) return toast("Write the note first"); return act(rid, { action: "note", note: note(rid), recalculate: false }, "Note added", b); }
      if (await confirmDialog(rs.find(x => x.rule_id === rid).status === "CONFIRMED" ? "Reopen this confirmed rule?" : "Reject this rule?", "The rule returns to UNKNOWN: its lines show candidate quantities only until a new option is approved. The change is versioned and audited.", "Reject rule", true)) act(rid, { action: "reject", note: note(rid) }, "Rule reset to UNKNOWN", b); });
  };
  bindSeg("rf", v => { f = v; draw(); });
  draw();
  if ($("#vstart")) $("#vstart").onclick = async () => { try { await api("/api/validation/sessions", { method: "POST", body: { estimator: $("#vest").value.trim(), scope: $("#vscope").value.trim() } }); toast("Validation session started — decisions are now traced to it"); route(); } catch (e) { toast(e.message, 5000, "error"); } };
  if ($("#vcancel")) $("#vcancel").onclick = async () => { if (!(await confirmDialog("Cancel the validation session?", `The session is closed as <b>cancelled</b>. ${sess.summary.reviewed.length} rule decision(s) and ${sess.summary.line_decisions || 0} BOQ line decision(s) already made in it stay recorded — nothing is undone.`, "Cancel session", true))) return;
    try { await api(`/api/validation/sessions/${sess.id}/finish`, { method: "POST", body: { note: "cancelled", cancelled: true } }); toast("Validation session cancelled"); route(); } catch (e) { toast(e.message, 5000, "error"); } };
  if ($("#vfinish")) $("#vfinish").onclick = async () => { if (!(await confirmDialog("Finish the validation session?", `${sess.summary.reviewed.length} rules reviewed, ${sess.summary.confirmed.length} confirmed, ${sess.summary.unresolved.length} still unconfirmed; ${sess.summary.line_decisions || 0} BOQ line decision(s)${Object.keys(sess.summary.line_decisions_by_action || {}).length ? " (" + Object.entries(sess.summary.line_decisions_by_action).map(([k, v]) => `${v} ${k.toLowerCase().replace("_", " ")}`).join(", ") + ")" : ""}. The session summary is frozen and audited.`, "Finish session"))) return;
    try { await api(`/api/validation/sessions/${sess.id}/finish`, { method: "POST", body: { note: "" } }); toast("Validation session finished and recorded"); route(); } catch (e) { toast(e.message, 5000, "error"); } };
  if (params.r) setTimeout(() => { const el = document.getElementById("rule-" + params.r); if (el) { el.scrollIntoView({ block: "start", behavior: "instant" }); el.style.boxShadow = "0 0 0 2px var(--primary)"; setTimeout(() => el.style.boxShadow = "", 1800); } }, 50);
}



/* ================= CONTROLLED LIVE VALIDATION ================= */
const LS_CLS = { "Accepted by estimator": "b-success", "Corrected by estimator": "b-info", "Rejected by estimator": "b-error", "Kept unconfirmed": "b-neutral", "Awaiting estimator": "b-outline" };
const lsBadge = s => `<span class="badge ${LS_CLS[s] || (String(s).includes("stale") ? "b-warning" : "b-neutral")}">${esc(s)}</span>`;
async function liveTab(main, arg, params) {
  const d = await api(P("/live"));
  const m = d.metrics, props = d.proposals;
  let filt = params.f || "";
  const dep = d.dependencies;
  main.innerHTML = `<div class="banner info">${icon("info")}<div>Estimator-controlled validation. The engine <b>proposes</b> a quantity for each measurable BOQ line; only an estimator <b>ACCEPT</b> or <b>CORRECT</b> produces an estimator-confirmed quantity. Decisions never change methodology rules, engine results or baselines, and are audited${d.session ? "" : ""}. Start a validation session on <a href="#/rules">Rule Approval</a> to group decisions.</div></div>
  <div class="grid g2"><div class="card"><h3>Validation dependencies</h3>${dep.map(x => `<div class="row" style="padding:5px 0;border-bottom:1px solid var(--border)"><span class="badge ${x.ok ? "b-success" : "b-warning"} plain" style="min-width:64px;justify-content:center">${x.ok ? "Ready" : "Missing"}</span><div style="flex:1"><b>${esc(x.item)}</b><div class="small">${esc(x.detail)}</div></div></div>`).join("")}</div>
   <div class="card"><div class="row"><h3 style="margin:0">Validation metrics</h3><span class="spacer"></span><span class="badge b-warning plain">Preliminary</span></div>${m ? `
    <div class="grid g3" style="margin:12px 0">${[["AI-proposed lines", m.total_ai_proposed_lines], ["Accepted", m.accepted], ["Corrected", m.corrected], ["Rejected", m.rejected], ["Unconfirmed", m.unconfirmed], ["Stale decisions", m.stale_decisions]].map(([l, v]) => `<div><div class="small">${l}</div><div style="font-size:20px;font-weight:600">${v}</div></div>`).join("")}</div>
    <div class="kv tight small"><div>Avg |variance|</div><div>${m.average_abs_variance_pct == null ? "— (no correction against an AI quantity yet)" : m.average_abs_variance_pct + " %"}</div><div>Median |variance|</div><div>${m.median_abs_variance_pct == null ? "—" : m.median_abs_variance_pct + " %"}</div><div>Max |variance|</div><div>${m.max_abs_variance_pct == null ? "—" : m.max_abs_variance_pct + " %"}</div>
    <div>Basis</div><div>${esc(m.variance_basis)}</div><div>Rules validated</div><div>${m.rules_validated} of ${m.rules_total} · ${m.rules_unknown} still UNKNOWN</div><div>Estimator review time</div><div>${m.estimator_review_hours == null ? "Not recorded (Pilot tab)" : m.estimator_review_hours + " h"}</div></div>
    <div class="small" style="margin-top:8px">${esc(m.note)}</div>` : '<div class="small">Process the project first.</div>'}</div></div>
  <div class="section-title">AI-proposed BOQ lines <span class="count">${props.length} measurable</span></div>
  <div class="toolbar">${seg("lvf", [["", "All", props.length], ["await", "Awaiting estimator", props.filter(p => !p.decision).length], ["decided", "Decided", props.filter(p => p.decision && !p.decision_stale).length], ["stale", "Stale", props.filter(p => p.decision_stale).length], ["unknown", "UNKNOWN rule", props.filter(p => p.unknown_rules.length).length]], filt)}</div>
  <div id="lvt"></div>
  <div class="section-title">Baselines &amp; revision comparison <span class="count">${d.baselines.length}</span></div>
  <div class="grid g2"><div class="card"><h3>Create a baseline (read-only once created)</h3><div class="mapping"><label for="bl-src">Source</label><select id="bl-src"><option value="historical_boq">Static Group historical BOQ (reference projects)</option><option value="client_boq">Imported client / existing BOQ</option><option value="estimator_decisions">Estimator-approved quantities (ACCEPT / CORRECT)</option></select>
     <label for="bl-rev">Drawing revision of the baseline</label><input id="bl-rev" placeholder="e.g. Tender issue, Rev 0 — as on the title blocks"><label for="bl-label">Label</label><input id="bl-label" placeholder="optional"></div><div class="toolbar" style="margin-top:10px"><button id="bl-go">${icon("plus")}Create baseline</button></div></div>
   <div class="card"><h3>Baselines</h3>${d.baselines.length ? d.baselines.map(b => `<div class="row" style="padding:6px 0;border-bottom:1px solid var(--border)"><div style="flex:1"><b>${esc(b.label)}</b><div class="small">${esc(b.source)} · revision ${esc(b.revision || "not recorded")} · ${b.lines} lines · ${fmtIso(b.created)} by ${esc(b.created_by)}</div></div><button class="sec small" data-cmp="${esc(b.baseline_id)}">Compare with latest run</button></div>`).join("") : '<div class="small">No baseline yet. A baseline is never overwritten; create a new one for each reference set.</div>'}</div></div>
  <div id="cmp"></div>
  <details style="margin-top:20px"><summary>Drawing register (${d.register.length}) — number, revision, title, source, upload, status</summary><div class="small" style="margin:8px 0">Numbers and titles parsed from file names are labelled as such; revisions stay "not recorded" until entered from the title block.</div><div id="reg"></div></details>`;
  const draw = () => {
    const rows = props.filter(p => !filt || (filt === "await" ? !p.decision : filt === "decided" ? p.decision && !p.decision_stale : filt === "stale" ? p.decision_stale : p.unknown_rules.length));
    $("#lvt").innerHTML = table([{ t: "BOQ line", f: p => `<b>${esc(p.description)}</b><div class="small mono">${esc(p.item_id)}${p.variant ? " · " + esc(p.variant) : ""}</div>`, sv: p => p.item_id + p.variant },
      { t: "AI quantity", num: 1, f: p => p.ai_quantity != null ? `<b>${n2(p.ai_quantity)}</b> ${esc(UNIT(p.unit))}` : Object.keys(p.candidates).length ? '<span class="small">candidates only</span>' : '<span class="small">—</span>', sv: p => p.ai_quantity ?? -1 },
      { t: "AI status", f: p => dsBadge(p.ai_display_status), sv: p => p.ai_display_status },
      { t: "Rules", f: p => p.rules.map(r => ruleBadge(r.status)).join(" ") || '<span class="small">none</span>' },
      { t: "Drawings", f: p => `<span class="small">${p.drawings.slice(0, 3).map(x => esc((x.drawing_number || x.file || x.drawing_id) + " rev " + (x.revision || "n/r"))).join("<br>")}${p.drawings.length > 3 ? `<br>+${p.drawings.length - 3}` : ""}</span>` },
      { t: "Estimator", f: p => `${lsBadge(p.line_status)}${p.estimator_quantity != null ? `<div class="small tnum">${n2(p.estimator_quantity)} ${esc(UNIT(p.unit))}</div>` : ""}`, sv: p => p.line_status },
      { t: "", f: () => '<span class="btn sec small">Decide</span>' }], rows, { onclick: lineDecision });
  };
  bindSeg("lvf", v => { filt = v; draw(); }); draw();
  $("#bl-go").onclick = async () => { const b = $("#bl-go"); b.disabled = true;
    try { const r = await api(P("/live/baselines"), { method: "POST", body: { source: $("#bl-src").value, revision: $("#bl-rev").value, label: $("#bl-label").value } }); toast(`Baseline created (${Object.keys(r.lines).length} lines) — read-only from now on`); route(); } catch (e) { toast(e.message, 6000, "error"); b.disabled = false; } };
  $$("[data-cmp]").forEach(b => b.onclick = () => showCompare(b.dataset.cmp));
  $("#reg").innerHTML = table([{ t: "Drawing number", f: r => `<input data-rg="${esc(r.drawing_id)}" data-k="drawing_number" value="${esc(r.drawing_number || "")}" style="width:120px" aria-label="Drawing number"><div class="small">${esc(r.drawing_number_source)}</div>` },
    { t: "Revision", f: r => `<input data-rg="${esc(r.drawing_id)}" data-k="revision" value="${esc(r.revision || "")}" placeholder="not recorded" style="width:90px" aria-label="Revision">` },
    { t: "Title", f: r => `<input data-rg="${esc(r.drawing_id)}" data-k="title" value="${esc(r.title || "")}" style="width:220px" aria-label="Title">` },
    { t: "Source file", f: r => `<span class="small">${esc(r.source_file)}</span>` }, { t: "Uploaded", f: r => `<span class="small">${r.uploaded_at ? fmtIso(r.uploaded_at) : esc(r.registration)}</span>` },
    { k: "status", t: "Status" }, { t: "", f: r => `<button class="ghost small" data-rgs="${esc(r.drawing_id)}">Save</button>` }], d.register);
  setTimeout(() => $$("[data-rgs]").forEach(b => b.onclick = async ev => { ev.stopPropagation(); const id = b.dataset.rgs; const body = {}; $$(`[data-rg="${id}"]`).forEach(i => body[i.dataset.k] = i.value);
    try { await api(P(`/live/drawings/${id}`), { method: "POST", body }); toast("Drawing register updated (audited)"); } catch (e) { toast(e.message, 5000, "error"); } }), 50);
  if (params.cmp) showCompare(params.cmp);
}
async function showCompare(bid) {
  const c = await api(P(`/live/baselines/${bid}/compare`));
  const CH = { added: "b-info", omitted: "b-error", changed: "b-warning", unchanged: "b-success" };
  let f = "";
  const box = $("#cmp");
  box.innerHTML = `<div class="card flush" style="margin-top:16px"><div class="card-head"><div><h3>Revision comparison</h3><div class="small">Baseline “${esc(c.baseline.label)}” (revision ${esc(c.baseline.revision || "not recorded")}) vs latest run ${esc(c.new_run)} · new drawing revisions: ${esc(c.new_drawing_revisions.join(", "))}. ${esc(c.note)}</div></div></div>
    <div class="card-body">${seg("cmpf", [["", "All", c.rows.length], ...Object.entries(c.summary).map(([k, v]) => [k, k[0].toUpperCase() + k.slice(1), v])], "")}</div><div id="cmpt" style="padding:0 16px 16px"></div></div>`;
  const draw = () => { $("#cmpt").innerHTML = table([{ t: "BOQ line", f: r => `<b>${esc(r.description)}</b><div class="small mono">${esc(r.item_id)}${r.variant ? " · " + esc(r.variant) : ""}</div>` },
    { t: "Change", f: r => `<span class="badge ${CH[r.change] || "b-neutral"}">${esc(r.change)}</span>`, sv: r => r.change },
    { t: "Baseline", num: 1, f: r => r.baseline_quantity == null ? "—" : n2(r.baseline_quantity) }, { t: "New AI", num: 1, f: r => r.new_ai_quantity != null ? n2(r.new_ai_quantity) : Object.keys(r.candidates || {}).length ? '<span class="small">candidates</span>' : "—" },
    { t: "Delta", num: 1, f: r => r.delta == null ? "—" : `${n2(r.delta)}<div class="small">${pct(r.delta_pct)}</div>`, sv: r => Math.abs(r.delta_pct ?? 0) },
    { t: "Estimator", num: 1, f: r => r.estimator_quantity == null ? "—" : n2(r.estimator_quantity) }, { t: "Variance (est − AI)", num: 1, f: r => r.variance == null ? "—" : n2(r.variance) },
    { t: "Status", f: r => `${lsBadge(r.status)}${r.ai_status ? `<div style="margin-top:3px">${dsBadge(r.ai_status)}</div>` : ""}` }, { t: "Rule", f: r => r.rules.map(x => ruleBadge(x.status) + `<span class="small"> ${esc(x.title || x.rule_id)}</span>`).join("<br>") },
    { t: "Evidence / revision", f: r => `<span class="small">${esc(r.evidence?.formula || "")}${r.drawing_revisions.length ? "<br>" + esc(r.drawing_revisions.slice(0, 3).join(", ")) : ""}${r.baseline_refs.length ? "<br>baseline: " + esc(r.baseline_refs[0]) : ""}</span>` }],
    c.rows.filter(r => !f || r.change === f)); };
  bindSeg("cmpf", v => { f = v; draw(); }); draw();
  box.scrollIntoView({ block: "start", behavior: "instant" });
}
async function lineDecision(p) {
  const d = p.decision;
  openSheet(`<div class="sheet-head"><div class="eyebrow">Estimator decision · ${esc(p.item_id)}${p.variant ? " · " + esc(p.variant) : ""}</div><h2>${esc(p.description)}</h2><div class="row wrap" style="margin-top:8px">${dsBadge(p.ai_display_status)}${lsBadge(p.line_status)}</div></div>
   <div class="sheet-section"><h4>AI proposal (run ${esc(p.run_id)})</h4><div class="qty-hero"><div><div class="small">AI quantity</div><div class="v">${p.ai_quantity != null ? n2(p.ai_quantity) : "—"}<span class="u">${esc(UNIT(p.unit))}</span></div></div><div><div class="small">Confidence state</div><div style="font-size:15px;font-weight:600">${esc(p.ai_display_status)}${p.confidence != null ? ` · ${Math.round(p.confidence * 100)} %` : ""}</div></div></div>
    ${p.ai_quantity == null ? `<div class="flag info small" style="margin-top:10px">No AI quantity to accept${p.unknown_rules.length ? ` — methodology rule ${esc(p.unknown_rules.join(", "))} is UNKNOWN (candidates only)` : ""}. You can CORRECT with your own quantity or KEEP UNCONFIRMED. A correction does not change the rule.</div>` : ""}
    ${Object.keys(p.candidates).length ? `<table class="plain" style="margin-top:8px"><tbody>${Object.entries(p.candidates).map(([k, v]) => `<tr><td class="small">${esc(k)}</td><td class="num">${n2(v)}</td></tr>`).join("")}</tbody></table>` : ""}</div>
   <div class="sheet-section"><h4>Evidence</h4><div class="kv tight small"><div>Rules</div><div>${p.rules.map(r => `${ruleBadge(r.status)} ${esc(r.title || r.rule_id)}${r.option ? " · " + esc(r.option) : ""}`).join("<br>") || "none"}</div><div>Formula</div><div class="mono">${esc(p.evidence.formula || "")}</div>
    <div>Source</div><div>${p.evidence.evidence.map(esc).join("<br>")}</div><div>Drawings</div><div>${p.drawings.map(x => esc((x.drawing_number || x.file) + " rev " + (x.revision || "not recorded"))).join("<br>") || "—"}</div><div>Missing</div><div>${esc(p.missing.join("; ") || "—")}</div></div>
    <div style="margin-top:8px"><a class="btn sec small" href="#/project/boq" onclick="closeDrawer()">${icon("boq")}Open BOQ evidence</a></div></div>
   <div class="sheet-section"><h4>Decision</h4>
    <div class="mapping" style="grid-template-columns:minmax(110px,150px) minmax(0,1fr)"><label for="ld-q">Estimator quantity</label><input id="ld-q" type="number" min="0" step="0.001" placeholder="required for CORRECT"><label for="ld-c">Comment</label><textarea id="ld-c" rows="2" placeholder="required for CORRECT"></textarea><label for="ld-r">Rejection reason</label><input id="ld-r" placeholder="required for REJECT"></div>
    <div class="row wrap" style="margin-top:12px"><button data-la="ACCEPT" ${p.ai_quantity == null ? "disabled title='No AI quantity to accept'" : ""}>${icon("check")}Accept</button><button class="sec" data-la="CORRECT">Correct</button><button class="danger" data-la="REJECT">Reject</button><button class="ghost" data-la="KEEP_UNCONFIRMED">Keep unconfirmed</button></div>
    <div class="small" style="margin-top:8px">Accept records your approval of the AI quantity. Correct records your quantity, the AI quantity and the variance. Reject and Keep unconfirmed never produce a quantity.</div></div>
   ${d ? `<div class="sheet-section"><h4>Latest decision</h4><div class="small">${esc(d.action)} by ${esc(d.user)} · ${fmtIso(d.at)} · v${d.version}${d.final_quantity != null ? ` · ${n2(d.final_quantity)} ${esc(UNIT(d.unit))}` : ""}${d.variance != null ? ` · variance ${n2(d.variance)} (${pct(d.variance_pct)})` : ""}${d.comment ? ` · “${esc(d.comment)}”` : ""}${d.reason ? ` · reason: ${esc(d.reason)}` : ""}${p.decision_stale ? '<br><b style="color:var(--warning)">Stale: the AI quantity changed since this decision — decide again.</b>' : ""}</div></div>` : ""}`, true);
  $$("[data-la]").forEach(b => b.onclick = async () => {
    const action = b.dataset.la, body = { item_id: p.item_id, variant: p.variant, action, estimator_quantity: $("#ld-q").value === "" ? null : +$("#ld-q").value, comment: $("#ld-c").value, reason: $("#ld-r").value };
    if (action === "ACCEPT" && !(await confirmDialog("Accept the AI quantity?", `Records your approval of <b>${n2(p.ai_quantity)} ${esc(UNIT(p.unit))}</b> for this line (audited). The engine result and the methodology rules are not changed.`, "Accept"))) return;
    b.disabled = true;
    try { const r = await api(P("/live/lines"), { method: "POST", body }); toast(`${r.line_status}${r.final_quantity != null ? ` — ${n2(r.final_quantity)} ${UNIT(r.unit)}` : ""}${r.session_id ? " · session " + r.session_id : ""}`, 6000); closeDrawer(); route(); }
    catch (e) { toast(e.message, 7000, "error"); b.disabled = false; }
  });
}

/* ================= PILOT MEASUREMENT ================= */
async function pilotTab(main) {
  const [r, items] = await Promise.all([api(P("/pilot")), cached("items", () => api(P("/items")))]);
  const rec = r.record, a = r.automated, fx = v => v == null ? '<span class="small">—</span>' : n2(v);
  const sec = s => s == null ? "—" : s < 120 ? `${n0(s)} s` : `${(s / 60).toFixed(1)} min`;
  const num = (sect, k, label) => `<label for="pl-${sect}-${k}">${label}</label><input id="pl-${sect}-${k}" data-sec="${sect}" data-k="${k}" type="number" min="0" step="0.25" value="${rec[sect][k] ?? ""}">`;
  const qty = rec.quantities.slice();
  const opts = items.filter(i => i.unit !== "item").map(i => [i.item_id + "|" + i.variant, `${i.item_id}${i.variant ? " " + i.variant : ""} — ${i.description.slice(0, 50)}`]);
  main.innerHTML = `<div class="banner info">${icon("info")}<div>Live-pilot record for a real project: manual take-off vs this system. Manual figures are entered by Static Group; automated figures are read from the application. A difference appears only when both values exist. <b>No accuracy percentage or time-saving figure is produced</b> until real manual data has been entered and reviewed.</div></div>
  <div class="grid g2"><div class="card"><h3>Manual process (entered)</h3><div class="mapping">${num("manual", "takeoff_hours", "Manual take-off (h)")}${num("manual", "boq_hours", "Manual BOQ preparation (h)")}${num("manual", "review_hours", "Manual review (h)")}${num("manual", "missing_items_found", "Missing items found manually")}${num("manual", "corrections", "Manual corrections")}</div></div>
   <div class="card"><h3>Automated process</h3><div class="kv tight small"><div>Drawing processing</div><div>${sec(a.processing_seconds)} <span class="mono">${esc(a.processing_run || "")}</span></div><div>Quantity calculation</div><div>${sec(a.calculation_seconds)} <span class="mono">${esc(a.calculation_run || "")}</span></div><div>BOQ generation</div><div>${a.boq_generation_seconds == null ? "—" : a.boq_generation_seconds + " s"}</div>
     <div>BOQ lines</div><div>${a.boq_lines} — ${Object.entries(a.boq_status).map(([k, v]) => `${esc(k)} ${v}`).join(" · ")}</div><div>Missing-information lines</div><div>${a.missing_lines}</div><div>Audited corrections</div><div>${a.corrections}</div><div>Review decisions</div><div>${a.review_decisions}</div><div>Methodology rules</div><div>${a.rules_confirmed} confirmed · ${a.rules_unconfirmed} unconfirmed</div></div>
     <div class="mapping" style="margin-top:12px">${num("automated", "estimator_review_hours", "Estimator review (h)")}${num("automated", "accepted_quantities", "Quantities accepted by estimator")}${num("automated", "rejected_quantities", "Quantities rejected by estimator")}</div></div></div>
  <div class="card flush" style="margin-top:16px"><div class="card-head"><h3>Manual vs automated</h3><span class="small">differences only where both values exist</span></div><div class="tablewrap" style="max-height:none;border:0"><table><thead><tr><th>Category</th><th class="num">Manual</th><th class="num">Automated</th><th class="num">Difference</th><th>Basis</th></tr></thead><tbody>
   ${r.comparison.map(c => `<tr><td>${esc(c.category)}</td><td class="num">${fx(c.manual)}</td><td class="num">${fx(c.automated)}</td><td class="num">${fx(c.difference)}</td><td class="small">${esc(c.note)}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="card" style="margin-top:16px"><div class="row" style="margin-bottom:10px"><h3 style="margin:0">Quantity comparison</h3><span class="spacer"></span><button class="sec small" id="pl-addq">${icon("plus")}Add item</button></div><div id="pl-q"></div>
   <div class="small" style="margin-top:8px">A variance against a value that is not final (Needs Review) is shown for investigation only — it is not an accuracy measure.</div></div>
  <div class="card" style="margin-top:16px"><h3>Revision handling</h3><div class="row wrap" style="margin-bottom:10px"><span class="badge b-warning">${esc(r.revision.state)}</span></div>
   <div class="row wrap"><label class="small"><input type="checkbox" id="pl-rev" ${rec.revision.real_revision_received ? "checked" : ""}> Real revised drawing set received</label><label class="small"><input type="checkbox" id="pl-revman" ${rec.revision.manual_review_required ? "checked" : ""}> Manual review required</label></div>
   ${r.revision.latest_comparison ? `<div class="small" style="margin-top:8px">Latest run comparison ${esc(r.revision.latest_comparison.old)} → ${esc(r.revision.latest_comparison.new)}: ${r.revision.latest_comparison.summary.drawings_changed} drawings, +${r.revision.latest_comparison.summary.elements_added}/−${r.revision.latest_comparison.summary.elements_removed} elements (${r.revision.latest_comparison.summary.elements_modified} modified), ${r.revision.latest_comparison.summary.boq_items_changed} BOQ lines changed. <a href="#/project/changes">Open changes</a></div>` : ""}
   <textarea id="pl-revnotes" rows="2" style="width:100%;margin-top:10px" placeholder="Revision notes">${esc(rec.revision.notes || "")}</textarea></div>
  <div class="card" style="margin-top:16px"><h3>Pilot notes</h3><textarea id="pl-notes" rows="3" style="width:100%">${esc(rec.notes || "")}</textarea>${rec.updated ? `<div class="small" style="margin-top:6px">Last updated ${fmtIso(rec.updated)} by ${esc(rec.updated_by)}</div>` : ""}</div>
  <div class="toolbar" style="margin-top:16px"><button id="pl-save">Save pilot record</button></div>`;
  const drawQ = () => {
    const by = Object.fromEntries(r.quantities.map(q => [q.item_id + "|" + q.variant, q]));
    $("#pl-q").innerHTML = qty.length ? `<div class="tablewrap" style="max-height:none"><table><thead><tr><th>BOQ item</th><th class="num">Manual qty</th><th class="num">Automated</th><th>Status</th><th class="num">Difference</th><th class="num">Variance</th><th>Note</th><th></th></tr></thead><tbody>${qty.map((q, i) => { const c = by[q.item_id + "|" + (q.variant || "")] || {};
      return `<tr><td><select data-qi="${i}" data-qk="key" style="max-width:300px">${opts.map(([v, l]) => `<option value="${esc(v)}" ${v === q.item_id + "|" + (q.variant || "") ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></td>
        <td class="num"><input data-qi="${i}" data-qk="manual_qty" type="number" min="0" step="0.01" value="${q.manual_qty ?? ""}" style="width:100px"></td><td class="num">${fx(c.automated_qty)}${c.automated_qty == null && Object.keys(c.candidates || {}).length ? '<div class="small">candidates only</div>' : ""}</td>
        <td>${c.automated_status ? dsBadge(RAW2DS[c.automated_status] || c.automated_status) : '<span class="small">save to compare</span>'}</td><td class="num">${fx(c.difference)}</td><td class="num">${c.variance_pct == null ? "—" : pct(c.variance_pct)}${c.variance_pct != null && !c.automated_final ? '<div class="small">not final</div>' : ""}</td>
        <td><input data-qi="${i}" data-qk="note" value="${esc(q.note || "")}" style="width:160px"></td><td><button class="ghost small" data-qdel="${i}" aria-label="Remove">${icon("x")}</button></td></tr>`; }).join("")}</tbody></table></div>` : '<div class="small">No quantities entered. Add the BOQ items measured manually (e.g. footings, beams, slabs) with the manual quantity.</div>';
    $$("[data-qdel]").forEach(b => b.onclick = () => { collect(); qty.splice(+b.dataset.qdel, 1); drawQ(); });
  };
  const collect = () => $$("[data-qi]").forEach(el => { const q = qty[+el.dataset.qi]; if (el.dataset.qk === "key") { const [id, v] = el.value.split("|"); q.item_id = id; q.variant = v || ""; } else q[el.dataset.qk] = el.dataset.qk === "manual_qty" ? (el.value === "" ? null : +el.value) : el.value; });
  drawQ();
  $("#pl-addq").onclick = () => { collect(); const [id, v] = (opts[0] || ["|"])[0].split("|"); qty.push({ item_id: id, variant: v || "", manual_qty: null, note: "" }); drawQ(); };
  $("#pl-save").onclick = async () => {
    collect();
    const body = { manual: {}, automated: {}, quantities: qty, revision: { real_revision_received: $("#pl-rev").checked, manual_review_required: $("#pl-revman").checked, notes: $("#pl-revnotes").value }, notes: $("#pl-notes").value };
    $$("[data-sec]").forEach(i => body[i.dataset.sec][i.dataset.k] = i.value === "" ? null : +i.value);
    $("#pl-save").disabled = true;
    try { await api(P("/pilot"), { method: "POST", body }); toast("Pilot record saved and audited"); route(); } catch (e) { toast(e.message, 5000, "error"); $("#pl-save").disabled = false; }
  };
}

/* ================= PROJECT INPUTS ================= */
async function inputs(main) {
  const inp = await api(P("/inputs"));
  const tanks = inp.tanks || [];
  const bw = inp.boundary_wall || {};
  const BWF = { length: "Length (m)", height: "Height (m)", footing_w: "Strip footing width (m)", footing_t: "Strip footing thickness (m)", exc_depth: "Excavation depth (m)", gb_w: "Ground beam width (m)", gb_d: "Ground beam depth (m)", col_w: "Column width (m)", col_d: "Column depth (m)", col_spacing: "Column spacing (m)", neck_h: "Neck column height (m)", stiff_w: "Stiffener beam width (m)", stiff_d: "Stiffener beam depth (m)", block_t: "Block thickness (m)" };
  const TF = { name: "Name", L: "Internal L (m)", W: "Internal W (m)", H: "Internal H (m)", wall_t: "Wall t (m)", base_t: "Base t (m)", slab_t: "Cover slab t (m)", blinding_t: "Blinding t (m)", blinding_projection: "Blinding proj. (m)" };
  main.innerHTML = `<div class="banner info">${icon("info")}<div>Project information the drawings do not provide in machine-readable form. Every value is labelled <b>User input</b> on the quantities it drives and recorded in the audit log. Leave a field empty if it is not known — the affected lines stay "Missing".</div></div>
  <div class="grid g2"><div class="card"><h3>Ground</h3><div class="mapping"><label for="ngl">Natural ground level (m, project datum)</label><input id="ngl" type="number" step="0.01" value="${inp.natural_ground_level ?? ""}"></div></div>
  <div class="card"><h3>Boundary wall — typical section</h3><div class="mapping" style="grid-template-columns:200px 120px">${Object.entries(BWF).map(([k, l]) => `<label for="bw-${k}">${l}</label><input id="bw-${k}" data-bw="${k}" type="number" step="0.01" value="${bw[k] ?? ""}">`).join("")}</div></div></div>
  <div class="card" style="margin-top:16px"><div class="row" style="margin-bottom:10px"><h3 style="margin:0">Tanks</h3><span class="spacer"></span><button class="sec small" id="addt">${icon("plus")}Add tank</button></div><div id="tk"></div></div>
  <div class="toolbar" style="margin-top:16px"><button id="svi">Save inputs &amp; recalculate</button></div>`;
  const drawT = () => { $("#tk").innerHTML = tanks.length ? `<div class="tablewrap" style="max-height:none"><table><thead><tr>${Object.values(TF).map(l => `<th>${l}</th>`).join("")}<th></th></tr></thead><tbody>${tanks.map((t, i) => `<tr>${Object.keys(TF).map(k => `<td><input data-t="${i}" data-k="${k}" value="${esc(t[k] ?? "")}" style="width:${k === "name" ? 120 : 84}px" aria-label="${TF[k]}"></td>`).join("")}<td><button class="ghost small" data-del="${i}" aria-label="Remove tank">${icon("x")}</button></td></tr>`).join("")}</tbody></table></div>` : `<div class="small">No tanks entered. Add each tank with its internal dimensions from the tank drawings.</div>`;
    $$("[data-del]").forEach(b => b.onclick = () => { tanks.splice(+b.dataset.del, 1); drawT(); }); };
  drawT();
  $("#addt").onclick = () => { $$("[data-t]").forEach(i => { const v = i.value.trim(); tanks[+i.dataset.t][i.dataset.k] = i.dataset.k === "name" ? v : (v === "" ? null : +v); }); tanks.push({ name: `Tank ${tanks.length + 1}` }); drawT(); };
  $("#svi").onclick = async () => {
    $$("[data-t]").forEach(i => { const v = i.value.trim(); tanks[+i.dataset.t][i.dataset.k] = i.dataset.k === "name" ? v : (v === "" ? null : +v); });
    const b = {}; $$("[data-bw]").forEach(i => { if (i.value !== "") b[i.dataset.bw] = +i.value; });
    const body = { natural_ground_level: $("#ngl").value === "" ? null : +$("#ngl").value, tanks, boundary_wall: b };
    $("#svi").disabled = true; $("#svi").innerHTML = '<span class="spinner"></span> Recalculating…';
    try { await api(P("/inputs"), { method: "POST", body }); invalidate(); toast("Inputs saved, quantities recalculated"); refreshChrome(); } catch (e) { toast(e.message, 5000, "error"); }
    $("#svi").disabled = false; $("#svi").textContent = "Save inputs & recalculate";
  };
}

/* ================= NEW PROJECT ================= */
async function newproject(main) {
  setCrumb("Workspace", "Projects", "New project");
  const proj = cur();
  const isNew = proj && proj.role === "new project";
  const files = isNew ? await api(P("/files")).catch(() => ({})) : {};
  const KINDS = [["drawings", "Drawings", ".dxf measured · .dwg measured (needs the free ODA File Converter installed on the server once) · .pdf stored · .zip extracted"], ["schedules", "Schedules", ".dxf / .pdf / .xlsx"], ["specifications", "Specifications", ".pdf / .docx"], ["client_boq", "Client BOQ (optional)", ".xlsx / .csv — compared on the Client BOQ tab"]];
  const steps = ["Create project", "Upload drawings", "Process", "Review", "Generate BOQ", "Export"];
  main.innerHTML = pageHead("New project", "The new project's quantities are calculated from its own drawings and information. Reference projects are used only as methodology evidence — no quantity is copied.", `<a class="btn sec" href="#/projects">${icon("back")}Projects</a>`) +
  `<div class="card" style="margin-bottom:16px"><div class="row wrap" style="gap:6px">${steps.map((s, i) => `<span class="badge ${i === 0 && !isNew ? "b-dark" : i === 1 && isNew ? "b-dark" : "b-outline"} plain">${i + 1}. ${s}</span>${i < steps.length - 1 ? '<span class="small">→</span>' : ""}`).join("")}</div></div>
  <div class="card"><h3>1. Create project</h3><div class="mapping"><label for="np_name">Project name</label><input id="np_name" placeholder="e.g. Mr. X Villa (G+F+PH)"><label for="np_client">Client</label><input id="np_client"><label for="np_loc">Location</label><input id="np_loc">
  <label for="np_rules">CAD standard (rules)</label><select id="np_rules"><option value="rules_villa_std.json">Consultant standard (villa, no basement)</option><option value="rules_ramzi_villa.json">Consultant standard (with basement)</option></select></div>
  <div class="toolbar" style="margin-top:12px"><button id="np_create">${icon("plus")}Create project</button>${isNew ? `<span class="small">Current: <b>${esc(proj.name)}</b></span>` : ""}</div></div>
  ${isNew ? `<div class="grid g2" style="margin-top:16px">${KINDS.map(([k, t, hint], i) => `<div class="card"><h3>${i + 2}. ${t}</h3><div class="small">${hint}</div>
    <div class="toolbar" style="margin-top:10px;flex-wrap:wrap"><input type="file" multiple data-up="${k}" aria-label="${t} — choose files"><label class="btn sec small" style="margin:0">${icon("projects")}Choose folder<input type="file" multiple webkitdirectory data-upd="${k}" aria-label="${t} — choose folder" style="display:none"></label><button class="small" data-upb="${k}">Upload</button></div>
    <div class="small" data-upsel="${k}"></div>
    <div class="small">${(files[k] || []).length} file(s)${(files[k] || []).length ? ": " + (files[k] || []).slice(0, 8).map(f => esc(f.file)).join(", ") : ""}${(files[k] || []).length > 8 ? "…" : ""}</div></div>`).join("")}</div>
  <div class="card" style="margin-top:16px"><h3>Next steps</h3><div class="row wrap"><a class="btn" href="#/processing">${icon("play")}Process drawings</a><a class="btn sec" href="#/project/drawings">Review disciplines</a><a class="btn sec" href="#/project/elements">Review elements</a><a class="btn sec" href="#/project/boq">Generate BOQ</a><a class="btn sec" href="#/project/reviews">Review exceptions</a><a class="btn sec" href="${P("/export/static-boq")}">${icon("export")}Export</a></div></div>` : `<div class="banner info" style="margin-top:16px">${icon("info")}<div>Create a project (or select one created here) to upload its documents.</div></div>`}`;
  $("#np_create").onclick = async () => {
    const name = $("#np_name").value.trim(); if (!name) return toast("Enter a project name");
    try { const p = await api("/api/projects", { method: "POST", body: { name, client: $("#np_client").value, location: $("#np_loc").value, rules_file: $("#np_rules").value, mode: "upload" } });
      S.pid = p.id; localStorage.setItem("pid", p.id); await init(); location.hash = "#/newproject"; toast("Project created"); } catch (e) { toast(e.message, 5000, "error"); }
  };
  const selLabel = k => { const fInp = $(`[data-up="${k}"]`), dInp = $(`[data-upd="${k}"]`); const n = fInp.files.length + dInp.files.length;
    $(`[data-upsel="${k}"]`).textContent = n ? `${n} file(s) selected${dInp.files.length ? ` (folder: ${esc(dInp.files[0]?.webkitRelativePath?.split("/")[0] || "")})` : ""}` : ""; };
  $$("[data-up]").forEach(inp => inp.onchange = () => selLabel(inp.dataset.up));
  $$("[data-upd]").forEach(inp => inp.onchange = () => selLabel(inp.dataset.upd));
  $$("[data-upb]").forEach(b => b.onclick = async () => {
    const k = b.dataset.upb;
    const fInp = $(`[data-up="${k}"]`), dInp = $(`[data-upd="${k}"]`);
    const all = [...fInp.files, ...dInp.files];
    if (!all.length) return toast("Choose files or a folder first");
    const fd = new FormData(); all.forEach(f => fd.append("files", f, f.webkitRelativePath || f.name));
    try { b.disabled = true; b.innerHTML = '<span class="spinner"></span>';
      const r = await api(P(`/upload/${k}`), { method: "POST", body: fd });
      toast(`${r.saved.length} file(s) saved${r.skipped.length ? `, ${r.skipped.length} skipped` : ""}. ${r.notes.join(" ")}`, 8000);
      fInp.value = ""; dInp.value = ""; route();
    } catch (e) { toast(e.message, 5000, "error"); b.disabled = false; b.textContent = "Upload"; }
  });
}

/* ================= ASSISTANT ================= */
const SUGGEST = ["Which projects need attention?", "What information is missing?", "Why is beam concrete different from the historical BOQ?", "Which methodology rules are unknown?", "What changed since yesterday?", "Give me today's management summary"];
async function assistant(main) {
  setCrumb("Intelligence", "Assistant");
  const d = await api("/api/ceo").catch(() => ({ ai_mode: "" }));
  main.innerHTML = `<div style="max-width:920px;margin:0 auto">` + pageHead("Static Group Project Assistant", "Ask about projects, BOQs, quantities, issues and missing information. Answers are assembled from the application's own records and always show their sources — the assistant never measures drawings and never answers from memory.", `<span class="badge b-outline plain">${icon("info")}Mode: ${esc(d.ai_mode || "data only")}</span>`) +
    `<div class="row wrap small" style="margin:-8px 0 16px">Context project: <b style="color:var(--text-primary)">${esc(shortName(cur().name))}</b> <span>· change it in the top bar</span></div>
    <div class="chat" id="chat"></div>
    <div id="sugg" style="margin:18px 0"><div class="small" style="margin-bottom:8px">Try asking</div><div class="suggest">${SUGGEST.map(q => `<button type="button" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div></div>
    <form class="composer" id="cform"><input id="chatq" placeholder="Ask a question about your projects…" autocomplete="off" aria-label="Question"><button type="submit">${icon("send")}Ask</button></form></div>`;
  const render = () => {
    $("#chat").innerHTML = S.chat.map(m => m.q ? `<div class="msg-q">${esc(m.q)}</div>` : m.pending ? `<div class="msg-a"><span class="spinner dark"></span> <span class="small">Querying project data…</span></div>` : m.error ? `<div class="msg-a"><div class="banner warn" style="margin:0">${esc(m.error)}</div></div>` : (() => {
      const cites = [...new Map((m.r.citations || []).map(c => [c.type + c.project + c.ref, c])).values()];
      return `<div class="msg-a"><div class="eyebrow">Answer</div><div class="ans">${esc(m.r.answer)}</div>${(m.r.notes || []).map(n => `<div class="small" style="margin-top:6px">${esc(n)}</div>`).join("")}
        <div class="meta"><span class="lbl">Sources</span>${cites.map((c, ci) => ci === 6 ? `<button type="button" class="ghost small more-src">+${cites.length - 6} more</button>` + srcChip(c, true) : srcChip(c, ci > 6)).join("") || '<span class="small">none</span>'}
        <span class="spacer"></span><span class="small">${(m.r.tool_calls || []).length} data quer${(m.r.tool_calls || []).length === 1 ? "y" : "ies"} · ${esc(m.r.mode)}</span></div></div>`; })()).join("");
    $$("#chat .more-src").forEach(b => b.onclick = () => { b.parentElement.querySelectorAll(".chip.hidden").forEach(x => x.classList.remove("hidden")); b.remove(); });
    $$("#chat a.chip[data-pid]").forEach(a => a.onclick = () => selectProjectQuiet(a.dataset.pid));
    $("#sugg").style.display = S.chat.length ? "none" : "";
    main.parentElement.scrollTop = main.parentElement.scrollHeight;
  };
  const srcChip = (c, hide) => `<a class="chip${hide ? " hidden" : ""}" href="${esc(c.url || "#")}" ${c.project ? `data-pid="${esc(c.project)}"` : ""}>${icon(c.type === "benchmark" ? "bench" : c.type === "rules" ? "rules" : c.type === "review_queue" ? "review" : c.type === "audit" ? "audit" : "doc")}${esc(c.type.replace(/_/g, " "))}${c.project ? " · " + esc(shortName((S.projects.find(p => p.id === c.project) || {}).name || c.project)) : ""}${c.ref ? " · " + esc(String(c.ref).slice(0, 28)) : ""}</a>`;
  const ask = async q => {
    q = (q || "").trim(); if (!q) return; $("#chatq").value = "";
    S.chat.push({ q }); const slot = { pending: true }; S.chat.push(slot); render();
    try { slot.r = await api("/api/chat", { method: "POST", body: { message: q, project: S.pid } }); delete slot.pending; }
    catch (e) { delete slot.pending; slot.error = "The assistant could not answer: " + e.message; }
    render(); $("#chatq").focus();
  };
  $("#cform").onsubmit = e => { e.preventDefault(); ask($("#chatq").value); };
  $$("#sugg [data-q]").forEach(b => b.onclick = () => ask(b.dataset.q));
  render(); $("#chatq").focus();
}

/* ================= DAILY REPORT ================= */
async function report(main) {
  setCrumb("Intelligence", "Daily Report");
  const r = await api("/api/reports/daily");
  const live = r.projects.filter(p => p.processed);
  const crit = live.reduce((a, p) => a + p.critical_issues, 0);
  const attn = live.reduce((a, p) => a + p.items_needing_review + p.items_missing_input, 0);
  const qch = live.reduce((a, p) => a + (p.drawing_changes?.boq_items_changed || 0), 0);
  const large = live.flatMap(p => p.large_variances.map(v => ({ ...v, project: p.name })));
  main.innerHTML = `<div style="max-width:1180px"><div class="report-head"><div><div class="eyebrow">Daily Project Intelligence</div><h1 class="page-title">${new Date(r.date).toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}</h1>
    <div class="page-sub">Generated ${fmtIso(r.generated)} · compared with ${r.compared_with ? "snapshot of " + esc(r.compared_with) : "no earlier snapshot (new / resolved issues appear from the next report)"}</div></div>
    <div class="row no-print"><button class="sec" id="snap">${icon("check")}Save snapshot</button><button class="sec" onclick="window.print()">${icon("print")}Print</button><img src="/static/brand/static-logo.png" alt="STATIC" style="height:30px;margin-left:12px"></div></div>
  <div class="grid g4">${kpi("Critical", crit, "review items needing an engineer decision", { cls: crit ? "accent-error" : "" })}${kpi("Needs attention", attn, "BOQ lines needing review or missing data", { cls: "accent-warning" })}${kpi("Pending decisions", r.pending_approvals.length, "methodology rules to approve", { href: "#/rules" })}${kpi("Quantity changes", qch, "BOQ lines changed vs previous runs")}</div>
  <div class="split" style="margin-top:20px"><div class="card"><h3>Recommended actions</h3><ol class="actions-list">${r.recommended_actions.map(a => `<li>${esc(a)}</li>`).join("")}</ol></div>
    <div class="card"><h3>Large variances vs historical BOQ</h3>${large.length ? large.map(v => `<div style="padding:8px 0;border-bottom:1px solid var(--border)"><div class="row"><b style="flex:1">${esc(v.description.slice(0, 70))}</b><b class="tnum" style="color:${Math.abs(v.diff_pct) >= 50 ? "var(--error)" : "var(--warning)"}">${pct(v.diff_pct)}</b></div><div class="small">${esc(shortName(v.project))} · engine ${n2(v.engine)} vs ${n2(v.historical)} ${esc(UNIT(v.unit))}</div></div>`).join("") : '<div class="small">None ≥ 20 %.</div>'}</div></div>
  <div class="card flush" style="margin-top:20px"><div class="card-head"><h3>Project status</h3></div><div class="tablewrap" style="max-height:none;border:0"><table><thead><tr><th>Project</th><th style="min-width:200px">BOQ lines: calculated/estimated · lump sum/excluded</th><th class="num">Needs review</th><th class="num">Missing</th><th class="num">Open issues</th><th>New / resolved</th><th>Since previous run</th></tr></thead><tbody>
    ${r.projects.map(p => p.processed ? `<tr><td><b>${esc(shortName(p.name))}</b><div class="small">${fmtIso(p.finished)}</div></td><td><div class="progress"><div class="stack thin"><div style="width:${p.items_final / p.boq_items * 100}%;background:#1d7048"></div><div style="width:${p.items_lump_excluded / p.boq_items * 100}%;background:#9aa1a9"></div></div><span class="small tnum">${p.items_final} · ${p.items_lump_excluded} of ${p.boq_items}</span></div></td>
      <td class="num">${p.items_needing_review}</td><td class="num">${p.items_missing_input}</td><td class="num">${p.open_issues}<div class="small">${p.critical_issues} critical</div></td>
      <td class="small">${p.new_issues == null ? "first report" : `+${p.new_issues.length} / −${p.resolved_issues.length}`}</td><td class="small">${p.drawing_changes ? `${p.drawing_changes.drawings_changed} drawings · ${p.drawing_changes.boq_items_changed} BOQ lines` : "—"}</td></tr>` : `<tr><td><b>${esc(shortName(p.name))}</b></td><td colspan="6" class="small">Not processed</td></tr>`).join("")}</tbody></table></div></div>
  <div class="grid g2" style="margin-top:20px"><div class="card"><h3>Missing information</h3>${live.map(p => p.missing_information.length ? `<div style="margin-bottom:10px"><b>${esc(shortName(p.name))}</b><ul class="small" style="margin:4px 0 0;padding-left:18px">${p.missing_information.slice(0, 5).map(m => `<li>${esc(m)}</li>`).join("")}</ul></div>` : "").join("")}</div>
    <div class="card"><h3>Pending methodology decisions</h3>${r.pending_approvals.slice(0, 10).map(a => `<div class="row" style="padding:4px 0">${ruleBadge(a.status)}<span>${esc(a.title)}</span></div>`).join("")}${r.pending_approvals.length > 10 ? `<div class="small" style="margin-top:6px"><a href="#/rules">+ ${r.pending_approvals.length - 10} more on Rule Approval</a></div>` : ""}</div></div>
  <div class="banner info" style="margin-top:20px">${icon("info")}<div>${esc(r.not_measured.join(" "))} No e-mail or Teams delivery is configured. Schedule <span class="mono">python qto_cli.py daily-report</span> to produce this report automatically.</div></div></div>`;
  $("#snap").onclick = async () => { $("#snap").disabled = true; try { await api("/api/reports/daily?save=true"); toast("Report and issue snapshot saved under data/reports"); } catch (e) { toast(e.message, 5000, "error"); } $("#snap").disabled = false; };
}

/* ================= CHANGES ================= */
async function changes(main, arg, params) {
  const runs = await api(P("/runs"));
  if (runs.length < 2) { main.innerHTML = emptyState("changes", "No revision to compare yet", "Implemented — Real Revised Drawing Validation Pending. At least two processing runs are needed: process the project again when a revised drawing set arrives to see added, removed and modified elements, quantity changes, affected BOQ lines and sections, and what needs review."); return; }
  const c = await api(P(`/changes${params.old ? `?old=${params.old}&new=${params.new}` : ""}`));
  const opt = sel => runs.map(r => `<option value="${r.run_id}" ${r.run_id === sel ? "selected" : ""}>${fmtRun(r.run_id)} · ${esc(r.kind || "")}</option>`).join("");
  const s = c.summary || {};
  main.innerHTML = `<div class="banner warn">${icon("alert")}<div><b>Implemented — Real Revised Drawing Validation Pending.</b> Differences between two stored processing runs: drawings added / removed / modified (file size, entity count or extents), elements added / removed / modified, quantity and BOQ-line changes with their status. Results have not yet been checked against a real revised drawing set; treat them as review prompts, not validated changes.</div></div>
  <div class="toolbar"><label class="small" for="ro">Older run</label><select id="ro">${opt(c.old)}</select><label class="small" for="rn">Newer run</label><select id="rn">${opt(c.new)}</select><button id="rc">Compare</button><span class="spacer"></span>${c.available ? `<a class="btn sec" href="${P(`/export/changes?old=${c.old}&new=${c.new}`)}">${icon("export")}Export Changes Report</a>` : ""}</div>
  <div class="grid g4">${kpi("Drawings changed", s.drawings_changed ?? "—")}${kpi("Elements", `+${s.elements_added ?? 0} / −${s.elements_removed ?? 0}`, `${s.elements_modified ?? 0} modified`)}${kpi("BOQ lines changed", s.boq_items_changed ?? "—")}${kpi("Element concrete", n2(s.concrete_new_m3) + " m³", `was ${n2(s.concrete_old_m3)} m³`)}</div>
  <div class="section-title">BOQ impact <span class="count">${(c.items || []).length}</span></div>${table([{ k: "item_id", t: "Item", f: r => `<span class="mono">${esc(r.item_id)}</span>` }, { k: "variant", t: "Variant" }, { k: "description", t: "Description" }, { t: "Unit", f: r => esc(UNIT(r.unit)) },
    { t: "Old", num: true, f: r => n3(r.old), sv: r => r.old ?? -1 }, { t: "New", num: true, f: r => n3(r.new), sv: r => r.new ?? -1 }, { t: "Δ", num: true, f: r => n3(r.delta), sv: r => r.delta ?? 0 }, { t: "Δ %", num: true, f: r => pct(r.delta_pct), sv: r => r.delta_pct ?? 0 },
    { t: "Status", f: r => r.old_status === r.new_status ? dsBadge(RAW2DS[r.new_status] || r.new_status) : `${dsBadge(RAW2DS[r.old_status] || r.old_status || "—")} → ${dsBadge(RAW2DS[r.new_status] || r.new_status || "—")}` }], c.items || [])}
  <div class="grid g2" style="margin-top:16px"><div><div class="section-title" style="margin-top:0">Drawings <span class="count">${(c.drawings || []).length}</span></div>${table([{ k: "drawing", t: "Drawing" }, { k: "change", t: "Change" }, { t: "Detail", f: r => r.fields ? r.fields.map(f => `${f}: ${esc(JSON.stringify(r.old[f]))} → ${esc(JSON.stringify(r.new[f]))}`).join("<br>") : "" }], c.drawings || [])}</div>
  <div><div class="section-title" style="margin-top:0">Elements <span class="count">${(c.elements || []).length}</span></div>${table([{ k: "uid", t: "Element" }, { k: "type", t: "Type" }, { k: "change", t: "Change" },
    { t: "Detail", f: r => Object.entries({ ...(r.dims || {}), ...(r.quantities || {}) }).map(([k, v]) => `${esc(k)}: ${esc(v[0])} → ${esc(v[1])}`).join("<br>") }], c.elements || [], { onclick: r => r.change !== "removed" && openEvidence(r.uid) })}</div></div>`;
  $("#rc").onclick = () => location.hash = `#/project/changes?old=${$("#ro").value}&new=${$("#rn").value}`;
}

/* ================= SEARCH ================= */
function setupSearch() {
  const inp = $("#search"), box = $("#searchResults"); let h;
  inp.oninput = () => { clearTimeout(h); h = setTimeout(async () => {
    if (!inp.value.trim()) return box.classList.add("hidden");
    try { const r = await api(P("/search?q=" + encodeURIComponent(inp.value)));
      box.innerHTML = r.map((x, i) => `<div data-i="${i}" role="option" tabindex="0"><span class="pill">${esc(x.kind)}</span> <b>${esc(x.title)}</b><div class="small">${esc(x.sub)}</div></div>`).join("") || "<div class='small'>No matches in this project</div>";
      box.classList.remove("hidden");
      $$("div[data-i]", box).forEach(d => d.onclick = () => { const x = r[+d.dataset.i]; box.classList.add("hidden");
        if (x.kind === "element") openEvidence(x.id); else if (x.kind === "drawing") location.hash = "#/viewer/" + x.id; else location.hash = "#/project/boq"; });
    } catch (e) { box.innerHTML = "<div class='small'>Search is available once the project is processed</div>"; box.classList.remove("hidden"); } }, 250); };
  document.addEventListener("click", ev => { if (!box.contains(ev.target) && ev.target !== inp) box.classList.add("hidden"); });
}
init();
