// Planer core: constants (same look as the diagram), text measuring, card geometry (same rules as
// hld/render.py Node), endpoints of cables (same rules as hld/layouts_manual.py), checks
// (like hld/validate.py), IP list (like hld/ips.py), conversion of old files (like hld/legacy.py).
"use strict";
const C = { BG: "#0b0f15", GRID: "#151c26", PANEL: "#111821", PANEL2: "#161f2b", CHIP: "#19222e", BORDER: "#253042",
  TEXT: "#e6edf3", MUTED: "#8d9aab", FAINT: "#5d6a7c", TRUNK: "#d5dde6", TRUNK_BORDER: "#3a475a", LINK: "#79c0ff",
  HWC: "#c08a5c", RED: "#ff7b72", OK: "#3fb950", SEL: "#58a6ff" };
const SPEED_W = { "40G": 11.5, "25G": 10.5, "10G": 9.5, "5G": 5.0, "2.5G": 3.8, "1G": 2.4, "100M": 1.4 };
const SPEEDS = Object.keys(SPEED_W);
const TAB = 34, GRID = 8;
const ROLES = [
  ["isp_router", "ISP-Router / Modem"], ["firewall", "Firewall"], ["router", "Router"], ["switch", "Switch"],
  ["ap", "Access Point"], ["server", "Server (Proxmox)"], ["nas", "NAS"], ["workstation", "PC / Laptop"],
  ["pi", "Raspberry Pi"], ["kvm", "KVM"], ["iot", "IoT-Gerät"], ["printer", "Drucker"], ["ups", "USV"], ["other", "Sonstiges"]];
const INFRA = ["isp_router", "firewall", "router", "switch"];
const LINK_KINDS = [["cable", "Kabel"], ["wifi", "WLAN"], ["kvm", "KVM-Konsole"], ["vpn", "VPN (nicht gezeichnet)"]];
const STATUS = [["active", "vorhanden"], ["planned", "geplant"], ["later", "später"]];

// ------------------------------------------------------------------ text measuring (real Fira fonts)
const _cv = document.createElement("canvas").getContext("2d");
const _mcache = new Map();
function mw(s, size, weight = 400, mono = false) {
  s = String(s ?? "");
  const k = s + "|" + size + "|" + weight + "|" + mono;
  if (_mcache.has(k)) return _mcache.get(k);
  _cv.font = `${weight} ${size}px ${mono ? '"Fira Code"' : '"Fira Sans"'}`;
  const w = _cv.measureText(s).width;
  _mcache.set(k, w);
  return w;
}
function clearMeasureCache() { _mcache.clear(); }

