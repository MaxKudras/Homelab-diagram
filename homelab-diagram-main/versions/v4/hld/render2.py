"""2-D layouts (v3): cluster per switch, flow left → right. Cables by the area router (route2).

Shared with the row layout (render.Renderer): card measuring (Node), card drawing, panels,
legend features, cable styles. New here: layouts that place cards in blocks/columns, endpoints on
any side of a card, and routing of every cable around all cards with even spacing.

Cluster: the edge chain (ISP → firewall(s) → core switch(es)) stays centered on top. Below every
chain device hangs its *block*: a tree of everything that is connected through it. Inside a block
the children stand in columns; each child gets its own lane on the left of its column and enters
its card from the left (like a file tree), so cables stay short, local and never run across other
blocks. Sub-switches and APs are blocks inside the block. Servers are children like any device.
"""
from . import panels as P
from . import parts
from . import theme as T
from .ips import collect as collect_ips, table as ip_table
from .model import INFRA_ROLES
from .render import Renderer, _vlan_tag, pav
from .route2 import Router
from .text import measure

LANE = 16           # distance between neighbouring lanes
LABEL_GAP = 64      # room between the innermost lane and the cards (speed label)
ITEM_GAP = 52       # vertical gap between cards in a column (> tab height)
COL_GAP = 64        # gap between columns of a block (room for a few passing cables)
BLOCK_GAP = 70      # gap between blocks
TOP_GAP = 46        # switch bottom → first card, plus one track per cable


WIDTH_WEIGHT = [0.4]     # how much a block's width counts against its height (raised if too wide)
MAX_W = 3400             # preferred canvas width; blocks get narrower before the canvas grows


MID_GAP = 56             # between the left and the right column group (the port drops come down here)


class Box:
    """A placed group: a card (optional) on top, its children in columns on BOTH sides of its ports.

    Children are in port order. The first nL of them stand in columns LEFT of the ports: their
    lanes run on the right of the column and they are entered from the right (E); top → bottom in
    port order. The rest stand RIGHT of the ports: lanes on the left, entered from the left (W),
    highest port on top. With this rule the comb (Renderer2.comb) never crosses itself and every
    cable takes the short way. The optimizer (optimize.py) picks nL and the column sizes per side.
    """

    def __init__(self, node, items, lab, renderer, key=None):
        self.node, self.items, self.R = node, items, renderer
        self.key = key or (node.id if node else None)
        self.layout()

    def n_cables(self, it):
        """How many cables come from the block's root into this item (its lanes)."""
        n = it.node if isinstance(it, Box) else it
        return max(1, len([c for c in self.R.cables if self.R.parent_cable(c) and c["child"] is n]))

    def default_params(self):
        n = len(self.items)
        nl = n // 2
        hl = [it.h for it in self.items[:nl]]
        hr = [it.h for it in self.items[nl:]]
        kl = max(1, min(len(hl), round(sum(hl) / 900))) if hl else 0
        kr = max(1, min(len(hr), round(sum(hr) / 900))) if hr else 0
        from .optimize import _sizes_balanced
        return {"nL": nl, "L": _sizes_balanced(hl, kl) if hl else [], "R": _sizes_balanced(hr, kr) if hr else []}

    def layout(self):
        items = self.items
        root_w = self.node.w if self.node else 0
        if not items:
            self.cols, self.geo = [], {"w": root_w, "h": (self.node.h if self.node else 0), "cols": [],
                                       "root_x": 0, "anchor": root_w / 2}
            self.w, self.h = root_w, self.geo["h"]
            return
        prm = self.R.box_params.get(self.key)
        if not prm or prm["nL"] + 0 > len(items) or sum(prm["L"]) != prm["nL"] or \
                sum(prm["R"]) != len(items) - prm["nL"]:
            prm = self.default_params()
            self.R.box_params[self.key] = prm
        nl = prm["nL"]
        left, right = items[:nl], items[nl:]
        cols = []
        i = 0
        for n in prm["L"]:
            cols.append(("E", left[i:i + n]))               # port order, top → bottom
            i += n
        i = 0
        for n in prm["R"]:
            cols.append(("W", list(reversed(right[i:i + n]))))   # highest port on top
            i += n
        self.cols = cols
        self.geo = self._geometry(cols)
        self.w, self.h = self.geo["w"], self.geo["h"]

    def port_mid(self):
        """x (relative to the root card) in the middle of the ports its children hang on."""
        n = self.node
        xs = []
        for c in self.R.cables:
            if c.get("par") is n and c.get("child") is not None:
                p = c["link"].port_of(n.id)
                xs.append(n.port_x[p] if p in n.port_x else n.w / 2)
        return sum(xs) / len(xs) if xs else n.w / 2

    def _geometry(self, cols):
        head = self.node.h if self.node else 0
        nl = sum(self.n_cables(it) for side, col in cols if side == "E" for it in col)
        nr = sum(self.n_cables(it) for side, col in cols if side == "W" for it in col)
        top = head + (TOP_GAP + T.TAB + max(nl, nr) * LANE if self.node else 0)
        x, out, hmax = 0, [], 0
        anchor = None
        for side, col in cols:
            if side == "W" and anchor is None:
                anchor = x + (MID_GAP / 2 if out else 0)
                x += MID_GAP if out else 0
            lanes = sum(self.n_cables(it) for it in col)
            lane_w = 18 + lanes * LANE + LABEL_GAP
            maxw = max(it.w for it in col)
            y = top
            places = []
            for it in col:
                if side == "E":                          # right-aligned, lanes on the right
                    places.append((x + maxw - it.w, y))
                else:                                    # left-aligned, lanes on the left
                    places.append((x + lane_w, y))
                y += it.h + ITEM_GAP
            out.append({"x": x, "side": side, "lane_w": lane_w, "maxw": maxw, "places": places})
            hmax = max(hmax, y - ITEM_GAP)
            x += maxw + lane_w + COL_GAP
        if anchor is None:                               # only left columns
            anchor = x - COL_GAP + MID_GAP / 2
            width = x - COL_GAP + MID_GAP
        else:
            width = x - COL_GAP
        root_x = 0
        if self.node:                                    # the root card's ports above the middle gap
            root_x = anchor - self.port_mid()
        shift = -min(0, root_x)
        for g in out:
            g["x"] += shift
            g["places"] = [(px + shift, py) for px, py in g["places"]]
        root_x += shift
        anchor += shift
        width = max(width + shift, root_x + (self.node.w if self.node else 0))
        return {"w": width, "h": max(hmax, head), "cols": out, "root_x": root_x, "anchor": anchor}

    def place(self, x, y):
        """Absolute positions for the root card and all children (recursively)."""
        self.x, self.y = x, y
        if self.node:
            self.node.x, self.node.y = x + self.geo["root_x"], y
        for (side, col), g in zip(self.cols, self.geo["cols"]):
            for it, (px, py) in zip(col, g["places"]):
                n = it.node if isinstance(it, Box) else it
                n.col = {"side": side, "items_x": x + g["x"] + (g["lane_w"] if side == "W" else 0),
                         "edge_x": x + g["x"] + g["maxw"]}
                if isinstance(it, Box):
                    it.place(x + px - (it.geo["root_x"] if side == "W" else 0), y + py)
                else:
                    it.x, it.y = x + px, y + py


