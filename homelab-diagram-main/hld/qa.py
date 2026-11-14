"""Checks on the finished drawing: text on text, cables through cards.

Works on the registry the SVG class keeps while drawing. Returns a list of German messages;
render stops the build when there is any (use --no-qa to look at a broken picture anyway).
"""


def _overlap(a, b, tol=0.6):
    return (min(a[2], b[2]) - max(a[0], b[0]) > tol) and (min(a[3], b[3]) - max(a[1], b[1]) > tol)


def texts(S):
    """Text boxes that overlap each other (different texts)."""
    msgs = []
    T = S.texts
    cell = 120
    grid = {}
    for i, t in enumerate(T):
        for gx in range(int(t[0] // cell), int(t[2] // cell) + 1):
            for gy in range(int(t[1] // cell), int(t[3] // cell) + 1):
                grid.setdefault((gx, gy), []).append(i)
    seen = set()
    for ids in grid.values():
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)):
                i, j = ids[a], ids[b]
                if (i, j) in seen:
                    continue
                seen.add((i, j))
                if _overlap(T[i], T[j]):
                    msgs.append(f"Text überlappt: „{T[i][4]}“ ({T[i][5]}) und „{T[j][4]}“ ({T[j][5]}) "
                                f"bei x={T[i][0]:.0f}, y={T[i][1]:.0f}")
    return msgs


def cables(S):
    """Cable segments that run through a card they don't belong to."""
    msgs = []
    for pts, name, ends, *_ in S.cables:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = (min(x0, x1) - 0.5, min(y0, y1), max(x0, x1) + 0.5, max(y0, y1))
            for c in S.cards:
                if c[4] in ends:
                    continue
                inner = (c[0] + 2, c[1] + 2, c[2] - 2, c[3] - 2)
                if _overlap(seg, inner, 0):
                    msgs.append(f"Kabel {name} läuft durch „{c[4]}“ bei x={x0:.0f}, y={min(y0, y1):.0f}")
    return msgs


def text_on_cables(S):
    """Texts that a cable runs through (labels with their own knock-out are fine)."""
    msgs = []
    for pts, name, ends, *_ in S.cables:
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            seg = (min(x0, x1) - 1, min(y0, y1), max(x0, x1) + 1, max(y0, y1))
            for t in S.texts:
                if t[5] in ("cables", "label"):
                    continue
                if t[4] == "[jack]" and any(t[5] in (e, e + " jacks") for e in ends):
                    continue                       # a cable plugged into its own jack
                if _overlap(seg, t, 0.5):
                    msgs.append(f"Kabel {name} läuft durch Text „{t[4]}“ ({t[5]})")
    return msgs


def _segs(S):
    """[(horizontal?, fixed coordinate, lo, hi, width, cable index)] of every cable piece."""
    out = []
    for ci, (pts, name, ends, *w) in enumerate(S.cables):
        w = w[0] if w else 3
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if abs(y0 - y1) < 0.5 and abs(x0 - x1) > 0.5:
                out.append((True, y0, min(x0, x1), max(x0, x1), w, ci))
            elif abs(x0 - x1) < 0.5 and abs(y0 - y1) > 0.5:
                out.append((False, x0, min(y0, y1), max(y0, y1), w, ci))
    return out


def cable_overlap(S):
    """Two different cables running parallel closer than their line widths allow (= on top of
    each other or touching)."""
    msgs = []
    segs = _segs(S)
    for i in range(len(segs)):
        h1, c1, lo1, hi1, w1, k1 = segs[i]
        for j in range(i + 1, len(segs)):
            h2, c2, lo2, hi2, w2, k2 = segs[j]
            if k1 == k2 or h1 != h2:
                continue
            if abs(c1 - c2) < (w1 + w2) / 2 + 2 and min(hi1, hi2) - max(lo1, lo2) > 6:
                n1, n2 = S.cables[k1][1], S.cables[k2][1]
                msgs.append(f"Kabel liegen aufeinander: {n1} und {n2} bei {'y' if h1 else 'x'}={c1:.0f}")
    return msgs


def score(S, w, h):
    """Numbers that say how tidy a picture is (lower is better, except nothing)."""
    segs = _segs(S)
    cross = 0
    hs = [s for s in segs if s[0]]
    vs = [s for s in segs if not s[0]]
    for _, y, x0, x1, _, a in hs:
        for _, x, y0, y1, _, b in vs:
            if a != b and x0 + 1 < x < x1 - 1 and y0 + 1 < y < y1 - 1:
                cross += 1
    length = sum(s[3] - s[2] for s in segs)
    bends = sum(max(0, len(c[0]) - 2) for c in S.cables)
    longest = max([sum(abs(p[0] - q[0]) + abs(p[1] - q[1]) for p, q in zip(c[0], c[0][1:])) for c in S.cables]
                  or [0])
    return {"Kreuzungen": cross, "Kabellänge": round(length), "Knicke": bends, "längstes Kabel": round(longest),
            "Kabel": len(S.cables), "Größe": f"{round(w)}×{round(h)}"}


def run(S):
    return texts(S) + cables(S) + text_on_cables(S) + cable_overlap(S)
