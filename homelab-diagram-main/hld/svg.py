"""SVG primitives (same look as the original build.py) plus a registry for the QA checks.

Every text, opaque card and cable that is drawn is also recorded, so qa.py can find text on
text, text running out of its card and cables running through cards after the drawing is done.
"""
import base64
import pathlib

from . import theme as T
from .text import esc, measure

ICONS = pathlib.Path(__file__).resolve().parent.parent / "icons"


def rounded(pts, r):
    """Orthogonal polyline with rounded corners."""
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    if len(pts) == 2:
        return f"M{pts[0][0]:.1f},{pts[0][1]:.1f} L{pts[1][0]:.1f},{pts[1][1]:.1f}"
    d = f"M{pts[0][0]:.1f},{pts[0][1]:.1f}"
    for i in range(1, len(pts) - 1):
        (x0, y0), (x1, y1), (x2, y2) = pts[i - 1], pts[i], pts[i + 1]
        l1 = max(abs(x1 - x0), abs(y1 - y0))
        l2 = max(abs(x2 - x1), abs(y2 - y1))
        rr = min(r, l1 / 2, l2 / 2)
        ax = x1 - (x1 - x0) / l1 * rr if l1 else x1
        ay = y1 - (y1 - y0) / l1 * rr if l1 else y1
        bx = x1 + (x2 - x1) / l2 * rr if l2 else x1
        by = y1 + (y2 - y1) / l2 * rr if l2 else y1
        d += f" L{ax:.1f},{ay:.1f} Q{x1:.1f},{y1:.1f} {bx:.1f},{by:.1f}"
    d += f" L{pts[-1][0]:.1f},{pts[-1][1]:.1f}"
    return d


class SVG:
    def __init__(self, w=T.W):
        self.p = []
        self.w = w
        self._icon_cache = {}
        self.texts = []      # (x0, y0, x1, y1, text, tag)
        self.cards = []      # (x0, y0, x1, y1, name)  opaque boxes cables must not cross
        self.cables = []     # (points, name, allowed card names at the ends)
        self.tag = ""        # who is drawing right now (for QA messages)

    def add(self, s):
        self.p.append(s)

    # ---- registry
    def reg_text(self, x0, y0, x1, y1, s):
        self.texts.append((x0, y0, x1, y1, str(s), self.tag))

    def reg_card(self, x, y, w, h, name):
        self.cards.append((x, y, x + w, y + h, name))

    def reg_cable(self, pts, name, ends=()):
        self.cables.append((list(pts), name, tuple(ends)))

    # ---- primitives
    def rect(self, x, y, w, h, rx=10, fill=T.PANEL, stroke=T.BORDER, sw=1.2, op=1, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{op}"{d}/>')

    def text(self, x, y, s, size=14, fill=T.TEXT, weight=400, anchor="start", mono=False, ls=0, op=1,
             reg=True):
        fam = T.MONO if mono else T.SANS
        lsa = f' letter-spacing="{ls}"' if ls else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{fam}" font-size="{size}" fill="{fill}" '
                 f'font-weight="{weight}" text-anchor="{anchor}" opacity="{op}"{lsa}>{esc(s)}</text>')
        w = measure(s, size, weight, mono, ls)
        if reg and str(s).strip():
            x0 = x - (w / 2 if anchor == "middle" else w if anchor == "end" else 0)
            self.reg_text(x0, y - size * 0.74, x0 + w, y + size * 0.2, s)
        return w

    def icon(self, name, x, y, size):
        if name not in self._icon_cache:
            f = ICONS / f"{name}.svg"
            if not f.exists():
                raise SystemExit(f"Icon '{name}' fehlt – erst ausführen: python3 setup.py")
            self._icon_cache[name] = base64.b64encode(f.read_bytes()).decode()
        self.add(f'<image x="{x:.1f}" y="{y:.1f}" width="{size}" height="{size}" '
                 f'href="data:image/svg+xml;base64,{self._icon_cache[name]}"/>')

    def line(self, pts, color, sw=3, dash=None, r=10, op=1, cap="round"):
        self.add(f'<path d="{rounded(pts, r)}" fill="none" stroke="{color}" stroke-width="{sw}" '
                 f'stroke-linecap="{cap}" stroke-linejoin="round" opacity="{op}"'
                 + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")

    def trunk(self, pts, r=12, sw=7):
        """Tagged trunk: light cable with a dark core."""
        self.line(pts, T.TRUNK, sw=sw, r=r)
        self.line(pts, T.BG, sw=sw - 4.4, r=r)

    def arrow(self, pts, color=T.MUTED, sw=1.8, dash=None, r=8):
        """Line with an arrowhead at the last point."""
        self.line(pts, color, sw, dash=dash, r=r)
        (x0, y0), (x1, y1) = pts[-2], pts[-1]
        dx, dy = x1 - x0, y1 - y0
        ln = max(abs(dx), abs(dy)) or 1
        ux, uy = dx / ln, dy / ln
        a, b = 8, 4.5
        p1 = (x1 - ux * a - uy * b, y1 - uy * a + ux * b)
        p2 = (x1 - ux * a + uy * b, y1 - uy * a - ux * b)
        self.add(f'<path d="M{x1:.1f},{y1:.1f} L{p1[0]:.1f},{p1[1]:.1f} L{p2[0]:.1f},{p2[1]:.1f} Z" fill="{color}"/>')

    def pill_w(self, s, size=12, mono=False, pad=8, weight=600):
        return measure(s, size, weight, mono) + pad * 2

    def pill(self, x, y, s, color, size=12, fill=None, mono=False, anchor="start", h=None, pad=8, tcolor=None,
             weight=600):
        w = self.pill_w(s, size, mono, pad, weight)
        h = h or size + 10
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        self.rect(x, y, w, h, rx=h / 2, fill=fill or color + "22", stroke=color + "88", sw=1)
        self.text(x + w / 2, y + h / 2 + size * 0.36, s, size, tcolor or color, weight, "middle", mono, reg=False)
        self.reg_text(x, y, x + w, y + h, s)
        return w

    def label_w(self, s, size=12, mono=False):
        return measure(s, size, 500, mono) + 12

    def label(self, x, y, s, color=T.MUTED, size=12, anchor="middle", mono=False, bg=T.BG):
        """Text on a line, with a background knock-out."""
        w = self.label_w(s, size, mono)
        bx = x - w / 2 if anchor == "middle" else (x if anchor == "start" else x - w)
        self.rect(bx, y - size - 2, w, size + 9, rx=5, fill=bg, stroke=bg, sw=0)
        tag, self.tag = self.tag, "label"          # has its own knock-out: cables may pass behind
        self.text(bx + w / 2, y + 1, s, size, color, 500, "middle", mono)
        self.tag = tag
        return w

    def render(self, h):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{h:.0f}" '
                f'viewBox="0 0 {self.w} {h:.0f}">'
                f'<defs><pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">'
                f'<circle cx="1.5" cy="1.5" r="1.3" fill="{T.GRID}"/></pattern></defs>'
                f'<rect x="0" y="0" width="{self.w}" height="{h:.0f}" fill="{T.BG}"/>'
                f'<rect x="0" y="0" width="{self.w}" height="{h:.0f}" fill="url(#dots)"/>')
        return head + "".join(self.p) + "</svg>"
