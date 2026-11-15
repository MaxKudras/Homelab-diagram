"""Drawing building blocks, taken over from the original build.py.

Every block has a size function (*_w / *_h) that measures first, so the layout can reserve the
exact space before anything is drawn.
"""
from . import theme as T
from .text import fqdn, measure


def get(o, k, default=None):
    if isinstance(o, dict):
        return o.get(k, default)
    v = getattr(o, k, default)
    return default if v is None else v


# ---------------------------------------------------------------- addresses
def hostname(g):
    """(text, color) for the second address line: public host, or <name>.internal."""
    if get(g, "host"):
        return fqdn(get(g, "host")), T.LINK
    if get(g, "internal"):
        return f"{get(g, 'internal')}.internal", None
    return None, None


def addr_w(ip, g, size=12):
    cw = size * 0.6
    name, _ = hostname(g)
    w = len(str(ip)) * cw
    if name:
        w += cw * 0.6 + cw * 1.6 + measure(name, size, 400, True)
    return w


def addr(S, x, y, ip, g, color, size=12):
    """Address line: IP · hostname, in the VLAN color (a public hostname is blue)."""
    S.text(x, y, ip, size, color, 500, mono=True)
    name, ncol = hostname(g)
    if name:
        cw = size * 0.6
        dx = x + len(str(ip)) * cw + cw * 0.6
        S.text(dx, y, "·", size, T.MUTED, 400, mono=True)
        S.text(dx + cw * 1.6, y, name, size, ncol or color, 400, mono=True, op=1 if ncol else 0.85)


# ---------------------------------------------------------------- physical-device card (folder tab)
def tab_width(name, typ):
    """Tab fits 'name · type' (name 20px bold, type 14px semibold)."""
    return 16 + measure(name, 20, 700) + 7 + measure("·", 20, 700) + 7 + measure(typ, 14, 600) + 18


def folder(S, x, y, w, h, tab_w, fill, stroke, sw):
    """Card body at (x, y, w, h) with a folder tab on its top-left edge, tab_w wide and TAB high."""
    t = y - T.TAB
    r, rt, sl = 12, 9, 16
    d = (f"M{x:.1f},{y+h-r:.1f} L{x:.1f},{t+rt:.1f} Q{x:.1f},{t:.1f} {x+rt:.1f},{t:.1f} L{x+tab_w-sl:.1f},{t:.1f} "
         f"C{x+tab_w-sl/3:.1f},{t:.1f} {x+tab_w-sl/3:.1f},{y:.1f} {x+tab_w+sl/2:.1f},{y:.1f} "
         f"L{x+w-r:.1f},{y:.1f} Q{x+w:.1f},{y:.1f} {x+w:.1f},{y+r:.1f} L{x+w:.1f},{y+h-r:.1f} "
         f"Q{x+w:.1f},{y+h:.1f} {x+w-r:.1f},{y+h:.1f} L{x+r:.1f},{y+h:.1f} Q{x:.1f},{y+h:.1f} {x:.1f},{y+h-r:.1f} Z")
    S.add(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')


def header_w(d, n_icons):
    """Width the body header needs: icons + model / IP · host / OS / config lines."""
    tx = 14 + 58 * n_icons + 8
    lines = [measure(get(d, "model") or "custom build", 14, 500), addr_w(get(d, "ip", ""), d),
             measure(get(d, "os", ""), 12, 400), measure(get(d, "config", ""), 12, 400)]
    return tx + max(lines)


def header_h(d):
    return 92 if get(d, "config") else 86 if get(d, "os") else 86


def device_card(S, x, y, w, h, icons, d, color, fill=T.PANEL, stroke=None, sw=1.6, dash=None):
    """Physical device: folder tab 'name · type'; body = icon, full device name, IP · hostname, OS."""
    tw_ = tab_width(d.name, d.type)
    folder(S, x, y, w, h, tw_, fill, stroke or color + "aa", sw)
    if dash:   # planned device: dashed outline on top
        S.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="12" fill="none" '
              f'stroke="{fill}" stroke-width="{sw + 1}" stroke-dasharray="{dash}"/>')
    S.reg_card(x, y, w, h, d.name)
    S.reg_card(x, y - T.TAB, tw_, T.TAB, d.name + " (tab)")
    from .text import esc
    S.add(f'<text x="{x+16:.1f}" y="{y-10:.1f}" font-family="{T.SANS}" fill="{T.TEXT}">'
          f'<tspan font-size="20" font-weight="700">{esc(d.name)}</tspan>'
          f'<tspan dx="7" font-size="20" font-weight="700" fill-opacity="0.6">·</tspan>'
          f'<tspan dx="7" font-size="14" font-weight="600">{esc(d.type)}</tspan></text>')
    S.reg_text(x + 16, y - 25, x + tw_ - 16, y - 6, d.name)
    ix = x + 14
    for ic in icons:                      # icon spans the three body lines (full name … OS)
        S.icon(ic, ix, y + 15, 54)
        S.reg_text(ix, y + 15, ix + 54, y + 69, "[icon]")
        ix += 58
    tx_ = ix + 8
    dy = 0 if d.os else 8                 # no OS line → center the two lines on the icon
    S.text(tx_, y + 28 + dy, d.model or "custom build", 14, T.TEXT if d.model else T.MUTED, 500)
    addr(S, tx_, y + 48 + dy, d.ip, d, color)
    if d.os:
        S.text(tx_, y + 66, d.os, 12, T.MUTED, 400)
    if d.config:                          # optional 4th line: how the device is set up
        S.text(tx_, y + 84, d.config, 12, T.FAINT, 400)
    return tx_


