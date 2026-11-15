"""Data checks before drawing, with clear German messages.

errors   → the drawing would be wrong or impossible: build stops
warnings → suspicious but drawable (printed, build goes on)
"""
import ipaddress

from .model import INFRA_ROLES

ROLES = INFRA_ROLES + ("ap", "server", "nas", "workstation", "kvm", "pi", "iot", "printer", "ups", "other")
KINDS = ("cable", "kvm", "wifi", "vpn")


def check(lab):
    err, warn = [], []
    nets = lab.net
    ids = set()
    for d in lab.devices:
        where = f"Gerät „{d.name}“ ({d.id})"
        if d.id in ids:
            err.append(f"{where}: die ID gibt es doppelt")
        ids.add(d.id)
        if d.role not in ROLES:
            warn.append(f"{where}: unbekannte Rolle „{d.role}“ (bekannt: {', '.join(ROLES)})")
        if d.net and d.net not in nets:
            err.append(f"{where}: Netz „{d.net}“ gibt es nicht (bekannt: {', '.join(nets)})")
        for p in d.ports:
            for k in ([p.untagged] if p.untagged else []) + p.tagged:
                if k not in nets:
                    err.append(f"{where}, Port {p.id}: VLAN „{k}“ gibt es nicht")
        vmids = set()
        for g in d.guests:
            gw = f"{where}, Gast „{g.name}“"
            if g.id in vmids:
                err.append(f"{gw}: VMID {g.id} gibt es doppelt auf diesem Host")
            vmids.add(g.id)
            if g.net and g.net not in nets:
                err.append(f"{gw}: Netz „{g.net}“ gibt es nicht")
            if not g.icons:
                err.append(f"{gw}: braucht mindestens ein Icon (icons: [...])")
    used_ports = {}
    for i, l in enumerate(lab.links):
        where = f"Verbindung {i + 1} ({l.a} ↔ {l.b})"
        if l.kind not in KINDS:
            err.append(f"{where}: unbekannte Art „{l.kind}“ (bekannt: {', '.join(KINDS)})")
        for end in (l.a, l.b):
            dev, port = l.split(end)
            if dev not in lab.dev:
                err.append(f"{where}: Gerät „{dev}“ gibt es nicht")
                continue
            dd = lab.dev[dev]
            if port and dd.port_row and not dd.port(port):
                err.append(f"{where}: Port „{port}“ gibt es an „{dd.name}“ nicht")
            if port and l.kind == "cable":
                if (dev, port) in used_ports:
                    err.append(f"{where}: Port {dev}.{port} ist schon belegt von {used_ports[(dev, port)]}")
                used_ports[(dev, port)] = where
        for k in ([l.net] if l.net else []) + l.vlans:
            if k not in nets:
                err.append(f"{where}: Netz/VLAN „{k}“ gibt es nicht")
    # IPs: inside the subnet of their network, no duplicates
    from .ips import collect
    seen = {}
    for e in collect(lab):
        try:
            a = ipaddress.ip_address(e["ip"])
        except ValueError:
            err.append(f"„{e['name']}“: „{e['ip']}“ ist keine gültige IP-Adresse")
            continue
        n = nets.get(e["net"]) if e["net"] else None
        if e.get("declared") and n and n.net and a not in n.net:
            warn.append(f"„{e['name']}“: {a} liegt nicht im Netz {n.name} ({n.subnet})")
        owner = e["name"].split(" · ")[0]
        if e["ip"] in seen and seen[e["ip"]] != owner:
            warn.append(f"IP {e['ip']} doppelt: „{seen[e['ip']]}“ und „{owner}“")
        seen.setdefault(e["ip"], owner)
    return err, warn