// ------------------------------------------------------------------ lab helpers
function emptyLab() {
  return { schema: 2, meta: { title: "Mein Homelab", title_redacted: "Mein Homelab", date: "", watermark: "", domain: "example.com" },
    redact: { domain: true, domain_placeholder: "redacted.com", ssid_names: true },
    networks: [{ key: "10", name: "LAN", subnet: "192.168.10.0/24", color: "#58a6ff", note: "" }],
    internet: { label: "Internet", sub: "", speed: { down: "", up: "" } }, remote: [], cloud: [],
    devices: [], links: [], port_forwards: [], panels: [], ip_extra: [], layout: { mode: "manual", panels: {} } };
}
function normalize(lab) {
  for (const k of ["networks", "devices", "links", "port_forwards", "cloud", "remote", "panels", "ip_extra"])
    if (!Array.isArray(lab[k])) lab[k] = [];
  lab.meta = lab.meta || {}; lab.redact = lab.redact || {}; lab.internet = lab.internet || { label: "Internet" };
  lab.layout = lab.layout || {}; lab.layout.panels = lab.layout.panels || {}; lab.layout.mode = "manual";
  lab.schema = 2;
  for (const n of lab.networks) { n.key = String(n.key); }
  for (const d of lab.devices) {
    d.id = String(d.id); d.icons = d.icons || []; d.ports = d.ports || [];
    if (d.net != null) d.net = String(d.net);
    for (const p of d.ports) { p.id = String(p.id); if (p.untagged != null) p.untagged = String(p.untagged); p.tagged = (p.tagged || []).map(String); }
    for (const g of d.guests || []) if (g.net != null) g.net = String(g.net);
  }
  for (const l of lab.links) { l.a = String(l.a); l.b = String(l.b); if (l.net != null) l.net = String(l.net); l.vlans = (l.vlans || []).map(String); l.speed = String(l.speed || "1G"); }
  return lab;
}
const netOf = (lab, key) => lab.networks.find(n => n.key === String(key));
const color = (lab, key) => (netOf(lab, key) || {}).color || C.MUTED;
const devOf = (lab, id) => lab.devices.find(d => d.id === id);
function splitEnd(e) { const s = String(e); const i = s.indexOf("."); return i < 0 ? [s, null] : [s.slice(0, i), s.slice(i + 1)]; }
function portOf(l, dev) { for (const e of [l.a, l.b]) { const [d, p] = splitEnd(e); if (d === dev) return p; } return null; }
function otherDev(l, dev) { const [a] = splitEnd(l.a); const [b] = splitEnd(l.b); return a === dev ? b : a; }
const isTrunk = l => (l.vlans || []).length > 0;
function lineW(l) {
  if (l.kind === "kvm" || l.kind === "wifi") return 2;
  return (SPEED_W[l.speed] || 2.4) + (isTrunk(l) ? 3.4 : 0);
}
function vtag(lab, key) { const n = netOf(lab, key); if (!n) return String(key ?? ""); const t = n.tag || (/^\d+$/.test(n.key) ? "VLAN " + n.key : n.name); return t.startsWith("VLAN") ? `${t} · ${n.name}` : n.name; }
function hostName(o, lab) {
  if (o.host) return [`${o.host}.${(lab.meta || {}).domain || "example.com"}`, C.LINK];
  if (o.internal) return [`${o.internal}.internal`, null];
  return [null, null];
}

