#!/usr/bin/env python3
"""Render the homelab diagram (v2 engine, package hld/).

Usage:
  python3 build.py                       inventory.yaml → out/homelab.svg + .png (redacted)
  python3 build.py --unredacted          real domain + SSIDs → out/homelab-unredacted.*
  python3 build.py --lab FILE.yaml       another lab file (schema 1 or 2)
  python3 build.py --ips=MODE            IP list: table | inline | both | sheet
  python3 build.py --variants            default + all IP variants
  python3 build.py --examples            every lab in examples/ → out/examples/<name>.png
  python3 build.py --collect             pull data from the sources in sources.yaml first
  python3 build.py --no-qa               draw even if the overlap check finds problems

Old versions: versions/vN/build.py (see versions/README.md).
"""
import pathlib
import subprocess
import sys

import yaml

from hld import legacy, qa, theme as T
from hld.ips import collect as collect_ips, table as ip_table
from hld.model import Lab
from hld.render import Renderer
from hld.svg import SVG
from hld.text import configure
from hld import validate

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "out"
IP_MODES = ("table", "inline", "both", "sheet")


def arg(name, default=None):
    return next((a.split("=", 1)[1] for a in sys.argv if a.startswith(f"--{name}=")), default)


def load(path):
    d = yaml.safe_load(pathlib.Path(path).read_text())
    if d.get("schema") != 2:
        d = legacy.convert(d)
    return d


def merged(path):
    """Lab file + (optional) data pulled by --collect + hand-made overrides."""
    d = load(path)
    gen = ROOT / "inventory.generated.yaml"
    ovr = ROOT / "overrides.yaml"
    if path == str(ROOT / "inventory.yaml") or pathlib.Path(path).name == "inventory.yaml":
        from hld.sources import merge
        if gen.exists():
            d = merge.merge(d, yaml.safe_load(gen.read_text()) or {})
        if ovr.exists():
            d = merge.merge(d, yaml.safe_load(ovr.read_text()) or {})
    return d


def render(lab_d, out_name, unredacted=False, ip_mode="none", check=True):
    lab = Lab(lab_d)
    meta, red = lab.meta, lab.redact
    redact_domain = red.get("domain", True) and not unredacted
    configure(meta.get("domain", ""), meta.get("domain") if not redact_domain else
              red.get("domain_placeholder", "redacted.com"), redact_domain)
    err, warn = validate.check(lab)
    for w in warn:
        print("Warnung:", w)
    if err:
        raise SystemExit("Fehler in den Daten:\n  " + "\n  ".join(err))
    title = meta.get("title", "My Homelab") if not redact_domain else meta.get("title_redacted", meta.get("title", ""))
    if ip_mode == "sheet":
        S = SVG()
        from hld import panels
        panels.header(S, title, meta.get("watermark", ""), meta.get("date", ""))
        ips = collect_ips(lab)
        h = ip_table(S, lab, ips, 40, 130, T.W - 80, 4, hosts=True)
        H = 130 + h + 40
    else:
        R = Renderer(lab, ip_mode, unredacted)
        H = R.draw(title)
        S = R.S
        for w in R.warnings:
            print("Warnung:", w)
    if check:
        problems = qa.run(S)
        if problems:
            for p in problems[:40]:
                print("QA:", p)
            raise SystemExit(f"{len(problems)} Darstellungsprobleme gefunden (Bild trotzdem ansehen: --no-qa)")
    out = OUT / out_name
    out.parent.mkdir(parents=True, exist_ok=True)
    svg = out.with_suffix(".svg")
    svg.write_text(S.render(H))
    png = out.with_suffix(".png")
    subprocess.run(["rsvg-convert", "-z", "1.6", "-o", str(png), str(svg)], check=True)
    print(svg, png)
    return png


def main():
    unred = "--unredacted" in sys.argv
    check = "--no-qa" not in sys.argv
    if "--collect" in sys.argv:
        from hld.sources import collect
        collect.run(ROOT)
    if "--examples" in sys.argv:
        for f in sorted((ROOT / "examples").glob("*.yaml")):
            render(load(f), f"examples/{f.stem}", unred, "none", check)
        return
    path = arg("lab", str(ROOT / "inventory.yaml"))
    d = merged(path)
    base = "homelab-unredacted" if unred else "homelab"
    if "--variants" in sys.argv:
        modes = ("none",) + IP_MODES
    else:
        modes = (arg("ips", "none"),)
    for m in modes:
        if m not in IP_MODES + ("none",):
            raise SystemExit(f"--ips= muss eins davon sein: {', '.join(IP_MODES)}")
        render(d, base + ("" if m == "none" else f"-ips-{m}"), unred, m, check)


if __name__ == "__main__":
    main()