def hw_bar(S, x, y, h):
    """Left accent bar = this card is a physical box / hardware part."""
    S.add(f'<rect x="{x+1:.1f}" y="{y+12:.1f}" width="4" height="{h-24:.1f}" rx="2" fill="{T.HWC}"/>')


def hw_tile(S, x, y, w, hwi, h=58):
    S.rect(x, y, w, h, rx=11, fill="#151d29", stroke="#2e3a4c", sw=1.2)
    hw_bar(S, x, y, h)
    S.icon(hwi["icon"], x + 12, y + 15, 28)
    S.text(x + 50, y + 17, hwi["label"], 10, T.HWC, 700, ls=1.3)
    from .text import fit_size
    S.text(x + 50, y + 35, hwi["value"], fit_size(hwi["value"], 15.5, w - 62, 700), T.TEXT, 700)
    S.text(x + 50, y + 50, hwi.get("sub", ""), fit_size(hwi.get("sub", ""), 10.5, w - 58), T.MUTED, 400)


def hw_tile_w(hwi):
    return 62 + max(measure(hwi["value"], 15.5, 700), measure(hwi.get("sub", ""), 10.5, 400) - 4)


def service_tile(S, x, y, w, sv, h=50):
    S.rect(x, y, w, h, rx=9, fill=T.CHIP, stroke=T.BORDER, sw=1)
    S.icon(sv["icon"], x + 9, y + 12, 26)
    S.text(x + 44, y + 22, sv["name"], 14, T.TEXT, 600)
    S.text(x + 44, y + 39, sv.get("note", ""), 11.5, T.MUTED, 400)


def service_tile_w(sv):
    return 44 + max(measure(sv["name"], 14, 600), measure(sv.get("note", ""), 11.5)) + 12


# ---------------------------------------------------------------- ports
def jack(S, x, y, w, h, fill, stroke, sfp=False):
    S.rect(x, y, w, h, rx=5, fill=fill, stroke=stroke, sw=1.4)
    S.reg_text(x, y, x + w, y + h, "[jack]")          # QA: nothing may be written under a jack
    if sfp:
        S.rect(x + 8, y + 9, w - 16, h - 18, rx=2, fill="#0b0f15", stroke="none", sw=0)
    else:
        S.add(f'<path d="M{x+10:.1f},{y+h-8:.1f} v-14 h6 v-5 h{w-32:.1f} v5 h6 v14 z" fill="#0b0f15"/>')