// ------------------------------------------------------------------ card geometry (as hld Node)
function tabWidth(d) { return 16 + mw(d.name || d.id, 20, 700) + 7 + mw("·", 20, 700) + 7 + mw(d.type || "", 14, 600) + 18; }
function addrW(d, lab) {
  const cw = 12 * 0.6; let w = String(d.ip || "").length * cw;
  const [h] = hostName(d, lab); if (h) w += cw * 0.6 + cw * 1.6 + mw(h, 12, 400, true);
  return w;
}
function headerW(d, lab) {
  const tx = 14 + 58 * Math.max(1, (d.icons || []).length) + 8;
  return tx + Math.max(mw(d.model || "custom build", 14, 500), addrW(d, lab), mw(d.os || "", 12), mw(d.config || "", 12));
}
function geom(d, lab) {
  const g = { kind: "device", tab_w: tabWidth(d), hdr: headerW(d, lab), port_x: {} };
  const portRow = (d.role === "isp_router" || d.role === "switch") && (d.ports || []).length;
  if (portRow && d.role === "isp_router") {
    g.kind = "isp"; let x = g.hdr + 46, lastCoax = false;
    d.ports.forEach((p, i) => { if (i) x += lastCoax ? 64 : 52; g.port_x[p.id] = x; lastCoax = p.kind === "coax"; });
    g.w = Math.max(x + 46, g.tab_w + 40); g.h = 104; g.port_y = 28;
  } else if (portRow) {
    g.kind = "switch"; const px0 = g.hdr + 30; const nr = d.ports.filter(p => p.kind !== "sfp").length;
    const pitch = d.ports.length <= 14 ? 58 : 52; let ri = 0, si = 0;
    for (const p of d.ports) {
      if (p.kind === "sfp") { g.port_x[p.id] = px0 + nr * pitch + 22 + 30 + si * 70; si++; }
      else { g.port_x[p.id] = px0 + ri * pitch + 24; ri++; }
    }
    g.pitch = pitch; g.w = Math.max(...Object.values(g.port_x)) + 30 + 64; g.h = 112; g.port_y = 30;
  } else if (INFRA.includes(d.role)) {
    g.kind = "appliance";
    const hw = d.hw || [], sv = d.services || [];
    g.hw_w = hw.length ? Math.max(200, ...hw.map(h => 62 + Math.max(mw(h.value || "", 15.5, 700), mw(h.sub || "", 10.5) - 4))) : 0;
    g.sv_w = sv.length ? Math.max(190, ...sv.map(s => 44 + Math.max(mw(s.name || "", 14, 600), mw(s.note || "", 11.5)) + 12)) : 0;
    g.sv_cols = Math.min(3, sv.length);
    const body = 16 + (hw.length ? g.hw_w + 28 : 0) + (g.sv_cols ? g.sv_cols * (g.sv_w + 9) - 9 : 0) + 18;
    g.w = Math.max(body, g.hdr + 30 + 2 * 54 + 48);
    const content = Math.max(hw.length * 64, (g.sv_cols ? Math.ceil(sv.length / g.sv_cols) : 0) * 58);
    g.h = (content ? 106 + content : 96) + 68;
  } else if ((d.guests || []).length || (d.role === "server" && (d.hw || []).length)) {
    g.kind = "server";
    g.w = (d.pos && d.pos.w) ? +d.pos.w : 1100;
    g.h = serverHeight(d, g.w);
  } else {
    const ss = d.ssids || [];
    let bw = g.hdr + 20;
    if (ss.length) bw = Math.max(bw, 150 + Math.max(...ss.map(s => mw(vtag(lab, s.vlan), 12, 500, true))) + 18);
    g.w = Math.max(bw, g.tab_w + 120);
    g.h = ss.length ? 106 + ss.length * 17 + 3 : (d.config ? 92 : 86);
  }
  if ((d.extra_h || 0) > 0) g.h += d.extra_h;
  return g;
}
// estimate of hld/server.py ServerCard height for a given width
function serverHeight(d, w) {
  const hw = d.hw || [], guests = d.guests || [];
  const feat = guests.filter(g => g.featured), rest = guests.filter(g => !g.featured);
  const hwh = hw.length ? 22 + hw.length * 64 : 0;
  const fgh = feat.reduce((a, g) => a + (g.pools && g.pools.length ? 84 + g.pools.length * 140 + 24 : g.addons && g.addons.length ? 120 : 84) + 14, 0);
  const zw = w - 20 - 20 - (hw.length ? 270 : 0) - (feat.length ? 500 : 0);
  const ncol = Math.max(1, Math.floor((zw - 32 + 14) / (354)));
  const zones = {};
  for (const g of rest) { const k = g.net ?? "?"; (zones[k] = zones[k] || {}); (zones[k][g.group || ""] = zones[k][g.group || ""] || []).push(g); }
  let zh = 0;
  for (const z of Object.values(zones)) {
    const ghs = Object.entries(z).map(([n, gs]) => (n ? 22 : 0) + gs.reduce((a, g) => a + ((g.apps || []).length ? 54 + g.apps.length * 21 : 64) + 7, 0) + 14);
    const total = ghs.reduce((a, b) => a + b, 0);
    zh += 56 + Math.max(Math.max(...ghs), total / ncol) + 6 + 16;
  }
  return 92 + Math.max(hwh, fgh, zh, 60) + 22;
}
function boxOf(d, lab) {
  const g = geom(d, lab); const p = d.pos || { x: 0, y: 0 };
  return { x: +p.x, y: +p.y, w: g.w, h: g.h, g };
}

