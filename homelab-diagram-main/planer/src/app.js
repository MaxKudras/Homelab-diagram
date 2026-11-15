// Planer UI: canvas (pan/zoom/drag/connect/waypoints), inspector forms, lists, IP list, checks,
// save (browser + YAML file), undo/redo, examples, automatic start layout.
"use strict";
const $ = s => document.querySelector(s);
const STORE = "hld-planer-v1", HIST = "hld-planer-verlauf";
let lab = normalize(emptyLab());
let sel = { kind: null, ids: [] };           // kind: device | link | panel | net | meta
let view = { x: 40, y: 20, k: 0.5 };
let undo = [], redo = [], lastSnap = "";
let boxes = {}, ends = new Map(), result = { err: [], warn: [] };
let tab = "draw";

// ------------------------------------------------------------------ state changes
function snap() { return JSON.stringify(lab); }
function commit(msg) {
  const s = snap();
  if (s === lastSnap) return;
  undo.push(lastSnap); if (undo.length > 150) undo.shift();
  redo = []; lastSnap = s; save(); render();
  if (msg) status(msg);
}
function doUndo() { if (!undo.length) return; redo.push(snap()); lab = JSON.parse(undo.pop()); lastSnap = snap(); save(); render(); inspector(); status("Rückgängig"); }
function doRedo() { if (!redo.length) return; undo.push(snap()); lab = JSON.parse(redo.pop()); lastSnap = snap(); save(); render(); inspector(); status("Wiederholt"); }
let saveTimer = null;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem(STORE, JSON.stringify({ ts: Date.now(), lab }));
      const h = JSON.parse(localStorage.getItem(HIST) || "[]");
      if (!h.length || Date.now() - h[0].ts > 120000) { h.unshift({ ts: Date.now(), title: lab.meta.title, lab }); localStorage.setItem(HIST, JSON.stringify(h.slice(0, 20))); }
      $("#saved").textContent = "im Browser gespeichert " + new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
    } catch (e) { $("#saved").textContent = "Speichern im Browser nicht möglich – bitte als Datei sichern"; }
  }, 400);
}
function status(t) { $("#status").textContent = t; }
function setLab(l, msg) {
  lab = normalize(l);
  if (lab.devices.some(d => !d.pos)) autoArrange(lab.devices.every(d => !d.pos));
  undo = []; redo = []; lastSnap = snap(); sel = { kind: null, ids: [] }; save(); render(); fit(); inspector(); status(msg || "geladen");
}

// ------------------------------------------------------------------ automatic start layout (rows by distance to the internet)
function autoArrange(all) {
  const adj = new Map(lab.devices.map(d => [d.id, []]));
  for (const l of lab.links) { if (l.kind === "kvm" || l.kind === "vpn") continue; const [a] = splitEnd(l.a), [b] = splitEnd(l.b); if (adj.has(a) && adj.has(b)) { adj.get(a).push(b); adj.get(b).push(a); } }
  const roots = lab.devices.filter(d => d.role === "isp_router").map(d => d.id);
  if (!roots.length && lab.devices.length) roots.push((lab.devices.find(d => d.role === "firewall") || lab.devices[0]).id);
  const depth = new Map(roots.map(r => [r, 0])), q = [...roots];
  while (q.length) { const c = q.shift(); for (const n of adj.get(c) || []) if (!depth.has(n)) { depth.set(n, depth.get(c) + 1); q.push(n); } }
  const rows = [];
  for (const d of lab.devices) {
    if (!all && d.pos) continue;
    const g = geom(d, lab); const t = g.kind === "server" ? 99 : (depth.has(d.id) ? depth.get(d.id) : 50);
    (rows[t] = rows[t] || []).push(d);
  }
  let y = 324;
  const used = all ? [] : lab.devices.filter(d => d.pos).map(d => boxOf(d, lab));
  if (used.length) y = Math.max(...used.map(b => b.y + b.h)) + 140;
  for (const row of rows.filter(Boolean)) {
    const bs = row.map(d => geom(d, lab));
    const total = bs.reduce((a, g) => a + g.w, 0) + 60 * (row.length - 1);
    const maxW = 2320; let x = Math.max(40, 1200 - Math.min(total, maxW) / 2), h = 0;
    row.forEach((d, i) => {
      if (x + bs[i].w > 40 + Math.max(maxW, total > maxW ? maxW : total) + 600) { x = 40; y += h + 120; h = 0; }
      d.pos = Object.assign({}, d.pos || {}, { x: Math.round(x / GRID) * GRID, y: Math.round(y / GRID) * GRID });
      x += bs[i].w + 60; h = Math.max(h, bs[i].h);
    });
    y += h + 140;
  }
}

