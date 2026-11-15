#!/usr/bin/env python3
"""Builds planer/planer.html: one offline file with fonts, icons, examples and the planner code.

    python3 planer/build_planer.py        # → planer/planer.html

Icons that fetch_icons.py has not downloaded yet are simply missing (the card shows a grey box).
"""
import base64
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
FONTS = [("Fira Sans", w, f"FiraSans-{n}.ttf") for w, n in ((400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold"))] + \
        [("Fira Code", w, f"FiraCode-{n}.ttf") for w, n in ((400, "Regular"), (500, "Medium"))]
EXAMPLES = ["manuell", "klein", "max-zukunft", "aus-quellen", "stress-60"]


def b64(p):
    return base64.b64encode(p.read_bytes()).decode()


def build(out=HERE / "planer.html"):
    html = (HERE / "src" / "planer.html").read_text()
    fonts = "\n".join(
        f'@font-face {{ font-family: "{fam}"; font-weight: {w}; font-style: normal; '
        f'src: url(data:font/ttf;base64,{b64(ROOT / "fonts" / f)}) format("truetype"); }}'
        for fam, w, f in FONTS)
    icons = {p.stem: "data:image/svg+xml;base64," + b64(p) for p in sorted((ROOT / "icons").glob("*.svg"))}
    examples = {}
    for name in EXAMPLES:
        p = ROOT / "examples" / f"{name}.yaml"
        if p.exists():
            examples[name] = p.read_text()
    inv = ROOT / "inventory.yaml"
    if inv.exists():
        examples["original (u/goblinmine)"] = inv.read_text()
    data = "const ICONS = " + json.dumps(icons) + ";\nconst EXAMPLES = " + json.dumps(examples, ensure_ascii=False) + ";"
    parts = {"FONTS": fonts, "DATA": data}
    for k in ("yaml", "core", "draw", "app"):
        parts[k.upper()] = (HERE / "src" / f"{k}.js").read_text()
    for k, v in parts.items():
        tag = f"/*{k}*/"
        assert tag in html, tag
        html = html.replace(tag, v.replace("</script", "<\\/script"), 1)
    out.write_text(html)
    print(f"{out.name}: {len(html) / 1e6:.1f} MB, {len(icons)} Icons, {len(examples)} Beispiele")
    return out


if __name__ == "__main__":
    build()