// ------------------------------------------------------------------ cable endpoints (as layouts_manual)
function sideTowards(a, b) {
  if (b.y >= a.y + a.h) return "S";
  if (b.y + b.h <= a.y) return "N";
  return (b.x + b.w / 2 > a.x + a.w / 2) ? "E" : "W";
}
function spread(want, lo, hi, sp) {
  // positions close to want (sorted), at least sp apart, inside [lo, hi] (pool adjacent violators)
  const n = want.length; if (!n) return [];
  if (hi - lo < sp * (n - 1)) sp = Math.max(20, (hi - lo) / Math.max(1, n - 1));
  const t = want.map((x, i) => x - i * sp);
  const blocks = [];
  for (const v of t) { blocks.push([v, 1]); while (blocks.length > 1 && blocks[blocks.length - 2][0] > blocks[blocks.length - 1][0]) { const [v2, c2] = blocks.pop(); const [v1, c1] = blocks.pop(); blocks.push([(v1 * c1 + v2 * c2) / (c1 + c2), c1 + c2]); } }
  const ys = []; for (const [v, c] of blocks) for (let k = 0; k < c; k++) ys.push(v);
  const top = hi - sp * (n - 1);
  return ys.map((y, i) => Math.max(lo, Math.min(y, top)) + i * sp);
}
function cableEnds(lab, boxes) {
  const ends = new Map(), groups = new Map();
  for (const l of lab.links) {
    if (l.kind === "vpn") continue;
    const [ai] = splitEnd(l.a), [bi] = splitEnd(l.b);
    const A = boxes[ai], B = boxes[bi]; if (!A || !B) continue;
    const sides = l.sides || {};
    for (const [nid, n, o] of [[ai, A, B], [bi, B, A]]) {
      const side = sides[nid] || sideTowards(n, o);
      const p = portOf(l, nid);
      if ((n.g.kind === "isp" || n.g.kind === "switch") && p in n.g.port_x && (side === "S" || side === "N")) {
        ends.set(l, Object.assign(ends.get(l) || {}, { [nid]: [n.x + n.g.port_x[p], side === "S" ? n.y + n.h : n.y, side] }));
        continue;
      }
      const k = nid + "|" + side; if (!groups.has(k)) groups.set(k, []); groups.get(k).push([l, o]);
    }
  }
  for (const [k, lst] of groups) {
    const [nid, side] = k.split("|"); const n = boxes[nid]; const free = n.g.kind === "appliance";
    if (side === "N" || side === "S") {
      lst.sort((a, b) => (a[1].x + a[1].w / 2) - (b[1].x + b[1].w / 2));
      let lo = n.x + (free ? 54 : 24);
      if (side === "N" && (n.g.kind === "device" || n.g.kind === "server")) lo = n.x + n.g.tab_w + 34;
      else if (side === "N" && free) lo = n.x + n.g.hdr + 54;
      const hi = Math.max(lo, n.x + n.w - (free ? 54 : 40));
      const xs = spread(lst.map(t => t[1].x + t[1].w / 2), lo, hi, free ? 58 : side === "N" ? 70 : 30);
      lst.forEach(([l], i) => ends.set(l, Object.assign(ends.get(l) || {}, { [nid]: [xs[i], side === "N" ? n.y : n.y + n.h, side] })));
    } else {
      lst.sort((a, b) => (a[1].y + a[1].h / 2) - (b[1].y + b[1].h / 2));
      const mid = n.y + Math.min(n.h / 2, 46), x = side === "W" ? n.x : n.x + n.w;
      lst.forEach(([l], i) => ends.set(l, Object.assign(ends.get(l) || {}, { [nid]: [x, mid + (i - (lst.length - 1) / 2) * 30, side] })));
    }
  }
  return ends;
}
// a simple right-angled path for the editor (the diagram tool routes cables without waypoints itself)
function cablePath(a, b, via) {
  const out = (p, s, d = 24) => s === "N" ? [p[0], p[1] - d] : s === "S" ? [p[0], p[1] + d] : s === "W" ? [p[0] - d, p[1]] : [p[0] + d, p[1]];
  const pts = [[a[0], a[1]]];
  if (via && via.length) {
    let vertical = a[2] === "N" || a[2] === "S";
    for (const q0 of [...via, [b[0], b[1]]]) {
      const q = [+q0[0], +q0[1]], p = pts[pts.length - 1];
      if (Math.abs(p[0] - q[0]) > .5 && Math.abs(p[1] - q[1]) > .5) { pts.push(vertical ? [p[0], q[1]] : [q[0], p[1]]); vertical = !vertical; }
      else vertical = Math.abs(p[0] - q[0]) <= .5;
      pts.push(q);
    }
    return pts;
  }
  const s = out(a, a[2]), e = out(b, b[2]);
  pts.push(s);
  const av = a[2] === "N" || a[2] === "S", bv = b[2] === "N" || b[2] === "S";
  if (av && bv) { const my = (s[1] + e[1]) / 2; pts.push([s[0], my], [e[0], my]); }
  else if (!av && !bv) { const mx = (s[0] + e[0]) / 2; pts.push([mx, s[1]], [mx, e[1]]); }
  else if (av) pts.push([s[0], e[1]]);
  else pts.push([e[0], s[1]]);
  pts.push(e, [b[0], b[1]]);
  return pts.filter((p, i) => i === 0 || Math.abs(p[0] - pts[i - 1][0]) + Math.abs(p[1] - pts[i - 1][1]) > .1);
}

