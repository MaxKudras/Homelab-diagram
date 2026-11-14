"""Panels around the network drawing: header, internet + remote + cloud, networks table, legend,
port forwards, flow panels (media pipeline). Each returns its height and can be measured first."""
import math

from . import theme as T
from .parts import ticks
from .text import fqdn, measure


# ---------------------------------------------------------------- header
def header(S, title, watermark, date):
    S.tag = "header"
    S.text(40, 86, title, 46, T.TEXT, 700, ls=-0.5)
    S.text(T.W - 40, 74, watermark, 21, T.REDDIT, 700, "end")
    S.text(T.W - 40, 100, date, 16, T.MUTED, 400, "end")


# ---------------------------------------------------------------- internet cloud
BLOBS = [(-95, 18, 42), (-45, -8, 56), (25, -18, 62), (90, 6, 48), (130, 26, 30), (-130, 30, 28)]
CLOUD_Y = 172


def cloud_edge(cx, cy, y, side=1):
    """x of the cloud's outline at height y (side=1 right, -1 left)."""
    best = None
    for dx, dy, r in BLOBS:
        if abs(y - (cy + dy)) <= r:
            x = cx + dx + side * math.sqrt(r * r - (y - cy - dy) ** 2)
            best = x if best is None else (max(best, x) if side > 0 else min(best, x))
    if cy + 12 <= y <= cy + 58:
        x = cx + side * 150
        best = x if best is None else (max(best, x) if side > 0 else min(best, x))
    return best


def internet(S, lab, cx, cy=CLOUD_Y):
    S.tag = "internet"
    for dx, dy, r in BLOBS:
        S.add(f'<circle cx="{cx+dx}" cy="{cy+dy}" r="{r+2.5}" fill="#3a4a60"/>')
    S.add(f'<rect x="{cx-150}" y="{cy+12}" width="300" height="46" rx="23" fill="#3a4a60"/>')
    for dx, dy, r in BLOBS:
        S.add(f'<circle cx="{cx+dx}" cy="{cy+dy}" r="{r}" fill="#1a2433"/>')
    S.add(f'<rect x="{cx-147.5}" y="{cy+14.5}" width="295" height="41" rx="20.5" fill="#1a2433"/>')
    inet = lab.internet
    S.text(cx, cy + 14, inet.get("label", "Internet"), 26, T.TEXT, 600, "middle")
    if inet.get("sub"):
        S.text(cx, cy + 40, inet["sub"], 13, T.MUTED, 400, "middle")
    S.reg_card(cx - 150, cy - 80, 300, 138, "internet")


def remote(S, lab, cx, cy=CLOUD_Y):
    """Remote-access clients left of the cloud, dotted line into the cloud."""
    S.tag = "remote"
    x = cx - 500
    for i, r in enumerate(lab.remote):
        y = 150 + i * 96
        col = lab.color(r.get("net"))
        ly = y + 42
        edge = cloud_edge(cx, cy, ly, -1) or (cx - 150)
        S.line([(x + 300, ly), (edge + 50, ly)], col, 1.8, dash="2 5", r=0)
        S.rect(x, y, 300, 84, rx=12, fill=T.PANEL, stroke=col + "aa", sw=1.6)
        S.reg_card(x, y, 300, 84, r["name"])
        S.icon(r.get("icon", "wireguard"), x + 16, y + 22, 38)
        S.text(x + 66, y + 38, r["name"], 18, T.TEXT, 600)
        S.text(x + 66, y + 60, r.get("note", ""), 13, T.MUTED, 400)


def cloud_services(S, lab, cx, x, y, w, cy=CLOUD_Y):
    """Cloud services (right column top) with dotted lines from the cloud. Returns height."""
    S.tag = "cloud services"
    items = lab.cloud
    for i, cs in enumerate(items):
        yy = y + i * 54
        ly = yy + 22
        edge = cloud_edge(cx, cy, ly, 1)
        if edge is not None:
            S.line([(edge - 20, ly), (x, ly)], T.FAINT, 1.6, dash="2 5", r=0)
        else:                                  # below the cloud: one shared dotted bus
            S.line([(cx + 150, cy + 35), (x - 24, cy + 35), (x - 24, ly), (x, ly)], T.FAINT, 1.6, dash="2 5", r=6)
        S.rect(x, yy, w, 44, rx=10, fill=T.PANEL2, stroke=T.BORDER)
        S.reg_card(x, yy, w, 44, cs["name"])
        S.icon(cs["icon"], x + 10, yy + 9, 26)
        S.text(x + 46, yy + 20, cs["name"], 14, T.TEXT, 600)
        S.text(x + 46, yy + 36, cs.get("note", ""), 12, T.MUTED, 400)
    return len(items) * 54 - 10 if items else 0