// ------------------------------------------------------------------ rendering
function computeBoxes() { boxes = {}; for (const d of lab.devices) if (d.pos) boxes[d.id] = boxOf(d, lab); }
function cx0() {
  const L = lab.layout || {};
  if (L.internet && L.internet.x != null) return +L.internet.x;
  const isp = lab.devices.find(d => d.role === "isp_router" && d.pos);
  if (isp) { const b = boxOf(isp, lab), up = isp.ports.find(p => p.uplink); return b.x + (up ? b.g.port_x[up.id] : b.w / 2); }
  return 1200;
}
function render() {
  computeBoxes();
  ends = cableEnds(lab, boxes);
  result = checks(lab, boxes);
  const errIds = new Set(result.err.map(e => e[0]).filter(Boolean));
  const parts = [];
  const cx = cx0();
  parts.push(drawInternet(lab, cx));
  const isp = lab.devices.find(d => d.role === "isp_router" && boxes[d.id]);
  if (isp) { const b = boxes[isp.id], up = isp.ports.find(p => p.uplink); const x = b.x + (up ? b.g.port_x[up.id] : b.w / 2); parts.push(`<path d="${rounded([[cx, 230], [cx, (230 + b.y - TAB) / 2], [x, (230 + b.y - TAB) / 2], [x, b.y + 28]])}" fill="none" stroke="#6b7a90" stroke-width="3"/>`); }
  for (const p of panelList(lab)) parts.push(drawPanel(p, lab, sel.kind === "panel" && sel.ids.includes(p.key)));
  for (const d of lab.devices) if (boxes[d.id]) parts.push(drawCard(d, boxes[d.id], lab, { sel: sel.kind === "device" && sel.ids.includes(d.id), err: errIds.has(d.id), ports: drag && drag.mode === "connect" }));
  lab.links.forEach((l, i) => {
    const e = ends.get(l); if (!e) return;
    const [ai] = splitEnd(l.a), [bi] = splitEnd(l.b); if (!e[ai] || !e[bi]) return;
    parts.push(drawCable(l, cablePath(e[ai], e[bi], l.via), lab, sel.kind === "link" && sel.ids.includes(i), i));
  });
  parts.push(`<g id="overlay" pointer-events="none">${overlay}</g>`);
  $("#viewport").innerHTML = parts.join("");
  applyView();
  const n = result.err.length, w = result.warn.length;
  $("#tab-check").innerHTML = `Prüfung <b class="${n ? "bad" : w ? "warn" : "ok"}">${n ? n + " Fehler" : w ? w + " Hinweise" : "ok"}</b>`;
  if (tab !== "draw") renderTab();
}
let overlay = "";
function applyView() { $("#viewport").setAttribute("transform", `translate(${view.x},${view.y}) scale(${view.k})`); $("#zoomv").textContent = Math.round(view.k * 100) + " %"; }
function bounds() {
  const bs = Object.values(boxes), ps = panelList(lab);
  const xs = [0, ...bs.map(b => b.x), ...ps.map(p => p.x)], ys = [0, ...bs.map(b => b.y - TAB), ...ps.map(p => p.y)];
  const xe = [2400, ...bs.map(b => b.x + b.w), ...ps.map(p => p.x + p.w)], ye = [400, ...bs.map(b => b.y + b.h), ...ps.map(p => p.y + p.h)];
  return [Math.min(...xs), Math.min(...ys), Math.max(...xe), Math.max(...ye)];
}
function fit() {
  const r = $("#svg").getBoundingClientRect(); const [x0, y0, x1, y1] = bounds();
  view.k = Math.min(r.width / (x1 - x0 + 80), r.height / (y1 - y0 + 80), 1.2);
  view.x = (r.width - (x1 - x0) * view.k) / 2 - x0 * view.k; view.y = 20 - y0 * view.k; applyView();
}
function zoomAt(f, sx, sy) {
  const k = Math.max(0.08, Math.min(3, view.k * f));
  view.x = sx - (sx - view.x) * k / view.k; view.y = sy - (sy - view.y) * k / view.k; view.k = k; applyView();
}
function world(ev) { const r = $("#svg").getBoundingClientRect(); return [(ev.clientX - r.left - view.x) / view.k, (ev.clientY - r.top - view.y) / view.k]; }
const snapv = v => Math.round(v / GRID) * GRID;