// ------------------------------------------------------------------ IPv4 helpers, IP list, checks
function ip4(s) { const m = String(s).trim().match(/^(\d+)\.(\d+)\.(\d+)\.(\d+)$/); if (!m) return null; const v = m.slice(1).map(Number); if (v.some(x => x > 255)) return null; return ((v[0] << 24) >>> 0) + (v[1] << 16) + (v[2] << 8) + v[3]; }
function cidr(s) { const m = String(s || "").match(/^([\d.]+)\/(\d+)$/); if (!m) return null; const a = ip4(m[1]); if (a == null) return null; const bits = +m[2]; const mask = bits ? (~0 << (32 - bits)) >>> 0 : 0; return { net: (a & mask) >>> 0, mask, size: 2 ** (32 - bits) }; }
function inNet(ip, n) { const c = cidr(n.subnet); const a = ip4(ip); return c && a != null && ((a & c.mask) >>> 0) === c.net; }
function fullIp(lab, key, ip, base) {
  ip = String(ip).trim();
  if (!ip.startsWith(".")) return ip;
  let pre = base; if (!pre) { const n = netOf(lab, key); if (!n || !cidr(n.subnet)) return ip; pre = n.subnet.split("/")[0]; }
  return pre.split(".").slice(0, 3).join(".") + ip;
}
function netOfIp(lab, ip) { return (lab.networks.find(n => inNet(ip, n)) || {}).key ?? null; }
function collectIps(lab) {
  const out = [];
  const add = (ip, name, kind, key, base) => { const f = fullIp(lab, key, ip, base); out.push({ ip: f, name, kind, net: key && String(ip).startsWith(".") ? key : netOfIp(lab, f) }); };
  for (const d of lab.devices) {
    if (d.ip) {
      const parts = String(d.ip).split("/").map(s => s.trim());
      parts.forEach((p, j) => add(p, d.name + ((d.ip_labels || [])[j] ? " · " + d.ip_labels[j] : ""), d.type || d.role, j ? null : d.net, j ? fullIp(lab, d.net, parts[0]) : null));
    }
    for (const p of d.ports || []) {
      if (!p.ip) continue;
      for (const l of lab.links) if (portOf(l, d.id) === p.id) for (const k of (l.vlans.length ? l.vlans : l.net ? [l.net] : [])) add(p.ip, d.name, l.vlans.length ? "gateway" : (netOf(lab, k) || {}).name || "", k);
    }
    for (const g of d.guests || []) if (g.ip) add(g.ip, g.name, `${g.kind || "CT"} ${g.id}`, g.net);
  }
  for (const e of lab.ip_extra || []) add(e.ip, e.name, e.kind || "", e.vlan != null ? String(e.vlan) : null);
  const seen = new Map();
  for (const e of out) { const o = e.name.split(" · ")[0]; if (!seen.has(e.ip)) seen.set(e.ip, new Set()); seen.get(e.ip).add(o); }
  const uniq = [], keys = new Set();
  for (const e of out) { e.conflict = seen.get(e.ip).size > 1; const k = e.ip + "|" + e.name; if (!keys.has(k)) { keys.add(k); uniq.push(e); } }
  return uniq;
}
function checks(lab, boxes) {
  const err = [], warn = [];
  const nets = new Set(lab.networks.map(n => n.key)), ids = new Set();
  for (const d of lab.devices) {
    const w = `Gerät „${d.name || d.id}“`;
    if (ids.has(d.id)) err.push([d.id, `${w}: ID ${d.id} doppelt`]); ids.add(d.id);
    if (d.net != null && !nets.has(d.net)) err.push([d.id, `${w}: Netz „${d.net}“ gibt es nicht`]);
    for (const p of d.ports || []) for (const k of [p.untagged, ...(p.tagged || [])].filter(x => x != null && x !== ""))
      if (!nets.has(String(k))) err.push([d.id, `${w}, Port ${p.id}: VLAN „${k}“ gibt es nicht`]);
    const vm = new Set();
    for (const g of d.guests || []) {
      if (vm.has(g.id)) err.push([d.id, `${w}, Gast „${g.name}“: VMID ${g.id} doppelt`]); vm.add(g.id);
      if (g.net != null && !nets.has(String(g.net))) err.push([d.id, `${w}, Gast „${g.name}“: Netz „${g.net}“ gibt es nicht`]);
      if (!(g.icons || []).length) err.push([d.id, `${w}, Gast „${g.name}“: braucht ein Icon`]);
    }
  }
  const used = new Map();
  lab.links.forEach((l, i) => {
    const w = `Verbindung ${l.a} ↔ ${l.b}`;
    for (const e of [l.a, l.b]) {
      const [dv, p] = splitEnd(e); const d = devOf(lab, dv);
      if (!d) { err.push([null, `${w}: Gerät „${dv}“ gibt es nicht`]); continue; }
      if (p && (d.role === "switch" || d.role === "isp_router") && d.ports.length && !d.ports.some(x => x.id === p)) err.push([dv, `${w}: Port „${p}“ gibt es an „${d.name}“ nicht`]);
      if (p && (l.kind || "cable") === "cable") { const k = dv + "." + p; if (used.has(k)) err.push([dv, `${w}: Port ${k} ist schon belegt`]); used.set(k, i); }
    }
    for (const k of [l.net, ...(l.vlans || [])].filter(x => x != null && x !== "")) if (!nets.has(String(k))) err.push([null, `${w}: Netz/VLAN „${k}“ gibt es nicht`]);
  });
  for (const e of collectIps(lab)) {
    if (ip4(e.ip) == null) { err.push([null, `„${e.name}“: „${e.ip}“ ist keine gültige IP`]); continue; }
    const n = e.net ? netOf(lab, e.net) : null;
    if (n && n.subnet && !inNet(e.ip, n)) warn.push([null, `„${e.name}“: ${e.ip} liegt nicht im Netz ${n.name} (${n.subnet})`]);
    if (e.conflict) warn.push([null, `IP ${e.ip} doppelt vergeben (${e.name})`]);
  }
  // overlapping cards (the diagram would report them too)
  const bx = Object.entries(boxes);
  for (let i = 0; i < bx.length; i++) for (let j = i + 1; j < bx.length; j++) {
    const [ia, a] = bx[i], [ib, b] = bx[j];
    const ay = a.y - TAB, by = b.y - TAB;
    if (a.x < b.x + b.w + 8 && b.x < a.x + a.w + 8 && ay < b.y + b.h + 8 && by < a.y + a.h + 8)
      warn.push([ia, `„${devOf(lab, ia).name}“ und „${devOf(lab, ib).name}“ liegen zu dicht oder übereinander`]);
  }
  return { err, warn };
}

