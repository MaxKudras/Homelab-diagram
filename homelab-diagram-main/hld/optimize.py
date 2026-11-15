"""Layout optimizer for the cluster view: shortest cables, compact picture.

Every block (the tree under a switch/AP) can split its children into columns in many ways. The
optimizer tries them and keeps the arrangement with the lowest *cost*:

    cost = total cable length (estimated, without routing)
         + 2.0 × picture height + 0.8 × picture width
         + a big penalty above the preferred width (render2.MAX_W)

Cable length of a tree cable = horizontal way from its port to the lane of its column + the way
down to the card. That is exactly what the comb draws later, so the estimate is close.

Search: start with balanced columns, then coordinate descent over all blocks (number of columns,
every column boundary one step left/right), a few rounds until nothing improves.
"""
from . import theme as T

ROUNDS = 4


def _sizes_balanced(heights, k):
    from .server import _partition
    return [len(p) for p in _partition(heights, k)]


def _neighbours(sizes):
    """Column-size variants one step away: move a boundary, split a column, merge two."""
    out = []
    for i in range(len(sizes) - 1):
        for d in (-1, 1):
            s = list(sizes)
            s[i] += d
            s[i + 1] -= d
            if min(s) >= 1:
                out.append(s)
    for i, n in enumerate(sizes):                 # split one column in two
        for a in range(1, n):
            out.append(sizes[:i] + [a, n - a] + sizes[i + 1:])
    for i in range(len(sizes) - 1):               # merge two neighbours
        out.append(sizes[:i] + [sizes[i] + sizes[i + 1]] + sizes[i + 2:])
    return out


def _candidates(heights, cur):
    """Parameter sets for one box: every left/right split × 1..4 balanced columns per side,
    plus small changes of the current choice."""
    n = len(heights)
    out = []
    for nl in range(0, n + 1):
        hl, hr = heights[:nl], heights[nl:]
        for kl in (range(1, min(len(hl), 4) + 1) if hl else [0]):
            for kr in (range(1, min(len(hr), 4) + 1) if hr else [0]):
                out.append({"nL": nl, "L": _sizes_balanced(hl, kl) if hl else [],
                            "R": _sizes_balanced(hr, kr) if hr else []})
    for side in ("L", "R"):
        for sz in _neighbours(cur[side]):
            out.append(dict(cur, **{side: sz}))
    return out


def estimate(R, blocks):
    """Place everything and estimate the cost of the result (no routing)."""
    from .render2 import LABEL_GAP, MAX_W
    bottom, right = R.place_blocks(blocks)
    length = 0.0
    for c in R.cables:
        ch, par = c.get("child"), c.get("par")
        if ch is not None and getattr(ch, "col", None) and ch.x is not None and par.x is not None:
            p = c["link"].port_of(par.id)
            ex = par.x + par.port_x[p] if p in par.port_x else par.x + par.w / 2
            lane = ch.col["items_x"] - LABEL_GAP if ch.col["side"] == "W" else ch.col["edge_x"] + LABEL_GAP
            ey = ch.y + min(ch.h / 2, 46)
            length += abs(ex - lane) + abs(ey - (par.y + par.h)) + LABEL_GAP
        elif c["a"].x is not None and c["b"].x is not None:
            a, b = c["a"], c["b"]
            length += abs((a.x + a.w / 2) - (b.x + b.w / 2)) + abs((a.y + a.h / 2) - (b.y + b.h / 2))
    width = right + T.MARGIN
    over = max(0, width - MAX_W)
    return length + 2.0 * bottom + 0.8 * width + 40 * over


def boxes_of(blocks):
    """All boxes (keys + item counts + item heights), inner ones first."""
    from .render2 import Box
    out = []

    def walk(b):
        for it in b.items:
            if isinstance(it, Box):
                walk(it)
        if b.items:
            out.append((b.key, [it.h for it in b.items]))
    for _, b in blocks:
        walk(b)
    return out


def optimize(R):
    """Choose split and columns of every block; returns the blocks (placed by the caller)."""
    R.box_params = {}
    blocks = R.make_blocks()                     # heuristic start (writes default params)
    boxes = boxes_of(blocks)
    best = estimate(R, blocks)
    for _ in range(ROUNDS):
        improved = False
        for key, heights in boxes:
            cur = R.box_params[key]
            for prm in _candidates(heights, cur):
                if prm == cur:
                    continue
                R.box_params[key] = prm
                cost = estimate(R, R.make_blocks())
                if cost < best - 1:
                    best, cur, improved = cost, prm, True
                else:
                    R.box_params[key] = cur
            R.box_params[key] = cur
        if not improved:
            break
    R.opt_cost = best
    return R.make_blocks()