// ------------------------------------------------------------------ pointer handling
let drag = null; const pointers = new Map();
function onDown(ev) {
  const svg = $("#svg"); svg.setPointerCapture(ev.pointerId);
  pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
  if (pointers.size === 2) { const [a, b] = [...pointers.values()]; drag = { mode: "pinch", d: Math.hypot(a[0] - b[0], a[1] - b[1]), k: view.k }; return; }
  const t = ev.target, [wx, wy] = world(ev);
  const h = t.closest(".handle"), card = t.closest(".card"), cab = t.closest(".cable"), pan = t.closest(".panel");
  if (h && (h.classList.contains("conn") || h.classList.contains("port"))) {
    drag = { mode: "connect", from: h.dataset.id, port: h.dataset.port || null, x: wx, y: wy }; return;
  }
  if (h && h.classList.contains("via")) { drag = { mode: "via", link: +h.dataset.link, i: +h.dataset.via }; return; }
  if (h && h.classList.contains("resize")) { drag = { mode: "resize", id: h.dataset.id, x: wx, w: boxes[h.dataset.id].w }; return; }
  if (card) {
    const id = card.dataset.id;
    if (ev.shiftKey) { if (sel.kind !== "device") sel = { kind: "device", ids: [] }; sel.ids = sel.ids.includes(id) ? sel.ids.filter(x => x !== id) : sel.ids.concat(id); }
    else if (!(sel.kind === "device" && sel.ids.includes(id))) sel = { kind: "device", ids: [id] };
    drag = { mode: "move", x: wx, y: wy, start: sel.ids.map(i => [i, { ...devOf(lab, i).pos }]), moved: false };
    render(); inspector(); return;
  }
  if (pan) { sel = { kind: "panel", ids: [pan.dataset.panel] }; const p = panelList(lab).find(q => q.key === pan.dataset.panel); drag = { mode: "panel", key: p.key, x: wx, y: wy, px: p.x, py: p.y }; render(); inspector(); return; }
  if (cab) {
    const i = +cab.dataset.link;
    if (ev.detail === 2 || ev.altKey) {                    // double click: add a waypoint
      const l = lab.links[i]; l.via = l.via || [];
      const e = ends.get(l), [ai] = splitEnd(l.a), [bi] = splitEnd(l.b);
      const pts = [e[ai], ...l.via, e[bi]].map(p => [p[0], p[1]]);
      let best = 0, bd = 1e18; for (let k = 0; k < pts.length - 1; k++) { const m = [(pts[k][0] + pts[k + 1][0]) / 2, (pts[k][1] + pts[k + 1][1]) / 2]; const dd = Math.hypot(m[0] - wx, m[1] - wy); if (dd < bd) { bd = dd; best = k; } }
      l.via.splice(best, 0, [snapv(wx), snapv(wy)]); commit("Wegpunkt gesetzt");
    }
    sel = { kind: "link", ids: [i] }; render(); inspector(); return;
  }
  if (ev.shiftKey) { drag = { mode: "marquee", x: wx, y: wy }; return; }
  drag = { mode: "pan", sx: ev.clientX, sy: ev.clientY, vx: view.x, vy: view.y, click: true };
}
let raf = 0;
function onMove(ev) {
  if (pointers.has(ev.pointerId)) pointers.set(ev.pointerId, [ev.clientX, ev.clientY]);
  if (!drag) return;
  const [wx, wy] = world(ev);
  if (drag.mode === "pinch" && pointers.size === 2) { const [a, b] = [...pointers.values()]; const d = Math.hypot(a[0] - b[0], a[1] - b[1]); const r = $("#svg").getBoundingClientRect(); zoomAt(drag.k * d / drag.d / view.k, (a[0] + b[0]) / 2 - r.left, (a[1] + b[1]) / 2 - r.top); return; }
  if (drag.mode === "pan") { view.x = drag.vx + ev.clientX - drag.sx; view.y = drag.vy + ev.clientY - drag.sy; if (Math.abs(ev.clientX - drag.sx) + Math.abs(ev.clientY - drag.sy) > 4) drag.click = false; applyView(); return; }
  if (drag.mode === "move") {
    let dx = wx - drag.x, dy = wy - drag.y; drag.moved = drag.moved || Math.abs(dx) + Math.abs(dy) > 2;
    overlay = "";
    if (drag.start.length === 1) {                            // alignment guides to other cards
      const [id, p0] = drag.start[0], me = boxOf(devOf(lab, id), lab);
      let nx = snapv(p0.x + dx), ny = snapv(p0.y + dy), gx = null, gy = null;
      for (const [oid, o] of Object.entries(boxes)) {
        if (oid === id) continue;
        for (const [a, b] of [[nx, o.x], [nx + me.w, o.x + o.w], [nx + me.w / 2, o.x + o.w / 2], [nx, o.x + o.w + 60], [nx + me.w, o.x - 60]])
          if (Math.abs(a - b) < 7 / view.k + 2) { nx += b - a; gx = b; break; }
        for (const [a, b] of [[ny, o.y], [ny + me.h, o.y + o.h]])
          if (Math.abs(a - b) < 7 / view.k + 2) { ny += b - a; gy = b; break; }
      }
      devOf(lab, id).pos = Object.assign({}, p0, { x: nx, y: ny });
      if (gx != null) overlay += `<line x1="${gx}" y1="-5000" x2="${gx}" y2="20000" stroke="${C.SEL}" stroke-dasharray="6 6" stroke-width="${1.5 / view.k}"/>`;
      if (gy != null) overlay += `<line x1="-5000" y1="${gy}" x2="20000" y2="${gy}" stroke="${C.SEL}" stroke-dasharray="6 6" stroke-width="${1.5 / view.k}"/>`;
    } else for (const [id, p0] of drag.start) devOf(lab, id).pos = Object.assign({}, p0, { x: snapv(p0.x + dx), y: snapv(p0.y + dy) });
  } else if (drag.mode === "panel") {
    lab.layout.panels[drag.key] = { x: snapv(drag.px + wx - drag.x), y: snapv(drag.py + wy - drag.y) };
  } else if (drag.mode === "via") {
    lab.links[drag.link].via[drag.i] = [snapv(wx), snapv(wy)];
  } else if (drag.mode === "resize") {
    const d = devOf(lab, drag.id); d.pos = Object.assign({}, d.pos, { w: Math.max(500, snapv(drag.w + wx - drag.x)) });
  } else if (drag.mode === "connect") {
    overlay = `<line x1="${drag.x}" y1="${drag.y}" x2="${wx}" y2="${wy}" stroke="${C.SEL}" stroke-width="${3 / view.k}" stroke-dasharray="8 6"/>`;
  } else if (drag.mode === "marquee") {
    overlay = `<rect x="${Math.min(drag.x, wx)}" y="${Math.min(drag.y, wy)}" width="${Math.abs(wx - drag.x)}" height="${Math.abs(wy - drag.y)}" fill="${C.SEL}22" stroke="${C.SEL}"/>`;
    drag.wx = wx; drag.wy = wy;
  }
  cancelAnimationFrame(raf); raf = requestAnimationFrame(render);
}
function onUp(ev) {
  pointers.delete(ev.pointerId);
  if (!drag) return;
  const d = drag; drag = null; overlay = "";
  if (d.mode === "pan" && d.click) { sel = { kind: null, ids: [] }; render(); inspector(); return; }
  if (d.mode === "move" && d.moved) { commit("verschoben"); inspector(); return; }
  if (d.mode === "panel" || d.mode === "via" || d.mode === "resize") { commit(); inspector(); return; }
  if (d.mode === "connect") {
    const el = document.elementFromPoint(ev.clientX, ev.clientY);
    const ph = el && el.closest(".handle.port"), card = el && el.closest(".card");
    const to = ph ? ph.dataset.id : card ? card.dataset.id : null;
    if (to && to !== d.from) {
      const a = d.port ? `${d.from}.${d.port}` : d.from, b = ph && ph.dataset.port ? `${to}.${ph.dataset.port}` : to;
      const src = devOf(lab, d.from), net = src.net || (lab.networks[0] || {}).key;
      lab.links.push({ a, b, speed: "1G", net });
      sel = { kind: "link", ids: [lab.links.length - 1] }; commit("Verbindung angelegt"); inspector(); return;
    }
    render(); return;
  }
  if (d.mode === "marquee" && d.wx != null) {
    const x0 = Math.min(d.x, d.wx), x1 = Math.max(d.x, d.wx), y0 = Math.min(d.y, d.wy), y1 = Math.max(d.y, d.wy);
    sel = { kind: "device", ids: Object.entries(boxes).filter(([, b]) => b.x >= x0 && b.x + b.w <= x1 && b.y >= y0 && b.y + b.h <= y1).map(([i]) => i) };
    render(); inspector(); return;
  }
  render();
}