// ------------------------------------------------------------------ old inventory.yaml (schema 1) → schema 2 (as hld/legacy.py)
function convertLegacy(inv) {
  const nets = inv.vlans.map(v => ({ key: String(v.key), tag: v.tag, name: v.name, subnet: v.subnet, color: v.color, note: v.note }));
  const trunkV = inv.vlans.filter(v => String(v.tag).startsWith("VLAN")).map(v => String(v.key));
  const fb = inv.fritzbox, opn = inv.opnsense, sw = inv.switch, dev = inv.devices, T = inv.terra;
  const fbPorts = [{ id: "cable", label: "Cable", kind: "coax", uplink: true, note: "internet" }];
  fb.lan_ports.forEach((sp, i) => fbPorts.push(Object.assign({ id: `lan${i + 1}`, label: sp }, i === fb.opnsense_port ? { note: "exposed host" } : {})));
  const swPorts = sw.ports.map(p => { const sfp = p.name.startsWith("sfpp"); return { id: p.name, label: sfp ? "SFP+" + p.name.slice(-1) : p.name.replace("ether", ""), kind: sfp ? "sfp" : "rj45", untagged: p.untagged, tagged: p.tagged || [], to: p.to }; });
  const device = (key, role, extra) => { const d = Object.assign({}, dev[key], { id: key, role }, extra || {}); d.net = String(d.vlan); delete d.vlan; if (d.trunk) d.border = "trunk"; delete d.trunk; return d; };
  const guests = [];
  for (const g of Object.values(T.other_guests)) { const x = Object.assign({}, g, { net: String(g.vlan), featured: true }); delete x.vlan; guests.push(x); }
  for (const grp of T.dmz_groups) for (const g of grp.guests) guests.push(Object.assign({}, g, { net: "20", group: grp.name, kind: g.kind || "CT" }));
  return { schema: 2, meta: inv.meta, redact: inv.redact, networks: nets,
    internet: { label: "Internet", sub: "semi-static public IPv4", speed: inv.internet.speed },
    remote: [Object.assign({}, inv.remote, { icon: "wireguard", net: "vpn" })], cloud: inv.internet.cloud_services || [],
    devices: [
      { id: "fritzbox", role: "isp_router", name: fb.name, type: fb.type, model: fb.model, ip: fb.ip, os: fb.os, net: "wan", icons: ["fritzbox"], ports: fbPorts },
      { id: "opnsense", role: "firewall", name: opn.name, type: opn.type, model: opn.model, os: opn.os, ip: opn.ip, internal: opn.internal, net: "99", border: "trunk", icons: ["opnsense"], hw: opn.hw, services: opn.services, ports: [{ id: "wan", ip: opn.wan_ip }, { id: "lan1" }, { id: "lan2", ip: ".1" }] },
      { id: "mikrotik", role: "switch", name: sw.name, type: sw.type, model: sw.model, ip: sw.ip, internal: sw.internal, os: sw.os, config: sw.config || "", net: "99", border: "trunk", icons: ["mikrotik-l"], ports: swPorts },
      device("madcat", "workstation"), device("jetkvm", "kvm"), device("ap", "ap", { ssids: inv.ssids || [] }), device("slzb", "iot"),
      { id: "terra", role: "server", name: T.name, type: T.type, model: T.model, os: T.os, ip: T.ip, internal: T.internal, net: "10", border: "trunk", icons: ["proxmox"], hw: T.hw, guests, zones: { "20": { note: "one unprivileged LXC per service · web apps behind Traefik (CT 149)" } } }],
    links: [
      { a: `fritzbox.lan${fb.opnsense_port + 1}`, b: "opnsense.wan", speed: "1G", net: "wan" },
      { a: "mikrotik.ether1", b: "opnsense.lan1", speed: "2.5G", vlans: trunkV, lag: "lacp", lag_label: "LACP · dual 2.5G" },
      { a: "mikrotik.ether2", b: "opnsense.lan2", speed: "2.5G", vlans: trunkV, lag: "lacp", lag_label: "LACP · dual 2.5G" },
      { a: "mikrotik.ether3", b: "madcat", speed: "2.5G", net: "10" }, { a: "mikrotik.sfpp1", b: "madcat", speed: "10G", net: "10" },
      { a: "mikrotik.ether5", b: "jetkvm", speed: "100M", net: "10" }, { a: "mikrotik.ether6", b: "ap", speed: "2.5G", vlans: ["99", "10", "30", "40"] },
      { a: "mikrotik.ether7", b: "slzb", speed: "100M", net: "40" }, { a: "mikrotik.sfpp2", b: "terra", speed: "10G", vlans: ["10", "20", "40", "99"] },
      { a: "jetkvm", b: "terra", kind: "kvm", label: "HDMI + USB console" }],
    port_forwards: inv.port_forwards || [], panels: T.media_pipeline ? [Object.assign({}, T.media_pipeline, { type: "media_pipeline" })] : [],
    ip_extra: inv.ip_extra || [] };
}

