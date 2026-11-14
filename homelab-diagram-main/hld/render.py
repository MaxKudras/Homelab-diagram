"""Put it all together: model → rows → placement → cable routing → drawing.

Layout pattern (same as the original diagram):
  header · internet cloud (center) with remote access (left) and cloud services (right column)
  left column : networks table, legend
  right column: cloud services, port forwards, flow panels
  center      : the edge chain, one row per tier (ISP router → firewall(s) → core switch(es)),
                straight cables wherever the ports line up
  below       : device rows (everything hanging off the switches), as many rows as needed
  bottom      : server band (big server cards), optional IP list

Tiers come from the link graph (distance from the internet). Cards are measured first, placed
as close as possible under the port they hang on (isotonic regression, no overlaps), cables are
routed through the channels between rows with their own tracks (route.py).
"""
from . import panels as P
from . import parts
from . import theme as T
from .ips import collect as collect_ips, table as ip_table
from .model import INFRA_ROLES
from .route import Wire, assign
from .server import ServerCard
from .svg import SVG
from .text import measure

GAP = 20            # between cards in a row
LANE = 16           # pass-through lane width
JACK_M = 54         # free jacks keep this distance from card edges


# ================================================================ nodes (cards to place)
class Node:
    def __init__(self, lab, d, inline):
        self.d, self.lab = d, lab
        self.id = d.id
        self.tab_w = parts.tab_width(d.name, d.type)
        self.port_x = {}            # port id → x offset (port-row cards)
        self.x = self.y = None
        self.row = None
        self.server = None
        self.pseudo = False
        n_icons = len(d.icons) or 1
        hdr = parts.header_w(d, n_icons) + (22 if d.extra.get("monitor") else 0)   # room for the status dot
        self.hdr = hdr
        if d.port_row and d.role == "isp_router":
            self.kind = "isp"
            x = hdr + 46
            last_coax = False
            for i, p in enumerate(d.ports):
                if i:
                    x += 64 if last_coax else 52
                self.port_x[p.id] = x
                last_coax = p.kind == "coax"
            self.w = max(x + 46, self.tab_w + 40)
            self.h = 104
        elif d.port_row:
            self.kind = "switch"
            self.size_switch(False)
        elif d.role in INFRA_ROLES:
            self.kind = "appliance"
            self.hw_w = max([200] + [parts.hw_tile_w(h) for h in d.hw]) if d.hw else 0
            self.sv_w = max([190] + [parts.service_tile_w(s) for s in d.services]) if d.services else 0
            self.size_appliance(min(3, len(d.services)) if d.services else 0)
        elif d.is_server:
            self.kind = "server"
            self.server = ServerCard(lab, d, inline)
            self.w = self.server.min_w()
            self.h = None
        else:
            self.kind = "device"
            body_w = hdr + 20
            if d.ssids:
                body_w = max(body_w, 150 + max(measure(_vlan_tag(lab, s["vlan"]), 12, 500, True) for s in d.ssids) + 18)
            self.w = max(body_w, self.tab_w + 120)
            self.h = 106 + len(d.ssids) * 17 + 3 if d.ssids else (92 if d.config else 86)

    def size_switch(self, compact):
        """Ports right of the header (normal) or in their own row under it (compact = narrower)."""
        d = self.d
        self.compact = compact
        px0 = self.tab_w - 10 if compact else self.hdr + 30
        nr = sum(1 for p in d.ports if p.kind != "sfp")
        pitch = 58 if len(d.ports) <= 14 else 52
        ri = si = 0
        for p in d.ports:
            if p.kind == "sfp":
                self.port_x[p.id] = px0 + nr * pitch + 22 + 30 + si * 70
                si += 1
            else:
                self.port_x[p.id] = px0 + ri * pitch + 24
                ri += 1
        self.pitch = pitch
        self.port_y = (108 if d.config else 96) if compact else 30
        self.w = max(max(self.port_x.values()) + 30 + (24 if compact else 64), self.hdr + 20, self.tab_w + 40)
        self.h = self.port_y + 82

    def size_appliance(self, ncol):
        d = self.d
        self.sv_cols = ncol
        body = 16 + (self.hw_w + 28 if d.hw else 0) + (ncol * (self.sv_w + 9) - 9 if ncol else 0) + 18
        self.w = max(body, self.hdr + 30 + 2 * JACK_M + 48)
        rows_sv = -(-len(d.services) // ncol) if ncol else 0
        content = max(len(d.hw) * 64, rows_sv * 58)
        self.h = (106 + content if content else 96) + 68          # bottom band keeps room for the jacks

    def shrink(self):
        """Make the card narrower if it can. Returns True if something changed."""
        if self.kind == "appliance" and self.sv_cols > 1:
            self.size_appliance(self.sv_cols - 1)
            return True
        if self.kind == "switch" and not self.compact:
            self.size_switch(True)
            return True
        return False

    def color(self):
        return self.lab.color(self.d.net)

    def stroke(self):
        return T.TRUNK_BORDER if self.d.border == "trunk" else None

    @property
    def free_jacks(self):
        return self.kind == "appliance" or (self.d.role in INFRA_ROLES and not self.d.port_row)


def _vlan_tag(lab, key):
    n = lab.net.get(str(key))
    if not n:
        return str(key)
    return f"{n.tag} · {n.name}" if n.tag.startswith("VLAN") else n.name


class Pseudo:
    """A cable passing a row: occupies a thin lane between the cards."""
    pseudo = True
    kind = "lane"

    def __init__(self, cable, width):
        self.cable, self.w, self.h = cable, width, 0
        self.x = None
        self.id = f"lane:{id(cable)}"


# ================================================================ placement
def pav(items, desired, gaps, L, R):
    """Place items (with .w) left to right in the given order, as close as possible to their
    desired centers, never overlapping, inside [L, R]. Isotonic regression (pool adjacent violators)."""
    n = len(items)
    off, o = [], 0
    for i, it in enumerate(items):
        off.append(o)
        o += it.w + (gaps[i] if i < n - 1 else 0)
    total = o
    target = [desired[i] - items[i].w / 2 - off[i] for i in range(n)]
    wts = [0.25 if it.pseudo else 1.0 for it in items]
    blocks = []                                   # [value, weight, count]
    for t, wt in zip(target, wts):
        blocks.append([t, wt, 1])
        while len(blocks) > 1 and blocks[-2][0] > blocks[-1][0]:
            v2, w2, c2 = blocks.pop()
            v1, w1, c1 = blocks.pop()
            blocks.append([(v1 * w1 + v2 * w2) / (w1 + w2), w1 + w2, c1 + c2])
    ys = []
    for v, _, c in blocks:
        ys += [v] * c
    hi = R - total
    for i, it in enumerate(items):
        y = ys[i]
        y = max(L, min(y, hi)) if hi >= L else L
        it.x = y + off[i]
    return total


def gap_between(a, b):
    if a.pseudo and b.pseudo:
        return 0
    if a.pseudo or b.pseudo:
        return 18
    return GAP


# ================================================================ main
class Renderer:
    def __init__(self, lab, ip_mode="none", unredacted=False):
        self.lab = lab
        self.ip_mode = ip_mode
        self.inline = ip_mode in ("inline", "both")
        self.S = SVG()
        self.nodes = {d.id: Node(lab, d, self.inline) for d in lab.devices}
        self.warnings = []
        self.redact = not unredacted
        self.channels = {}

    # ---------------------------------------------------------------- tiers
    def tiers(self):
        lab = self.lab
        phys = [l for l in lab.links if l.kind in ("cable", "wifi")]
        adj = {d.id: [] for d in lab.devices}
        for l in phys:
            adj[l.a_dev].append(l.b_dev)
            adj[l.b_dev].append(l.a_dev)
        roots = [d.id for d in lab.devices if d.role == "isp_router" or any(p.uplink for p in d.ports)]
        if not roots:
            roots = [d.id for d in lab.devices if d.role in ("firewall", "router")][:1]
        if not roots and lab.devices:
            roots = [lab.devices[0].id]
        depth = {r: 0 for r in roots}
        q = list(roots)
        while q:
            c = q.pop(0)
            for nb in adj[c]:
                if nb not in depth and not (self.nodes[nb].kind == "server"):
                    depth[nb] = depth[c] + 1
                    q.append(nb)
        servers = [d.id for d in lab.devices if self.nodes[d.id].kind == "server"]
        rest = [d.id for d in lab.devices if d.id not in depth and d.id not in servers]
        mx = max(depth.values(), default=0)
        tiers = [[] for _ in range(mx + 1)]
        for d in lab.devices:
            if d.id in depth:
                tiers[depth[d.id]].append(d.id)
        if rest:
            tiers.append(rest)
        # leading tiers of pure infrastructure that feed the next tier = the centered edge chain
        nchain = 0
        for t, ids in enumerate(tiers[:-1]):
            if all(self.lab.dev[i].role in INFRA_ROLES for i in ids) and len(tiers[t + 1]) > 0:
                nchain = t + 1
            else:
                break
        return tiers, nchain, servers

    # ---------------------------------------------------------------- frame (side columns)
    def columns(self):
        lab, S = self.lab, self.S
        self.feat = self.features()
        self.left = [("networks", P.networks_h(lab)), ("legend", P.legend_h(self.feat))]
        self.left_bottom = 150 + sum(h for _, h in self.left) + 20 * (len(self.left) - 1)
        y = 146
        self.right = []
        if lab.cloud:
            h = len(lab.cloud) * 54 - 10
            self.right.append(("cloud", y, h))
            y += h + 18
        if lab.port_forwards:
            h = P.forwards_h(lab)
            self.right.append(("forwards", y, h))
            y += h + 20
        for p in lab.panels:
            fn = P.PANELS.get(p.get("type"))
            if fn:
                h = fn(S, lab, p, T.RIGHT_X, y, T.RIGHT_W, draw=False)
                self.right.append((p, y, h))
                y += h + 20
        self.right_bottom = y - 20

    def bounds(self, y0, y1):
        """Free x-range for a row spanning y0..y1 (the side columns block the edges up top)."""
        L = T.MARGIN if self.left_bottom + 24 < y0 else T.LEFT_X + T.LEFT_W + 40
        R = T.W - T.MARGIN if self.right_bottom + 24 < y0 else T.RIGHT_X - 40
        return L, R

    def features(self):
        lab = self.lab
        f = {}
        cables = [l for l in lab.links if l.kind == "cable"]
        if any(l.trunk for l in cables):
            f["trunk"] = True
        acc = []
        for l in cables:
            if l.net and not l.trunk and l.net not in acc and lab.net.get(l.net) and lab.net[l.net].tag.startswith("VLAN"):
                acc.append(l.net)
        if acc:
            f["access"] = acc
        wan = [l.net for l in cables if l.net and lab.net.get(l.net) and not lab.net[l.net].tag.startswith("VLAN")]
        if wan:
            f["wan"] = wan[0]
        if any(l.kind == "kvm" for l in lab.links):
            f["kvm"] = True
        if any(l.kind == "wifi" for l in lab.links):
            f["wifi"] = True
        if lab.remote or lab.cloud:
            f["net"] = True
        sp = []
        for s in ("40G", "25G", "10G", "5G", "2.5G", "1G", "100M"):
            if any(l.speed == s for l in cables):
                sp.append(s)
        if sp:
            f["speed"] = sp
        guests = [g for d in lab.devices for g in d.guests]
        apps = [a for g in guests for a in g.apps]
        if any(g.host for g in guests) or any(a.get("host") for a in apps):
            f["public"] = True
        if any(g.internal for g in guests) or any(d.internal for d in lab.devices):
            f["internal"] = True
        if any(g.exposure == "local" for g in guests):
            f["lan"] = True
        if any(p.untagged or p.tagged for d in lab.devices for p in d.ports):
            f["ticks"] = True
        if any(p.get("type") == "media_pipeline" for p in lab.panels):
            f["share"] = True
        if any(d.status != "active" for d in lab.devices):
            f["planned"] = True
        if any(d.extra.get("monitor") or any(g.extra.get("monitor") for g in d.guests) for d in lab.devices):
            f["monitor"] = True
        return f

    # ---------------------------------------------------------------- cables
    def build_cables(self):
        """One record per drawn link: ends, kind, style. Rows are known by now."""
        old = {id(c["link"]): c for c in getattr(self, "cables", [])}
        cab = []
        for l in self.lab.links:
            if l.kind == "vpn":
                continue
            na, nb = self.nodes[l.a_dev], self.nodes[l.b_dev]
            if na.row is None or nb.row is None:
                continue
            up, dn = (na, nb) if na.row <= nb.row else (nb, na)
            c = old.get(id(l)) or {"link": l, "xs": {}, "w": self.line_w(l)}
            # keep what earlier rows already decided (slots, lanes); only the ends may move down
            c.update(up=up, dn=dn, same=up.row == dn.row, up_port=l.port_of(up.id), dn_port=l.port_of(dn.id))
            cab.append(c)
        self.cables = cab

    def line_w(self, l):
        if l.kind == "kvm":
            return 2
        if l.kind == "wifi":
            return 2
        return T.trunk_w(l.speed) if l.trunk else T.speed_w(l.speed)

    # ---------------------------------------------------------------- endpoints
    def up_x(self, c, nodes_below_placed=True):
        """x where the cable leaves its upper card (bottom edge)."""
        n, p = c["up"], c["up_port"]
        if n.x is None:
            return None
        if n.kind in ("isp", "switch") and p in n.port_x:
            return n.x + n.port_x[p]
        return c["xs"].get(("up", n.id))

    def dn_x(self, c):
        n, p = c["dn"], c["dn_port"]
        if n.x is None:
            return None
        if n.kind in ("isp", "switch") and p in n.port_x:
            return n.x + n.port_x[p]
        return c["xs"].get(("dn", n.id))

    def anchor_up(self, c):
        """Best guess of the upper x before the lower row is placed."""
        x = self.up_x(c)
        return x if x is not None else c["up"].x + c["up"].w / 2

    def assign_up_slots(self, n):
        """Free bottom positions on a card (jacks or plain exits), from the lower ends."""
        outs = [c for c in self.cables if c["up"] is n and not c["same"] and not (
            n.kind in ("isp", "switch") and c["up_port"] in n.port_x)]
        outs += [c for c in self.cables if c["same"] and n in (c["up"], c["dn"]) and not (
            n.kind in ("isp", "switch") and c["link"].port_of(n.id) in n.port_x)]
        if not outs:
            return
        def target(c):
            o = c["dn"] if c["up"] is n else c["up"]
            if c["same"]:
                return o.x + o.w / 2
            x = self.dn_x(c)
            if x is None and c.get("path"):
                x = c["path"][1] if len(c["path"]) > 1 else None
            return x if x is not None else (o.x + o.w / 2 if o.x is not None else n.x + n.w / 2)
        outs.sort(key=target)
        if n.free_jacks:
            lo, hi, sp = n.x + JACK_M, n.x + n.w - JACK_M, 58
        else:
            lo, hi, sp = n.x + 24, n.x + n.w - 24, 30
        xs = _spread([target(c) for c in outs], lo, hi, sp)
        for c, x in zip(outs, xs):
            key = ("up", n.id) if (c["up"] is n) else ("dn", n.id)
            c["xs"][key] = x
            c.setdefault("same_x", {})[n.id] = x

    def assign_dn_slots(self, n):
        ins = [c for c in self.cables if c["dn"] is n and not c["same"] and not (
            n.kind in ("isp", "switch") and c["dn_port"] in n.port_x)]
        if not ins:
            return
        src = {}                                    # x where the cable comes down (port or lane)
        for c in ins:
            xs = self.path_xs(c)[:-1]
            src[id(c)] = next((x for x in reversed(xs) if x is not None), c["up"].x + c["up"].w / 2)
        ins.sort(key=lambda c: src[id(c)])
        if n.free_jacks:
            lo, hi = n.x + n.hdr + 30 + 24, n.x + n.w - JACK_M
            xs = _spread([src[id(c)] for c in ins], lo, hi, 58)
        elif n.kind == "server":
            lo, hi = n.x + n.tab_w + 30, n.x + n.w - 60
            xs = _spread([src[id(c)] for c in ins], lo, hi, 64)
        else:
            # small cards: entries packed right of the tab, each followed by its speed tag
            xs, x = [], n.x + n.tab_w + 34
            for c in ins:
                xs.append(x)
                x += self.S.label_w(self.speed_txt(c), 11, True) + 22
            over = xs[-1] + self.S.label_w(self.speed_txt(ins[-1]), 11, True) + 14 - (n.x + n.w)
            if over > 0:
                self.warnings.append(f"„{n.d.name}“: zu viele Kabel für die Kartenbreite")
        for c, x in zip(ins, xs):
            c["xs"][("dn", n.id)] = x

    def speed_txt(self, c):
        l = c["link"]
        return l.speed if l.kind == "cable" else ""

    # ---------------------------------------------------------------- layout
    def layout(self):
        lab, S = self.lab, self.S
        tiers, nchain, servers = self.tiers()
        self.columns()
        rows = []
        for t, ids in enumerate(tiers):
            if ids:
                rows.append({"kind": "chain" if t < nchain else "device", "ids": ids})
        if servers:
            rows.append({"kind": "server", "ids": list(servers)})
        self.rows = rows
        # provisional rows to know which cables pass which row
        self.renumber()
        y = P.CLOUD_Y + 58 + 60 + T.TAB         # first row body (below cloud + speed labels)
        below_cols = max(self.left_bottom, self.right_bottom) + 24 + T.TAB
        prev_bottom = None
        r = 0
        while r < len(self.rows):
            row = self.rows[r]
            nodes = [self.nodes[i] for i in row["ids"]]
            min_y = y
            if row["kind"] == "server":
                min_y = y = max(y, below_cols)
            # too wide: narrower cards first, then the full width below the side columns, then wrap
            if row["kind"] in ("chain", "device"):
                def too_wide(yy):
                    L, R = self.bounds(yy - T.TAB, yy + max(n.h for n in nodes))
                    total = sum(n.w for n in nodes) + GAP * (len(nodes) - 1)
                    return total > R - L - (60 if row["kind"] == "device" else 0), R - L
                while too_wide(y)[0] and any(n.shrink() for n in nodes):
                    pass
                if too_wide(y)[0] and y < below_cols:
                    min_y = y = below_cols
            if row["kind"] in ("device", "server", "chain") and len(nodes) > 1:
                L, R = self.bounds(y - T.TAB, y + 400)
                desired = {n.id: self.desired(n) for n in nodes}
                if row["kind"] != "chain":
                    nodes.sort(key=lambda n: desired[n.id])
                total = sum(n.w for n in nodes) + GAP * (len(nodes) - 1)
                avail = R - L - (60 if row["kind"] == "device" else 0)
                if total > avail:
                    chunks = _chunks(nodes, avail)
                    self.rows[r:r + 1] = [{"kind": row["kind"], "ids": [n.id for n in ch]} for ch in chunks]
                    self.renumber()
                    continue
            # place, route the channel above, maybe again with the final y
            for attempt in range(3):
                self.place_row(r, nodes, y)
                ny = y if prev_bottom is None else max(min_y, self.route_channel(r, prev_bottom, y))
                if abs(ny - y) < 0.5:
                    break
                old = self.bounds(y - T.TAB, y + 100)
                y = ny
                if self.bounds(y - T.TAB, y + 100) == old and attempt:
                    break
            for n in nodes:
                n.y = y
            if prev_bottom is not None:
                self.route_channel(r, prev_bottom, y)
            prev_bottom = max(n.y + n.h for n in nodes)
            y = prev_bottom + 60 + T.TAB
            r += 1
        self.bottom = prev_bottom or y

    def renumber(self):
        for rr, rw in enumerate(self.rows):
            for i in rw["ids"]:
                self.nodes[i].row = rr
        self.build_cables()

    def desired(self, n):
        """Center x a card wants: its first cable entry right under the port it comes from."""
        ins = [c for c in self.cables if c["dn"] is n and not c["same"] and c["up"].x is not None]
        if not ins:
            return T.CX
        src = sorted(((self.lane_src(c), c) for c in ins), key=lambda t: t[0])
        x0, c0 = src[0]
        if n.kind in ("isp", "switch") and c0["dn_port"] in n.port_x:
            return x0 - n.port_x[c0["dn_port"]] + n.w / 2
        if n.kind == "device":
            return x0 - (n.tab_w + 34) + n.w / 2
        return sum(x for x, _ in src) / len(src)

    def place_row(self, r, nodes, y):
        lab = self.lab
        row = self.rows[r]
        h = max((n.h or 300) for n in nodes)
        L, R = self.bounds(y - T.TAB, y + h)
        # cables passing this row (start above, end below)
        passing = [c for c in self.cables if c["up"].row < r < c["dn"].row]
        lanes = []
        for c in passing:
            ln = Pseudo(c, 2)
            lanes.append(ln)
        if row["kind"] == "server":
            ll = sorted([l for l in lanes if self.lane_src(l.cable) < T.CX], key=lambda l: self.lane_src(l.cable))
            rl = sorted([l for l in lanes if self.lane_src(l.cable) >= T.CX], key=lambda l: self.lane_src(l.cable))
            left = T.MARGIN + (len(ll) * LANE + 14 if ll else 0)
            right = T.W - T.MARGIN - (len(rl) * LANE + 14 if rl else 0)
            for i, ln in enumerate(ll):
                ln.x = T.MARGIN + 6 + i * LANE
                ln.cable.setdefault("lanes", {})[r] = ln.x
            for i, ln in enumerate(rl):
                ln.x = right + 14 + i * LANE
                ln.cable.setdefault("lanes", {})[r] = ln.x
            avail = right - left
            nodes.sort(key=lambda n: self.desired(n))
            total = sum(n.server.min_w() for n in nodes)
            extra = avail - total - GAP * (len(nodes) - 1)
            x = left
            for n in nodes:
                mw = n.server.min_w()
                n.w = mw + extra * mw / total
                n.x = x
                x += n.w + GAP
            hh = max(n.server.size(n.w) for n in nodes)
            for n in nodes:
                n.h = n.server.h = hh            # one height per row: bottoms line up
            return
        items = list(nodes) + lanes
        desired = {}
        for it in items:
            if it.pseudo:
                desired[it.id] = self.lane_src(it.cable)
            else:
                desired[it.id] = self.desired(it)
        if row["kind"] == "chain" and len(nodes) == 1:
            n = nodes[0]
            desired[n.id] = self.chain_center(n)
        if row["kind"] == "chain":         # redundant pairs keep their order (A left of B)
            order = {n.id: i for i, n in enumerate(nodes)}
            items.sort(key=lambda it: (order.get(it.id, -1) if not it.pseudo else -1, desired[it.id]))
        else:
            items.sort(key=lambda it: desired[it.id])
        gaps = [gap_between(items[i], items[i + 1]) for i in range(len(items) - 1)]
        pav(items, [desired[it.id] for it in items], gaps, L, R)
        if row["kind"] == "chain" and len(nodes) == 1:
            self.chain_align(nodes[0], L, R)
        for ln in lanes:
            ln.cable.setdefault("lanes", {})[r] = ln.x + ln.w / 2

    def lane_src(self, c):
        lanes = c.get("lanes", {})
        if lanes:
            return lanes[max(lanes)]
        return self.anchor_up(c)

    def chain_center(self, n):
        """Edge chain: the ISP router puts its uplink (coax) port under the cloud, the rest is centered."""
        d = n.d
        up = next((p for p in d.ports if p.uplink), None)
        if up and up.id in n.port_x:
            return T.CX - n.port_x[up.id] + n.w / 2
        return T.CX

    def chain_align(self, n, L, R):
        """Shift a chain card so cables to the row above can run straight down."""
        lo, hi = L, R - n.w
        for c in self.cables:
            if c["dn"] is not n or c["same"]:
                continue
            ux = self.up_x(c)
            if n.free_jacks and ux is not None:          # our top jack goes under their port
                lo = max(lo, ux - n.w + JACK_M)
                hi = min(hi, ux - n.hdr - 54)
            elif n.kind in ("isp", "switch") and c["dn_port"] in n.port_x and c["up"].free_jacks:
                u = c["up"]
                off = n.port_x[c["dn_port"]]
                lo = max(lo, u.x + JACK_M - off)
                hi = min(hi, u.x + u.w - JACK_M - off)
        if lo <= hi:
            n.x = min(max(n.x, lo), hi)

    def route_channel(self, r, top, y_lower):
        """Route every cable crossing the channel between row r-1 (bottom = top) and row r.
        Returns the y row r needs so all tracks fit."""
        lower = [self.nodes[i] for i in self.rows[r]["ids"]]
        upper = [self.nodes[i] for i in self.rows[r - 1]["ids"]]
        # exits on the upper row and entries on the lower row
        for c in self.cables:
            c["path"] = self.path_xs(c)
        for n in upper:
            self.assign_up_slots(n)
        for c in self.cables:
            c["path"] = self.path_xs(c)
        for n in lower:
            self.assign_dn_slots(n)
        for c in self.cables:
            c["path"] = self.path_xs(c)
        wires = []
        for c in self.cables:
            v = self.channel_verts(c, r)
            if v:
                w = Wire(c, v, c["w"])
                wires.append(w)
        last, ntr = assign(wires, top, 20)
        straight_only = ntr == 0
        lag = any(c["link"].lag and not c["same"] and c["dn"].row == r for c in self.cables)
        tabbed = any(not n.pseudo for n in lower)
        if any(c["link"].kind == "kvm" and c["link"].label and c["dn"].row == r for c in self.cables):
            last = max(last, top + 46)                # room for the console label
            straight_only = False
        if straight_only:
            need = top + (92 if lag else 40)
            # a tab of the lower row must not touch a card of the upper row
            for n in lower:
                for u in upper:
                    if n.x < u.x + u.w and u.x < n.x + n.tab_w:
                        need = max(need, top + T.TAB + 16)
        else:
            need = last + 12 + (T.TAB if tabbed else 8) + 4
        self.channels[r] = {"wires": wires, "top": top}
        return max(need, top + 40)

    def path_xs(self, c):
        """x at every row boundary along the cable: [x at upper card, lanes …, x at lower card]."""
        xs = [self.up_x(c)]
        if xs[0] is None and c["up"].x is not None and not c["up"].free_jacks:
            xs[0] = c["up"].x + c["up"].w / 2
        for rr in sorted(c.get("lanes", {})):
            xs.append(c["lanes"][rr])
        if not c["same"]:
            xs.append(self.dn_x(c))
        return xs

    def same_x(self, c, n):
        """x where a same-row link leaves card n (its port, or an assigned bottom slot)."""
        p = c["link"].port_of(n.id)
        if n.kind in ("isp", "switch") and p in n.port_x:
            return n.x + n.port_x[p]
        return c.get("same_x", {}).get(n.id, n.x + n.w / 2)

    def channel_verts(self, c, r):
        """Vertical pieces of cable c inside the channel above row r."""
        up, dn = c["up"].row, c["dn"].row
        if c["same"]:
            if up != r - 1:
                return None
            return [(self.same_x(c, c["up"]), "top"), (self.same_x(c, c["dn"]), "top")]
        if not (up < r <= dn):
            return None
        xs = c["path"]
        i = r - 1 - up                    # index of the boundary above this channel in path
        if i + 1 >= len(xs) or xs[i] is None or xs[i + 1] is None:
            return None
        return [(xs[i], "top"), (xs[i + 1], "bottom")]

    # ---------------------------------------------------------------- drawing
    def draw(self, title):
        lab, S = self.lab, self.S
        self.channels = {}
        self.layout()
        # header + frame
        P.header(S, title, lab.meta.get("watermark", ""), lab.meta.get("date", ""))
        P.remote(S, lab, T.CX)
        P.internet(S, lab, T.CX)
        y = 150
        for name, h in self.left:
            if name == "networks":
                P.networks(S, lab, T.LEFT_X, y, T.LEFT_W)
            else:
                P.legend(S, lab, self.feat, T.LEFT_X, y, T.LEFT_W)
            y += h + 20
        for item, yy, h in self.right:
            if item == "cloud":
                P.cloud_services(S, lab, T.CX, T.RIGHT_X, yy, T.RIGHT_W)
            elif item == "forwards":
                P.forwards(S, lab, T.RIGHT_X, yy, T.RIGHT_W)
            else:
                P.PANELS[item["type"]](S, lab, item, T.RIGHT_X, yy, T.RIGHT_W)
        # internet into the edge chain
        self.draw_uplink()
        # cards
        for n in self.nodes.values():
            if n.x is not None and n.y is not None:
                self.draw_card(n)
        # cables, then jacks on top
        self.draw_cables()
        for n in self.nodes.values():
            if n.x is not None and n.free_jacks:
                self.draw_free_jacks(n)
        bottom = self.bottom
        if self.ip_mode in ("table", "both"):
            y = bottom + 24
            h = ip_table(S, lab, collect_ips(lab), T.MARGIN, y, T.W - 2 * T.MARGIN, 6)
            bottom = y + h
        return bottom + 32

    def draw_uplink(self):
        S, lab = self.S, self.lab
        cy0 = P.CLOUD_Y
        first = [self.nodes[i] for i in self.rows[0]["ids"]] if self.rows else []
        if not first:
            return
        n = first[0]
        up = next((p for p in n.d.ports if p.uplink), None)
        x = n.x + n.port_x[up.id] if up and up.id in n.port_x else T.CX
        top = n.y + 28
        S.tag = "internet line"
        S.line([(x, cy0 + 58), (x, top)], "#6b7a90", 3)
        S.reg_cable([(x, cy0 + 58), (x, top)], "internet", ("internet", n.d.name, n.d.name + " (tab)"))
        sp = lab.internet.get("speed") or {}
        my = (cy0 + 58 + n.y - T.TAB) / 2 + 5
        if sp.get("down"):
            S.label(x - 10, my, "↓ " + sp["down"], "#c3cdd9", 12, anchor="end", mono=True)
        if sp.get("up"):
            S.label(x + 10, my, "↑ " + sp["up"], "#c3cdd9", 12, anchor="start", mono=True)

    def draw_card(self, n):
        S, lab = self.S, self.lab
        d = n.d
        S.tag = d.name
        col = n.color()
        dash = "7 5" if d.status != "active" else None
        if n.kind == "server":
            n.server.draw(S, n.x, n.y, col, n.stroke() or col + "aa", sw=2, dash=dash)
            return
        fill = "#141b25" if n.kind == "switch" else T.PANEL
        parts.device_card(S, n.x, n.y, n.w, n.h, d.icons, d, col, fill=fill, stroke=n.stroke(), dash=dash)
        x, y = n.x, n.y
        parts.monitor_dot(S, d, x + n.w - 18, y + 18)
        if n.kind == "appliance":
            if d.hw:
                S.text(x + 20, y + 96, "HARDWARE", 11.5, T.HWC, 700, ls=1.4)
                for i, hwi in enumerate(d.hw):
                    parts.hw_tile(S, x + 16, y + 106 + i * 64, n.hw_w, hwi)
            if d.services:
                sx = x + 16 + (n.hw_w + 28 if d.hw else 0)
                S.text(sx + 2, y + 96, "SERVICES", 11.5, T.HWC, 700, ls=1.4)
                for i, sv in enumerate(d.services):
                    c, rr = i % n.sv_cols, i // n.sv_cols
                    parts.service_tile(S, sx + c * (n.sv_w + 9), y + 106 + rr * 58, n.sv_w, sv)
        elif n.kind in ("isp", "switch"):
            self.draw_port_row(n)
        elif d.ssids:
            S.text(x + 18, y + 96, "SSIDs", 11, T.FAINT, 600, ls=1.2)
            for i, s in enumerate(d.ssids):
                red = lab.redact.get("ssid_names", True) and self.redact
                name = s.get("redacted", s["name"]) if red else s["name"]
                c = lab.color(s["vlan"])
                sy = y + 106 + i * 17
                S.add(f'<circle cx="{x+24:.1f}" cy="{sy+5:.1f}" r="4" fill="{c}"/>')
                S.text(x + 36, sy + 9, name, 13, T.TEXT, 500)
                S.text(x + 150, sy + 9, _vlan_tag(lab, s["vlan"]), 12, c, 500, mono=True)

    def linked(self, n, pid):
        return [c for c in self.cables if c["link"].kind == "cable" and c["link"].port_of(n.id) == pid]

    def draw_port_row(self, n):
        S, lab = self.S, self.lab
        d = n.d
        x, y = n.x, n.y
        isp = n.kind == "isp"
        jy = y + (28 if isp else n.port_y)
        for p in d.ports:
            cx = x + n.port_x[p.id]
            used = self.linked(n, p.id)
            if p.kind == "coax":
                parts.coax(S, cx, jy)
                S.label(cx, jy - 8, p.label or "Cable", T.MUTED, 11, mono=True, bg=T.PANEL)
                if p.note:
                    S.text(cx, y + n.h - 9, p.note, 10.5, T.MUTED, 500, "middle")
                continue
            sfp = p.kind == "sfp"
            w = 60 if sfp else 48
            if isp:
                net = used[0]["link"].net if used else None
                parts.jack(S, cx - 22, jy, 44, 36, (lab.color(net) + "55") if used else "#1b222c",
                           lab.color(net) if used else "#3a475a")
                S.text(cx, jy - 7, p.label, 11, T.MUTED, 500, "middle", mono=True)
                if used and net:
                    parts.ticks(S, lab.color, cx, jy + 41, untagged=net)
                if p.note:
                    S.text(cx, y + n.h - 9, p.note, 10.5, lab.color(net) if used else T.MUTED, 600, "middle")
                continue
            unt, tagged = p.untagged, p.tagged
            to = p.to if p.to is not None else (lab.dev[used[0]["link"].other(n.id)].name if used else "")
            if to in ("free", "rescue") or (not used and p.to is None):
                fill, stroke = "#1b222c", (lab.color(unt) if unt and not tagged else T.TRUNK)
            elif unt and not tagged:
                fill, stroke = lab.color(unt) + "55", lab.color(unt)
            else:
                fill, stroke = "#2a3443", T.TRUNK
            parts.jack(S, cx - w / 2, jy, w, 36, fill, stroke, sfp)
            S.text(cx, jy - 7, p.label or p.id, 11, T.MUTED, 500, "middle", mono=True)
            parts.ticks(S, lab.color, cx, jy + 41, unt, tagged)
            cap_w = (n.pitch if not sfp else 70) - 4
            size = 10.5 if measure(to, 10.5, 500) <= cap_w else max(8, 10.5 * cap_w / measure(to, 10.5, 500))
            S.text(cx, y + n.h - 9, to, round(size, 2), T.FAINT if to in ("free", "rescue") else T.MUTED, 500,
                   "middle")

    def draw_free_jacks(self, n):
        S, lab = self.S, self.lab
        S.tag = n.d.name + " jacks"
        for c in self.cables:
            if c["link"].kind != "cable":
                continue
            for side in ("up", "dn"):
                if c[side] is not n:
                    continue
                x = c["xs"].get((side, n.id)) if not c["same"] else c.get("same_x", {}).get(n.id)
                if x is None:
                    continue
                l = c["link"]
                port = n.d.port(l.port_of(n.id) or "")
                if side == "dn" and not c["same"]:  # jack at the top edge (cable from above)
                    jy = n.y + 14
                    col = lab.color(l.net) if l.net else T.TRUNK
                    parts.jack(S, x - 24, jy, 48, 36, (col + "55") if not l.trunk else "#2a3443", col)
                    if l.trunk:
                        parts.ticks(S, lab.color, x, jy + 41, tagged=l.vlans)
                    else:
                        parts.ticks(S, lab.color, x, jy + 41, untagged=l.net)
                    if port and port.ip:
                        S.text(x + 32, jy + 24, port.ip, 14, col, 600, mono=True)
                else:                              # jack at the bottom edge (cable goes down)
                    jy = n.y + n.h - 46
                    col = lab.color(l.net) if (l.net and not l.trunk) else T.TRUNK
                    parts.jack(S, x - 24, jy, 48, 36, "#2a3443" if l.trunk else col + "55", col)
                    parts.ticks(S, lab.color, x, jy - 5, untagged=None if l.trunk else l.net,
                                tagged=l.vlans, up=True)
                    if port and port.ip:
                        S.text(x + 32, jy + 24, port.ip, 14, col, 600, mono=True)

    def end_y(self, c, side):
        if side == "up_dn":                    # the second card of a same-row link (bottom jack)
            n = c["dn"]
            return n.y + n.h - 28
        n = c[side]
        if side == "up":
            if n.free_jacks and c["link"].kind == "cable":
                return n.y + n.h - 28
            return n.y + n.h
        if n.free_jacks and c["link"].kind == "cable":
            return n.y + 32
        return n.y

    def draw_cables(self):
        S, lab = self.S, self.lab
        S.tag = "cables"
        labels = []
        lag_done = set()
        for c in self.cables:
            l = c["link"]
            pts = self.cable_points(c)
            if not pts:
                continue
            c["pts"] = pts
        for c in sorted([c for c in self.cables if c.get("pts")], key=lambda c: -c["w"]):
            l, pts = c["link"], c["pts"]
            col = lab.color(l.net) if l.net else T.MUTED
            w = c["w"]
            S.reg_cable(pts, f"{c['up'].d.name} ↔ {c['dn'].d.name}",
                        (c["up"].d.name, c["dn"].d.name, c["dn"].d.name + " (tab)", c["up"].d.name + " (tab)"), w)
            halo = _trim(pts, 6)
            if halo and len(pts) > 2:
                S.line(halo, T.BG, w + 7, cap="butt", r=10)
            if l.kind == "kvm":
                S.line(pts, T.MUTED, 2, dash="5 5", cap="butt")
            elif l.kind == "wifi":
                S.line(pts, col, 2, dash="1 4")
            elif l.trunk:
                S.trunk(pts, sw=w)
            else:
                S.line(pts, col, w)
            # labels
            (xa, ya), (xb, yb) = pts[-2], pts[-1]
            if l.kind == "kvm" and l.label:
                # in the free channel above the lower card, on the vertical piece that crosses it
                rowb = max(self.nodes[i].y + self.nodes[i].h for i in self.rows[c["dn"].row - 1]["ids"])
                ly = (rowb + c["dn"].y - T.TAB) / 2 + 5
                seg = next(((p[0], q[0]) for p, q in zip(pts, pts[1:]) if abs(p[0] - q[0]) < 0.1
                            and min(p[1], q[1]) <= ly <= max(p[1], q[1])), (xb, xb))
                labels.append(("kvm", seg[0] + 10, ly, l.label, T.MUTED))
            elif l.lag and not c["same"]:
                key = (l.lag, c["up"].id, c["dn"].id)
                if key not in lag_done:
                    lag_done.add(key)
                    labels.append(("lag", c, key))
            elif l.kind == "cable" and not c["same"]:
                tcol = T.TRUNK if l.trunk else col
                n = c["dn"]
                if n.kind in ("device", "server") or len(pts) > 2:
                    labels.append(("speed", xb + (8 if w > 5 else 5), min(yb, n.y) - 9, l.speed, tcol))
                else:                          # straight drop in the edge chain: label halfway
                    labels.append(("speed", xb + 6, (ya + min(yb, n.y)) / 2 + 4, l.speed, tcol))
        for lb in labels:
            if lb[0] == "lag":
                _, c, key = lb
                group = [cc for cc in self.cables if cc["link"].lag == key[0] and cc["up"].id == key[1]
                         and cc["dn"].id == key[2] and cc.get("pts")]
                xs = [cc["pts"][-1][0] for cc in group]
                ya = max(cc["pts"][0][1] for cc in group)
                yb = min(cc["pts"][-1][1] for cc in group)
                upper_bottom = c["up"].y + c["up"].h
                lower_top = c["dn"].y
                ly = (upper_bottom + lower_top) / 2
                lx = (min(xs) + max(xs)) / 2
                rx = (max(xs) - min(xs)) / 2 + 17
                S.add(f'<ellipse cx="{lx:.1f}" cy="{ly:.1f}" rx="{rx:.1f}" ry="12" fill="none" stroke="{T.TRUNK}" '
                      f'stroke-width="1.4" stroke-dasharray="3 3"/>')
                S.label(lx + rx + 8, ly + 4, c["link"].lag_label or f"LAG · {len(group)}× {c['link'].speed}",
                        T.TRUNK, 11, anchor="start", mono=True)
            elif lb[0] == "kvm":
                _, x, y, t, col = lb
                S.label(x, y, t, col, 12, anchor="start")
            else:
                _, x, y, t, col = lb
                S.label(x, y, t, col, 11, anchor="start", mono=True)

    def cable_points(self, c):
        xs = c["path"] if c.get("path") else self.path_xs(c)
        if c["same"]:
            r = c["up"].row + 1
            ch = self.channels.get(r)
            if not ch:
                return None
            wire = next((w for w in ch["wires"] if w.key is c), None)
            if not wire or wire.y is None:
                return None
            xa, xb = self.same_x(c, c["up"]), self.same_x(c, c["dn"])
            ya = self.end_y(c, "up") if c["up"].free_jacks else c["up"].y + c["up"].h
            yb = self.end_y(c, "up_dn") if c["dn"].free_jacks else c["dn"].y + c["dn"].h
            return [(xa, ya), (xa, wire.y), (xb, wire.y), (xb, yb)]
        if any(x is None for x in xs):
            return None
        pts = [(xs[0], self.end_y(c, "up"))]
        for i in range(len(xs) - 1):
            r = c["up"].row + 1 + i
            ch = self.channels.get(r)
            wire = next((w for w in ch["wires"] if w.key is c), None) if ch else None
            if wire is not None and wire.y is not None:
                pts += [(xs[i], wire.y), (xs[i + 1], wire.y)]
        pts.append((xs[-1], self.end_y(c, "dn")))
        out = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - out[-1][0]) > 0.01 or abs(p[1] - out[-1][1]) > 0.01:
                out.append(p)
        return out