def _split(items, ncol):
    """Contiguous split of items into ncol columns with balanced heights."""
    from .server import _partition
    parts_ = _partition([it.h + ITEM_GAP for it in items], ncol)
    return [[items[i] for i in p] for p in parts_]


class Renderer2(Renderer):
    def __init__(self, lab, ip_mode="none", unredacted=False, layout="cluster"):
        super().__init__(lab, ip_mode, unredacted)
        self.layout_name = layout
        self.box_params = {}            # box key → column sizes (from the optimizer)

    # ------------------------------------------------------------ graph helpers
    def build_tree(self):
        """Parent of every device = its neighbour one tier closer to the internet (switch/AP first)."""
        tiers, nchain, servers = self.tiers()
        depth = {}
        for t, ids in enumerate(tiers):
            for i in ids:
                depth[i] = t
        for s in servers:
            depth[s] = 10 ** 6                      # servers hang below whatever they connect to
        self.chain = [ids for ids in tiers[:nchain]]
        chain_ids = {i for ids in self.chain for i in ids}
        pref = {"switch": 0, "ap": 1, "firewall": 2, "router": 2, "isp_router": 3}
        self.parent = {}
        for d in self.lab.devices:
            if d.id in chain_ids:
                continue
            cands = []
            for l in self.lab.links_of(d.id):
                if l.kind not in ("cable", "wifi"):
                    continue
                o = l.other(d.id)
                if depth.get(o, 10 ** 7) < depth.get(d.id, 10 ** 7):
                    cands.append((pref.get(self.lab.dev[o].role, 5), depth[o], self._port_index(l, o), o))
            if cands:
                self.parent[d.id] = min(cands)[3]
        self.children = {}
        for c, p in self.parent.items():
            self.children.setdefault(p, []).append(c)
        for p, cs in self.children.items():
            cs.sort(key=lambda c: self._child_order(p, c))
        self.orphans = [d.id for d in self.lab.devices if d.id not in chain_ids and d.id not in self.parent]

    def _port_index(self, l, dev):
        port = l.port_of(dev)
        d = self.lab.dev[dev]
        ids = [p.id for p in d.ports]
        return ids.index(port) if port in ids else 999

    def _child_order(self, p, c):
        idx = [self._port_index(l, p) for l in self.lab.links_of(c) if l.other(c) == p]
        return (min(idx) if idx else 999, self.lab.devices.index(self.lab.dev[c]))

    def parent_cable(self, c):
        return c.get("child") is not None

    # ------------------------------------------------------------ cables
    def make_cables(self):
        """Cables to draw. A KVM switch with several servers gets badges instead of long console lines."""
        cab = []
        self.kvm_badges = {}
        kvm_links = {}
        for l in self.lab.links:
            if l.kind == "kvm":
                k = l.a_dev if self.lab.dev[l.a_dev].role == "kvm" else l.b_dev
                kvm_links.setdefault(k, []).append(l)
        for k, ls in kvm_links.items():
            if len(ls) > 1:
                for l in ls:
                    self.kvm_badges[l.other(k)] = self.lab.dev[k].name
                self.nodes[k].d.extra["kvm_note"] = f"Konsole für {len(ls)} Server"
        for l in self.lab.links:
            if l.kind == "vpn" or (l.kind == "kvm" and len(kvm_links.get(
                    l.a_dev if self.lab.dev[l.a_dev].role == "kvm" else l.b_dev, [])) > 1):
                continue
            a, b = self.nodes[l.a_dev], self.nodes[l.b_dev]
            c = {"link": l, "a": a, "b": b, "w": self.line_w(l), "child": None, "ends": {}}
            if self.parent.get(b.id) == a.id:
                c["child"], c["par"] = b, a
            elif self.parent.get(a.id) == b.id:
                c["child"], c["par"] = a, b
            cab.append(c)
        self.cables = cab

    # ------------------------------------------------------------ cluster layout
    def build_box(self, nid):
        kids = self.children.get(nid, [])
        items = []
        for k in kids:
            items.append(self.build_box(k) if self.children.get(k) else self.nodes[k])
        return Box(self.nodes[nid], items, self.lab, self)

    def layout_cluster(self):
        self.build_tree()
        self.make_cables()
        for n in self.nodes.values():
            if n.d.extra.get("kvm_note"):
                n.h += 26                      # room for the "Konsole für N Server" pill
            if n.kind == "server":
                n.w = n.server.best_w(max_h=1000, max_w=1300)
                n.h = n.server.size(n.w)
        self.columns()
        # chain rows, centered
        y = P.CLOUD_Y + 58 + 60 + T.TAB
        prev = None
        for ids in self.chain:
            nodes = [self.nodes[i] for i in ids]
            gap = 120 if any(l.a_dev in ids and l.b_dev in ids for l in self.lab.links) else 40
            total = sum(n.w for n in nodes) + gap * (len(nodes) - 1)
            while total > T.CENTER_R - T.CENTER_L and any(n.shrink() for n in nodes):
                total = sum(n.w for n in nodes) + gap * (len(nodes) - 1)
            if prev is not None:
                y = prev + 96 + T.TAB
            if total > T.W - 2 * T.MARGIN:          # wider than the canvas: widen it
                self.set_width(total + 2 * T.MARGIN)
            x = T.CX - total / 2
            if len(nodes) == 1 and nodes[0].kind == "isp":
                x = self.chain_center(nodes[0]) - nodes[0].w / 2
            # beside the side columns only if it fits between them, else below them
            h = max(n.h for n in nodes)
            if x < T.LEFT_X + T.LEFT_W + 30 and y - T.TAB < self.left_bottom + 30:
                y = max(y, self.left_bottom + 60 + T.TAB)
            if x + total > T.RIGHT_X - 30 and y - T.TAB < self.right_bottom + 30:
                y = max(y, self.right_bottom + 60 + T.TAB)
            for n in nodes:
                n.x, n.y = x, y
                x += n.w + gap
            prev = max(n.y + n.h for n in nodes)
        chain_bottom = prev or y
        self.chain_bottom = chain_bottom
        from .optimize import optimize
        blocks = optimize(self)
        self.blocks = blocks
        self.place_blocks(blocks, final=True)

    def block_area(self, blocks):
        """y of the block row and the free x-range for it."""
        total = sum(b.w for _, b in blocks) + BLOCK_GAP * max(0, len(blocks) - 1)
        y0 = self.chain_bottom + 120 + self.n_block_tracks()
        L, R = T.CENTER_L, T.CENTER_R
        if total > R - L:
            y0 = max(y0, max(self.left_bottom, self.right_bottom) + 60)
            L, R = T.MARGIN, max(T.W, total + 2 * T.MARGIN) - T.MARGIN
        return y0, L, R, total

    def block_anchor(self, root, box):
        """Center x a block wants: its middle gap (between left and right group) under the ports
        its cables leave from."""
        if root is None:
            return T.CX
        return self.ports_mid(root) - box.geo["anchor"] + box.w / 2

    def ports_mid(self, root):
        xs = []
        for c in self.cables:
            if c.get("par") is root and c.get("child") is not None:
                p = c["link"].port_of(root.id)
                xs.append(root.x + root.port_x[p] if p in root.port_x else root.x + root.w / 2)
        return sum(xs) / len(xs) if xs else root.x + root.w / 2

    def place_blocks(self, blocks, final=False):
        y0, L, R, total = self.block_area(blocks)
        if final and R + T.MARGIN > T.W:
            self.set_width(R + T.MARGIN)

        class It:
            pseudo = False

            def __init__(s, b):
                s.b, s.w = b, b.w
        its = [It(b) for _, b in blocks]
        desired = [self.block_anchor(root, b) for root, b in blocks]
        pav(its, desired, [BLOCK_GAP] * max(0, len(its) - 1), L, R)
        bottom = y0
        for it in its:
            it.b.place(it.x, y0)
            bottom = max(bottom, y0 + it.b.h)
        self.bottom = bottom
        return bottom, max([it.x + it.w for it in its] + [T.W - T.MARGIN])

    def make_blocks(self):
        """One block per chain device (its children), in chain order (left → right)."""
        blocks = []
        for ids in self.chain:
            for i in ids:
                if self.children.get(i):
                    items = [self.build_box(k) if self.children.get(k) else self.nodes[k] for k in self.children[i]]
                    blocks.append((self.nodes[i], Box(None, items, self.lab, self, key="blk:" + i)))
        for o in self.orphans:                   # unconnected devices: their own block at the end
            if o not in self.parent:
                blocks.append((None, self.build_box(o)))
        return blocks

    def n_block_tracks(self):
        """Room under the chain for cables that run from a chain port to its block."""
        return 16 * len([c for c in self.cables if c.get("par") is not None and c["par"].id in
                         {i for ids in self.chain for i in ids}])

    def set_width(self, w):
        w = int(max(w, T.W))
        d = w - T.W
        T.W = w
        if T.RIGHT_X != T.LEFT_X:
            T.RIGHT_X += d
        T.CENTER_R += d / 2
        T.CENTER_L += d / 2
        T.CX += d / 2
        self.S.w = w

    # ------------------------------------------------------------ endpoints
    def assign_ends(self):
        """Side and position of both ends of every cable."""
        if self.layout_name == "manual":
            from .layouts_manual import assign_ends_manual
            return assign_ends_manual(self)
        chain_ids = {i for ids in self.chain for i in ids}
        by_card = {}
        kvm_out = {}
        for c in self.cables:
            l = c["link"]
            a, b = c["a"], c["b"]
            if c["child"] is not None and c["child"].id not in chain_ids:
                par, ch = c["par"], c["child"]
                side_c = (getattr(ch, "col", None) or {}).get("side", "W")   # tree: from its lane
                c["ends"][par.id] = self.exit_point(par, c, "S")
                by_card.setdefault((ch.id, side_c), []).append(c)
            else:
                up, dn = (a, b) if (a.y + a.h / 2) <= (b.y + b.h / 2) else (b, a)
                if abs(a.y - b.y) < 1:
                    lft, rgt = (a, b) if a.x < b.x else (b, a)
                    between = [n for n in self.nodes.values() if n.x is not None and abs(n.y - a.y) < 1
                               and lft.x < n.x < rgt.x]
                    if not between:                   # neighbours: short and straight, side to side
                        yy = min(lft.y + lft.h, rgt.y + rgt.h) - 30
                        c["ends"][lft.id] = (lft.x + lft.w, yy, "E")
                        c["ends"][rgt.id] = (rgt.x, yy, "W")
                        c["side_link"] = True
                    else:                             # same row, not neighbours: both from below
                        c["ends"][a.id] = self.exit_point(a, c, "S")
                        c["ends"][b.id] = self.exit_point(b, c, "S")
                    continue
                if l.kind == "kvm":                 # console: from the KVM device, wherever the server is
                    k, s_ = (a, b) if a.d.role == "kvm" else (b, a)
                    kvm_out.setdefault(k.id, []).append(c)
                    by_card.setdefault((s_.id, "N"), []).append(c)
                    continue
                c["ends"][up.id] = self.exit_point(up, c, "S")
                if dn.kind in ("isp", "switch") and l.port_of(dn.id) in dn.port_x:
                    c["ends"][dn.id] = (dn.x + dn.port_x[l.port_of(dn.id)], dn.y, "N")
                else:
                    by_card.setdefault((dn.id, "N"), []).append(c)
        # console cables leave the KVM on its right side, one above the other
        for kid, cs in kvm_out.items():
            k = self.nodes[kid]
            cs.sort(key=lambda c: (c["b"] if c["a"] is k else c["a"]).y)
            # the side away from its own lane (its lane runs on the side it is entered from)
            lane_side = (getattr(k, "col", None) or {}).get("side", "W")
            out_side = "W" if lane_side == "E" else "E"
            xx = k.x if out_side == "W" else k.x + k.w
            for i, c in enumerate(cs):
                c["ends"][kid] = (xx, k.y + k.h / 2 + 14 + (i - (len(cs) - 1) / 2) * 18, out_side)
        # spread entries on the receiving cards
        for (nid, side), cs in by_card.items():
            n = self.nodes[nid]
            other = {}
            for c in cs:
                o = c["a"] if c["b"] is n else c["b"]
                e = c["ends"].get(o.id)
                other[id(c)] = e if e else (o.x + o.w / 2, o.y + o.h, "S")
            if side in ("W", "E"):
                # W: highest port on top · E: lowest port on top (matches the comb, no crossings)
                cs.sort(key=lambda c: -self.lane_order(c) if side == "W" else self.lane_order(c))
                k = len(cs)
                mid = n.y + min(n.h / 2, 46)          # tall cards (servers): at the header, not the middle
                ys = [mid + (i - (k - 1) / 2) * 34 for i in range(k)]
                ex = n.x if side == "W" else n.x + n.w
                for c, yy in zip(cs, ys):
                    c["ends"][n.id] = (ex, yy, side)
            else:
                cs.sort(key=lambda c: (other[id(c)] or (0,))[0])
                if n.free_jacks:
                    lo, hi = n.x + n.hdr + 54, n.x + n.w - 54
                    from .render import _spread
                    xs = _spread([(other[id(c)] or (n.x,))[0] for c in cs], lo, hi, 58)
                elif n.kind == "server":
                    from .render import _spread
                    xs = _spread([(other[id(c)] or (n.x,))[0] for c in cs], n.x + n.tab_w + 30, n.x + n.w - 60, 70)
                else:
                    xs, x = [], n.x + n.tab_w + 34
                    for c in cs:
                        xs.append(x)
                        x += self.S.label_w(self.speed_txt(c), 11, True) + 22
                for c, x in zip(cs, xs):
                    c["ends"][n.id] = (x, n.y, "N")

    def lane_order(self, c):
        return self._port_index(c["link"], c["par"].id)

    def exit_point(self, n, c, side):
        l = c["link"]
        p = l.port_of(n.id)
        if n.kind in ("isp", "switch") and p in n.port_x:
            return (n.x + n.port_x[p], n.y + n.h, "S")
        # free jacks / plain cards: spread along the bottom, decided after all exits are known
        key = ("exit", n.id)
        self._exits = getattr(self, "_exits", {})
        self._exits.setdefault(key, []).append(c)
        return None

    def spread_exits(self):
        """Bottom exits of cards without a port row: ordered by where their cables go."""
        from .render import _spread
        for (_, nid), cs in getattr(self, "_exits", {}).items():
            n = self.nodes[nid]

            def target(c):
                o = c["b"] if c["a"] is n else c["a"]
                e = c["ends"].get(o.id)
                return e[0] if e else o.x + o.w / 2
            cs.sort(key=target)
            if n.free_jacks:
                xs = _spread([target(c) for c in cs], n.x + 54, n.x + n.w - 54, 58)
            else:
                xs = _spread([target(c) for c in cs], n.x + 24, n.x + n.w - 24, 30)
            for c, x in zip(cs, xs):
                c["ends"][n.id] = (x, n.y + n.h, "S")

    # ------------------------------------------------------------ routing
    def route_all(self, height):
        R = Router(T.W, height)
        self.router = R
        for n in self.nodes.values():
            if n.x is None:
                continue
            R.block_rect(n.x, n.y, n.x + n.w, n.y + n.h, margin=8)
            R.block_rect(n.x, n.y - T.TAB, n.x + n.tab_w, n.y, margin=8)
        for x0, y0, x1, y1 in self.panel_boxes():
            R.block_rect(x0, y0, x1, y1, margin=14)
        # reserve the speed-label boxes next to every entry
        for c in self.cables:
            for nid, e in c["ends"].items():
                if not e or c["link"].kind != "cable":
                    continue
                n = self.nodes[nid]
                # label boxes keep one grid cell away from the cable's own stub
                if e[2] == "N" and n.kind in ("device", "server"):
                    lw = self.S.label_w(self.speed_txt(c), 11, True)
                    R.block_rect(e[0] + 12, e[1] - 24, e[0] + 8 + lw, e[1] - 4, margin=0)
                elif e[2] == "W":
                    lw = self.S.label_w(self.speed_txt(c), 11, True)
                    R.block_rect(e[0] - 10 - lw, e[1] - 20, e[0] - 10, e[1] - 13, margin=0)
                elif e[2] == "E" and c.get("child") is n:
                    lw = self.S.label_w(self.speed_txt(c), 11, True)
                    R.block_rect(e[0] + 10, e[1] - 20, e[0] + 10 + lw, e[1] - 13, margin=0)

        def prio(c):
            l = c["link"]
            if l.kind == "kvm":
                return (3, 0)
            if c["child"] is None:
                return (0, -abs(self.end(c, 0)[1] - self.end(c, 1)[1]))
            ch = c["child"]
            depth, n = 0, ch.id                       # inner blocks first: they claim their gaps
            while n in self.parent:
                depth += 1
                n = self.parent[n]
            return (1, -depth, ch.x, ch.y)
        self.failed = []
        self.comb(R)
        for c in self.cables:                    # hand-drawn cables (manual layout: via points)
            if c.get("manual_pts"):
                c["pts"] = self.with_jacks(c, c["manual_pts"])
                R.commit_path(c["manual_pts"], c["w"])
        for c in sorted([c for c in self.cables if not c.get("pts")], key=prio):
            a, b = self.end(c, 0), self.end(c, 1)
            if not a or not b:
                continue
            pts = R.route((a[0], a[1]), a[2], (b[0], b[1]), b[2], c["w"])
            if pts is None:
                self.failed.append(c)
                pts = [(a[0], a[1]), (a[0], (a[1] + b[1]) / 2), (b[0], (a[1] + b[1]) / 2), (b[0], b[1])]
            c["pts"] = self.with_jacks(c, pts)

    def comb(self, R):
        """Tree cables (parent → children in its block) as a comb that never crosses itself.
        Left group (E entries): lanes right of the column, lowest port = innermost lane = top card.
        Right group (W entries): lanes left of the column, highest port = innermost lane = top card.
        Every cable gets its own level under the parent (left and right group count separately),
        is drawn explicitly and registered as an obstacle for the A* router."""
        by_parent = {}
        for c in self.cables:
            if c.get("child") is None or c["link"].kind == "kvm":
                continue
            ch = c["child"]
            col = getattr(ch, "col", None)
            if not col or c["ends"].get(ch.id, (0, 0, ""))[2] != col["side"]:
                continue
            if self.layout_name == "flow" and c["par"].id in {i for ids in self.chain for i in ids}:
                continue                          # flow: blocks sit beside the chain, A* finds the way
            by_parent.setdefault(c["par"].id, []).append(c)
        for pid, cs in by_parent.items():
            par = self.nodes[pid]
            ex = {id(c): c["ends"][pid][0] for c in cs if c["ends"].get(pid)}
            cs = [c for c in cs if id(c) in ex]
            cols = {}
            for c in cs:
                col = c["child"].col
                cols.setdefault((col["side"], col["items_x"], col["edge_x"]), []).append(c)
            lane = {}
            for (side, ix, edge), ccs in cols.items():
                if side == "E":
                    ccs.sort(key=lambda c: ex[id(c)])
                    for i, c in enumerate(ccs):
                        lane[id(c)] = edge + LABEL_GAP + LANE / 2 + i * LANE
                else:
                    ccs.sort(key=lambda c: -ex[id(c)])
                    for i, c in enumerate(ccs):
                        lane[id(c)] = ix - LABEL_GAP - LANE / 2 - i * LANE
            left = sorted([c for c in cs if lane[id(c)] <= ex[id(c)]], key=lambda c: ex[id(c)])
            right = sorted([c for c in cs if lane[id(c)] > ex[id(c)]], key=lambda c: -ex[id(c)])
            y0 = par.y + par.h + 24
            for group in (left, right):
                for k, c in enumerate(group):
                    yk = y0 + k * LANE
                    e = c["ends"][c["child"].id]
                    lx = lane[id(c)]
                    pts = [(ex[id(c)], par.y + par.h), (ex[id(c)], yk), (lx, yk), (lx, e[1]), (e[0], e[1])]
                    c["pts"] = self.with_jacks(c, pts)
                    R.commit_path(pts, c["w"])

    def end(self, c, i):
        """End i (0 = a, 1 = b) as (x, y, side)."""
        n = c["a"] if i == 0 else c["b"]
        return c["ends"].get(n.id)

    def with_jacks(self, c, pts):
        """Cables into free jacks continue to the jack's middle (the jack is drawn on top)."""
        pts = list(pts)
        if c["link"].kind != "cable":
            return pts
        for i, n in ((0, c["a"]), (-1, c["b"])):
            if not n.free_jacks:
                continue
            x, y = pts[i]
            if abs(y - n.y) < 1:
                ext = (x, n.y + 32)
            elif abs(y - (n.y + n.h)) < 1:
                ext = (x, n.y + n.h - 28)
            else:
                continue
            if i == 0:
                pts.insert(0, ext)
            else:
                pts.append(ext)
        return pts

    def panel_list(self):
        """Every side panel with its box: [{key, kind, item, x, y, w, h}]. Default: the left and right
        column; a manual layout (layout.panels.<key>: {x, y}) moves single panels anywhere."""
        out = []
        y = 150
        for name, h in self.left:
            out.append({"key": name, "kind": name, "item": None, "x": T.LEFT_X, "y": y, "w": T.LEFT_W, "h": h})
            y += h + 20
        for i, (item, yy, h) in enumerate(self.right):
            kind = item if isinstance(item, str) else "panel"
            key = item if isinstance(item, str) else f"panel{i}"
            out.append({"key": key, "kind": kind, "item": item, "x": T.RIGHT_X, "y": yy, "w": T.RIGHT_W, "h": h})
        man = ((self.lab.raw.get("layout") or {}).get("panels") or {})
        for pnl in out:
            pos = man.get(pnl["key"])
            if pos:
                pnl["x"], pnl["y"] = float(pos["x"]), float(pos["y"])
        return out

    def panel_boxes(self):
        boxes = []
        for pnl in self.panel_list():
            boxes.append((pnl["x"], pnl["y"], pnl["x"] + pnl["w"], pnl["y"] + pnl["h"]))
        boxes.append((T.CX - 160, P.CLOUD_Y - 85, T.CX + 160, P.CLOUD_Y + 62))      # internet cloud
        for i, _ in enumerate(self.lab.remote):
            boxes.append((T.CX - 500, 150 + i * 96, T.CX - 200, 234 + i * 96))
        return boxes

    # ------------------------------------------------------------ drawing
    def draw(self, title):
        saved = (T.W, T.RIGHT_X, T.RIGHT_W, T.CENTER_L, T.CENTER_R, T.CX)
        try:
            return self._draw(title)
        finally:
            T.W, T.RIGHT_X, T.RIGHT_W, T.CENTER_L, T.CENTER_R, T.CX = saved

    def _draw(self, title):
        lab, S = self.lab, self.S
        if self.layout_name == "flow":
            from .layouts_flow import layout_flow
            layout_flow(self)
        elif self.layout_name == "manual":
            from .layouts_manual import layout_manual
            layout_manual(self)
        else:
            self.layout_cluster()
        self._exits = {}
        self.assign_ends()
        self.spread_exits()
        bottom = max([self.bottom] + [p_["y"] + p_["h"] for p_ in self.panel_list()])
        H = bottom + 40
        self.route_all(H + 400)
        bottom = max([bottom] + [p[1] for c in self.cables for p in c.get("pts", [])])
        # panels + frame
        P.header(S, title, lab.meta.get("watermark", ""), lab.meta.get("date", ""))
        P.remote(S, lab, T.CX)
        P.internet(S, lab, T.CX)
        for pnl in self.panel_list():
            k, x, yy, w = pnl["kind"], pnl["x"], pnl["y"], pnl["w"]
            if k == "networks":
                P.networks(S, lab, x, yy, w)
            elif k == "legend":
                P.legend(S, lab, self.feat, x, yy, w)
            elif k == "cloud":
                P.cloud_services(S, lab, T.CX, x, yy, w, lines=self.layout_name == "cluster")
            elif k == "forwards":
                P.forwards(S, lab, x, yy, w)
            else:
                P.PANELS[pnl["item"]["type"]](S, lab, pnl["item"], x, yy, w)
        self.draw_uplink2()
        for n in self.nodes.values():
            if n.x is not None:
                self.draw_card(n)
                self.draw_badges(n)
        self.draw_cables2()
        for n in self.nodes.values():
            if n.x is not None and n.free_jacks:
                self.draw_jacks2(n)
        if self.ip_mode in ("table", "both"):
            y = bottom + 30
            h = ip_table(S, lab, collect_ips(lab), T.MARGIN, y, T.W - 2 * T.MARGIN, 6)
            bottom = y + h
        for c in self.failed:
            self.warnings.append(f"Kein freier Weg für {c['a'].d.name} ↔ {c['b'].d.name} (Notlösung gezeichnet)")
        return bottom + 40

    def draw_uplink2(self):
        S, lab = self.S, self.lab
        first = [self.nodes[i] for i in self.chain[0]] if self.chain else []
        if not first:
            return
        n = first[0]
        up = next((p for p in n.d.ports if p.uplink), None)
        x = n.x + n.port_x[up.id] if up and up.id in n.port_x else n.x + n.w / 2
        cy0 = P.CLOUD_Y
        top = n.y + 28
        S.tag = "internet line"
        pts = [(x, cy0 + 58), (x, top)] if abs(x - T.CX) < 1 else \
            [(T.CX, cy0 + 58), (T.CX, (cy0 + 58 + n.y - T.TAB) / 2), (x, (cy0 + 58 + n.y - T.TAB) / 2), (x, top)]
        S.line(pts, "#6b7a90", 3)
        S.reg_cable(pts, "internet", ("internet", n.d.name, n.d.name + " (tab)"))
        sp = lab.internet.get("speed") or {}
        my = (cy0 + 58 + n.y - T.TAB) / 2 + 5
        if sp.get("down"):
            S.label(T.CX - 10, my - (14 if len(pts) > 2 else 0), "↓ " + sp["down"], "#c3cdd9", 12, anchor="end", mono=True)
        if sp.get("up"):
            S.label(T.CX + 10, my - (14 if len(pts) > 2 else 0), "↑ " + sp["up"], "#c3cdd9", 12, anchor="start", mono=True)

    def draw_cables2(self):
        S, lab = self.S, self.lab
        S.tag = "cables"
        from .render import _trim
        labels = []
        for c in sorted([c for c in self.cables if c.get("pts")], key=lambda c: -c["w"]):
            l, pts = c["link"], c["pts"]
            col = lab.color(l.net) if l.net else T.MUTED
            w = c["w"]
            S.reg_cable(pts, f"{c['a'].d.name} ↔ {c['b'].d.name}",
                        (c["a"].d.name, c["b"].d.name, c["a"].d.name + " (tab)", c["b"].d.name + " (tab)"), w)
            halo = _trim(pts, 7)
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
            if c.get("side_link") and l.kind == "cable":
                (xa, ya), (xb, yb) = pts[0], pts[-1]
                def plabel(n):
                    pp = n.d.port(l.port_of(n.id) or "")
                    return (pp.label or pp.id) if pp else ""
                txt = l.label or (f"{plabel(c['a'])} ↔ {plabel(c['b'])}" if plabel(c["a"]) else l.speed)
                labels.append(((xa + xb) / 2, ya - 8, txt, T.TRUNK if l.trunk else col, 11, "middle"))
                continue
            if l.kind == "kvm" and l.label:          # right under the KVM device, beside the line
                labels.append((pts[0][0] + 10, pts[0][1] + 22, l.label, T.MUTED, 12, False))
            elif l.kind == "cable":
                tcol = T.TRUNK if l.trunk else col
                for nid, e in c["ends"].items():
                    n = self.nodes[nid]
                    if not e:
                        continue
                    if e[2] == "N" and n.kind in ("device", "server"):
                        labels.append((e[0] + (8 if w > 5 else 5), e[1] - 9, l.speed, tcol, 11, "start"))
                    elif e[2] == "W":
                        labels.append((e[0] - 8, e[1] - 8, l.speed, tcol, 11, "end"))
                    elif e[2] == "E" and c.get("child") is n:
                        labels.append((e[0] + 8, e[1] - 8, l.speed, tcol, 11, "start"))
                    elif e[2] == "N" and n.free_jacks:
                        labels.append((e[0] + 8, e[1] - 9, l.speed, tcol, 11, "start"))
        for x, y, t, col, size, anchor in labels:
            if anchor is False:
                S.label(x, y, t, col, size, anchor="start")
            else:
                S.label(x, y, t, col, size, anchor=anchor, mono=True)

    def draw_jacks2(self, n):
        S, lab = self.S, self.lab
        S.tag = n.d.name + " jacks"
        for c in self.cables:
            e = c["ends"].get(n.id)
            if not e or c["link"].kind != "cable" or n not in (c["a"], c["b"]):
                continue
            l = c["link"]
            x = e[0]
            port = n.d.port(l.port_of(n.id) or "")
            col = lab.color(l.net) if (l.net and not l.trunk) else T.TRUNK
            if e[2] in ("E", "W"):                 # side link between neighbours: no jack
                continue
            if e[2] == "N":
                jy = n.y + 14
                parts.jack(S, x - 24, jy, 48, 36, (col + "55") if not l.trunk else "#2a3443", col)
                parts.ticks(S, lab.color, x, jy + 41, untagged=None if l.trunk else l.net, tagged=l.vlans)
            else:
                jy = n.y + n.h - 46
                parts.jack(S, x - 24, jy, 48, 36, "#2a3443" if l.trunk else col + "55", col)
                parts.ticks(S, lab.color, x, jy - 5, untagged=None if l.trunk else l.net, tagged=l.vlans, up=True)
            if port and port.ip:
                S.text(x + 32, jy + 24, port.ip, 14, col, 600, mono=True)

    def draw_badges(self, n):
        """KVM badge on servers reached by a multi-port KVM; note on the KVM card itself."""
        S = self.S
        if n.id in self.kvm_badges:
            t = "KVM · " + self.kvm_badges[n.id]
            right = n.x + n.w - (36 if n.d.extra.get("monitor") else 16)
            S.pill(right, n.y + 12, t, T.MUTED, 10.5, mono=True, h=19, pad=7, anchor="end")
        note = n.d.extra.get("kvm_note")
        if note:
            S.pill(n.x + n.w - 16, n.y + n.h - 28, note, T.MUTED, 10.5, h=19, pad=7, anchor="end")

    # ------------------------------------------------------------ flow endpoints
    def assign_ends_flow(self):
        """Left → right: a cable leaves the left card on its right side (or its port row) and enters
        the right card on its left side (switches: at the port, from below)."""
        outs, ins = {}, {}
        for c in self.cables:
            l = c["link"]
            a, b = c["a"], c["b"]
            if l.kind == "kvm":
                k, s_ = (a, b) if a.d.role == "kvm" else (b, a)
                outs.setdefault(k.id, []).append(c)
                ins.setdefault(s_.id, []).append(c)
                continue
            left, right = (a, b) if a.x <= b.x else (b, a)
            if abs(a.x - b.x) < 1:                     # same column: from the right sides
                left, right = (a, b) if a.y < b.y else (b, a)
            for n, bucket in ((left, outs), (right, ins)):
                p = l.port_of(n.id)
                if n.kind in ("isp", "switch") and p in n.port_x:
                    c["ends"][n.id] = (n.x + n.port_x[p], n.y + n.h, "S")
                else:
                    bucket.setdefault(n.id, []).append(c)

        def other_y(c, n):
            o = c["b"] if c["a"] is n else c["a"]
            e = c["ends"].get(o.id)
            return e[1] if e else o.y + o.h / 2
        for nid, cs in outs.items():
            n = self.nodes[nid]
            cs.sort(key=lambda c: other_y(c, n))
            k = len(cs)
            for i, c in enumerate(cs):
                c["ends"][nid] = (n.x + n.w, n.y + min(n.h / 2, 46) + (i - (k - 1) / 2) * 30, "E")
        for nid, cs in ins.items():
            n = self.nodes[nid]
            cs.sort(key=lambda c: other_y(c, n))
            k = len(cs)
            for i, c in enumerate(cs):
                c["ends"][nid] = (n.x, n.y + min(n.h / 2, 46) + (i - (k - 1) / 2) * 34, "W")
