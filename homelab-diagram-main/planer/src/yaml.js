// Small YAML reader/writer for lab files (no external library: the planner works offline).
// Reads: block mappings and sequences, flow {…} and […], quoted and plain scalars, comments,
// numbers, true/false/null. Writes: readable block style, short objects as one-line flow maps.
"use strict";
const YAML = (() => {
  function scalar(s) {
    s = s.trim();
    if (s === "" || s === "~" || s === "null") return null;
    if (s === "true") return true;
    if (s === "false") return false;
    if (/^-?\d+$/.test(s)) return parseInt(s, 10);
    if (/^-?\d*\.\d+$/.test(s)) return parseFloat(s);
    if ((s[0] === '"' && s.endsWith('"')) || (s[0] === "'" && s.endsWith("'"))) {
      if (s[0] === "'") return s.slice(1, -1).replace(/''/g, "'");
      return JSON.parse(s.replace(/\\'/g, "'"));
    }
    return s;
  }
  // strip a trailing comment that is not inside quotes
  function stripComment(line) {
    let q = null;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) { if (c === q && line[i - 1] !== "\\") q = null; continue; }
      if (c === '"' || c === "'") { if (i === 0 || /[\s:\[{,-]/.test(line[i - 1])) q = c; continue; }
      if (c === "#" && (i === 0 || /\s/.test(line[i - 1]))) return line.slice(0, i);
    }
    return line;
  }
  // flow style: {a: 1, b: [x, y]} / [..]
  function parseFlow(s, pos) {
    const ws = () => { while (pos.i < s.length && /\s/.test(s[pos.i])) pos.i++; };
    ws();
    const c = s[pos.i];
    if (c === "{") {
      pos.i++; const obj = {};
      for (;;) {
        ws(); if (s[pos.i] === "}" || pos.i >= s.length) { pos.i++; return obj; }
        const before = pos.i;
        const key = readToken(s, pos, ":"); pos.i++;
        if (pos.i <= before) throw new Error("YAML: kann {…} nicht lesen bei Zeichen " + before);
        obj[String(scalar(key))] = parseFlow(s, pos); ws();
        if (s[pos.i] === ",") pos.i++;
      }
    }
    if (c === "[") {
      pos.i++; const arr = [];
      for (;;) {
        ws(); if (s[pos.i] === "]" || pos.i >= s.length) { pos.i++; return arr; }
        const before = pos.i;
        arr.push(parseFlow(s, pos)); ws();
        if (pos.i <= before) throw new Error("YAML: kann […] nicht lesen bei Zeichen " + before);
        if (s[pos.i] === ",") pos.i++;
      }
    }
    return scalar(readToken(s, pos, ",]}"));
  }
  function readToken(s, pos, stops) {
    let out = "", q = null;
    while (pos.i < s.length) {
      const c = s[pos.i];
      if (q) { out += c; pos.i++; if (c === q && s[pos.i - 2] !== "\\") q = null; continue; }
      if ((c === '"' || c === "'") && out.trim() === "") { q = c; out += c; pos.i++; continue; }
      if (stops.includes(c)) {
        if (c === ":" && !/\s/.test(s[pos.i + 1] || " ") && stops === ":") { out += c; pos.i++; continue; }
        break;
      }
      out += c; pos.i++;
    }
    return out.trim();
  }
  function inlineValue(v) {
    v = v.trim();
    if (v === "") return undefined;
    if (v[0] === "{" || v[0] === "[") return parseFlow(v, { i: 0 });
    if (v === "|" || v === ">") return undefined;
    return scalar(v);
  }
  // split "key: value" (key may be quoted)
  function splitKey(t) {
    let q = null;
    for (let i = 0; i < t.length; i++) {
      const c = t[i];
      if (q) { if (c === q) q = null; continue; }
      if ((c === '"' || c === "'") && i === 0) { q = c; continue; }
      if (c === ":" && (i + 1 === t.length || t[i + 1] === " ")) return [t.slice(0, i), t.slice(i + 1)];
      if ((c === "{" || c === "[") && i === 0) return null;
    }
    return null;
  }
  function parse(text) {
    const lines = [];
    for (const raw of text.replace(/\r/g, "").split("\n")) {
      const l = stripComment(raw);
      if (!l.trim() || l.trim() === "---") continue;
      lines.push({ ind: l.length - l.trimStart().length, t: l.trim() });
    }
    // join flow collections that continue over several lines
    for (let i = 0; i < lines.length; i++) {
      const open = (x) => (x.match(/[\[{]/g) || []).length - (x.match(/[\]}]/g) || []).length;
      while (open(lines[i].t) > 0 && i + 1 < lines.length) {
        lines[i].t += " " + lines[i + 1].t; lines.splice(i + 1, 1);
      }
    }
    let i = 0;
    const anchors = {};
    // "&name value" / "*name": YAML anchors and aliases (written by some exporters)
    function anchored(raw, then) {
      const t = raw.trim();
      if (t.startsWith("*")) return anchors[t.slice(1)];
      if (t.startsWith("&")) {
        const sp = t.indexOf(" ");
        const name = sp < 0 ? t.slice(1) : t.slice(1, sp);
        const v = sp < 0 ? then() : inlineValue(t.slice(sp + 1));
        anchors[name] = v;
        return v;
      }
      return undefined;
    }
    function block(ind) {
      if (i >= lines.length) return null;
      if (lines[i].t[0] === "{" || lines[i].t[0] === "[") {     // a flow value on its own line
        const v = inlineValue(lines[i].t); i++; return v;
      }
      if (lines[i].t.startsWith("- ") || lines[i].t === "-") {
        const arr = [];
        while (i < lines.length && lines[i].ind === ind && (lines[i].t.startsWith("- ") || lines[i].t === "-")) {
          const rest = lines[i].t.slice(2);
          const kv = splitKey(rest);
          if (kv) {                                      // "- key: value" starts a mapping item
            const childInd = ind + 2;
            lines[i] = { ind: childInd, t: rest };
            arr.push(mapping(childInd));
          } else if (rest.trim() === "") {
            i++; arr.push(block(lines[i] ? lines[i].ind : ind + 2));
          } else { arr.push(inlineValue(rest)); i++; }
        }
        return arr;
      }
      return mapping(ind);
    }
    function mapping(ind) {
      const obj = {};
      while (i < lines.length && lines[i].ind === ind && !lines[i].t.startsWith("- ")) {
        const kv = splitKey(lines[i].t);
        if (!kv) { i++; continue; }
        const key = String(scalar(kv[0]));
        i++;
        const vt = kv[1].trim();
        if (vt.startsWith("&") || vt.startsWith("*")) {
          obj[key] = anchored(vt, () => (i < lines.length && (lines[i].ind > ind ||
            (lines[i].ind === ind && lines[i].t.startsWith("- "))) ? block(lines[i].ind) : null));
          continue;
        }
        const v = inlineValue(kv[1]);
        if (v !== undefined) obj[key] = v;
        else if (i < lines.length && (lines[i].ind > ind || (lines[i].ind === ind && lines[i].t.startsWith("- "))))
          obj[key] = block(lines[i].ind);
        else obj[key] = null;
      }
      return obj;
    }
    return lines.length ? block(lines[0].ind) : {};
  }

  // ---------------------------------------------------------------- writer
  function q(s) {
    if (s === null || s === undefined) return "null";
    if (typeof s === "number" || typeof s === "boolean") return String(s);
    s = String(s);
    const back = scalar(s);
    if (back !== s && !(typeof back === "string" && back === s.trim())) return JSON.stringify(s);
    if (s === "" || /^[\s]|[\s]$|^[-?:,\[\]{}#&*!|>'"%@`]|: |\s#|^(true|false|null|~|-?\d+(\.\d+)?)$/.test(s)
        || /[{}\[\],]/.test(s) || s.includes(":"))
      return JSON.stringify(s);
    return s;
  }
  function isScalar(v) { return v === null || typeof v !== "object"; }
  function flowable(v) {
    if (Array.isArray(v)) return v.every(isScalar) && JSON.stringify(v).length < 90;
    return Object.values(v).every(x => isScalar(x) || (Array.isArray(x) && x.every(isScalar)))
      && Object.keys(v).length <= 10 && JSON.stringify(v).length < 150;
  }
  function flow(v) {
    if (isScalar(v)) return q(v);
    if (Array.isArray(v)) return "[" + v.map(flow).join(", ") + "]";
    return "{" + Object.entries(v).filter(([, x]) => x !== undefined).map(([k, x]) => q(k) + ": " + flow(x)).join(", ") + "}";
  }
  function dump(v, ind = 0) {
    const pad = " ".repeat(ind);
    if (Array.isArray(v)) {
      if (!v.length) return " []";
      return v.map(x => {
        if (isScalar(x) || flowable(x)) return "\n" + pad + "- " + flow(x);
        const inner = dump(x, ind + 2).replace(/^\n\s*/, "");
        return "\n" + pad + "- " + inner;
      }).join("");
    }
    if (v && typeof v === "object") {
      const keys = Object.keys(v).filter(k => v[k] !== undefined);
      if (!keys.length) return " {}";
      return keys.map(k => {
        const x = v[k];
        if (isScalar(x)) return "\n" + pad + q(k) + ": " + q(x);
        if (flowable(x)) return "\n" + pad + q(k) + ": " + flow(x);
        return "\n" + pad + q(k) + ":" + dump(x, ind + 2);
      }).join("");
    }
    return " " + q(v);
  }
  return { parse, dump: (v) => dump(v, 0).replace(/^\n/, "") + "\n" };
})();
if (typeof module !== "undefined") module.exports = YAML;