// ------------------------------------------------------------------ inspector (forms)
function h(tag, attrs = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) { if (k.startsWith("on")) e.addEventListener(k.slice(2), v); else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? "" : v); }
  for (const k of kids.flat()) if (k != null) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
const netOptions = (empty = true) => (empty ? [["", "—"]] : []).concat(lab.networks.map(n => [n.key, vtag(lab, n.key)]));
function field(label, value, set, type = "text", opts = null, hint = null) {
  let inp;
  if (type === "select") { inp = h("select", { onchange: e => { set(e.target.value); commit(); } }, ...opts.map(([v, t]) => h("option", { value: v, selected: String(value ?? "") === String(v) }, t))); }
  else if (type === "check") inp = h("input", { type: "checkbox", checked: !!value, onchange: e => { set(e.target.checked); commit(); } });
  else if (type === "area") inp = h("textarea", { rows: 3, onchange: e => { set(e.target.value); commit(); } }, value ?? "");
  else inp = h("input", { type, value: value ?? "", onchange: e => { set(type === "number" ? (e.target.value === "" ? null : +e.target.value) : e.target.value); commit(); } });
  return h("label", { class: "f" }, h("span", {}, label), inp, hint ? h("small", {}, hint) : null);
}
function listEditor(title, arr, cols, make, after) {
  const box = h("div", { class: "list" }, h("div", { class: "lh" }, h("b", {}, title), h("button", { class: "mini", onclick: () => { arr.push(make()); commit(); inspector(); } }, "+ hinzufügen")));
  const tbl = h("table");
  tbl.append(h("tr", {}, ...cols.map(c => h("th", {}, c[1])), h("th")));
  arr.forEach((row, i) => {
    tbl.append(h("tr", {}, ...cols.map(([k, , type, opts]) => {
      const v = row[k];
      let inp;
      if (type === "select") inp = h("select", { onchange: e => { row[k] = e.target.value === "" ? undefined : e.target.value; commit(); } }, ...opts().map(([ov, ot]) => h("option", { value: ov, selected: String(v ?? "") === String(ov) }, ot)));
      else if (type === "check") inp = h("input", { type: "checkbox", checked: !!v, onchange: e => { row[k] = e.target.checked || undefined; commit(); } });
      else if (type === "list") inp = h("input", { value: (v || []).join(", "), onchange: e => { row[k] = e.target.value.split(",").map(s => s.trim()).filter(Boolean); commit(); } });
      else if (type === "number") inp = h("input", { type: "number", value: v ?? "", onchange: e => { row[k] = e.target.value === "" ? undefined : +e.target.value; commit(); } });
      else inp = h("input", { value: v ?? "", onchange: e => { row[k] = e.target.value === "" ? undefined : e.target.value; commit(); } });
      return h("td", {}, inp);
    }), h("td", {}, h("button", { class: "mini del", title: "entfernen", onclick: () => { arr.splice(i, 1); commit(); inspector(); } }, "✕"))));
  });
  box.append(h("div", { class: "scroll" }, tbl));
  if (after) box.append(after);
  return box;
}
function iconPicker(d) {
  const names = Object.keys(typeof ICONS !== "undefined" ? ICONS : {}).sort();
  const box = h("details", { class: "icons" }, h("summary", {}, "Icon wählen …"));
  const grid = h("div", { class: "igrid" });
  for (const n of names) grid.append(h("button", { class: "ib", title: n, onclick: () => { d.icons = [n]; commit(); inspector(); } }, h("img", { src: ICONS[n], alt: n }), h("span", {}, n)));
  box.append(grid); return box;
}
function renameDevice(d, nid) {
  nid = nid.trim(); if (!nid || nid === d.id || devOf(lab, nid)) return;
  for (const l of lab.links) for (const k of ["a", "b"]) { const [dv, p] = splitEnd(l[k]); if (dv === d.id) l[k] = p ? `${nid}.${p}` : nid; if (l.sides && l.sides[d.id]) { l.sides[nid] = l.sides[d.id]; delete l.sides[d.id]; } }
  d.id = nid; sel.ids = [nid];
}
function inspector() {
  const el = $("#insp"); el.innerHTML = "";
  if (sel.kind === "device" && sel.ids.length === 1) {
    const d = devOf(lab, sel.ids[0]); if (!d) return;
    const g = geom(d, lab);
    el.append(h("h3", {}, d.name || d.id, h("small", {}, " " + ((ROLES.find(r => r[0] === d.role) || [])[1] || d.role))),
      h("div", { class: "row" },
        h("button", { onclick: () => { const c = JSON.parse(JSON.stringify(d)); c.id = d.id + "-kopie"; while (devOf(lab, c.id)) c.id += "x"; c.name = (d.name || d.id) + " (Kopie)"; c.pos = { ...d.pos, x: d.pos.x + 40, y: d.pos.y + 40 }; lab.devices.push(c); sel = { kind: "device", ids: [c.id] }; commit("dupliziert"); inspector(); } }, "Duplizieren"),
        h("button", { class: "danger", onclick: () => delSel() }, "Löschen")),
      h("fieldset", {}, h("legend", {}, "Allgemein"),
        field("Funktion (Name)", d.name, v => d.name = v), field("Mythos-Name", d.mythos, v => d.mythos = v || undefined),
        field("ID (für Verbindungen)", d.id, v => renameDevice(d, v)),
        field("Rolle", d.role, v => d.role = v, "select", ROLES),
        field("Typ (im Reiter)", d.type, v => d.type = v), field("Modell", d.model, v => d.model = v),
        field("OS + Version", d.os, v => d.os = v), field("Konfiguration (4. Zeile)", d.config, v => d.config = v || undefined),
        field("Status", d.status || "active", v => d.status = v, "select", STATUS),
        field("Rand", d.border || "", v => d.border = v || undefined, "select", [["", "Farbe des Netzes"], ["trunk", "neutral (am Trunk)"]])),
      h("fieldset", {}, h("legend", {}, "Adresse"),
        field("IP", d.ip, v => d.ip = v, "text", null, "mehrere: 10.0.10.30 / .31"),
        field("Netz", d.net ?? "", v => d.net = v || undefined, "select", netOptions()),
        field("Hostname öffentlich (→ name.domain)", d.host, v => d.host = v || undefined),
        field("Hostname intern (→ name.internal)", d.internal, v => d.internal = v || undefined)),
      h("fieldset", {}, h("legend", {}, "Icons"), field("Icons (mit Komma)", (d.icons || []).join(", "), v => d.icons = v.split(",").map(s => s.trim()).filter(Boolean)), iconPicker(d)),
      h("fieldset", {}, h("legend", {}, "Position"),
        field("x", d.pos.x, v => d.pos.x = v ?? 0, "number"), field("y", d.pos.y, v => d.pos.y = v ?? 0, "number"),
        g.kind === "server" ? field("Breite", d.pos.w || g.w, v => d.pos.w = v || undefined, "number") : null));
    if (d.role === "switch" || d.role === "isp_router")
      el.append(listEditor("Ports", d.ports, [["id", "ID"], ["label", "Beschr."], ["kind", "Art", "select", () => [["rj45", "RJ45"], ["sfp", "SFP"], ["coax", "Koax/DSL"]]],
        ["untagged", "untagged", "select", () => netOptions()], ["tagged", "tagged", "list"], ["to", "Text darunter"], ["uplink", "Internet", "check"]],
        () => ({ id: "p" + (d.ports.length + 1), label: String(d.ports.length + 1) })));
    else el.append(listEditor("Ports (optional, z. B. für die IP am Port)", d.ports, [["id", "ID"], ["ip", "IP am Port"]], () => ({ id: "p" + (d.ports.length + 1) })));
    if (INFRA.includes(d.role) || g.kind === "server") {
      d.hw = d.hw || [];
      el.append(listEditor("Hardware", d.hw, [["icon", "Icon"], ["label", "Typ"], ["value", "Bauteil"], ["sub", "Info"]], () => ({ icon: "glyph-cpu", label: "CPU", value: "", sub: "" })));
    }
    if (INFRA.includes(d.role)) { d.services = d.services || []; el.append(listEditor("Dienste", d.services, [["icon", "Icon"], ["name", "Name"], ["note", "Info"]], () => ({ icon: "docker", name: "", note: "" }))); }
    if (d.role === "ap" || (d.ssids || []).length) { d.ssids = d.ssids || []; el.append(listEditor("SSIDs", d.ssids, [["name", "Name"], ["redacted", "Name öffentlich"], ["vlan", "Netz", "select", () => netOptions(false)]], () => ({ name: "WLAN", redacted: "WLAN", vlan: (lab.networks[0] || {}).key }))); }
    if (d.role === "server" || (d.guests || []).length) {
      d.guests = d.guests || [];
      el.append(listEditor("Gäste (VMs / Container)", d.guests, [["id", "VMID", "number"], ["kind", "Art", "select", () => [["CT", "CT"], ["VM", "VM"]]], ["name", "Name"], ["net", "Netz", "select", () => netOptions()],
        ["ip", "IP"], ["host", "öffentl. Name"], ["internal", "intern"], ["exposure", "Freigabe", "select", () => [["", "—"], ["public", "öffentlich"], ["local", "nur LAN/VPN"]]],
        ["group", "Gruppe"], ["icons", "Icons", "list"], ["note", "Info"], ["featured", "groß", "check"], ["docker", "Docker", "check"]],
        () => ({ id: 100 + d.guests.length, kind: "CT", name: "Dienst", icons: ["docker"], net: d.net, note: "" })));
    }
  } else if (sel.kind === "device" && sel.ids.length > 1) {
    el.append(h("h3", {}, `${sel.ids.length} Geräte ausgewählt`),
      h("div", { class: "row" },
        h("button", { onclick: () => align("top") }, "oben bündig"), h("button", { onclick: () => align("left") }, "links bündig"),
        h("button", { onclick: () => align("hdist") }, "waagerecht verteilen"), h("button", { onclick: () => align("vdist") }, "senkrecht verteilen")),
      h("div", { class: "row" }, h("button", { class: "danger", onclick: () => delSel() }, "Alle löschen")));
  } else if (sel.kind === "link") {
    const l = lab.links[sel.ids[0]]; if (!l) return;
    const [ad, ap] = splitEnd(l.a), [bd, bp] = splitEnd(l.b);
    const devOpts = lab.devices.map(d => [d.id, d.name || d.id]);
    const portOpts = id => [["", "(ganze Karte)"]].concat(((devOf(lab, id) || {}).ports || []).map(p => [p.id, p.label ? `${p.label} (${p.id})` : p.id]));
    el.append(h("h3", {}, "Verbindung"), h("div", { class: "row" },
      h("button", { onclick: () => { delete l.via; delete l.sides; commit("Weg zurückgesetzt"); inspector(); } }, "Weg automatisch"),
      h("button", { class: "danger", onclick: () => delSel() }, "Löschen")),
      h("fieldset", {}, h("legend", {}, "Enden"),
        field("von Gerät", ad, v => l.a = v + (ap ? "." + ap : ""), "select", devOpts), field("Port", ap || "", v => l.a = ad + (v ? "." + v : ""), "select", portOpts(ad)),
        field("nach Gerät", bd, v => l.b = v + (bp ? "." + bp : ""), "select", devOpts), field("Port", bp || "", v => l.b = bd + (v ? "." + v : ""), "select", portOpts(bd))),
      h("fieldset", {}, h("legend", {}, "Art"),
        field("Art", l.kind || "cable", v => l.kind = v === "cable" ? undefined : v, "select", LINK_KINDS),
        field("Geschwindigkeit", l.speed, v => l.speed = v, "select", SPEEDS.map(s => [s, s])),
        field("Netz (access, untagged)", l.net ?? "", v => l.net = v || undefined, "select", netOptions()),
        h("div", { class: "f" }, h("span", {}, "VLANs (Trunk, getaggt)"), h("div", { class: "chips" }, ...lab.networks.map(n => h("label", { class: "chip", style: `border-color:${n.color}` },
          h("input", { type: "checkbox", checked: (l.vlans || []).includes(n.key), onchange: e => { l.vlans = (l.vlans || []).filter(k => k !== n.key); if (e.target.checked) l.vlans.push(n.key); commit(); } }), vtag(lab, n.key))))),
        field("Beschriftung", l.label, v => l.label = v || undefined), field("LAG-Gruppe", l.lag, v => l.lag = v || undefined), field("LAG-Text", l.lag_label, v => l.lag_label = v || undefined)),
      h("p", { class: "hint" }, `Wegpunkte: ${(l.via || []).length}. Doppelklick auf das Kabel setzt einen Wegpunkt, ziehen verschiebt ihn. Ohne Wegpunkte legt das Diagramm-Tool den Weg selbst.`));
  } else if (sel.kind === "panel") {
    const key = sel.ids[0], p = panelList(lab).find(q => q.key === key);
    el.append(h("h3", {}, p ? p.title : key), h("div", { class: "row" }, h("button", { onclick: () => { delete lab.layout.panels[key]; commit("Panel an Standardplatz"); inspector(); } }, "an Standardplatz")));
    if (key === "networks") el.append(listEditor("Netze", lab.networks, [["key", "Schlüssel"], ["tag", "Tag"], ["name", "Name"], ["subnet", "Subnetz"], ["color", "Farbe"], ["note", "Info"]], () => ({ key: String(10 * (lab.networks.length + 1)), name: "NEU", subnet: "", color: "#8d9aab", note: "" })));
    if (key === "cloud") el.append(listEditor("Cloud-Dienste", lab.cloud, [["icon", "Icon"], ["name", "Name"], ["note", "Info"]], () => ({ icon: "cloudflare", name: "", note: "" })));
    if (key === "forwards") el.append(listEditor("Portweiterleitungen", lab.port_forwards, [["port", "Port"], ["proto", "Protokoll"], ["to", "Ziel"], ["what", "Wofür"]], () => ({ port: "", proto: "TCP", to: "", what: "" })));
  } else {
    const m = lab.meta, inet = lab.internet; inet.speed = inet.speed || {};
    el.append(h("h3", {}, "Lab"), h("p", { class: "hint" }, "Nichts ausgewählt: hier stehen die Angaben für das ganze Diagramm."),
      h("fieldset", {}, h("legend", {}, "Titel"), field("Titel", m.title, v => m.title = v), field("Titel (geschwärzt)", m.title_redacted, v => m.title_redacted = v),
        field("Datum", m.date, v => m.date = v), field("Wasserzeichen", m.watermark, v => m.watermark = v), field("Domain (wird geschwärzt)", m.domain, v => m.domain = v)),
      h("fieldset", {}, h("legend", {}, "Internet"), field("Text", inet.label, v => inet.label = v), field("Unterzeile", inet.sub, v => inet.sub = v),
        field("Download", inet.speed.down, v => inet.speed.down = v), field("Upload", inet.speed.up, v => inet.speed.up = v)),
      listEditor("Netze", lab.networks, [["key", "Schlüssel"], ["tag", "Tag"], ["name", "Name"], ["subnet", "Subnetz"], ["color", "Farbe"], ["note", "Info"]], () => ({ key: String(10 * (lab.networks.length + 1)), name: "NEU", subnet: "", color: "#8d9aab", note: "" })),
      listEditor("Fernzugriff", lab.remote, [["name", "Name"], ["note", "Info"], ["icon", "Icon"], ["net", "Netz", "select", () => netOptions()]], () => ({ name: "Fernzugriff", note: "", icon: "wireguard" })),
      listEditor("Weitere IPs (ohne eigene Karte)", lab.ip_extra, [["vlan", "Netz", "select", () => netOptions(false)], ["ip", "IP"], ["name", "Name"], ["kind", "Art"]], () => ({ vlan: (lab.networks[0] || {}).key, ip: ".", name: "", kind: "" })));
  }
}
function delSel() {
  if (sel.kind === "device") {
    const ids = new Set(sel.ids);
    lab.devices = lab.devices.filter(d => !ids.has(d.id));
    lab.links = lab.links.filter(l => !ids.has(splitEnd(l.a)[0]) && !ids.has(splitEnd(l.b)[0]));
  } else if (sel.kind === "link") lab.links.splice(sel.ids[0], 1);
  else return;
  sel = { kind: null, ids: [] }; commit("gelöscht"); inspector();
}
function align(how) {
  const ds = sel.ids.map(i => devOf(lab, i)).filter(Boolean), bs = ds.map(d => boxOf(d, lab));
  if (how === "top") { const y = Math.min(...bs.map(b => b.y)); ds.forEach(d => d.pos.y = y); }
  if (how === "left") { const x = Math.min(...bs.map(b => b.x)); ds.forEach(d => d.pos.x = x); }
  if (how === "hdist") { const o = ds.map((d, i) => [d, bs[i]]).sort((a, b) => a[1].x - b[1].x); let x = o[0][1].x; o.forEach(([d, b]) => { d.pos.x = snapv(x); x += b.w + 60; }); }
  if (how === "vdist") { const o = ds.map((d, i) => [d, bs[i]]).sort((a, b) => a[1].y - b[1].y); let y = o[0][1].y; o.forEach(([d, b]) => { d.pos.y = snapv(y); y += b.h + TAB + 52; }); }
  commit("ausgerichtet");
}

