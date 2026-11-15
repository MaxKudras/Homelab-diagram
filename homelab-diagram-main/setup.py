#!/usr/bin/env python3
"""One-step setup for rendering: fonts from fonts/, rsvg-convert, icons.

Usage:
  python3 setup.py                 install fonts (from this repo), check rsvg-convert, fetch missing icons
  python3 setup.py --check-fonts   compare the fonts in fonts/ with the newest upstream versions
  python3 setup.py --update-fonts  download the newest upstream fonts into fonts/ (then commit them)

The fonts (Fira Sans + Fira Code, SIL Open Font License, see fonts/OFL-*.txt) are part of the
repo so a fresh machine needs no download for them. fonts/fonts.json records where each file
comes from, its version and its sha256, which --check-fonts compares against upstream.
"""
import hashlib
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent
FONTS = ROOT / "fonts"
MANIFEST = FONTS / "fonts.json"
WEIGHTS = ["Regular", "Medium", "SemiBold", "Bold"]
SANS_URL = "https://raw.githubusercontent.com/mozilla/Fira/master/ttf/FiraSans-{}.ttf"
CODE_README = "https://raw.githubusercontent.com/tonsky/FiraCode/master/README.md"
CODE_ZIP = "https://github.com/tonsky/FiraCode/releases/download/{v}/Fira_Code_v{v}.zip"
UA = {"User-Agent": "homelab-diagram-setup/1.0"}


def get(url, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def sha(b):
    return hashlib.sha256(b).hexdigest()


def manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def code_latest():
    """Newest Fira Code release, read from the README's download link (no GitHub API needed)."""
    m = re.findall(r"Fira_Code_v([0-9.]+)\.zip", get(CODE_README).decode())
    return max(m, key=lambda v: [int(x) for x in v.split(".")]) if m else None


def code_files(version):
    z = zipfile.ZipFile(io.BytesIO(get(CODE_ZIP.format(v=version), timeout=120)))
    return {f"FiraCode-{w}.ttf": z.read(f"ttf/FiraCode-{w}.ttf") for w in WEIGHTS}


def check_fonts(update=False):
    man = manifest()
    changed = {}
    print("Fira Sans (mozilla/Fira, master):")
    for w in WEIGHTS:
        name = f"FiraSans-{w}.ttf"
        new = get(SANS_URL.format(w))
        same = man.get(name, {}).get("sha256") == sha(new)
        print(f"  {name:24} {'up to date' if same else 'NEWER VERSION UPSTREAM'}")
        if not same:
            changed[name] = (new, {"source": SANS_URL.format(w), "version": "master"})
    have = man.get("FiraCode-Regular.ttf", {}).get("version")
    latest = code_latest()
    print(f"Fira Code (tonsky/FiraCode releases): repo {have} · newest {latest}"
          + ("  up to date" if have == latest else "  NEWER VERSION UPSTREAM"))
    if latest and have != latest:
        for name, data in code_files(latest).items():
            changed[name] = (data, {"source": CODE_ZIP.format(v=latest), "version": latest})
    if not changed:
        print("all fonts are current")
        return 0
    if not update:
        print("run: python3 setup.py --update-fonts   (then re-render and commit fonts/)")
        return 1
    for name, (data, info) in changed.items():
        (FONTS / name).write_bytes(data)
        man[name] = {**info, "sha256": sha(data)}
    MANIFEST.write_text(json.dumps(man, indent=2) + "\n")
    print(f"updated {len(changed)} font file(s) in fonts/")
    return 0


def install_fonts():
    """Copy fonts/ into the user font dir (fontconfig finds them there) and refresh the cache."""
    dst = pathlib.Path.home() / ".local/share/fonts/homelab-diagram"
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in FONTS.glob("*.ttf"):
        t = dst / f.name
        if not t.exists() or t.read_bytes() != f.read_bytes():
            shutil.copy(f, t)
            n += 1
    if n:
        subprocess.run(["fc-cache", "-f", str(dst)], check=False, capture_output=True)
    print(f"fonts: {n} installed/updated in {dst}" if n else "fonts: already installed")


def ensure_rsvg():
    if shutil.which("rsvg-convert"):
        print("rsvg-convert: ok")
        return
    if os.geteuid() == 0 and shutil.which("apt-get"):
        print("rsvg-convert: installing librsvg2-bin …")
        r = subprocess.run(["apt-get", "install", "-y", "librsvg2-bin"], capture_output=True)
        if r.returncode:
            subprocess.run(["apt-get", "update"], capture_output=True)
            subprocess.run(["apt-get", "install", "-y", "librsvg2-bin"], capture_output=True)
    print("rsvg-convert: ok" if shutil.which("rsvg-convert") else
          "rsvg-convert: MISSING – install librsvg (Debian: librsvg2-bin, Arch: librsvg)")


def main():
    if "--check-fonts" in sys.argv or "--update-fonts" in sys.argv:
        raise SystemExit(check_fonts(update="--update-fonts" in sys.argv))
    install_fonts()
    ensure_rsvg()
    subprocess.run([sys.executable, str(ROOT / "fetch_icons.py")], check=True)


if __name__ == "__main__":
    main()
