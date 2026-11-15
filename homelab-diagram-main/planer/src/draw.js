// Planer drawing: SVG in the look of the diagram (folder-tab cards, jacks, VLAN ticks, trunks …).
"use strict";
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const iconHref = n => (typeof ICONS !== "undefined" && ICONS[n]) || "";
function T_(x, y, s, size, fill, weight = 400, anchor = "start", mono = false, extra = "") {
  return `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-family="${mono ? "Fira Code" : "Fira Sans"}" font-size="${size}" fill="${fill}" font-weight="${weight}" text-anchor="${anchor}" ${extra}>${esc(s)}</text>`;
}
function R_(x, y, w, h, rx, fill, stroke, sw = 1.2, extra = "") {
  return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${Math.max(0, w).toFixed(1)}" height="${Math.max(0, h).toFixed(1)}" rx="${rx}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}" ${extra}/>`;
}
function I_(n, x, y, s) { const h = iconHref(n); return h ? `<image x="${x}" y="${y}" width="${s}" height="${s}" href="${h}"/>` : R_(x, y, s, s, 6, C.CHIP, C.BORDER); }
function rounded(pts, r = 10) {
  if (pts.length < 2) return "";
  let d = `M${pts[0][0]},${pts[0][1]}`;
  for (let i = 1; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i - 1], [x1, y1] = pts[i], [x2, y2] = pts[i + 1];
    const l1 = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)), l2 = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
    const rr = Math.min(r, l1 / 2, l2 / 2);
    const ax = l1 ? x1 - (x1 - x0) / l1 * rr : x1, ay = l1 ? y1 - (y1 - y0) / l1 * rr : y1;
    const bx = l2 ? x1 + (x2 - x1) / l2 * rr : x1, by = l2 ? y1 + (y2 - y1) / l2 * rr : y1;
    d += ` L${ax.toFixed(1)},${ay.toFixed(1)} Q${x1},${y1} ${bx.toFixed(1)},${by.toFixed(1)}`;
  }
  const L = pts[pts.length - 1];
  return d + ` L${L[0]},${L[1]}`;
}
function folderPath(x, y, w, h, tw) {
  const t = y - TAB, r = 12, rt = 9, sl = 16;
  return `M${x},${y + h - r} L${x},${t + rt} Q${x},${t} ${x + rt},${t} L${x + tw - sl},${t} C${x + tw - sl / 3},${t} ${x + tw - sl / 3},${y} ${x + tw + sl / 2},${y} L${x + w - r},${y} Q${x + w},${y} ${x + w},${y + r} L${x + w},${y + h - r} Q${x + w},${y + h} ${x + w - r},${y + h} L${x + r},${y + h} Q${x},${y + h} ${x},${y + h - r} Z`;
}
function jack(x, y, w, h, fill, stroke, sfp) {
  let s = R_(x, y, w, h, 5, fill, stroke, 1.4);
  s += sfp ? R_(x + 8, y + 9, w - 16, h - 18, 2, "#0b0f15", "none", 0) : `<path d="M${x + 10},${y + h - 8} v-14 h6 v-5 h${w - 32} v5 h6 v14 z" fill="#0b0f15"/>`;
  return s;
}
function ticks(lab, cx, y, unt, tagged, up = false) {
  const vk = (unt != null && unt !== "" ? [unt] : []).concat(tagged || []);
  const x0 = cx - vk.length * 7 / 2; let s = "";
  vk.forEach((k, j) => { const hh = k === unt ? 8 : 5; s += `<rect x="${(x0 + j * 7).toFixed(1)}" y="${(up ? y - hh : y).toFixed(1)}" width="5" height="${hh}" rx="1" fill="${color(lab, k)}"/>`; });
  return s;
}
function addrSvg(x, y, d, col, lab) {
  let s = T_(x, y, d.ip || "", 12, col, 500, "start", true);
  const [h, hc] = hostName(d, lab);
  if (h) { const cw = 7.2, dx = x + String(d.ip || "").length * cw + cw * .6; s += T_(dx, y, "·", 12, C.MUTED, 400, "start", true) + T_(dx + cw * 1.6, y, h, 12, hc || col, 400, "start", true, hc ? "" : 'opacity="0.85"'); }
  return s;
}
function drawCard(d, b, lab, st) {
  const g = b.g, x = b.x, y = b.y, w = b.w, h = b.h;
  const col = color(lab, d.net);
  const stroke = st.err ? C.RED : st.sel ? C.SEL : (d.border === "trunk" ? C.TRUNK_BORDER : col + "aa");
  const fill = g.kind === "server" ? "#0f151e" : g.kind === "switch" ? "#141b25" : C.PANEL;
  let s = `<g class="card${st.sel ? " sel" : ""}" data-id="${esc(d.id)}">`;
  s += `<path d="${folderPath(x, y, w, h, g.tab_w)}" fill="${fill}" stroke="${stroke}" stroke-width="${st.sel || st.err ? 3 : 1.6}"/>`;
  if (d.status && d.status !== "active") s += `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="12" fill="none" stroke="${fill}" stroke-width="2.6" stroke-dasharray="7 5"/>`;
  s += `<text x="${x + 16}" y="${y - 10}" font-family="Fira Sans" fill="${C.TEXT}"><tspan font-size="20" font-weight="700">${esc(d.name || d.id)}</tspan><tspan dx="7" font-size="20" font-weight="700" fill-opacity="0.6">·</tspan><tspan dx="7" font-size="14" font-weight="600">${esc(d.type || "")}</tspan></text>`;
  if (d.mythos) s += T_(x + g.tab_w + 14, y - 10, d.mythos, 12, C.FAINT, 500, "start", false, 'font-style="italic"');
  let ix = x + 14;
  for (const ic of (d.icons || []).length ? d.icons : [""]) { s += I_(ic, ix, y + 15, 54); ix += 58; }
  const tx = ix + 8, dy = d.os ? 0 : 8;
  s += T_(tx, y + 28 + dy, d.model || "custom build", 14, d.model ? C.TEXT : C.MUTED, 500);
  s += addrSvg(tx, y + 48 + dy, d, col, lab);
  if (d.os) s += T_(tx, y + 66, d.os, 12, C.MUTED);
  if (d.config) s += T_(tx, y + 84, d.config, 12, C.FAINT);
  if (g.kind === "isp" || g.kind === "switch") s += portRow(d, b, lab, st);
  if (g.kind === "appliance") {
    const hw = d.hw || [], sv = d.services || [];
    if (hw.length) { s += T_(x + 20, y + 96, "HARDWARE", 11.5, C.HWC, 700, "start", false, 'letter-spacing="1.4"'); hw.forEach((t, i) => s += tile(x + 16, y + 106 + i * 64, g.hw_w, t)); }
    if (sv.length) { const sx = x + 16 + (hw.length ? g.hw_w + 28 : 0); s += T_(sx + 2, y + 96, "SERVICES", 11.5, C.HWC, 700, "start", false, 'letter-spacing="1.4"'); sv.forEach((t, i) => s += svc(sx + (i % g.sv_cols) * (g.sv_w + 9), y + 106 + Math.floor(i / g.sv_cols) * 58, g.sv_w, t)); }
  }
  if (g.kind === "server") s += serverBody(d, b, lab);
  if ((d.ssids || []).length && g.kind === "device") {
    s += T_(x + 18, y + 96, "SSIDs", 11, C.FAINT, 600);
    d.ssids.forEach((ss, i) => { const sy = y + 106 + i * 17, c = color(lab, ss.vlan); s += `<circle cx="${x + 24}" cy="${sy + 5}" r="4" fill="${c}"/>` + T_(x + 36, sy + 9, ss.name, 13, C.TEXT, 500) + T_(x + 150, sy + 9, vtag(lab, ss.vlan), 12, c, 500, "start", true); });
  }
  if (st.sel) s += `<circle class="handle conn" data-id="${esc(d.id)}" cx="${x + w + 12}" cy="${y + 24}" r="9" fill="${C.SEL}" stroke="${C.BG}" stroke-width="2"/><text x="${x + w + 12}" y="${y + 28.5}" font-size="13" text-anchor="middle" fill="${C.BG}" font-weight="700" pointer-events="none">+</text>`;
  if (g.kind === "server" && st.sel) s += `<rect class="handle resize" data-id="${esc(d.id)}" x="${x + w - 9}" y="${y + h - 9}" width="18" height="18" rx="4" fill="${C.SEL}"/>`;
  return s + "</g>";
}
function tile(x, y, w, t) {
  return R_(x, y, w, 58, 11, "#151d29", "#2e3a4c") + `<rect x="${x + 1}" y="${y + 12}" width="4" height="34" rx="2" fill="${C.HWC}"/>` + I_(t.icon, x + 12, y + 15, 28)
    + T_(x + 50, y + 17, t.label || "", 10, C.HWC, 700) + T_(x + 50, y + 35, t.value || "", 15.5, C.TEXT, 700) + T_(x + 50, y + 50, t.sub || "", 10.5, C.MUTED);
}
function svc(x, y, w, t) { return R_(x, y, w, 50, 9, C.CHIP, C.BORDER, 1) + I_(t.icon, x + 9, y + 12, 26) + T_(x + 44, y + 22, t.name || "", 14, C.TEXT, 600) + T_(x + 44, y + 39, t.note || "", 11.5, C.MUTED); }
function portRow(d, b, lab, st) {
  const g = b.g, x = b.x, y = b.y; let s = "";
  const jy = y + g.port_y, isp = g.kind === "isp";
  for (const p of d.ports) {
    const cx = x + g.port_x[p.id];
    const used = lab.links.filter(l => (l.kind || "cable") === "cable" && portOf(l, d.id) === p.id);
    if (p.kind === "coax") {
      s += R_(cx - 22, jy, 44, 36, 5, "#2a3443", C.TRUNK, 1.4) + `<circle cx="${cx}" cy="${jy + 18}" r="11" fill="#0b0f15" stroke="#5a6b82" stroke-width="2"/><circle cx="${cx}" cy="${jy + 18}" r="2.5" fill="${C.TRUNK}"/>`;
      s += T_(cx, jy - 7, p.label || "Cable", 11, C.MUTED, 500, "middle", true);
      if (p.note) s += T_(cx, y + b.h - 9, p.note, 10.5, C.MUTED, 500, "middle");
    } else {
      const sfp = p.kind === "sfp", w = isp ? 44 : sfp ? 60 : 48;
      const l = used[0], unt = isp ? (l && l.net) : p.untagged, tg = isp ? [] : p.tagged || [];
      let fill = "#1b222c", stroke = "#3a475a";
      if (used.length && unt && !tg.length) { fill = color(lab, unt) + "55"; stroke = color(lab, unt); }
      else if (used.length || tg.length) { fill = "#2a3443"; stroke = C.TRUNK; }
      s += jack(cx - w / 2, jy, w, 36, fill, stroke, sfp);
      s += T_(cx, jy - 7, p.label || p.id, 11, C.MUTED, 500, "middle", true) + ticks(lab, cx, jy + 41, unt, tg);
      const cap = p.to != null ? p.to : used.length ? ((devOf(lab, otherDev(used[0], d.id)) || {}).name || "") : (p.note || "");
      if (cap) s += T_(cx, y + b.h - 9, cap, Math.min(10.5, 10.5 * ((g.pitch || 52) - 4) / Math.max(1, mw(cap, 10.5, 500))), C.MUTED, 500, "middle");
    }
    if (st.sel || st.ports) s += `<circle class="handle port" data-id="${esc(d.id)}" data-port="${esc(p.id)}" cx="${cx}" cy="${jy + 18}" r="10" fill="${C.SEL}" fill-opacity="${used.length ? 0.15 : 0.35}" stroke="${C.SEL}"/>`;
  }
  return s;
}
function serverBody(d, b, lab) {
  const x = b.x, y = b.y, w = b.w; let s = "", cx = x + 20;
  const hw = d.hw || [];
  if (hw.length) { s += T_(cx + 2, y + 104, "HARDWARE", 11.5, C.HWC, 700); hw.forEach((t, i) => s += tile(cx, y + 114 + i * 64, 250, t)); cx += 270; }
  const guests = d.guests || [];
  const zones = {};
  for (const gu of guests) (zones[gu.net ?? "?"] = zones[gu.net ?? "?"] || []).push(gu);
  let zy = y + 92;
  for (const [k, gs] of Object.entries(zones)) {
    const zc = color(lab, k), zw = x + w - 20 - cx;
    const ncol = Math.max(1, Math.floor((zw - 32 + 14) / 354)), cw = (zw - 32 - 14 * (ncol - 1)) / ncol;
    const rows = Math.ceil(gs.length / ncol), zh = 56 + rows * 71 + 6;
    s += R_(cx, zy, zw, zh, 14, zc + "0d", zc + "88", 1.5) + T_(cx + zw - 14, zy + 29, vtag(lab, k), 10.5, zc, 600, "end", true);
    gs.forEach((gu, i) => {
      const gx = cx + 16 + (i % ncol) * (cw + 14), gy = zy + 56 + Math.floor(i / ncol) * 71;
      s += R_(gx, gy, cw, 64, 9, C.CHIP, C.BORDER, 1) + I_((gu.icons || [""])[0], gx + 10, gy + 16, 32);
      s += T_(gx + 52, gy + 21, gu.name || "", 14.5, C.TEXT, 600) + T_(gx + 52, gy + 37, gu.note || "", 11.5, C.MUTED);
      const [hn, hc] = hostName(gu, lab); if (hn) s += T_(gx + 52, gy + 54, hn, 11.5, hc || C.MUTED, 500, "start", true);
      s += T_(gx + cw - 12, gy + 21, `${gu.kind || "CT"} ${gu.id ?? ""}`, 12, C.FAINT, 500, "end", true) + T_(gx + cw - 12, gy + 37, gu.ip || "", 11, C.FAINT, 500, "end", true);
    });
    zy += zh + 16;
  }
  return s;
}
function drawCable(l, pts, lab, sel, idx) {
  const w = lineW(l), col = l.net ? color(lab, l.net) : C.MUTED;
  const d = rounded(pts);
  let s = `<g class="cable" data-link="${idx}">`;
  if (pts.length > 2) s += `<path d="${d}" fill="none" stroke="${C.BG}" stroke-width="${w + 7}" stroke-linejoin="round"/>`;
  if (l.kind === "kvm") s += `<path d="${d}" fill="none" stroke="${C.MUTED}" stroke-width="2" stroke-dasharray="5 5"/>`;
  else if (l.kind === "wifi") s += `<path d="${d}" fill="none" stroke="${col}" stroke-width="2" stroke-dasharray="1 4" stroke-linecap="round"/>`;
  else if (isTrunk(l)) s += `<path d="${d}" fill="none" stroke="${C.TRUNK}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"/><path d="${d}" fill="none" stroke="${C.BG}" stroke-width="${w - 4.4}" stroke-linejoin="round"/>`;
  else s += `<path d="${d}" fill="none" stroke="${col}" stroke-width="${w}" stroke-linejoin="round" stroke-linecap="round"/>`;
  if (sel) s += `<path d="${d}" fill="none" stroke="${C.SEL}" stroke-width="${w + 10}" stroke-opacity="0.25" stroke-linejoin="round"/>`;
  s += `<path class="hit" d="${d}" fill="none" stroke="transparent" stroke-width="${Math.max(16, w + 10)}" data-link="${idx}"/>`;
  if (l.kind === "cable" || !l.kind) {
    const e = pts[pts.length - 1], p = pts[pts.length - 2] || e;
    const vert = Math.abs(p[0] - e[0]) < .5;
    s += T_(e[0] + (vert ? 7 : (p[0] < e[0] ? -8 : 8)), e[1] + (vert ? (p[1] < e[1] ? -9 : 18) : -7), l.speed, 11, isTrunk(l) ? C.TRUNK : col, 500, vert ? "start" : (p[0] < e[0] ? "end" : "start"), true);
  }
  if (sel) (l.via || []).forEach((v, i) => s += `<circle class="handle via" data-link="${idx}" data-via="${i}" cx="${v[0]}" cy="${v[1]}" r="8" fill="${C.BG}" stroke="${C.SEL}" stroke-width="3"/>`);
  return s + "</g>";
}

