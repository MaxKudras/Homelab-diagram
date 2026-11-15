"""Channel cable router.

Between two rows of cards lies a horizontal *channel*. Every cable that crosses it comes in from
the top at x_in, runs horizontally on its own *track* and leaves downwards at x_out (or, for a
link between two cards of the same row, goes up again: a U-turn). The router

  1. orders the tracks so that as few cables as possible cross
     (pairwise crossing costs + insertion search = linear-ordering heuristic),
  2. never lets two vertical pieces lie on top of each other,
  3. packs tracks: cables whose horizontal pieces are far enough apart share a track,
  4. spaces tracks by the drawn line widths (a 10G trunk needs more room than a 100M line).

The result is a y for every cable, from which render.py builds the orthogonal path.
"""

GAP_X = 16          # horizontal clearance between two horizontal pieces sharing a track
CLEAR = 7           # free space between two neighbouring lines (edge to edge)


class Wire:
    """One cable inside one channel."""

    def __init__(self, key, verts, width):
        self.key = key
        self.verts = verts          # [(x, 'top'|'bottom')]
        self.width = width          # drawn line width
        xs = [x for x, _ in verts]
        self.lo, self.hi = min(xs), max(xs)
        self.y = None

    @property
    def straight(self):
        return self.hi - self.lo < 0.5


def _cost(a, b):
    """Crossings (and forbidden overlaps) if a's track lies above b's track."""
    c = 0
    for x, side in b.verts:                       # b's verticals that come down from the top pass a's track
        if side == "top" and a.lo < x < a.hi:
            c += 1
    for x, side in a.verts:                       # a's verticals that go down to the bottom pass b's track
        if side == "bottom" and b.lo < x < b.hi:
            c += 1
    for xa, sa in a.verts:                        # a vertical going down from a, one coming in to b at same x
        for xb, sb in b.verts:
            if sa == "bottom" and sb == "top" and abs(xa - xb) < a.width / 2 + b.width / 2 + CLEAR:
                c += 1000
    return c


def order(wires):
    """Order of the tracks from top to bottom with few crossings."""
    n = len(wires)
    if n < 2:
        return list(wires)
    C = [[_cost(a, b) if a is not b else 0 for b in wires] for a in wires]
    idx = {id(w): i for i, w in enumerate(wires)}
    # start: cables going right ordered by descending x_in, going left by ascending x_in (nesting)
    def start_key(w):
        tops = [x for x, s in w.verts if s == "top"]
        bots = [x for x, s in w.verts if s == "bottom"]
        xi = tops[0] if tops else w.lo
        xo = bots[0] if bots else w.hi
        return (-xi if xo >= xi else xi)
    seq = sorted(wires, key=start_key)
    seq = [idx[id(w)] for w in seq]

    def total(s):
        return sum(C[s[i]][s[j]] for i in range(n) for j in range(i + 1, n))

    best = total(seq)
    improved = True
    rounds = 0
    while improved and rounds < 50:
        improved = False
        rounds += 1
        for i in range(n):
            e = seq[i]
            rest = seq[:i] + seq[i + 1:]
            # cost of e at each position: above all after p, below all before p
            above = [C[e][o] for o in rest]
            below = [C[o][e] for o in rest]
            cur = sum(below[:i]) + sum(above[i:])
            bestpos, bestc = i, cur
            run = sum(above)                      # e at position 0
            if run < bestc:
                bestpos, bestc = 0, run
            for p in range(1, n):
                run += below[p - 1] - above[p - 1]
                if run < bestc - 1e-9:
                    bestpos, bestc = p, run
            if bestpos != i:
                seq = rest[:bestpos] + [e] + rest[bestpos:]
                improved = True
        nt = total(seq)
        if nt >= best and not improved:
            break
        best = min(best, nt)
    return [wires[i] for i in seq]


def assign(wires, top, min_first=20):
    """Give every non-straight wire a y (top + offset). Returns the y of the lowest track (or top)."""
    bent = [w for w in wires if not w.straight]
    seq = order(bent)
    # track packing: a wire must lie below every earlier wire whose span is close to its own
    track_of = {}
    tracks = []                                   # per track: max line width
    for i, w in enumerate(seq):
        t = 0
        for prev in seq[:i]:
            close = not (w.hi + GAP_X < prev.lo or prev.hi + GAP_X < w.lo)
            if close or _cost(prev, w) >= 1000:
                t = max(t, track_of[id(prev)] + 1)
        track_of[id(w)] = t
        while len(tracks) <= t:
            tracks.append(0)
        tracks[t] = max(tracks[t], w.width)
    ys, y = [], top + min_first
    for t, wd in enumerate(tracks):
        if t:
            y += tracks[t - 1] / 2 + wd / 2 + CLEAR + 4
        ys.append(y)
    for w in seq:
        w.y = ys[track_of[id(w)]]
    return (ys[-1] if ys else top), len(tracks)


def crossings(wires):
    """Number of crossings in a routed channel (for reports/tests)."""
    bent = [w for w in wires if w.y is not None]
    c = 0
    for a in bent:
        for b in bent:
            if a is not b and a.y < b.y:
                c += _cost(a, b) % 1000
    for s in wires:                               # straight wires cross every horizontal they pass
        if s.y is None:
            x = s.lo
            c += sum(1 for b in bent if b.lo < x < b.hi)
    return c
