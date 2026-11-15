"""Proxmox VE API → one server card per node, its VMs and LXCs as guests.

cfg: {type: proxmox, url: https://pve1:8006, token_env: PVE_TOKEN, verify_tls: false,
      icons: {vmid or name: icon}}
PVE_TOKEN = "user@pam!tokenid=secret" (an API token with the PVEAuditor role is enough: read only).
IP and VLAN of a guest come from its net0 (tag=…) and ip=… / ipconfig0, the VLAN tag is the network key.
"""
from .base import get_json, secret, short_ip, slug


def _kv(s):
    return dict(x.split("=", 1) for x in str(s).split(",") if "=" in x)


def collect(cfg):
    tok = secret(cfg)
    h = {"Authorization": f"PVEAPIToken={tok}"} if tok else {}

    def get(path):
        return get_json(cfg, "/api2/json" + path, h, fixture_key=path).get("data", [])

    icons = {str(k): v for k, v in (cfg.get("icons") or {}).items()}
    devices = []
    for nd in get("/nodes"):
        n = nd["node"]
        gib = round(nd.get("maxmem", 0) / 2 ** 30)
        dev = {"id": slug(n), "role": "server", "name": n, "type": "server", "model": "Proxmox VE node",
               "os": cfg.get("os", "Proxmox VE"), "internal": slug(n), "icons": ["proxmox"], "border": "trunk",
               "status": "active" if nd.get("status") == "online" else "later", "source": "proxmox",
               "hw": [{"icon": "glyph-cpu", "label": "CPU", "value": f"{nd.get('maxcpu', '?')} threads",
                       "sub": f"{round(nd.get('cpu', 0) * 100)} % load"},
                      {"icon": "glyph-ram", "label": "MEMORY", "value": f"{gib} GiB",
                       "sub": f"{round(nd.get('mem', 0) / 2 ** 30)} GiB used"}],
               "guests": []}
        for kind, path in (("VM", "qemu"), ("CT", "lxc")):
            for g in get(f"/nodes/{n}/{path}"):
                vmid = int(g["vmid"])
                conf = get(f"/nodes/{n}/{path}/{vmid}/config") or {}
                net0 = _kv(conf.get("net0", ""))
                ip = short_ip(net0.get("ip")) if kind == "CT" else short_ip(_kv(conf.get("ipconfig0", "")).get("ip"))
                if ip in ("dhcp", "manual"):
                    ip = None
                guest = {"id": vmid, "name": g.get("name", str(vmid)), "kind": kind, "ip": ip,
                         "icons": [icons.get(str(vmid)) or icons.get(g.get("name", "")) or "docker"],
                         "note": f"{g.get('cpus', g.get('maxcpu', '?'))} vCPU · {round(g.get('maxmem', 0) / 2 ** 30)} GB",
                         "internal": slug(g.get("name", vmid)), "source": "proxmox"}
                if net0.get("tag"):
                    guest["net"] = str(net0["tag"])
                if g.get("status") != "running":
                    guest["note"] += " · gestoppt"
                dev["guests"].append(guest)
        devices.append(dev)
    return {"devices": devices}