// ------------------------------------------------------------------ list views
function renderTab() {
  const el = $("#tabview"); el.innerHTML = "";
  const go = id => { sel = { kind: "device", ids: [id] }; setTab("draw"); const b = boxes[id]; if (b) { const r = $("#svg").getBoundingClientRect(); view.x = r.width / 2 - (b.x + b.w / 2) * view.k; view.y = r.height / 2 - (b.y + b.h / 2) * view.k; } render(); inspector(); };
  if (tab === "lists") {
    const t = h("table", { class: "grid" }, h("tr", {}, ...["Funktion", "Mythos", "Rolle", "Modell", "IP", "Netz", "Status", "Verbindungen"].map(x => h("th", {}, x))));
    for (const d of lab.devices) t.append(h("tr", { onclick: () => go(d.id) }, h("td", {}, d.name), h("td", {}, d.mythos || ""), h("td", {}, (ROLES.find(r => r[0] === d.role) || [, d.role])[1]), h("td", {}, d.model || ""), h("td", { class: "mono" }, d.ip || ""), h("td", {}, d.net != null ? vtag(lab, d.net) : ""), h("td", {}, (STATUS.find(s => s[0] === (d.status || "active")) || [])[1]), h("td", {}, lab.links.filter(l => splitEnd(l.a)[0] === d.id || splitEnd(l.b)[0] === d.id).length)));
    const lt = h("table", { class: "grid" }, h("tr", {}, ...["von", "nach", "Art", "Speed", "Netz / VLANs"].map(x => h("th", {}, x))));
    lab.links.forEach((l, i) => lt.append(h("tr", { onclick: () => { sel = { kind: "link", ids: [i] }; setTab("draw"); render(); inspector(); } }, h("td", {}, l.a), h("td", {}, l.b), h("td", {}, (LINK_KINDS.find(k => k[0] === (l.kind || "cable")) || [])[1]), h("td", {}, l.speed), h("td", {}, l.vlans.length ? "Trunk: " + l.vlans.join(", ") : l.net ? vtag(lab, l.net) : ""))));
    const gt = h("table", { class: "grid" }, h("tr", {}, ...["Host", "VMID", "Art", "Name", "Netz", "IP", "Hostname"].map(x => h("th", {}, x))));
    for (const d of lab.devices) for (const g of d.guests || []) gt.append(h("tr", { onclick: () => go(d.id) }, h("td", {}, d.name), h("td", {}, g.id), h("td", {}, g.kind || "CT"), h("td", {}, g.name), h("td", {}, g.net != null ? vtag(lab, g.net) : ""), h("td", { class: "mono" }, g.ip || ""), h("td", { class: "mono" }, (hostName(g, lab)[0]) || "")));
    el.append(h("h3", {}, `Geräte (${lab.devices.length})`), t, h("h3", {}, `Verbindungen (${lab.links.length})`), lt, h("h3", {}, "Gäste"), gt);
  } else if (tab === "ips") {
    const ips = collectIps(lab);
    for (const n of lab.networks) {
      const rows = ips.filter(e => e.net === n.key).sort((a, b) => ip4(a.ip) - ip4(b.ip)); if (!rows.length) continue;
      const c = cidr(n.subnet);
      el.append(h("h3", { style: `color:${n.color}` }, `${vtag(lab, n.key)} · ${n.subnet || ""}`, h("small", {}, ` ${rows.length} genutzt${c ? ` · ${c.size - 2 - rows.length} frei` : ""}`)));
      const t = h("table", { class: "grid" });
      for (const e of rows) t.append(h("tr", { class: e.conflict ? "bad" : "" }, h("td", { class: "mono" }, e.ip), h("td", {}, e.name), h("td", {}, e.kind)));
      el.append(t);
    }
    const rest = ips.filter(e => !e.net); if (rest.length) { el.append(h("h3", {}, "ohne Netz")); const t = h("table", { class: "grid" }); rest.forEach(e => t.append(h("tr", {}, h("td", { class: "mono" }, e.ip), h("td", {}, e.name)))); el.append(t); }
  } else if (tab === "check") {
    if (!result.err.length && !result.warn.length) el.append(h("p", { class: "okbox" }, "Alles in Ordnung: keine Fehler, keine Hinweise."));
    const item = ([id, msg], cls) => h("li", { class: cls, onclick: () => id && go(id) }, msg);
    if (result.err.length) el.append(h("h3", {}, "Fehler (das Diagramm-Tool würde abbrechen)"), h("ul", { class: "msgs" }, ...result.err.map(e => item(e, "bad"))));
    if (result.warn.length) el.append(h("h3", {}, "Hinweise"), h("ul", { class: "msgs" }, ...result.warn.map(e => item(e, "warn"))));
  }
}
function setTab(t) {
  tab = t;
  for (const b of document.querySelectorAll(".tabs button")) b.classList.toggle("on", b.dataset.tab === t);
  $("#stage").hidden = t !== "draw"; $("#tabview").hidden = t === "draw";
  if (t !== "draw") renderTab(); else render();
}

