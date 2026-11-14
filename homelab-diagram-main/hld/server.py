"""The big server card (like 'terra'): hardware list | featured guest cards | one zone per network
with chips in balanced columns. Any number of guests, groups and zones; height follows content."""
from . import theme as T
from .parts import (CG, chip, chip_h, chip_w, device_card, guest_card, guest_card_h, guest_card_w, hw_tile, hw_tile_w)
from .text import measure

GY = 92            # body starts below the header
HWW_MIN = 250
GW_MIN = 480
CW_MIN = 340
CGAP = 14


def vtag(lab, key):
    n = lab.net.get(key)
    if not n:
        return str(key)
    return f"{n.tag} · {n.name}" if n.tag.startswith("VLAN") else n.name


def _ip_txt(lab, g, inline):
    ip = g.ip or f".{g.id}"
    return lab.full_ip(g.net, ip) if inline else ip


def _partition(heights, k):
    """Split the list into ≤ k contiguous parts with the smallest possible maximum sum."""
    n = len(heights)
    k = max(1, min(k, n))
    pre = [0]
    for h in heights:
        pre.append(pre[-1] + h)
    INF = float("inf")
    best = [[INF] * (n + 1) for _ in range(k + 1)]
    cut = [[0] * (n + 1) for _ in range(k + 1)]
    best[0][0] = 0
    for j in range(1, k + 1):
        for i in range(1, n + 1):
            for m in range(j - 1, i):
                v = max(best[j - 1][m], pre[i] - pre[m])
                if v < best[j][i]:
                    best[j][i], cut[j][i] = v, m
    parts, i = [], n
    for j in range(k, 0, -1):
        m = cut[j][i]
        parts.append(list(range(m, i)))
        i = m
    return [p for p in reversed(parts) if p]


class ServerCard:
    def __init__(self, lab, d, inline_ips=False):
        self.lab, self.d, self.inline = lab, d, inline_ips
        self.featured = [g for g in d.guests if g.featured]
        rest = [g for g in d.guests if not g.featured]
        order = [n.key for n in lab.networks]
        keys = sorted({g.net for g in rest}, key=lambda k: order.index(k) if k in order else 99)
        self.zones = []
        for k in keys:
            grouped = {}
            for g in rest:
                if g.net == k:
                    grouped.setdefault(g.group or "", []).append(g)
            groups = list(grouped.items())
            self.zones.append({"key": k, "groups": groups, "note": (d.zones.get(k) or {}).get("note", "")})
        self.hww = max([HWW_MIN] + [hw_tile_w(h) for h in d.hw]) if d.hw else 0
        self.gw = max([GW_MIN] + [guest_card_w(g, vtag(lab, g.net)) for g in self.featured]) if self.featured else 0

    def min_w(self):
        zw = max([0] + [max([CW_MIN] + [chip_w(g, _ip_txt(self.lab, g, self.inline)) for _, gs in z["groups"] for g in gs])
                       + 32 for z in self.zones])
        return 40 + (self.hww + 20 if self.hww else 0) + (self.gw + 20 if self.gw else 0) + zw

    def best_w(self, max_h=820, max_w=2200):
        """Narrowest width at which the card is no taller than max_h (or max_w)."""
        w = self.min_w()
        while w < max_w and self.size(w) > max_h:
            w += 80
        return min(w, max_w)

    # ---- geometry
    def _zone_cols(self, z, zw):
        cwmin = max([CW_MIN] + [chip_w(g, _ip_txt(self.lab, g, self.inline)) for _, gs in z["groups"] for g in gs])
        ncol = max(1, int((zw - 32 + CGAP) // (cwmin + CGAP)))
        gh = [22 + sum(chip_h(g) + CG for g in gs) + 14 - (22 if not name else 0) for name, gs in z["groups"]]
        parts = _partition(gh, ncol)
        cw = (zw - 32 - CGAP * (ncol - 1)) / ncol
        colh = max(sum(gh[i] for i in p) for p in parts)
        return parts, cw, 56 + colh + 6

    def size(self, w):
        """Height for a given width."""
        self.w = w
        d = self.d
        hw_h = 22 + len(d.hw) * 64 if d.hw else 0
        fg_h = sum(guest_card_h(g) + 14 for g in self.featured) - 14 if self.featured else 0
        self.zx_off = 20 + (self.hww + 20 if self.hww else 0) + (self.gw + 20 if self.gw else 0)
        zw = w - 20 - self.zx_off
        self.zlay = [self._zone_cols(z, zw) for z in self.zones]
        z_h = sum(zh for _, _, zh in self.zlay) + 16 * (len(self.zones) - 1) if self.zones else 0
        self.zh = max(hw_h, fg_h, z_h, 60)
        self.h = GY + self.zh + 22 if (d.hw or d.guests) else 86
        return self.h

    def draw(self, S, x, y, color, stroke, sw=2, dash=None):
        lab, d = self.lab, self.d
        S.tag = d.name
        w, h = self.w, self.h
        device_card(S, x, y, w, h, d.icons, d, color, fill="#0f151e", stroke=stroke, sw=sw, dash=dash)
        hy0 = y + GY
        cx = x + 20
        if d.hw:
            S.text(cx + 2, hy0 + 12, "HARDWARE", 11.5, T.HWC, 700, ls=1.4)
            for i, hwi in enumerate(d.hw):
                hw_tile(S, cx, hy0 + 22 + i * 64, self.hww, hwi)
            cx += self.hww + 20
        if self.featured:
            gy = hy0
            for g in self.featured:
                gh = guest_card_h(g)
                guest_card(S, g, cx, gy, self.gw, gh, lab.color(g.net), vtag(lab, g.net))
                gy += gh + 14
            cx += self.gw + 20
        zx = cx
        zw = x + w - 20 - zx
        zy = hy0
        for z, (parts, cw, zh) in zip(self.zones, self.zlay):
            col = lab.color(z["key"])
            S.rect(zx, zy, zw, zh, rx=14, fill=col + "0d", stroke=col + "88", sw=1.5)
            pw = S.pill(zx + zw - 14, zy + 16, vtag(lab, z["key"]), col, 10.5, mono=True, h=19, pad=6, anchor="end")
            if z["note"]:                       # the note never runs into the VLAN pill
                from .text import fit_size
                S.text(zx + 18, zy + 31, z["note"], fit_size(z["note"], 12.5, zw - 32 - 16 - pw), T.MUTED, 400)
            for ci, p in enumerate(parts):
                xx, yy = zx + 16 + ci * (cw + CGAP), zy + 56
                for gi in p:
                    name, gs = z["groups"][gi]
                    if name:
                        S.text(xx + 2, yy + 12, name.upper(), 11.5, T.GT, 700, ls=1.4)
                        yy += 22
                    for g in gs:
                        yy += chip(S, g, xx, yy, cw, _ip_txt(lab, g, self.inline)) + CG
                    yy += 14
            zy += zh + 16
