"""Every IP address in use (from devices, ports, guests, ip_extra) and the IP-list panel."""
import ipaddress

from . import theme as T
from .parts import hostname
from .text import measure

HEAD, ROW, GAP = 50, 22, 12      # block header, row, gap between network blocks


def collect(lab):
    """[{net, ip, name, kind, host, conflict, declared}] – one entry per address."""
    out = []

    def add(ip, name, kind, g=None, key=None, base=None, declared=True):
        ip = lab.full_ip(key, ip, base)
        host = hostname(g)[0] if g is not None else None
        if g is not None and not host and getattr(g, "apps", None):     # multi-app CT: first app's hostname
            host = next((hostname(a)[0] for a in g.apps if hostname(a)[0]), None)
        out.append({"net": key or lab.net_of_ip(ip), "ip": ip, "name": name, "kind": kind, "host": host,
                    "declared": declared})

    for d in lab.devices:
        if d.ip:
            parts = [p.strip() for p in str(d.ip).split("/")]
            for j, p in enumerate(parts):
                lbl = f"{d.name} · {d.ip_labels[j]}" if j < len(d.ip_labels) else d.name
                if j == 0:
                    add(p, lbl, d.type or d.role, d, key=d.net if p.startswith(".") else None)
                else:
                    add(p, lbl, d.type or d.role, d, base=lab.full_ip(d.net, parts[0]))
        for p in d.ports:            # addresses on ports: the WAN side, gateways on trunks
            if not p.ip:
                continue
            for l in lab.links_of(d.id):
                if l.port_of(d.id) != p.id:
                    continue
                keys = l.vlans or ([l.net] if l.net else [])
                for k in keys:
                    kind = "gateway" if l.vlans else (lab.net[k].name if k in lab.net else "")
                    add(p.ip, d.name, kind, d if lab.full_ip(k, p.ip) == lab.full_ip(d.net, d.ip) else None, key=k)
        for g in d.guests:
            if g.ip:
                add(g.ip, g.name, f"{g.kind} {g.id}", g, key=g.net if str(g.ip).startswith(".") else None)
    for e in lab.ip_extra:
        add(e["ip"], e["name"], e.get("kind", ""), key=str(e["vlan"]) if str(e["ip"]).startswith(".") else None)
    by_ip = {}
    for e in out:
        by_ip.setdefault(e["ip"], set()).add(e["name"].split(" · ")[0])
    seen, uniq = set(), []
    for e in out:
        e["conflict"] = len(by_ip[e["ip"]]) > 1
        if (e["ip"], e["name"]) not in seen:
            seen.add((e["ip"], e["name"]))
            uniq.append(e)
    return uniq


def _key(e):
    try:
        return ipaddress.ip_address(e["ip"])
    except ValueError:
        return ipaddress.ip_address("0.0.0.0")


def layout(lab, ips, ncol):
    """Split the network blocks into ncol columns (newspaper style; a block may continue in the
    next column with a repeated header). Returns (columns, height of the tallest column)."""
    items = []
    for n in lab.networks:
        rows = sorted((e for e in ips if e["net"] == n.key), key=_key)
        if rows:
            items.append((n, rows))

    def pack(limit):
        cols, cur, h = [], [], 0
        for n, rows in items:
            rest, cont = list(rows), False
            while rest:
                need = (GAP if cur else 0) + HEAD + ROW
                if cur and h + need > limit:
                    cols.append((cur, h)); cur, h = [], 0
                    need = HEAD + ROW
                h += need - ROW
                take = max(1, int((limit - h) // ROW)) if len(cols) < ncol - 1 else len(rest)
                part, rest = rest[:take], rest[take:]
                cur.append((n, part, cont, len(rows)))
                h += len(part) * ROW
                cont = True
                if rest:
                    cols.append((cur, h)); cur, h = [], 0
        if cur:
            cols.append((cur, h))
        return cols

    if not items:
        return [], 0
    total = sum(HEAD + len(r) * ROW + GAP for _, r in items)
    limit = max(HEAD + ROW, total / ncol)
    while True:
        cols = pack(limit)
        if len(cols) <= ncol and all(h <= limit for _, h in cols[:-1]):
            return [c for c, _ in cols], max(h for _, h in cols)
        limit += ROW / 2


def table(S, lab, ips, x, y, w, ncol, hosts=False, draw=True):
    """Panel listing every IP in use, grouped by network. Returns its height."""
    cols, ch = layout(lab, ips, ncol)
    h = 78 + ch + 18
    if not draw:
        return h
    S.tag = "IP list"
    S.rect(x, y, w, h, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.text(x + 20, y + 36, "IP addresses", 19, T.TEXT, 600)
    nconf = len({e["ip"] for e in ips if e["conflict"]})
    sub_ = (f"every address in use · {len(ips)} addresses in {len({e['net'] for e in ips})} networks · "
            "sorted by VLAN, then address" + (f" · {nconf} conflicts in red" if nconf else " · no conflicts"))
    S.text(x + 20, y + 58, sub_, 12.5, T.MUTED, 400)
    gap = 16
    cw_ = (w - 28 - gap * (ncol - 1)) / ncol
    for ci, blocks in enumerate(cols):
        cx_ = x + 14 + ci * (cw_ + gap)
        yy = y + 78
        for bi, (n, rows, cont, cnt) in enumerate(blocks):
            if bi:
                yy += GAP
            col = n.color
            S.rect(cx_, yy, cw_, HEAD - 8 + len(rows) * ROW + 6, rx=9, fill=T.CHIP, stroke=col + "55", sw=1)
            S.add(f'<rect x="{cx_:.1f}" y="{yy:.1f}" width="6" height="{HEAD - 8}" rx="3" fill="{col}"/>')
            S.text(cx_ + 16, yy + 18, n.tag, 12.5, col, 600, mono=True)
            S.text(cx_ + 16 + measure(n.tag, 12.5, 600, True) + 10, yy + 18, n.name + (" (cont.)" if cont else ""),
                   14, T.TEXT, 600)
            S.text(cx_ + cw_ - 12, yy + 18, n.subnet, 12, T.TEXT, 500, "end", mono=True)
            free = (n.net.num_addresses - 2 - cnt) if n.net else 0
            S.text(cx_ + 16, yy + 35, "continued from the left" if cont else f"{cnt} used · {free} free", 11.5,
                   T.MUTED, 400)
            yy += HEAD - 8
            for k, e in enumerate(rows):
                ry = yy + k * ROW
                if k:
                    S.add(f'<line x1="{cx_+12:.1f}" y1="{ry+2:.1f}" x2="{cx_+cw_-12:.1f}" y2="{ry+2:.1f}" '
                          f'stroke="{T.BORDER}" stroke-width="0.8"/>')
                c = T.CONFLICT if e["conflict"] else None
                S.text(cx_ + 16, ry + 17, e["ip"], 12.5, c or col, 600, mono=True)
                nx_ = cx_ + 16 + 7.5 * 15 + 6          # after the widest address (15 chars)
                S.text(nx_, ry + 17, e["name"], 13, c or T.TEXT, 500)
                S.text(cx_ + cw_ - 12, ry + 17, e["kind"], 11, T.FAINT, 500, "end", mono=True)
                if hosts and e["host"]:
                    hx = nx_ + measure(e["name"], 13, 500) + 10
                    S.text(hx, ry + 17, e["host"], 11, T.LINK if not e["host"].endswith(".internal") else T.MUTED,
                           400, mono=True)
            yy += len(rows) * ROW + 6
    return h