def coax(S, cx, y):
    S.rect(cx - 22, y, 44, 36, rx=5, fill="#2a3443", stroke=T.TRUNK, sw=1.4)
    S.add(f'<circle cx="{cx:.1f}" cy="{y+18:.1f}" r="11" fill="#0b0f15" stroke="#5a6b82" stroke-width="2"/>'
          f'<circle cx="{cx:.1f}" cy="{y+18:.1f}" r="2.5" fill="{T.TRUNK}"/>')


def ticks(S, colors, cx, y, untagged=None, tagged=(), up=False):
    """VLAN indicator bars for a port: tall = untagged, short = tagged. up=True grows upwards."""
    vk = ([untagged] if untagged else []) + list(tagged)
    x0 = cx - (len(vk) * 7) / 2
    for j, k in enumerate(vk):
        hh = 8 if k == untagged else 5
        yy = y - hh if up else y
        S.add(f'<rect x="{x0 + j*7:.1f}" y="{yy:.1f}" width="5" height="{hh}" rx="1" fill="{colors(k)}"/>')


# ---------------------------------------------------------------- guests (VMs/CTs)
def guest_card_h(g):
    h = 84
    if get(g, "addons"):
        h = 120
    if get(g, "pools"):
        h = 84 + sum(pool_box_h(p) + 8 for p in get(g, "pools")) + (20 if get(g, "footer") else 0) + 4
    return h


def guest_card(S, g, x, y, w, h, col, vtag):
    S.rect(x, y, w, h, rx=12, fill=T.PANEL, stroke=col + "99", sw=1.5)
    S.reg_card(x, y, w, h, get(g, "name"))
    S.icon(get(g, "icons")[0], x + 16, y + 14, 34)
    if get(g, "badge"):
        S.add(f'<circle cx="{x+45:.1f}" cy="{y+44:.1f}" r="11" fill="{T.PANEL}"/>')
        S.icon(get(g, "badge"), x + 35, y + 34, 20)
    S.text(x + 60, y + 32, get(g, "name"), 17, T.TEXT, 600)
    S.pill(x + w - 14, y + 16, vtag, col, 10.5, mono=True, h=19, pad=6, anchor="end")
    addr(S, x + 60, y + 51, get(g, "ip"), g, col)
    S.text(x + 60, y + 69, get(g, "note", ""), 12.5, T.MUTED, 400)
    yy = y + 84
    for p in get(g, "pools") or []:
        ph = pool_box_h(p)
        pool_box(S, p, x + 14, yy, w - 28, ph, col)
        yy += ph + 8
    if get(g, "footer"):
        S.text(x + 18, yy + 12, get(g, "footer"), 12, T.MUTED, 400)
    if get(g, "addons"):
        ax = x + 18
        for ic in get(g, "addons"):
            S.icon(ic, ax, y + 80, 26)
            ax += 34
        S.text(ax + 8, y + 98, get(g, "addons_text", ""), 12, T.MUTED, 400)


def guest_card_w(g, vtag):
    w = 60 + max(measure(get(g, "name"), 17, 600) + 20 + measure(vtag, 10.5, 600, True) + 12 + 14,
                 addr_w(get(g, "ip"), g) + 14, measure(get(g, "note", ""), 12.5) + 14)
    if get(g, "addons"):
        w = max(w, 18 + 34 * len(get(g, "addons")) + 8 + measure(get(g, "addons_text", ""), 12) + 14)
    if get(g, "footer"):
        w = max(w, 36 + measure(get(g, "footer"), 12))
    return w


