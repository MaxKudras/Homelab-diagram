"""Exact text measurement and redaction.

Widths come from the real font files in fonts/ (Pillow), never from estimates, so every box
is sized from its text before anything is placed.
"""
import html
import pathlib

from PIL import ImageFont

FONTS = pathlib.Path(__file__).resolve().parent.parent / "fonts"
_FILES = {
    ("sans", 400): "FiraSans-Regular.ttf", ("sans", 500): "FiraSans-Medium.ttf",
    ("sans", 600): "FiraSans-SemiBold.ttf", ("sans", 700): "FiraSans-Bold.ttf",
    ("mono", 400): "FiraCode-Regular.ttf", ("mono", 500): "FiraCode-Medium.ttf",
    ("mono", 600): "FiraCode-SemiBold.ttf", ("mono", 700): "FiraCode-Bold.ttf",
}
_CACHE = {}

# redaction settings, set once by render.configure()
CFG = {"domain": "example.com", "shown": "redacted.com", "redact": True}


def configure(domain, shown, redact):
    CFG.update(domain=domain, shown=shown, redact=redact)


def sub(s):
    """Fill {domain} placeholders and apply redaction."""
    s = str(s).replace("{domain}", CFG["shown"])
    if CFG["redact"] and CFG["domain"]:
        s = s.replace(CFG["domain"], CFG["shown"])
    return s


def esc(s):
    return html.escape(sub(s), quote=True)


def fqdn(h):
    return f"{h}.{CFG['shown']}"


def _font(mono, weight, size):
    w = min((400, 500, 600, 700), key=lambda k: abs(k - weight))
    key = ("mono" if mono else "sans", w, size)
    if key not in _CACHE:
        _CACHE[key] = ImageFont.truetype(str(FONTS / _FILES[key[:2]]), size=max(1, round(size * 8)))
    return _CACHE[key]


def measure(s, size, weight=400, mono=False, ls=0):
    """Exact advance width of s (after redaction) in SVG units."""
    s = sub(s)
    return _font(mono, weight, size).getlength(s) / 8 + ls * max(0, len(s) - 1)


def fit_size(s, size, max_w, weight=400, mono=False, min_size=8):
    """Largest font size ≤ size at which s fits into max_w (used only for long part names)."""
    w = measure(s, size, weight, mono)
    if w <= max_w:
        return size
    return max(min_size, round(size * max_w / w, 2))