def _trim(pts, d):
    """Polyline without its first and last d units (for the knock-out halo)."""
    if len(pts) < 2:
        return None
    p = list(pts)

    def cut(a, b):
        L = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
        if L <= d:
            return None
        t = d / L
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
    s = cut(p[0], p[1])
    e = cut(p[-1], p[-2])
    if s is None or e is None:
        return None
    return [s] + p[1:-1] + [e]


def _spread(desired, lo, hi, sp):
    """Positions as close to desired (sorted) as possible, at least sp apart, inside [lo, hi]."""
    n = len(desired)
    if not n:
        return []

    class It:
        pseudo = False

        def __init__(self):
            self.w = 0
    items = [It() for _ in desired]
    if hi - lo < sp * (n - 1):
        sp = max(20, (hi - lo) / max(1, n - 1))
    pav(items, list(desired), [sp] * (n - 1), lo, hi)
    return [it.x for it in items]


def _chunks(nodes, avail):
    """Split nodes (in order) into the fewest contiguous rows that fit avail, balanced."""
    total = sum(n.w for n in nodes) + GAP * (len(nodes) - 1)
    k = max(2, -(-int(total) // int(avail)))
    while True:
        target = total / k
        rows, cur, w = [], [], 0
        for n in nodes:
            add = n.w + (GAP if cur else 0)
            if cur and (w + add > avail or (w + add / 2 > target and len(rows) < k - 1)):
                rows.append(cur); cur, w = [], 0
                add = n.w
            cur.append(n); w += add
        rows.append(cur)
        if all(sum(n.w for n in rr) + GAP * (len(rr) - 1) <= avail for rr in rows) or k > len(nodes):
            return rows
        k += 1
