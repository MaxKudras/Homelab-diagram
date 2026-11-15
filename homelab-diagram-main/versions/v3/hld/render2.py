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


class Box:
    """A placed group: a card (optional) with children in columns. Coordinates are relative."""

    def __init__(self, node, items, lab, renderer):
        self.node, self.items, self.R = node, items, renderer
        self.layout()

    def n_cables(self, it):
        """How many cables come from the block's root into this item (its lanes)."""
        n = it.node if isinstance(it, Box) else it
        return max(1, len([c for c in self.R.cables if self.R.parent_cable(c) and c["child"] is n]))

    def layout(self):
        """Pick the number of columns that gives the most compact block and place everything."""
        items = self.items
        best = None
        root_w = self.node.w if self.node else 0
        for ncol in range(1, len(items) + 1):
            # columns take the ports from left to right; inside a column the highest port is on top,
            # so the comb of cables (see Renderer2.comb) never crosses itself
            cols = [list(reversed(c)) for c in _split(items, ncol)]
            geo = self._geometry(cols)
            w, h = geo["w"], geo["h"]
            if w > 2600 and ncol > 1:
                break
            score = h + WIDTH_WEIGHT[0] * max(w, root_w)
            if best is None or score < best[0]:
                best = (score, cols, geo)
        if not items:
            self.cols, self.geo = [], {"w": root_w, "h": (self.node.h if self.node else 0), "cols": []}
        else:
            _, self.cols, self.geo = best
        self.w = max(root_w, self.geo["w"])
        self.h = self.geo["h"]

    def _geometry(self, cols):
        head = self.node.h if self.node else 0
        ncab = sum(self.n_cables(it) for col in cols for it in col)
        top = head + (TOP_GAP + T.TAB + ncab * LANE if self.node else 0)
        x, out, hmax = 0, [], 0
        for col in cols:
            lanes = sum(self.n_cables(it) for it in col)
            lane_w = 18 + lanes * LANE + LABEL_GAP
            y = top
            places = []
            for it in col:
                places.append((x + lane_w, y))
                y += it.h + ITEM_GAP
            cw = lane_w + max(it.w for it in col)
            out.append({"x": x, "lane_w": lane_w, "places": places})
            hmax = max(hmax, y - ITEM_GAP)
            x += cw + COL_GAP
        return {"w": x - COL_GAP, "h": hmax, "cols": out}

    def place(self, x, y):
        """Absolute positions for the root card and all children (recursively)."""
        self.x, self.y = x, y
        if self.node:
            self.node.x, self.node.y = x, y
        for col, g in zip(self.cols, self.geo["cols"]):
            for it, (px, py) in zip(col, g["places"]):
                n = it.node if isinstance(it, Box) else it
                n.col = {"items_x": x + px, "members": [m.node if isinstance(m, Box) else m for m in col]}
                if isinstance(it, Box):
                    it.place(x + px, y + py)
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
                n.w = n.server.best_w()
                n.h = n.server.size(n.w)
        self.columns()
        # chain rows, centered
        y = P.CLOUD_Y + 58 + 60 + T.TAB
        prev = None
        for ids in self.chain:
            nodes = [self.nodes[i] for i in ids]
            total = sum(n.w for n in nodes) + 40 * (len(nodes) - 1)
            while total > T.CENTER_R - T.CENTER_L and any(n.shrink() for n in nodes):
                total = sum(n.w for n in nodes) + 40 * (len(nodes) - 1)
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
                x += n.w + 40
            prev = max(n.y + n.h for n in nodes)
        chain_bottom = prev or y
        blocks = self.make_blocks()
        # narrower blocks until everything fits into the preferred width (height is worse than width)
        def total_w(bl):
            return sum(b.w for _, b in bl) + BLOCK_GAP * max(0, len(bl) - 1)
        cands = []
        for wgt in (0.15, 0.4, 0.9, 1.8, 4.0, 10.0):
            WIDTH_WEIGHT[0] = wgt
            bl = self.make_blocks()
            cands.append((total_w(bl) > MAX_W - 2 * T.MARGIN, max([b.h for _, b in bl] or [0]), total_w(bl), bl))
        WIDTH_WEIGHT[0] = 0.4
        fits = [c for c in cands if not c[0]]
        # lowest picture that fits the preferred width; if nothing fits, the narrowest one
        blocks = min(fits, key=lambda c: (c[1], c[2]))[3] if fits else min(cands, key=lambda c: c[2])[3]
        self.blocks = blocks
        # place blocks under their chain device; below the side columns when they don't fit beside
        total = total_w(blocks)
        y0 = chain_bottom + 120 + self.n_block_tracks()
        L, R = T.CENTER_L, T.CENTER_R
        if total > R - L:
            y0 = max(y0, max(self.left_bottom, self.right_bottom) + 60)
            L, R = T.MARGIN, T.W - T.MARGIN
            if total > R - L:                   # grow the canvas sideways instead of downwards
                self.set_width(total + 2 * T.MARGIN)
                L, R = T.MARGIN, T.W - T.MARGIN
        class It:
            pseudo = False

            def __init__(s, b):
                s.b, s.w = b, b.w
        its = [It(b) for _, b in blocks]
        desired = [((root.x + root.w / 2) if root else T.CX) for root, _ in blocks]
        pav(its, desired, [BLOCK_GAP] * max(0, len(its) - 1), L, R)
        bottom = y0
        for it in its:
            it.b.place(it.x, y0)
            bottom = max(bottom, y0 + it.b.h)
        self.bottom = bottom

    def make_blocks(self):
        """One block per chain device (its children), in chain order (left → right)."""
        blocks = []
        for ids in self.chain:
            for i in ids:
                if self.children.get(i):
                    items = [self.build_box(k) if self.children.get(k) else self.nodes[k] for k in self.children[i]]
                    blocks.append((self.nodes[i], Box(None, items, self.lab, self)))
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
        chain_ids = {i for ids in self.chain for i in ids}
        by_card = {}
        kvm_out = {}
        for c in self.cables:
            l = c["link"]
            a, b = c["a"], c["b"]
            if c["child"] is not None and c["child"].id not in chain_ids:
                par, ch = c["par"], c["child"]
                side_c = "W"                       # tree: every child (servers too) from its lane on the left
                c["ends"][par.id] = self.exit_point(par, c, "S")
                by_card.setdefault((ch.id, side_c), []).append(c)
            else:
                up, dn = (a, b) if (a.y + a.h / 2) <= (b.y + b.h / 2) else (b, a)
                if abs(a.y - b.y) < 1:                                # same row: both from below
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
            for i, c in enumerate(cs):
                c["ends"][kid] = (k.x + k.w, k.y + k.h / 2 + (i - (len(cs) - 1) / 2) * 18, "E")
        # spread entries on the receiving cards
        for (nid, side), cs in by_card.items():
            n = self.nodes[nid]
            other = {}
            for c in cs:
                o = c["a"] if c["b"] is n else c["b"]
                e = c["ends"].get(o.id)
                other[id(c)] = e if e else (o.x + o.w / 2, o.y + o.h, "S")
            if side == "W":
                cs.sort(key=lambda c: -self.lane_order(c))
                k = len(cs)
                mid = n.y + min(n.h / 2, 46)          # tall cards (servers): at the header, not the middle
                ys = [mid + (i - (k - 1) / 2) * 34 for i in range(k)]
                for c, yy in zip(cs, ys):
                    c["ends"][n.id] = (n.x, yy, "W")
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
        """Tree cables (parent → children in its block) as a comb that never crosses itself:
        cables sorted by where they leave the parent; each gets its own level under the parent,
        its own lane left of its column (rightmost port = innermost lane = top card) and enters its
        card from the left. Routed explicitly, then registered as obstacles for the A* router."""
        by_parent = {}
        for c in self.cables:
            if c.get("child") is None or c["link"].kind == "kvm":
                continue
            ch = c["child"]
            if not getattr(ch, "col", None) or c["ends"].get(ch.id, (0, 0, ""))[2] != "W":
                continue
            if self.layout_name == "flow" and c["par"].id in {i for ids in self.chain for i in ids}:
                continue                          # flow: blocks sit beside the chain, A* finds the way
            by_parent.setdefault(c["par"].id, []).append(c)
        for pid, cs in by_parent.items():
            par = self.nodes[pid]
            ex = {id(c): c["ends"][pid][0] for c in cs if c["ends"].get(pid)}
            cs = [c for c in cs if id(c) in ex]
            # lanes per column: rightmost exit = innermost lane
            cols = {}
            for c in cs:
                cols.setdefault(c["child"].col["items_x"], []).append(c)
            lane = {}
            for ix, ccs in cols.items():
                ccs.sort(key=lambda c: -ex[id(c)])
                for i, c in enumerate(ccs):
                    lane[id(c)] = ix - LABEL_GAP - LANE / 2 - i * LANE
            left = sorted([c for c in cs if lane[id(c)] <= ex[id(c)]], key=lambda c: ex[id(c)])
            right = sorted([c for c in cs if lane[id(c)] > ex[id(c)]], key=lambda c: -ex[id(c)])
            y0 = par.y + par.h + 24
            for k, c in enumerate(left + right):
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

    def panel_boxes(self):
        boxes = []
        y = 150
        for name, h in self.left:
            boxes.append((T.LEFT_X, y, T.LEFT_X + T.LEFT_W, y + h))
            y += h + 20
        for item, yy, h in self.right:
            boxes.append((T.RIGHT_X, yy, T.RIGHT_X + T.RIGHT_W, yy + h))
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
        else:
            self.layout_cluster()
        self._exits = {}
        self.assign_ends()
        self.spread_exits()
        bottom = self.bottom
        H = bottom + 40
        self.route_all(H + 400)
        bottom = max([bottom] + [p[1] for c in self.cables for p in c.get("pts", [])])
        # panels + frame
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
                P.cloud_services(S, lab, T.CX, T.RIGHT_X, yy, T.RIGHT_W, lines=self.layout_name != "flow")
            elif item == "forwards":
                P.forwards(S, lab, T.RIGHT_X, yy, T.RIGHT_W)
            else:
                P.PANELS[item["type"]](S, lab, item, T.RIGHT_X, yy, T.RIGHT_W)
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
