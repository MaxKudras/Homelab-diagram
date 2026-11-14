"""Run all sources from sources.yaml, merge them and write inventory.generated.yaml + a report.

sources.yaml (not in git, see sources.example.yaml):
  sources:
    - {type: ansible, inventory: ~/infra/hosts.yml}
    - {type: netbox, url: https://netbox.lan, token_env: NETBOX_TOKEN}
    - {type: proxmox, url: https://pve1:8006, token_env: PVE_TOKEN, verify_tls: false}
    - {type: prometheus, url: http://prometheus:9090}
    - {type: opnsense, url: https://fw.lan, key_env: OPN_KEY, secret_env: OPN_SECRET}
Later sources win on the same field; overrides.yaml (by hand) wins over all of them.
"""
import importlib
import pathlib
import sys

import yaml

from . import merge as M
from .base import SourceError

TYPES = ("ansible", "netbox", "proxmox", "prometheus", "opnsense")


def gather(cfgs):
    """Run each source; returns (merged dict, per-source counts, errors)."""
    out, report, errors = {}, [], []
    mon, ips = {}, []
    for cfg in cfgs:
        t = cfg.get("type")
        if cfg.get("enabled") is False:
            continue
        if t not in TYPES:
            errors.append(f"unbekannte Quelle „{t}“ (bekannt: {', '.join(TYPES)})")
            continue
        try:
            part = importlib.import_module(f"hld.sources.{t}").collect(cfg)
        except SourceError as e:
            errors.append(str(e))
            continue
        mon.update(part.pop("_monitor", {}))
        ips += part.pop("_ips", [])
        nd = len(part.get("devices", []))
        ng = sum(len(d.get("guests", [])) for d in part.get("devices", []))
        report.append(f"{t}: {nd} Geräte, {ng} Gäste, {len(part.get('links', []))} Verbindungen, "
                      f"{len(part.get('networks', []))} Netze" + (f", {len(mon)} überwacht" if t == "prometheus" else "")
                      + (f", {len(ips)} Adressen" if t == "opnsense" else ""))
        out = M.merge(out, part)
    if mon:
        from .prometheus import apply
        apply(out, mon)
    if ips:
        known = {str(d.get("ip", "")).split(" ")[0] for d in out.get("devices", [])}
        known |= {str(g.get("ip")) for d in out.get("devices", []) for g in d.get("guests", [])}
        out["ip_extra"] = [e for e in ips if e["ip"] not in known]
    return out, report, errors


def diff(old, new):
    """Short change report between two generated files."""
    def idx(d):
        devs = {x["id"]: x for x in d.get("devices", [])}
        gs = {(x["id"], g.get("id"), g.get("name")): g for x in d.get("devices", []) for g in x.get("guests", [])}
        return devs, gs
    od, og = idx(old)
    nd, ng = idx(new)
    lines = []
    for k in nd.keys() - od.keys():
        lines.append(f"+ Gerät {nd[k].get('name', k)}")
    for k in od.keys() - nd.keys():
        lines.append(f"- Gerät {od[k].get('name', k)}")
    for k in nd.keys() & od.keys():
        if nd[k].get("ip") != od[k].get("ip"):
            lines.append(f"~ {nd[k].get('name', k)}: IP {od[k].get('ip')} → {nd[k].get('ip')}")
    for k in ng.keys() - og.keys():
        lines.append(f"+ Gast {ng[k].get('name')} auf {k[0]}")
    for k in og.keys() - ng.keys():
        lines.append(f"- Gast {og[k].get('name')} auf {k[0]}")
    return lines


def run(root, cfg_file=None):
    root = pathlib.Path(root)
    cfg_file = pathlib.Path(cfg_file or root / "sources.yaml")
    if not cfg_file.exists():
        sys.exit(f"{cfg_file.name} fehlt – Vorlage: sources.example.yaml kopieren und anpassen")
    cfgs = (yaml.safe_load(cfg_file.read_text()) or {}).get("sources", [])
    new, report, errors = gather(cfgs)
    gen = root / "inventory.generated.yaml"
    old = yaml.safe_load(gen.read_text()) if gen.exists() else {}
    for r in report:
        print("Quelle", r)
    for e in errors:
        print("Fehler:", e)
    changes = diff(old or {}, new)
    print("Änderungen seit dem letzten Einlesen:" if changes else "Keine Änderungen seit dem letzten Einlesen.")
    for c in changes:
        print(" ", c)
    gen.write_text("# automatisch erzeugt von build.py --collect – nicht von Hand ändern, dafür overrides.yaml\n"
                   + yaml.safe_dump(new, sort_keys=False, allow_unicode=True))
    print("geschrieben:", gen)
    return new