def disk(S, kind, x, y, col):
    if kind == "hdd":
        S.rect(x, y, 30, 40, rx=4, fill=T.DISK, stroke=T.DISK_EDGE, sw=1.2)
        S.add(f'<circle cx="{x+15:.1f}" cy="{y+16:.1f}" r="9" fill="none" stroke="{col}" stroke-width="1.6"/>'
              f'<circle cx="{x+15:.1f}" cy="{y+16:.1f}" r="2" fill="{col}"/>')
        S.rect(x + 8, y + 31, 14, 3, rx=1, fill=T.DISK_EDGE, stroke="none", sw=0)
        return 30
    if kind == "ssd":
        S.rect(x, y + 6, 44, 28, rx=3, fill=T.DISK, stroke=T.DISK_EDGE, sw=1.2)
        S.rect(x + 6, y + 12, 20, 16, rx=2, fill=col + "55", stroke="none", sw=0)
        S.rect(x + 30, y + 12, 8, 16, rx=1, fill=T.DISK_EDGE, stroke="none", sw=0)
        return 44
    S.rect(x, y + 10, 96, 20, rx=2, fill=T.DISK, stroke=T.DISK_EDGE, sw=1.2)        # nvme
    for k in range(3):
        S.rect(x + 8 + k * 22, y + 14, 16, 12, rx=1, fill=col + "55", stroke="none", sw=0)
    S.rect(x + 88, y + 15, 4, 10, rx=1, fill=T.BG, stroke="none", sw=0)
    return 96


def pool_box_h(p):
    return 158 if any(g["kind"] != "nvme" for g in p["groups"]) else 102


def pool_box(S, p, x, y, w, h, col):
    S.rect(x, y, w, h, rx=10, fill=T.CHIP, stroke=T.BORDER, sw=1)
    S.text(x + 14, y + 24, p["name"], 15.5, T.TEXT, 700)
    S.text(x + 14 + measure(p["name"], 15.5, 700) + 12, y + 24, p["layout"], 12.5, T.MUTED, 400)
    S.text(x + w - 14, y + 24, p["used"], 12, T.MUTED, 400, "end")
    bw_ = w - 28
    S.rect(x + 14, y + 34, bw_, 8, rx=4, fill="#253042", stroke="none", sw=0)
    S.rect(x + 14, y + 34, max(bw_ * p["pct"] / 100, 8), 8, rx=4, fill=col, stroke="none", sw=0)
    gx0 = x + 14
    for grp in p["groups"]:
        dx = gx0
        for _ in range(grp["count"]):
            dx += disk(S, grp["kind"], dx, y + 54, col) + 7
        gw_ = dx - 7 - gx0
        if grp["kind"] == "nvme":          # label to the right of the stick
            S.text(dx + 8, y + 64, grp["label"], 12.5, T.TEXT, 500)
            S.text(dx + 8, y + 80, grp["sub"], 11.5, T.MUTED, 400)
            if grp.get("sub2"):
                S.text(dx + 8, y + 95, grp["sub2"], 11.5, T.MUTED, 400)
        else:
            S.line([(gx0, y + 102), (gx0, y + 106), (gx0 + gw_, y + 106), (gx0 + gw_, y + 102)], T.DISK_EDGE, 1.2,
                   r=0, cap="butt")
            S.text(gx0, y + 122, grp["label"], 12.5, T.TEXT, 500)
            S.text(gx0, y + 137, grp["sub"], 11.5, T.MUTED, 400)
            if grp.get("sub2"):
                S.text(gx0, y + 152, grp["sub2"], 11.5, T.MUTED, 400)
            gw_ = max(gw_, measure(grp["label"], 12.5, 500), measure(grp["sub"], 11.5),
                      measure(grp.get("sub2", ""), 11.5))
        gx0 += gw_ + 30


# ---------------------------------------------------------------- DMZ-style chips
CH, CG = 64, 7


def docker_badge(S, x, y):
    """Small Docker whale on a corner = this CT runs its apps as Docker containers."""
    S.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="{T.PANEL}" stroke="#2f6fb0" stroke-width="1.2"/>')
    S.icon("docker", x - 8.5, y - 8.5, 17)


def chip_h(g):
    return 46 + len(get(g, "apps")) * 21 + 8 if get(g, "apps") else CH