// ------------------------------------------------------------------ files
function download(name, text, type = "text/yaml") {
  const a = h("a", { href: URL.createObjectURL(new Blob([text], { type })), download: name }); document.body.append(a); a.click(); a.remove();
}
function exportYaml() {
  const clean = JSON.parse(JSON.stringify(lab));
  const slug = (lab.meta.title || "homelab").toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "homelab";
  download(slug + ".yaml", "# Homelab-Planer · Schema 2 mit Positionen · zeichnen: python3 build.py --lab=" + slug + ".yaml\n" + YAML.dump(clean));
  status("YAML-Datei gespeichert");
}
function parseLab(txt) {
  let d = /^\s*[{[]/.test(txt) ? JSON.parse(txt) : YAML.parse(txt);
  if (d && d.schema !== 2 && d.vlans) d = convertLegacy(d);
  return d;
}
function openFile(file) {
  const r = new FileReader();
  r.onload = () => {
    try {
      setLab(parseLab(String(r.result)), "„" + file.name + "“ geöffnet");
    } catch (e) { alert("Datei konnte nicht gelesen werden:\n" + e.message); }
  };
  r.readAsText(file);
}
function addDevice(role) {
  const d = template(role, lab);
  const r = $("#svg").getBoundingClientRect();
  d.pos = Object.assign(d.pos || {}, { x: snapv((r.width / 2 - view.x) / view.k - 150), y: snapv((r.height / 2 - view.y) / view.k - 40) });
  lab.devices.push(d); sel = { kind: "device", ids: [d.id] }; commit((ROLES.find(x => x[0] === role) || [])[1] + " hinzugefügt"); inspector();
}

// ------------------------------------------------------------------ start
function init() {
  const pal = $("#palette-roles");
  for (const [r, t] of ROLES) pal.append(h("button", { onclick: () => addDevice(r) }, t));
  const ex = $("#examples");
  for (const name of Object.keys(typeof EXAMPLES !== "undefined" ? EXAMPLES : {})) ex.append(h("option", { value: name }, name));
  ex.onchange = () => { if (!ex.value) return; if (lab.devices.length && !confirm("Das aktuelle Lab ersetzen? (Es bleibt im Verlauf.)")) { ex.value = ""; return; } setLab(parseLab(EXAMPLES[ex.value]), "Beispiel „" + ex.value + "“ geladen"); ex.value = ""; };
  $("#btn-new").onclick = () => { if (!lab.devices.length || confirm("Neues, leeres Lab anfangen? (Das aktuelle bleibt im Verlauf.)")) setLab(emptyLab(), "neues Lab"); };
  $("#btn-open").onclick = () => $("#file").click();
  $("#file").onchange = e => { if (e.target.files[0]) openFile(e.target.files[0]); e.target.value = ""; };
  $("#btn-save").onclick = exportYaml;
  $("#btn-undo").onclick = doUndo; $("#btn-redo").onclick = doRedo;
  $("#btn-fit").onclick = fit;
  $("#btn-zin").onclick = () => { const r = $("#svg").getBoundingClientRect(); zoomAt(1.25, r.width / 2, r.height / 2); };
  $("#btn-zout").onclick = () => { const r = $("#svg").getBoundingClientRect(); zoomAt(0.8, r.width / 2, r.height / 2); };
  $("#btn-auto").onclick = () => { if (confirm("Alle Karten automatisch anordnen? (Rückgängig möglich)")) { autoArrange(true); commit("automatisch angeordnet"); fit(); } };
  $("#btn-hist").onclick = () => {
    const hst = JSON.parse(localStorage.getItem(HIST) || "[]");
    if (!hst.length) return alert("Noch kein Verlauf.");
    const pick = prompt("Welchen Stand wiederherstellen? Nummer eingeben:\n" + hst.map((x, i) => `${i + 1}: ${new Date(x.ts).toLocaleString("de-DE")} · ${x.title || ""}`).join("\n"));
    const i = parseInt(pick, 10) - 1; if (hst[i]) setLab(hst[i].lab, "Stand vom " + new Date(hst[i].ts).toLocaleString("de-DE") + " wiederhergestellt");
  };
  $("#btn-menu").onclick = () => document.body.classList.toggle("show-pal");
  $("#btn-insp").onclick = () => document.body.classList.toggle("show-insp");
  for (const b of document.querySelectorAll(".tabs button")) b.onclick = () => setTab(b.dataset.tab);
  $("#search").oninput = e => {
    const q = e.target.value.trim().toLowerCase(); if (!q) return;
    const d = lab.devices.find(x => [x.name, x.id, x.ip, x.mythos, x.model].some(v => String(v || "").toLowerCase().includes(q)) || (x.guests || []).some(g => String(g.name).toLowerCase().includes(q)));
    if (d && boxes[d.id]) { sel = { kind: "device", ids: [d.id] }; const b = boxes[d.id], r = $("#svg").getBoundingClientRect(); view.x = r.width / 2 - (b.x + b.w / 2) * view.k; view.y = r.height / 2 - (b.y + b.h / 2) * view.k; render(); inspector(); }
  };
  const svg = $("#svg");
  svg.addEventListener("pointerdown", onDown); svg.addEventListener("pointermove", onMove);
  svg.addEventListener("pointerup", onUp); svg.addEventListener("pointercancel", onUp);
  svg.addEventListener("wheel", e => { e.preventDefault(); const r = svg.getBoundingClientRect(); if (e.ctrlKey || e.metaKey || Math.abs(e.deltaY) > Math.abs(e.deltaX) && !e.shiftKey && e.deltaMode !== 0 || e.ctrlKey) zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top); else if (Math.abs(e.deltaX) > 0 || e.shiftKey) { view.x -= e.deltaX || e.deltaY; applyView(); } else zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top); }, { passive: false });
  document.addEventListener("keydown", e => {
    if (/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? doRedo() : doUndo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); doRedo(); }
    else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); exportYaml(); }
    else if (e.key === "Delete" || e.key === "Backspace") delSel();
    else if (e.key.startsWith("Arrow") && sel.kind === "device") {
      const s = e.shiftKey ? 64 : GRID, [dx, dy] = { ArrowLeft: [-s, 0], ArrowRight: [s, 0], ArrowUp: [0, -s], ArrowDown: [0, s] }[e.key];
      for (const id of sel.ids) { const d = devOf(lab, id); d.pos.x += dx; d.pos.y += dy; } e.preventDefault(); commit();
    } else if (e.key === "Escape") { sel = { kind: null, ids: [] }; render(); inspector(); }
  });
  window.addEventListener("resize", applyView);
  let start = null;
  try { start = JSON.parse(localStorage.getItem(STORE) || "null"); } catch (e) { start = null; }
  const first = start && start.lab ? start.lab : (typeof EXAMPLES !== "undefined" && EXAMPLES[Object.keys(EXAMPLES)[0]] ? parseLab(EXAMPLES[Object.keys(EXAMPLES)[0]]) : emptyLab());
  (document.fonts ? document.fonts.ready : Promise.resolve()).then(() => { clearMeasureCache(); setLab(first, start ? "letzter Stand aus dem Browser" : "Beispiel geladen"); });
}
window.addEventListener("DOMContentLoaded", init);
