"""Manual layout: every card where the lab file (or the planning tool) put it.

In the lab file (schema 2, all optional):
  devices: [{id: sw1, pos: {x: 700, y: 1000, w: 1200}, …}]   # top-left of the card body; w only for servers
  links:   [{a: sw1.g3, b: desk.p1, via: [[650, 1180], [400, 1180]], sides: {desk: W}}, …]
  layout:  {mode: manual, panels: {networks: {x, y}, legend: {x, y}, cloud: {…}, forwards: {…}, panel0: {…}},
            internet: {x: 1200}}

Devices without a position are placed by the cluster optimizer first, then the manual ones are set.
Cables: with `via` exactly through those points (right angles added), otherwise the area router.
The QA reports anything that overlaps, so a hand-made layout is checked like every other.
"""
from . import panels as P
from . import theme as T


def has_positions(lab):
    return any(d.extra.get("pos") for d in lab.devices)


def _shift_right(lab):
    """Cards dragged left of the margin in the planner: move the whole drawing right instead of cutting it."""
    man = lab.raw.get("layout") or {}
    xs = [float(d.extra["pos"]["x"]) for d in lab.devices if d.extra.get("pos")]
    xs += [float(p["x"]) for p in (man.get("panels") or {}).values() if p and p.get("x") is not None]
    xs += [float(v[0]) for l in lab.links for v in (l.extra.get("via") or [])]
    dx = T.MARGIN - min(xs) if xs and min(xs) < T.MARGIN else 0
    if not dx:
        return
    for d in lab.devices:
        if d.extra.get("pos"):
            d.extra["pos"] = dict(d.extra["pos"], x=float(d.extra["pos"]["x"]) + dx)
    for p in (man.get("panels") or {}).values():
        if p and p.get("x") is not None:
            p["x"] = float(p["x"]) + dx
    for l in lab.links:
        if l.extra.get("via"):
            l.extra["via"] = [[float(v[0]) + dx, float(v[1])] for v in l.extra["via"]]
    if (man.get("internet") or {}).get("x") is not None:
        man["internet"]["x"] = float(man["internet"]["x"]) + dx


def layout_manual(R):
    lab = R.lab
    _shift_right(lab)
    R.layout_cluster()                      # sensible places for everything first
    man = lab.raw.get("layout") or {}
    for d in lab.devices:
        pos = d.extra.get("pos")
        if not pos:
            continue
        n = R.nodes[d.id]
        if n.kind == "server" and pos.get("w"):
            n.w = float(pos["w"])
            n.h = n.server.size(n.w)
        n.x, n.y = float(pos["x"]), float(pos["y"])
    for n in R.nodes.values():              # no tree columns: sides follow the positions
        n.col = None
    first = [R.nodes[i] for i in R.chain[0]] if R.chain else []
    if (man.get("internet") or {}).get("x") is not None:
        T.CX = float(man["internet"]["x"])
    elif first and first[0].d.extra.get("pos"):
        n = first[0]
        up = next((p for p in n.d.ports if p.uplink), None)
        T.CX = n.x + (n.port_x[up.id] if up and up.id in n.port_x else n.w / 2)
    right = max([n.x + n.w for n in R.nodes.values() if n.x is not None] +
                [p["x"] + p["w"] for p in R.panel_list()])
    if right + T.MARGIN > T.W:
        R.set_width(right + T.MARGIN)
    R.bottom = max(n.y + n.h for n in R.nodes.values() if n.y is not None)


def _side_towards(n, o):
    """Side of card n that faces card o."""
    if o.y >= n.y + n.h:
        return "S"
    if o.y + o.h <= n.y:
        return "N"
    return "E" if o.x + o.w / 2 > n.x + n.w / 2 else "W"


def assign_ends_manual(R):
    from .render import _spread
    groups = {}
    for c in R.cables:
        l = c["link"]
        a, b = c["a"], c["b"]
        sides = l.extra.get("sides") or {}
        for n, o in ((a, b), (b, a)):
            side = sides.get(n.id) or _side_towards(n, o)
            p = l.port_of(n.id)
            if n.kind in ("isp", "switch") and p in n.port_x and side in ("S", "N"):
                y = n.y + n.h if side == "S" else n.y
                c["ends"][n.id] = (n.x + n.port_x[p], y, side)
                continue
            groups.setdefault((n.id, side), []).append((c, o))
    for (nid, side), lst in groups.items():
        n = R.nodes[nid]
        if side in ("N", "S"):
            lst.sort(key=lambda t: t[1].x + t[1].w / 2)
            want = [t[1].x + t[1].w / 2 for t in lst]
            if side == "N" and n.kind in ("device", "server"):
                lo = n.x + n.tab_w + 34
            elif n.free_jacks and side == "N":
                lo = n.x + n.hdr + 54
            else:
                lo = n.x + (54 if n.free_jacks else 24)
            hi = n.x + n.w - (54 if n.free_jacks else 40)
            xs = _spread(want, lo, max(lo, hi), 58 if n.free_jacks else 70 if side == "N" else 30)
            y = n.y if side == "N" else n.y + n.h
            for (c, _), x in zip(lst, xs):
                c["ends"][nid] = (x, y, side)
        else:
            lst.sort(key=lambda t: t[1].y + t[1].h / 2)
            k = len(lst)
            mid = n.y + min(n.h / 2, 46)
            x = n.x if side == "W" else n.x + n.w
            for i, (c, _) in enumerate(lst):
                c["ends"][nid] = (x, mid + (i - (k - 1) / 2) * 30, side)
    # cables with waypoints: drawn exactly through them (right angles added), not routed
    for c in R.cables:
        via = c["link"].extra.get("via")
        if not via:
            continue
        a, b = c["ends"].get(c["a"].id), c["ends"].get(c["b"].id)
        if not a or not b:
            continue
        pts = [(a[0], a[1])]
        vertical = a[2] in ("N", "S")             # leave the card straight out of its side
        for q in [tuple(map(float, v)) for v in via] + [(b[0], b[1])]:
            p = pts[-1]
            if abs(p[0] - q[0]) > 0.5 and abs(p[1] - q[1]) > 0.5:
                pts.append((p[0], q[1]) if vertical else (q[0], p[1]))
            else:
                vertical = abs(p[0] - q[0]) <= 0.5
            pts.append(q)
            vertical = not vertical if abs(p[0] - q[0]) > 0.5 and abs(p[1] - q[1]) > 0.5 else vertical
        c["manual_pts"] = pts
