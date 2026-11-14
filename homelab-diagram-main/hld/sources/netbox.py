"""NetBox (IPAM / DCIM, the 'source of truth') → networks, devices with ports, cables, VMs.

cfg: {type: netbox, url: https://netbox.lan, token_env: NETBOX_TOKEN, role_map: {slug: role}}
Read only (GET on the REST API). Cables become links, interface modes become port VLANs.
"""
from .base import get_json, secret, short_ip, slug

ROLE_MAP = {"firewall": "firewall", "router": "router", "switch": "switch", "core-switch": "switch",
            "access-switch": "switch", "access-point": "ap", "ap": "ap", "server": "server",
            "hypervisor": "server", "nas": "nas", "storage": "nas", "pi": "pi", "workstation": "workstation",
            "kvm": "kvm", "ups": "ups", "iot": "iot", "printer": "printer", "modem": "isp_router",
            "isp-router": "isp_router"}
ICONS = {"firewall": "opnsense", "router": "opnsense", "switch": "glyph-switch", "server": "proxmox", "nas": "omv",
         "pi": "raspberrypi", "ap": "glyph-antenna", "kvm": "glyph-kvm", "ups": "glyph-ups", "isp_router": "fritzbox",
         "iot": "glyph-antenna", "printer": "glyph-antenna", "workstation": "debian"}
SPEED_BY_TYPE = {"100base-tx": "100M", "1000base-t": "1G", "2.5gbase-t": "2.5G", "5gbase-t": "5G",
                 "10gbase-t": "10G", "10gbase-x-sfpp": "10G", "25gbase-x-sfp28": "25G", "1000base-x-sfp": "1G"}
STATUS = {"active": "active", "planned": "planned", "staged": "planned", "offline": "later", "inventory": "later"}


def _all(cfg, path):
    """GET every page of a NetBox list endpoint."""
    tok = secret(cfg)
    h = {"Authorization": f"Token {tok}"} if tok else {}
    out, url = [], path + ("&" if "?" in path else "?") + "limit=1000"
    while url:
        page = get_json(cfg, url, h, fixture_key=path)
        out += page.get("results", [])
        nxt = page.get("next")
        url = nxt[nxt.index("/api"):] if nxt and not cfg.get("fixture") else None
    return out


def _speed(itf):
    if itf.get("speed"):
        kb = itf["speed"]
        return {100000: "100M", 1000000: "1G", 2500000: "2.5G", 5000000: "5G", 10000000: "10G",
                25000000: "25G", 40000000: "40G"}.get(kb, "1G")
    return SPEED_BY_TYPE.get((itf.get("type") or {}).get("value", ""), "1G")


def collect(cfg):
    role_map = {**ROLE_MAP, **(cfg.get("role_map") or {})}
    vlans = _all(cfg, "/api/ipam/vlans/")
    prefixes = _all(cfg, "/api/ipam/prefixes/")
    nets = {}
    for v in vlans:
        nets[str(v["vid"])] = {"key": str(v["vid"]), "name": v["name"], "note": v.get("description", ""),
                               "source": "netbox"}
    for p in prefixes:
        if p.get("vlan"):
            k = str(p["vlan"]["vid"])
            nets.setdefault(k, {"key": k, "name": p["vlan"].get("name", k), "source": "netbox"})["subnet"] = p["prefix"]
    devices = {}
    for d in _all(cfg, "/api/dcim/devices/"):
        rs = (d.get("role") or d.get("device_role") or {}).get("slug", "")
        role = role_map.get(rs, "other")
        dt = d.get("device_type") or {}
        model = " ".join(x for x in ((dt.get("manufacturer") or {}).get("name"), dt.get("model")) if x)
        dev = {"id": slug(d["name"]), "role": role, "name": d["name"], "type": (d.get("role") or d.get("device_role") or {}).get("name", role),
               "model": model, "ip": short_ip((d.get("primary_ip4") or {}).get("address")) or "",
               "os": (d.get("platform") or {}).get("name", ""), "internal": slug(d["name"]),
               "status": STATUS.get((d.get("status") or {}).get("value"), "active"),
               "icons": [ICONS.get(role, "glyph-antenna")], "source": "netbox"}
        cf = d.get("custom_fields") or {}
        for k in ("mythos", "net"):
            if cf.get(k):
                dev[k] = str(cf[k])
        devices[d["id"]] = dev
    itfs = {}
    for i in _all(cfg, "/api/dcim/interfaces/"):
        itfs[i["id"]] = i
        did = (i.get("device") or {}).get("id")
        dev = devices.get(did)
        if not dev or dev["role"] not in ("switch", "isp_router"):
            continue
        typ = (i.get("type") or {}).get("value", "")
        port = {"id": i["name"], "label": i.get("label") or i["name"].split("/")[-1],
                "kind": "sfp" if "sfp" in typ or "-x" in typ else "rj45"}
        if dev["role"] == "isp_router" and (i["name"].lower() in ("cable", "dsl", "fiber", "docsis", "gpon")
                                            or typ in ("docsis", "xdsl", "gpon", "other")):
            port.update(kind="coax", uplink=True, note="internet")
        if i.get("untagged_vlan"):
            port["untagged"] = str(i["untagged_vlan"]["vid"])
        if i.get("tagged_vlans"):
            port["tagged"] = [str(v["vid"]) for v in i["tagged_vlans"]]
        dev.setdefault("ports", []).append(port)
    links = []
    for c in _all(cfg, "/api/dcim/cables/"):
        ends = []
        for side in ("a_terminations", "b_terminations"):
            t = (c.get(side) or [{}])[0]
            obj = t.get("object") or {}
            itf = itfs.get(t.get("object_id") or obj.get("id")) or obj
            devn = (itf.get("device") or {}).get("name")
            if not devn:
                break
            ends.append((slug(devn), itf.get("name"), itf))
        if len(ends) != 2:
            continue
        (da, pa, ia), (db, pb, ib) = ends
        l = {"a": f"{da}.{pa}", "b": f"{db}.{pb}", "speed": _speed(ia), "source": "netbox"}
        tagged = ia.get("tagged_vlans") or ib.get("tagged_vlans")
        unt = ia.get("untagged_vlan") or ib.get("untagged_vlan")
        if tagged:
            l["vlans"] = ([str(unt["vid"])] if unt else []) + [str(v["vid"]) for v in tagged]
        elif unt:
            l["net"] = str(unt["vid"])
        links.append(l)
    # VMs → guests of their host device
    by_name = {d["name"]: d for d in devices.values()}
    for vm in _all(cfg, "/api/virtualization/virtual-machines/"):
        host = by_name.get((vm.get("device") or {}).get("name"))
        if not host:
            continue
        cf = vm.get("custom_fields") or {}
        g = {"id": int(cf.get("vmid") or 0), "name": vm["name"], "kind": cf.get("kind", "VM"),
             "ip": short_ip((vm.get("primary_ip4") or {}).get("address")), "icons": [cf.get("icon") or "docker"],
             "note": vm.get("description") or (vm.get("role") or {}).get("name", ""), "internal": slug(vm["name"]),
             "source": "netbox"}
        if cf.get("net"):
            g["net"] = str(cf["net"])
        host["role"] = "server"
        host.setdefault("guests", []).append(g)
    return {"networks": list(nets.values()), "devices": list(devices.values()), "links": links}