def chip_w(g, ip_txt):
    """Minimum width a chip needs for its texts (the column width must be at least this)."""
    idw = max(measure(f"{get(g, 'kind', 'CT')} {get(g, 'id')}", 12, 500, True), measure(ip_txt, 11, 500, True))
    if get(g, "apps"):
        left = max(measure(get(g, "name"), 14.5, 600), measure(get(g, "note", ""), 11.5))
        rows = max((126 + (measure(fqdn(a["host"]), 11, 500, True) if a.get("host") else
                           measure(a.get("note", ""), 11.5))) for a in get(g, "apps"))
        return max(14 + left + 14 + idw + 12, rows + 14)
    n = len(get(g, "icons"))
    nx = 12 + 46 + 10 if n == 4 else 10 + n * ((32 if n == 1 else 26) + 4) + 6
    name, _ = hostname(g)
    host_w = measure(name, 11.5, 500, True) + (measure("LAN", 9.5, 600, True) + 16 if get(g, "exposure") == "local" else 0) if name else 0
    return nx + max(measure(get(g, "name"), 14.5, 600) + 10 + idw, measure(get(g, "note", ""), 11.5) + 10 + idw, host_w) + 12


def chip(S, g, x, y, w, ip_txt):
    kind_id = f"{get(g, 'kind', 'CT')} {get(g, 'id')}"
    if get(g, "apps"):
        h = chip_h(g)
        S.rect(x, y, w, h, rx=9, fill=T.CHIP, stroke=T.BORDER, sw=1)
        S.reg_card(x, y, w, h, get(g, "name"))
        S.text(x + 14, y + 22, get(g, "name"), 14.5, T.TEXT, 600)
        S.text(x + 14, y + 38, get(g, "note", ""), 11.5, T.MUTED, 400)
        S.text(x + w - 12, y + 21, kind_id, 12, T.FAINT, 500, "end", mono=True)
        S.text(x + w - 12, y + 37, ip_txt, 11, T.FAINT, 500, "end", mono=True)
        for k, a in enumerate(get(g, "apps")):
            ry = y + 50 + k * 21
            S.icon(a["icon"], x + 14, ry, 17)
            S.text(x + 38, ry + 13, a["name"], 12.5, T.TEXT, 600)
            if a.get("host"):
                S.text(x + 140, ry + 13, fqdn(a["host"]), 11, T.LINK, 500, mono=True)
            else:
                S.text(x + 140, ry + 13, a.get("note", ""), 11.5, T.MUTED, 400)
        if get(g, "docker"):
            docker_badge(S, x + 2, y + 2)
        return h
    S.rect(x, y, w, CH, rx=9, fill=T.CHIP, stroke=T.BORDER, sw=1)
    S.reg_card(x, y, w, CH, get(g, "name"))
    icons = get(g, "icons")
    if len(icons) == 4:                      # 2×2 grid
        for k, ic in enumerate(icons):
            S.icon(ic, x + 12 + (k % 2) * 23, y + 13 + (k // 2) * 21, 19)
        nx = x + 12 + 46 + 10
    else:
        isz = 32 if len(icons) == 1 else 26
        ix = x + 10
        for ic in icons:
            S.icon(ic, ix, y + (CH - isz) / 2, isz)
            ix += isz + 4
        nx = ix + 6
    S.text(nx, y + 21, get(g, "name"), 14.5, T.TEXT, 600)
    S.text(nx, y + 37, get(g, "note", ""), 11.5, T.MUTED, 400)
    name, ncol = hostname(g)
    if name:
        S.text(nx, y + 54, name, 11.5, ncol or T.MUTED, 500, mono=True)
        if get(g, "exposure") == "local":
            S.pill(nx + measure(name, 11.5, 500, True) + 8, y + 44, "LAN", T.MUTED, 9.5, mono=True, pad=4, h=14)
    S.text(x + w - 12, y + 21, kind_id, 12, T.FAINT, 500, "end", mono=True)
    S.text(x + w - 12, y + 37, ip_txt, 11, T.FAINT, 500, "end", mono=True)
    monitor_dot(S, g, x + w - 12, y + 52)
    if get(g, "docker"):
        docker_badge(S, x + 2, y + 2)
    return CH


def monitor_dot(S, o, x, y):
    """Small status dot: monitored by Prometheus and up (green) or down (red)."""
    m = get(o, "monitor") or (get(o, "extra") or {}).get("monitor")
    if not m:
        return
    col = "#3fb950" if m == "up" else "#f85149"
    S.add(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{col}" opacity="0.18"/>'
          f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4.2" fill="{col}"/>')
    S.reg_text(x - 8, y - 8, x + 8, y + 8, "[status]")