// ------------------------------------------------------------------ templates for new devices
function template(role, lab) {
  const net = (lab.networks[0] || {}).key || null;
  const n = lab.devices.filter(d => d.role === role).length + 1;
  const base = { role, net, status: "planned", icons: [], ports: [] };
  const T = {
    isp_router: { name: "Modem", type: "ISP", model: "Provider-Router", icons: ["fritzbox"], ports: [{ id: "wan", label: "WAN", kind: "coax", uplink: true, note: "internet" }, { id: "lan1", label: "1G" }, { id: "lan2", label: "1G" }] },
    firewall: { name: "Firewall", type: "router/firewall", model: "Mini-PC", os: "OPNsense", icons: ["opnsense"], border: "trunk", hw: [{ icon: "glyph-cpu", label: "CPU", value: "", sub: "" }], services: [], ports: [{ id: "wan" }, { id: "lan" }] },
    router: { name: "Router", type: "router", icons: ["opnsense"], border: "trunk" },
    switch: { name: "Switch", type: "switch", model: "Managed Switch", icons: ["glyph-switch"], border: "trunk", ports: [...Array(8).keys()].map(i => ({ id: "p" + (i + 1), label: String(i + 1) })).concat([{ id: "sfp1", label: "SFP+1", kind: "sfp" }, { id: "sfp2", label: "SFP+2", kind: "sfp" }]) },
    ap: { name: "Access Point", type: "access point", icons: ["glyph-antenna"], border: "trunk", ssids: [{ name: "WLAN", redacted: "WLAN", vlan: net }] },
    server: { name: "Server", type: "server", model: "Proxmox Node", os: "Proxmox VE", icons: ["proxmox"], border: "trunk", hw: [{ icon: "glyph-cpu", label: "CPU", value: "", sub: "" }, { icon: "glyph-ram", label: "MEMORY", value: "", sub: "" }], guests: [{ id: 100, kind: "CT", name: "Dienst", icons: ["docker"], net, ip: ".100", note: "", group: "Dienste" }], pos: { w: 1100 } },
    nas: { name: "NAS", type: "NAS", icons: ["omv"] }, workstation: { name: "PC", type: "workstation", icons: ["debian"] },
    pi: { name: "Pi", type: "Pi", model: "Raspberry Pi", icons: ["raspberrypi"] }, kvm: { name: "KVM", type: "IP-KVM", icons: ["glyph-kvm"] },
    iot: { name: "IoT-Gerät", type: "IoT", icons: ["glyph-antenna"] }, printer: { name: "Drucker", type: "printer", icons: ["bambulab"] },
    ups: { name: "USV", type: "UPS", icons: ["glyph-ups"] }, other: { name: "Gerät", type: "Gerät", icons: ["glyph-antenna"] } };
  const d = Object.assign(base, JSON.parse(JSON.stringify(T[role] || T.other)));
  let id = role.replace("_router", "") + n; while (devOf(lab, id)) id += "x";
  d.id = id; if (n > 1) d.name += " " + n;
  return d;
}
