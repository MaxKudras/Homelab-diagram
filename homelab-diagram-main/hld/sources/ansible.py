"""Ansible inventory (YAML or INI) + host_vars/ → devices and guests.

cfg: {type: ansible, inventory: path/to/hosts.yml, role_map: {group: role}, guest_groups: [lxc, vms]}

Recognised host variables (all optional, plain or with prefix hld_):
  ansible_host → ip · net/vlan · vmid · kind (CT/VM) · proxmox_node (→ guest of that node)
  name · type · model · os · icons · mythos · status · host / internal · group (chip heading)
  uplink: "switch.port"  (+ speed, vlans) → a cable to that switch port
"""
import configparser
import pathlib

import yaml

from .base import SourceError, slug

ROLE_MAP = {
    "firewalls": "firewall", "firewall": "firewall", "routers": "router", "switches": "switch",
    "switch": "switch", "proxmox": "server", "pve": "server", "servers": "server", "hypervisors": "server",
    "nas": "nas", "storage": "nas", "pis": "pi", "raspberrypi": "pi", "aps": "ap", "accesspoints": "ap",
    "iot": "iot", "workstations": "workstation", "clients": "workstation", "kvm": "kvm", "ups": "ups",
}
GUEST_GROUPS = ("lxc", "containers", "cts", "vms", "virtual_machines", "guests")
ICONS = {"firewall": "opnsense", "router": "opnsense", "switch": "glyph-switch", "server": "proxmox",
         "nas": "omv", "pi": "raspberrypi", "ap": "glyph-antenna", "iot": "glyph-antenna",
         "workstation": "debian", "kvm": "glyph-kvm", "ups": "glyph-ups"}


def _walk(node, groups, hosts, path=()):
    """Collect host → (vars, [groups]) from the YAML inventory tree."""
    if not isinstance(node, dict):
        return
    for h, hv in (node.get("hosts") or {}).items():
        e = hosts.setdefault(h, {"vars": {}, "groups": []})
        e["vars"].update(hv or {})
        e["groups"] += list(path)
    gv = node.get("vars") or {}
    for g, sub in (node.get("children") or {}).items():
        groups.setdefault(g, {}).update(gv)
        _walk(sub or {}, groups, hosts, path + (g,))


def _read(inv):
    p = pathlib.Path(inv)
    if not p.exists():
        raise SourceError(f"Ansible-Inventar {p} gibt es nicht")
    hosts, groups = {}, {}
    if p.suffix in (".yml", ".yaml"):
        d = yaml.safe_load(p.read_text()) or {}
        _walk(d.get("all", d), groups, hosts)
    else:                                       # INI: [group] host key=value …
        cp = configparser.ConfigParser(allow_no_value=True, delimiters=(" ",), strict=False)
        cp.optionxform = str
        cp.read_string(p.read_text())
        for g in cp.sections():
            if ":" in g:
                continue
            for line, rest in cp.items(g):
                kv = dict(x.split("=", 1) for x in (f"{line} {rest or ''}").split()[1:] if "=" in x)
                e = hosts.setdefault(line, {"vars": {}, "groups": []})
                e["vars"].update(kv)
                e["groups"].append(g)
    hv_dir = p.parent / "host_vars"
    for h, e in hosts.items():
        for f in (hv_dir / f"{h}.yml", hv_dir / f"{h}.yaml"):
            if f.exists():
                e["vars"].update(yaml.safe_load(f.read_text()) or {})
    return hosts


def _v(vars_, key, default=None):
    return vars_.get(f"hld_{key}", vars_.get(key, default))


def collect(cfg):
    role_map = {**ROLE_MAP, **(cfg.get("role_map") or {})}
    guest_groups = tuple(cfg.get("guest_groups") or GUEST_GROUPS)
    hosts = _read(cfg["inventory"])
    devices, links, guests = {}, [], []
    for h, e in hosts.items():
        v, gs = e["vars"], e["groups"]
        ip = _v(v, "ansible_host") or _v(v, "ip")
        net = _v(v, "net", _v(v, "vlan"))
        node = _v(v, "proxmox_node")
        if node or any(g in guest_groups for g in gs):
            kind = _v(v, "kind") or ("CT" if any(g in ("lxc", "containers", "cts") for g in gs) else "VM")
            g = {"id": int(_v(v, "vmid", 0) or 0), "name": _v(v, "name", h), "kind": kind, "ip": ip,
                 "net": str(net) if net is not None else None, "icons": _v(v, "icons", ["docker"]),
                 "note": _v(v, "note", ""), "internal": _v(v, "internal", slug(h)),
                 "source": "ansible"}
            for k in ("host", "exposure", "group"):
                if _v(v, k):
                    g[k] = _v(v, k)
            guests.append((slug(node) if node else None, g))
            continue
        role = _v(v, "role") or next((role_map[g] for g in gs if g in role_map), "other")
        d = {"id": slug(h), "role": role, "name": _v(v, "name", h), "type": _v(v, "type", role),
             "ip": ip or "", "internal": _v(v, "internal", slug(h)), "source": "ansible"}
        if net is not None:
            d["net"] = str(net)
        for k in ("model", "os", "mythos", "status", "icons", "host"):
            if _v(v, k):
                d[k] = _v(v, k)
        d.setdefault("icons", [ICONS.get(role, "glyph-antenna")])
        devices[d["id"]] = d
        up = _v(v, "uplink")
        if up:
            l = {"a": str(up), "b": d["id"], "speed": str(_v(v, "speed", "1G")), "source": "ansible"}
            if _v(v, "vlans"):
                l["vlans"] = [str(x) for x in _v(v, "vlans")]
            elif net is not None:
                l["net"] = str(net)
            links.append(l)
    for node, g in guests:
        if node and node in devices:
            devices[node].setdefault("guests", []).append(g)
            devices[node]["role"] = "server"
        else:
            raise SourceError(f"Ansible: Gast „{g['name']}“ gehört zu Proxmox-Node „{node}“, den es im Inventar nicht gibt")
    return {"devices": list(devices.values()), "links": links}