# ---------------------------------------------------------------- networks table
def networks_h(lab):
    return 70 + len(lab.networks) * 60


def networks(S, lab, x, y, w):
    S.tag = "networks"
    h = networks_h(lab)
    S.rect(x, y, w, h, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.reg_card(x, y, w, h, "Networks")
    S.text(x + 20, y + 36, "Networks", 19, T.TEXT, 600)
    for i, v in enumerate(lab.networks):
        yy = y + 56 + i * 60
        S.rect(x + 14, yy, w - 28, 52, rx=9, fill=T.CHIP, stroke=v.color + "55", sw=1)
        S.add(f'<rect x="{x+14}" y="{yy}" width="6" height="52" rx="3" fill="{v.color}"/>')
        S.text(x + 32, yy + 22, v.tag, 13, v.color, 600, mono=True)
        S.text(x + 128, yy + 22, v.name, 15.5, T.TEXT, 600)
        S.text(x + w - 28, yy + 22, v.subnet, 13.5, T.TEXT, 500, "end", mono=True)
        S.text(x + 32, yy + 42, v.note, 12, T.MUTED, 400)
    return h


# ---------------------------------------------------------------- legend
LR = 27


def legend_rows(feat):
    order = ["trunk", "access", "wan", "kvm", "wifi", "net", "speed", "public", "internal", "lan", "ticks",
             "share", "planned"]
    return [k for k in order if k in feat]


def legend_h(feat):
    return 52 + len(legend_rows(feat)) * LR + 8


def legend(S, lab, feat, x, y, w):
    S.tag = "legend"
    rows = legend_rows(feat)
    h = legend_h(feat)
    S.rect(x, y, w, h, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.reg_card(x, y, w, h, "Legend")
    S.text(x + 20, y + 36, "Legend", 19, T.TEXT, 600)
    SX, TX = x + 22, x + 162
    acc = feat.get("access") or ["10"]
    first = acc[0]
    for i, k in enumerate(rows):
        yy = y + 66 + i * LR
        t = None
        if k == "trunk":
            S.trunk([(SX, yy), (SX + 50, yy)], sw=T.trunk_w("2.5G"), r=0); t = "802.1Q trunk (tagged VLANs)"
        elif k == "access":
            for jj, c in enumerate(acc[:4]):
                S.line([(SX + jj * 13, yy), (SX + jj * 13 + 9, yy)], lab.color(c), 3.6, r=0, cap="butt")
            t = "access port, colored by VLAN"
        elif k == "wan":
            S.line([(SX, yy), (SX + 50, yy)], lab.color(feat["wan"]), 3, r=0)
            t = f"WAN ({lab.net[feat['wan']].tag} network)" if feat["wan"] in lab.net else "WAN"
        elif k == "kvm":
            S.line([(SX, yy), (SX + 50, yy)], T.MUTED, 2, dash="5 5", r=0, cap="butt"); t = "KVM console (HDMI + USB)"
        elif k == "wifi":
            S.line([(SX, yy), (SX + 50, yy)], lab.color(first), 2, dash="1 4", r=0); t = "Wi-Fi client"
        elif k == "net":
            S.line([(SX, yy), (SX + 50, yy)], T.MUTED, 1.8, dash="2 5", r=0); t = "over the internet (not a cable)"
        elif k == "speed":
            S.text(SX, yy + 4.5, "line width = speed", 12.5, T.MUTED, 400)
            x0 = TX
            for lbl in feat["speed"]:
                S.line([(x0, yy), (x0 + 26, yy)], lab.color(first), T.speed_w(lbl), r=0, cap="butt")
                S.text(x0 + 32, yy + 4.5, lbl, 12, T.TEXT, 500, mono=True)
                x0 += 32 + measure(lbl, 12, 500, True) + 20
        elif k == "public":
            S.text(SX, yy + 4.5, fqdn("app"), 12, T.LINK, 500, mono=True); t = "public via reverse proxy"
        elif k == "internal":
            S.text(SX, yy + 4.5, "name.internal", 12, lab.color(first), 400, mono=True, op=0.78)
            t = "local DNS, no reverse proxy"
        elif k == "lan":
            S.pill(SX, yy - 9, "LAN", T.MUTED, 10, mono=True, pad=5); t = "only from LAN / VPN"
        elif k == "ticks":
            for jj, c in enumerate(acc[:3]):
                S.add(f'<rect x="{SX + jj*7}" y="{yy-5 if jj == 0 else yy-2}" width="5" '
                      f'height="{8 if jj == 0 else 5}" rx="1" fill="{lab.color(c)}"/>')
            t = "port VLANs (tall = untagged)"
        elif k == "share":
            S.rect(SX, yy - 8, 22, 15, rx=3, fill=lab.color(first) + "16", stroke=lab.color(first) + "cc", sw=1.2,
                   dash="4 3")
            t = "NAS share, bind-mounted"
        elif k == "planned":
            S.rect(SX, yy - 8, 40, 16, rx=4, fill="none", stroke=T.MUTED, sw=1.4, dash="5 4"); t = "planned, not built yet"
        if t:
            S.text(TX, yy + 4.5, t, 13, T.MUTED, 400)
    return h


# ---------------------------------------------------------------- port forwards
def forwards_h(lab):
    return 84 + len(lab.port_forwards) * 44 if lab.port_forwards else 0


def forwards(S, lab, x, y, w):
    pf = lab.port_forwards
    if not pf:
        return 0
    S.tag = "port forwards"
    h = forwards_h(lab)
    S.rect(x, y, w, h, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.reg_card(x, y, w, h, "Open to the internet")
    S.text(x + 20, y + 34, "Open to the internet", 19, T.TEXT, 600)
    S.text(x + 20, y + 56, "port forwards on the firewall · blocklist + CrowdSec drop bad IPs first", 12.5, T.MUTED, 400)
    for i, r in enumerate(pf):
        yy = y + 72 + i * 44
        S.rect(x + 14, yy, w - 28, 38, rx=8, fill=T.CHIP, stroke=T.BORDER, sw=1)
        S.text(x + 26, yy + 24, r["port"], 13, T.TEXT, 600, mono=True)
        S.text(x + 236, yy + 17, r["to"], 13.5, T.TEXT, 600)
        S.text(x + 236, yy + 32, r["what"], 11.5, T.MUTED, 400)
        px = x + w - 24
        for pr in reversed(r["proto"].split("/")):
            px -= S.pill(px, yy + 9, pr, T.PROTO.get(pr, T.MUTED), 11, mono=True, anchor="end", pad=7, h=20) + 6
    return h


# ---------------------------------------------------------------- media pipeline (flow panel)
def media_pipeline(S, lab, p, PX, PY, PW, draw=True):
    """The *arr explainer: request → *arr → torrent → shares → library. Returns height."""
    N = p["nodes"]
    G_ = 42
    NW = (PW - 28 - 2 * G_) / 3
    NH = 68
    STACK_H = 3 * 46 + 2 * 6
    RA = PY + 98
    RS = RA + (STACK_H - NH) / 2
    RB = RA + STACK_H + 52
    RC = RB + NH + 40
    SH_ = 64
    SW_ = (PW - 28 - G_) / 2
    PH = RC + SH_ + 16 - PY
    if not draw:
        return PH
    S.tag = "media pipeline"
    CARD_BG = T.PANEL
    col = lab.color("10")
    S.rect(PX, PY, PW, PH, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.reg_card(PX, PY, PW, PH, "Media pipeline")
    S.text(PX + 20, PY + 32, p.get("title", "Media pipeline"), 17, T.TEXT, 600)
    S.text(PX + 20, PY + 52, p.get("sub", "how a request ends up in Jellyfin"), 12.5, T.MUTED, 400)

    def node_x(c):
        return PX + 14 + c * (NW + G_)

    def node(n, c, y):
        x = node_x(c)
        S.rect(x, y, NW, NH, rx=9, fill=T.CHIP, stroke=T.BORDER, sw=1)
        S.icon(n["icon"], x + 8, y + 9, 22)
        S.text(x + 35, y + 26, n["name"], 12.5, T.TEXT, 600)
        S.text(x + NW - 10, y + 26, f"CT {n['ct']}", 10.5, T.FAINT, 500, "end", mono=True)
        S.text(x + NW - 10, y + 46, n["ip"], 10.5, T.FAINT, 500, "end", mono=True)
        S.text(x + 10, y + 46, n["sub"], 11, T.MUTED, 400)
        S.text(x + 10, y + 62, fqdn(n["host"]), 10, T.LINK, 500, mono=True)

    def arr_node(a, x, y):
        S.rect(x, y, NW, 46, rx=8, fill=T.CHIP, stroke=T.BORDER, sw=1)
        S.icon(a["icon"], x + 10, y + 7, 20)
        S.text(x + 36, y + 22, a["name"], 13.5, T.TEXT, 600)
        S.text(x + NW - 10, y + 22, a["ip"], 12, T.FAINT, 500, "end", mono=True)
        S.text(x + 10, y + 38, fqdn(a["host"]), 10, T.LINK, 500, mono=True)

    def share(sh, x, y):
        S.rect(x, y, SW_, SH_, rx=9, fill=col + "16", stroke=col + "cc", sw=1.3, dash="5 4")
        S.icon("truenas", x + 10, y + 10, 22)
        S.text(x + 40, y + 26, sh["name"], 13.5, T.TEXT, 600)
        S.text(x + SW_ - 10, y + 26, "TrueNAS SMB", 10.5, col, 600, "end", mono=True)
        S.text(x + 10, y + 44, sh["pool"], 11, T.MUTED, 400)
        S.text(x + 10, y + 58, "bind mount: SMB ↔ terra ↔ CT", 10, col, 500, mono=True)

    node(N["seerr"], 0, RS)
    node(N["prowlarr"], 2, RS)
    S.rect(node_x(1) - 6, RA - 6, NW + 12, STACK_H + 12, rx=12, fill="none", stroke="#3a475a", sw=1.2, dash="3 3")
    lx0 = node_x(1) + 2
    S.rect(lx0, RA - 17, 58, 22, rx=5, fill=CARD_BG, stroke=CARD_BG, sw=0)
    S.text(lx0 + 6, RA - 1, "CT 154", 11.5, "#c3cdd9", 600, mono=True)
    for k, a in enumerate(p["arrs"]):
        arr_node(a, node_x(1), RA + k * 52)
    node(N["jellyfin"], 0, RB)
    node(N["qbit"], 2, RB)
    mx, tx_ = PX + 14, PX + 14 + SW_ + G_
    share(p["shares"]["media"], mx, RC)
    share(p["shares"]["torrents"], tx_, RC)
    midS = RS + NH / 2
    S.arrow([(node_x(0) + NW + 4, midS), (node_x(1) - 10, midS)])
    S.label(node_x(0) + NW + G_ / 2 - 3, midS - 8, "request", T.MUTED, 11, bg=CARD_BG)
    S.arrow([(node_x(2) - 4, midS), (node_x(1) + NW + 10, midS)])
    S.label(node_x(1) + NW + G_ / 2 + 3, midS - 8, "indexers", T.MUTED, 11, bg=CARD_BG)
    qx = node_x(2) + NW / 2
    yr = RA + 2 * 52 + 23
    S.arrow([(node_x(1) + NW + 8, yr), (qx, yr), (qx, RB - 5)])
    S.label((node_x(1) + NW + qx) / 2 + 4, yr - 8, "torrent", T.MUTED, 11, bg=CARD_BG)
    ax1, ax2 = node_x(1) + 24, node_x(1) + NW - 24
    S.arrow([(ax1, RA + STACK_H + 7), (ax1, RC - 5)])
    S.text(ax1 + 8, RB + 30, "copy +", 11, T.MUTED, 500)
    S.text(ax1 + 8, RB + 44, "rename", 11, T.MUTED, 500)
    S.arrow([(ax2, RC - 2), (ax2, RA + STACK_H + 10)])
    S.text(ax2 + 8, RB + 30, "pick up", 11, T.MUTED, 500)
    S.text(ax2 + 8, RB + 44, "when done", 11, T.MUTED, 500)
    jx = node_x(0) + NW / 2
    S.arrow([(jx, RB - 2), (jx, RS + NH + 5)], dash="4 4")
    S.text(jx + 10, (RS + NH + RB) / 2 + 4, "available", 11, T.MUTED, 500)
    S.arrow([(qx, RB + NH + 2), (qx, RC - 5)])
    S.text(qx + 10, (RB + NH + RC) / 2 + 4, "download", 11, T.MUTED, 500)
    S.arrow([(jx, RC - 2), (jx, RB + NH + 5)])
    S.text(jx + 10, (RB + NH + RC) / 2 + 4, "library", 11, T.MUTED, 500)
    return PH


# ---------------------------------------------------------------- generic flow panel
def flow(S, lab, p, PX, PY, PW, draw=True):
    """Simple explainer: nodes in a grid (row, col), arrows with labels between them.
    p = {title, sub, cols: 3, nodes: [{id, name, sub, icon, row, col}], edges: [{a, b, label}]}"""
    cols = p.get("cols", 3)
    G_ = 42
    NW = (PW - 28 - (cols - 1) * G_) / cols
    NH = 58
    rows = max((n.get("row", 0) for n in p["nodes"]), default=0) + 1
    RG = 52
    PH = 74 + rows * NH + (rows - 1) * RG + 18
    if not draw:
        return PH
    S.tag = "flow " + p.get("title", "")
    S.rect(PX, PY, PW, PH, rx=14, fill=T.PANEL, stroke=T.BORDER, sw=1.4)
    S.reg_card(PX, PY, PW, PH, p.get("title", "flow"))
    S.text(PX + 20, PY + 32, p.get("title", ""), 17, T.TEXT, 600)
    S.text(PX + 20, PY + 52, p.get("sub", ""), 12.5, T.MUTED, 400)
    pos = {}
    for n in p["nodes"]:
        x = PX + 14 + n.get("col", 0) * (NW + G_)
        y = PY + 74 + n.get("row", 0) * (NH + RG)
        pos[n["id"]] = (x, y)
        S.rect(x, y, NW, NH, rx=9, fill=T.CHIP, stroke=T.BORDER, sw=1)
        if n.get("icon"):
            S.icon(n["icon"], x + 8, y + 9, 22)
        S.text(x + (35 if n.get("icon") else 10), y + 26, n["name"], 12.5, T.TEXT, 600)
        S.text(x + 10, y + 46, n.get("sub", ""), 11, T.MUTED, 400)
    for e in p.get("edges", []):
        (ax, ay), (bx, by) = pos[e["a"]], pos[e["b"]]
        if abs(ay - by) < 1:                     # same row: horizontal arrow
            y = ay + NH / 2
            x0, x1 = (ax + NW + 4, bx - 6) if bx > ax else (ax - 4, bx + NW + 6)
            S.arrow([(x0, y), (x1, y)])
            if e.get("label"):
                S.label((x0 + x1) / 2, y - 8, e["label"], T.MUTED, 11, bg=T.PANEL)
        else:
            x = ax + NW / 2
            y0, y1 = (ay + NH + 4, by - 6) if by > ay else (ay - 4, by + NH + 6)
            pts = [(x, y0), (x, (y0 + y1) / 2), (bx + NW / 2, (y0 + y1) / 2), (bx + NW / 2, y1)] if abs(ax - bx) > 1 \
                else [(x, y0), (x, y1)]
            S.arrow(pts)
            if e.get("label"):
                S.text(x + 10, (y0 + y1) / 2 - 6, e["label"], 11, T.MUTED, 500)
    return PH


PANELS = {"media_pipeline": media_pipeline, "flow": flow}