// ------------------------------------------------------------------ panels (left/right column like the diagram, movable)
const LEFT_X = 40, LEFT_W = 500, RIGHT_X = 1790, RIGHT_W = 570;
function panelList(lab) {
  const out = [], y0 = 150;
  const nets = { key: "networks", title: "Networks", w: LEFT_W, h: 70 + lab.networks.length * 60 };
  const legend = { key: "legend", title: "Legend", w: LEFT_W, h: 52 + 9 * 27 + 8 };
  nets.x = LEFT_X; nets.y = y0; legend.x = LEFT_X; legend.y = y0 + nets.h + 20;
  out.push(nets, legend);
  let y = 146;
  if ((lab.cloud || []).length) { out.push({ key: "cloud", title: "Cloud", x: RIGHT_X, y, w: RIGHT_W, h: lab.cloud.length * 54 - 10 }); y += lab.cloud.length * 54 + 8; }
  if ((lab.port_forwards || []).length) { const h = 84 + lab.port_forwards.length * 44; out.push({ key: "forwards", title: "Open to the internet", x: RIGHT_X, y, w: RIGHT_W, h }); y += h + 20; }
  (lab.panels || []).forEach((p, i) => {
    const h = p.type === "media_pipeline" ? 560 : 74 + (Math.max(0, ...(p.nodes || []).map(n => n.row || 0)) + 1) * 110;
    out.push({ key: "panel" + i, title: p.title || (p.type === "media_pipeline" ? "Media pipeline" : "Flow"), x: RIGHT_X, y, w: RIGHT_W, h }); y += h + 20;
  });
  for (const p of out) { const m = (lab.layout.panels || {})[p.key]; if (m) { p.x = +m.x; p.y = +m.y; } }
  return out;
}
function drawPanel(p, lab, sel) {
  let s = `<g class="panel" data-panel="${p.key}">` + R_(p.x, p.y, p.w, p.h, 14, C.PANEL, sel ? C.SEL : C.BORDER, sel ? 3 : 1.4);
  s += T_(p.x + 20, p.y + 36, p.title, 19, C.TEXT, 600);
  if (p.key === "networks") lab.networks.forEach((n, i) => {
    const yy = p.y + 56 + i * 60;
    s += R_(p.x + 14, yy, p.w - 28, 52, 9, C.CHIP, (n.color || C.MUTED) + "55", 1) + `<rect x="${p.x + 14}" y="${yy}" width="6" height="52" rx="3" fill="${n.color}"/>`;
    s += T_(p.x + 32, yy + 22, n.tag || (/^\d+$/.test(n.key) ? "VLAN " + n.key : n.name), 13, n.color, 600, "start", true) + T_(p.x + 128, yy + 22, n.name || "", 15.5, C.TEXT, 600)
      + T_(p.x + p.w - 28, yy + 22, n.subnet || "", 13.5, C.TEXT, 500, "end", true) + T_(p.x + 32, yy + 42, n.note || "", 12, C.MUTED);
  });
  else if (p.key === "cloud") lab.cloud.forEach((c, i) => { const yy = p.y + i * 54; s += R_(p.x, yy, p.w, 44, 10, C.PANEL2, C.BORDER) + I_(c.icon, p.x + 10, yy + 9, 26) + T_(p.x + 46, yy + 20, c.name, 14, C.TEXT, 600) + T_(p.x + 46, yy + 36, c.note || "", 12, C.MUTED); });
  else if (p.key === "forwards") lab.port_forwards.forEach((f, i) => { const yy = p.y + 72 + i * 44; s += R_(p.x + 14, yy, p.w - 28, 38, 8, C.CHIP, C.BORDER, 1) + T_(p.x + 26, yy + 24, f.port, 13, C.TEXT, 600, "start", true) + T_(p.x + 236, yy + 17, f.to || "", 13.5, C.TEXT, 600) + T_(p.x + 236, yy + 32, f.what || "", 11.5, C.MUTED); });
  else s += T_(p.x + 20, p.y + 60, "(wird im Diagramm vollständig gezeichnet)", 12.5, C.MUTED);
  return s + "</g>";
}
function drawInternet(lab, cx) {
  const cy = 172, blobs = [[-95, 18, 42], [-45, -8, 56], [25, -18, 62], [90, 6, 48], [130, 26, 30], [-130, 30, 28]];
  let s = `<g class="internet">`;
  for (const [dx, dy, r] of blobs) s += `<circle cx="${cx + dx}" cy="${cy + dy}" r="${r + 2.5}" fill="#3a4a60"/>`;
  s += `<rect x="${cx - 150}" y="${cy + 12}" width="300" height="46" rx="23" fill="#3a4a60"/>`;
  for (const [dx, dy, r] of blobs) s += `<circle cx="${cx + dx}" cy="${cy + dy}" r="${r}" fill="#1a2433"/>`;
  s += `<rect x="${cx - 147.5}" y="${cy + 14.5}" width="295" height="41" rx="20.5" fill="#1a2433"/>`;
  s += T_(cx, cy + 14, (lab.internet || {}).label || "Internet", 26, C.TEXT, 600, "middle") + T_(cx, cy + 40, (lab.internet || {}).sub || "", 13, C.MUTED, 400, "middle");
  return s + "</g>";
}
