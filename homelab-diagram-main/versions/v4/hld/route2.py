"""Area cable router: orthogonal paths around all cards on a fine grid (A*).

Used by the 2-D layouts (cluster, flow). Rules a path has to follow:
  * never through a card, a tab, a panel or a reserved label box (cards get a small margin)
  * parallel cables keep a minimum distance that depends on both line widths (no lines on top of
    each other, bundles come out evenly spaced)
  * crossing another cable is allowed only at a right angle and costs a lot
  * few bends: a bend costs like a few grid steps
  * a cable leaves and enters a card straight (a short stub in the side's direction)

Cables are routed one after the other (longest/most important first); every routed cable becomes
an obstacle for the next ones. Returns polylines in canvas coordinates.
"""
import heapq
import math

G = 8                       # grid size in px
BEND = 7                    # cost of a bend (in grid steps)
CROSS = 26                  # cost of crossing another cable (≈ 26 steps of detour)
NEAR = 0.6                  # extra step cost right next to a card (keeps lines off borders)
DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))          # E S W N
SIDE = {"E": 0, "S": 1, "W": 2, "N": 3}


class Router:
    def __init__(self, w, h):
        self.cw, self.ch = int(math.ceil(w / G)) + 2, int(math.ceil(h / G)) + 2
        n = self.cw * self.ch
        self.block = bytearray(n)       # 1 = card / reserved: nothing may pass
        self.near = bytearray(n)        # 1 = next to a card
        self.line_h = bytearray(n)      # a horizontal cable runs through this cell
        self.line_v = bytearray(n)
        self.band_h = bytearray(n)      # too close to a horizontal cable for another horizontal one
        self.band_v = bytearray(n)

    # ---- grid helpers
    def idx(self, i, j):
        return j * self.cw + i

    def cell(self, x, y):
        return (min(self.cw - 1, max(0, int(round(x / G)))), min(self.ch - 1, max(0, int(round(y / G)))))

    def block_rect(self, x0, y0, x1, y1, margin=G):
        i0, j0 = self.cell(x0 - margin, y0 - margin)
        i1, j1 = self.cell(x1 + margin, y1 + margin)
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                self.block[self.idx(i, j)] = 1
        n0, m0 = self.cell(x0 - margin - 2 * G, y0 - margin - 2 * G)
        n1, m1 = self.cell(x1 + margin + 2 * G, y1 + margin + 2 * G)
        for j in range(max(0, m0), min(self.ch, m1 + 1)):
            for i in range(max(0, n0), min(self.cw, n1 + 1)):
                self.near[self.idx(i, j)] = 1

    # ---- routing
    def route(self, a, a_side, b, b_side, width, stub=3):
        """Path from point a (leaving towards a_side) to point b (entering from b_side).
        Returns a list of points or None."""
        da, db = SIDE[a_side], SIDE[b_side]
        sa = self._stub(a, da, stub)
        sb = self._stub(b, db, stub)
        free = set(sa) | set(sb)                     # the stubs may cross the card margins
        start, goal = sa[-1], sb[-1]
        r_band = self._band(width)
        path = self._astar(start, da, goal, (db + 2) % 4, r_band, free, a, b)
        if path is None:
            return None
        cells = sa + path[1:-1] + list(reversed(sb))
        self._commit(cells, width)
        return self._points(a, b, cells, da, db)

    def commit_path(self, pts, width):
        """Register a path that was routed elsewhere (e.g. the comb) as an obstacle."""
        cells = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            a, b = self.cell(x0, y0), self.cell(x1, y1)
            if a[1] == b[1]:
                step = 1 if b[0] >= a[0] else -1
                cells += [(i, a[1]) for i in range(a[0], b[0] + step, step)]
            else:
                step = 1 if b[1] >= a[1] else -1
                cells += [(a[0], j) for j in range(a[1], b[1] + step, step)]
        clean = [c for i, c in enumerate(cells) if i == 0 or c != cells[i - 1]]
        self._commit(clean, width)

    def _band(self, width):
        """Cells on each side where no parallel cable may run: thin lines 16 px apart, trunks 24 px."""
        return max(1, int(math.ceil((width / 2 + 6) / G)))

    def _stub(self, p, d, n):
        i, j = self.cell(*p)
        dx, dy = DIRS[d]
        return [(i + dx * k, j + dy * k) for k in range(0, n + 1)]

    def _astar(self, s, sd, g, gd, band, free, pa, pb):
        """A* over (cell, direction). sd = direction when leaving s, gd = direction when arriving at g."""
        cw, ch = self.cw, self.ch
        # search window: endpoints' box + margin, grown if nothing is found
        for grow in (60, 140, 10 ** 6):
            i0 = max(0, min(s[0], g[0]) - grow)
            i1 = min(cw - 1, max(s[0], g[0]) + grow)
            j0 = max(0, min(s[1], g[1]) - grow)
            j1 = min(ch - 1, max(s[1], g[1]) + grow)
            res = self._search(s, sd, g, gd, band, free, (i0, j0, i1, j1))
            if res:
                return res
        return None

    def _search(self, s, sd, g, gd, band, free, box):
        i0, j0, i1, j1 = box
        cw = self.cw
        block, near = self.block, self.near
        lh, lv, bh, bv = self.line_h, self.line_v, self.band_h, self.band_v
        gi, gj = g
        start = (s[0], s[1], sd)
        dist = {start: 0.0}
        prev = {}
        h0 = abs(s[0] - gi) + abs(s[1] - gj)
        heap = [(h0, 0.0, start)]
        while heap:
            f, c, st = heapq.heappop(heap)
            if c > dist.get(st, 1e18):
                continue
            i, j, d = st
            if (i, j) == (gi, gj):
                if d == gd:
                    out = [(i, j)]
                    while st in prev:
                        st = prev[st]
                        out.append((st[0], st[1]))
                    return list(reversed(out))
                continue
            for nd in (d, (d + 1) % 4, (d + 3) % 4):
                dx, dy = DIRS[nd]
                ni, nj = i + dx, j + dy
                if ni < i0 or ni > i1 or nj < j0 or nj > j1:
                    continue
                k = nj * cw + ni
                cell = (ni, nj)
                if block[k] and cell not in free:
                    continue
                horiz = nd % 2 == 0
                # parallel to an existing cable and too close → not allowed
                if horiz and bh[k] and cell not in free:
                    continue
                if not horiz and bv[k] and cell not in free:
                    continue
                cost = 1.0
                if nd != d:
                    cost += BEND
                    # turning on top of another cable's line is not allowed (would run along it)
                    if lh[i + j * cw] or lv[i + j * cw]:
                        continue
                if (horiz and lv[k]) or (not horiz and lh[k]):
                    cost += CROSS
                if near[k]:
                    cost += NEAR
                nc = c + cost
                ns = (ni, nj, nd)
                if nc < dist.get(ns, 1e18):
                    dist[ns] = nc
                    prev[ns] = st
                    hh = abs(ni - gi) + abs(nj - gj)
                    if (ni != gi and nj != gj) or nd != gd:
                        hh += BEND * 0.5
                    heapq.heappush(heap, (nc + hh, nc, ns))
        return None

    def _commit(self, cells, width):
        """Mark the routed cable: its line cells and the band where parallel cables may not run."""
        r = self._band(width)
        cw, ch = self.cw, self.ch
        for (a, b) in zip(cells, cells[1:]):
            horiz = a[1] == b[1]
            for (i, j) in (a, b):
                k = j * cw + i
                if horiz:
                    self.line_h[k] = 1
                    for t in range(-r, r + 1):
                        jj = j + t
                        if 0 <= jj < ch:
                            self.band_h[jj * cw + i] = 1
                else:
                    self.line_v[k] = 1
                    for t in range(-r, r + 1):
                        ii = i + t
                        if 0 <= ii < cw:
                            self.band_v[j * cw + ii] = 1

    def _points(self, a, b, cells, da, db):
        """Grid cells → corner points; the first and last straight runs snap to the exact end points."""
        pts = [(i * G, j * G) for i, j in cells]
        corners = [pts[0]]
        for p, q, r in zip(pts, pts[1:], pts[2:]):
            if (p[0] == q[0]) != (q[0] == r[0]):
                corners.append(q)
        corners.append(pts[-1])
        corners = [list(c) for c in corners]
        # exact start: the first run is in direction da → keep the cross coordinate of point a
        k = 0 if da % 2 else 1           # vertical start (N/S) → x is fixed; horizontal → y fixed
        corners[0][k] = a[k]
        if len(corners) > 1:
            corners[1][k] = a[k]
        corners[0][1 - k] = a[1 - k]
        k2 = 0 if db % 2 else 1
        corners[-1][k2] = b[k2]
        if len(corners) > 1:
            corners[-2][k2] = b[k2]
        corners[-1][1 - k2] = b[1 - k2]
        out = []
        for c in corners:
            c = (round(c[0], 1), round(c[1], 1))
            if not out or c != out[-1]:
                out.append(c)
        # a straight run whose two ends snapped to different lines gets a small S-jog in the middle
        fixed = [out[0]]
        for q in out[1:]:
            pq = fixed[-1]
            if abs(pq[0] - q[0]) > 0.01 and abs(pq[1] - q[1]) > 0.01:
                if da % 2:                       # vertical travel: jog halfway down
                    my = round((pq[1] + q[1]) / 2, 1)
                    fixed += [(pq[0], my), (q[0], my)]
                else:
                    mx = round((pq[0] + q[0]) / 2, 1)
                    fixed += [(mx, pq[1]), (mx, q[1])]
            fixed.append(q)
        out = fixed
        # drop zero-length / collinear leftovers
        clean = [out[0]]
        for p in out[1:]:
            if len(clean) >= 2:
                a_, b_ = clean[-2], clean[-1]
                if (abs(a_[0] - b_[0]) < 0.01 and abs(b_[0] - p[0]) < 0.01) or \
                   (abs(a_[1] - b_[1]) < 0.01 and abs(b_[1] - p[1]) < 0.01):
                    clean[-1] = p
                    continue
            clean.append(p)
        return clean
