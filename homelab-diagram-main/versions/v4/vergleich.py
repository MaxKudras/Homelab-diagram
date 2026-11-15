#!/usr/bin/env python3
"""Comparison page of all layouts: out/vergleich.html (one self-contained file, works offline and on
the phone: images embedded, tap to enlarge, scores per layout).

Usage: python3 build.py --examples --layout=all --no-qa && python3 build.py --layout=all --no-qa
       python3 vergleich.py
It reads the PNGs in out/ and out/examples/ and the scores printed by build.py (out/examples-all.log).
"""
import base64
import html
import io
import pathlib
import re

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "out"
LAYOUTS = [("rows", "Reihen (v2)"), ("cluster", "Cluster je Switch"), ("flow", "Fluss links → rechts")]
LABS = [("homelab", "Original-Lab (u/goblinmine)", OUT), ("examples/max-zukunft", "Zukunftsplan (Beispieldaten)", OUT),
        ("examples/klein", "Kleines Lab", OUT), ("examples/aus-quellen", "Aus Datenquellen", OUT),
        ("examples/stress-60", "Stresstest 51 Geräte", OUT)]


def scores():
    out = {}
    log = OUT / "examples-all.log"
    if log.exists():
        for line in log.read_text().splitlines():
            m = re.match(r"Bewertung (\S+): (.*)", line)
            if m:
                out[m.group(1)] = dict(kv.rsplit(" ", 1) for kv in m.group(2).split(" · "))
    return out


def thumb(png, width=1500):
    im = Image.open(png).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    sc = scores()
    parts = []
    for base, title, d in LABS:
        cells = []
        rows_sc = {}
        for key, name in LAYOUTS:
            png = d / f"{base}-{key}.png"
            if not png.exists():
                continue
            s = sc.get(f"{base}-{key}", {})
            rows_sc[key] = s
            cells.append((key, name, png, s))
        if not cells:
            continue
        best = {}
        for k in ("Kreuzungen", "längstes Kabel"):
            vals = [int(s.get(k, 10 ** 9)) for _, _, _, s in cells if s.get(k)]
            best[k] = min(vals) if vals else None
        cards = []
        for key, name, png, s in cells:
            img = thumb(png)
            stats = "".join(
                f'<li class="{"best" if best.get(k) is not None and s.get(k) and int(s[k]) == best[k] else ""}">'
                f'<b>{html.escape(k)}</b> {html.escape(str(v))}</li>'
                for k, v in s.items() if k in ("Kreuzungen", "Kabellänge", "Knicke", "längstes Kabel", "Größe"))
            cards.append(f'<figure><figcaption>{html.escape(name)}</figcaption>'
                         f'<img loading="lazy" src="data:image/jpeg;base64,{img}" alt="{html.escape(name)}">'
                         f'<ul>{stats}</ul></figure>')
        parts.append(f'<section><h2>{html.escape(title)}</h2><div class="grid">{"".join(cards)}</div></section>')
    page = f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Layout-Vergleich</title>
<style>
:root {{ --bg:#0b0f15; --panel:#111821; --chip:#19222e; --text:#e6edf3; --muted:#8d9aab; --line:#253042; --ok:#3fb950; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.45 "Fira Sans",system-ui,sans-serif; }}
header {{ padding:20px 16px 4px; }} h1 {{ margin:0 0 6px; font-size:26px; }}
header p {{ margin:0; color:var(--muted); max-width:900px; }}
section {{ padding:12px 16px 24px; border-bottom:1px solid var(--line); }}
h2 {{ font-size:19px; margin:10px 0 12px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:14px; }}
figure {{ margin:0; background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:10px; }}
figcaption {{ font-weight:600; margin-bottom:8px; }}
img {{ width:100%; border-radius:8px; cursor:zoom-in; background:#000; }}
ul {{ list-style:none; padding:0; margin:8px 0 0; display:flex; flex-wrap:wrap; gap:6px; }}
li {{ background:var(--chip); border-radius:6px; padding:2px 8px; font-size:13px; color:var(--muted); }}
li b {{ color:var(--text); font-weight:600; }} li.best {{ outline:1px solid var(--ok); }}
#zoom {{ position:fixed; inset:0; background:#000e; display:none; overflow:auto; z-index:9; }}
#zoom img {{ width:auto; max-width:none; min-width:100%; cursor:zoom-out; }}
</style></head><body>
<header><h1>Layout-Vergleich</h1>
<p>Jedes Lab in drei Ansichten. Bild antippen zum Vergrößern (dann scrollen/zoomen), noch einmal tippen zum Schließen.
Grün umrandet = bester Wert der Zeile. Weniger Kreuzungen und kürzere Kabel = aufgeräumter.</p></header>
{''.join(parts)}
<div id="zoom" onclick="this.style.display='none'"><img id="zimg" alt=""></div>
<script>
document.querySelectorAll('figure img').forEach(i => i.addEventListener('click', () => {{
  document.getElementById('zimg').src = i.src; document.getElementById('zoom').style.display = 'block'; }}));
</script></body></html>"""
    (OUT / "vergleich.html").write_text(page)
    print(OUT / "vergleich.html", f"{len(page) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
