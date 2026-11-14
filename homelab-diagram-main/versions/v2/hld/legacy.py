"""Convert the original inventory.yaml (schema 1, one fixed lab) into schema 2.

Things the original build.py had hard-coded (link speeds read from the switch, which device
hangs on which port, the KVM console line, the LACP bundle) are written out here as data.
"""


def convert(inv):
    nets = [{"key": v["key"], "tag": v["tag"], "name": v["name"], "subnet": v["subnet"],
             "color": v["color"], "note": v["note"]} for v in inv["vlans"]]
    trunk_vlans = [v["key"] for v in inv["vlans"] if v["tag"].startswith("VLAN")]
    fb, opn, sw = inv["fritzbox"], inv["opnsense"], inv["switch"]
    dev = inv["devices"]
    T = inv["terra"]

    fb_ports = [{"id": "cable", "label": "Cable", "kind": "coax", "uplink": True, "note": "internet"}]
    for i, sp in enumerate(fb["lan_ports"]):
        p = {"id": f"lan{i + 1}", "label": sp}
        if i == fb["opnsense_port"]:
            p["note"] = "exposed host"
        fb_ports.append(p)
    fb_lan = f"lan{fb['opnsense_port'] + 1}"

    sw_ports = []
    for p in sw["ports"]:
        sfp = p["name"].startswith("sfpp")
        sw_ports.append({"id": p["name"], "label": ("SFP+" + p["name"][-1]) if sfp else p["name"].replace("ether", ""),
                         "kind": "sfp" if sfp else "rj45", "untagged": p.get("untagged"),
                         "tagged": p.get("tagged", []), "to": p["to"]})

    def device(key, role, **kw):
        d = dict(dev[key])
        d.update(id=key, role=role, net=d.pop("vlan"), **kw)
        if d.pop("trunk", False):
            d["border"] = "trunk"
        return d

    guests = []
    for k, g in T["other_guests"].items():
        g = dict(g)
        g.update(net=g.pop("vlan"), featured=True)
        guests.append(g)
    for grp in T["dmz_groups"]:
        for g in grp["guests"]:
            g = dict(g)
            g.update(net="20", group=grp["name"], kind=g.get("kind", "CT"))
            guests.append(g)

    devices = [
        {"id": "fritzbox", "role": "isp_router", "name": fb["name"], "type": fb["type"], "model": fb["model"],
         "ip": fb["ip"], "os": fb["os"], "net": "wan", "icons": ["fritzbox"], "ports": fb_ports},
        {"id": "opnsense", "role": "firewall", "name": opn["name"], "type": opn["type"], "model": opn["model"],
         "os": opn["os"], "ip": opn["ip"], "internal": opn.get("internal"), "net": "99", "border": "trunk",
         "icons": ["opnsense"], "hw": opn["hw"], "services": opn["services"],
         "ports": [{"id": "wan", "ip": opn["wan_ip"]}, {"id": "lan1"}, {"id": "lan2", "ip": ".1"}]},
        {"id": "mikrotik", "role": "switch", "name": sw["name"], "type": sw["type"], "model": sw["model"],
         "ip": sw["ip"], "internal": sw.get("internal"), "os": sw["os"], "config": sw.get("config", ""),
         "net": "99", "border": "trunk", "icons": ["mikrotik-l"], "ports": sw_ports},
        device("madcat", "workstation"),
        device("jetkvm", "kvm"),
        device("ap", "ap", ssids=inv.get("ssids", [])),
        device("slzb", "iot"),
        {"id": "terra", "role": "server", "name": T["name"], "type": T["type"], "model": T["model"],
         "os": T["os"], "ip": T["ip"], "internal": T.get("internal"), "net": "10", "border": "trunk",
         "icons": ["proxmox"], "hw": T["hw"], "guests": guests,
         "zones": {"20": {"note": "one unprivileged LXC per service · web apps behind Traefik (CT 149)"}}},
    ]
    links = [
        {"a": f"fritzbox.{fb_lan}", "b": "opnsense.wan", "speed": "1G", "net": "wan"},
        {"a": "mikrotik.ether1", "b": "opnsense.lan1", "speed": "2.5G", "vlans": trunk_vlans,
         "lag": "lacp", "lag_label": "LACP · dual 2.5G"},
        {"a": "mikrotik.ether2", "b": "opnsense.lan2", "speed": "2.5G", "vlans": trunk_vlans,
         "lag": "lacp", "lag_label": "LACP · dual 2.5G"},
        # speeds as negotiated on the switch (read 2026-11-07)
        {"a": "mikrotik.ether3", "b": "madcat", "speed": "2.5G", "net": "10"},
        {"a": "mikrotik.sfpp1", "b": "madcat", "speed": "10G", "net": "10"},
        {"a": "mikrotik.ether5", "b": "jetkvm", "speed": "100M", "net": "10"},
        {"a": "mikrotik.ether6", "b": "ap", "speed": "2.5G", "vlans": ["99", "10", "30", "40"]},
        {"a": "mikrotik.ether7", "b": "slzb", "speed": "100M", "net": "40"},
        {"a": "mikrotik.sfpp2", "b": "terra", "speed": "10G", "vlans": ["10", "20", "40", "99"]},
        {"a": "jetkvm", "b": "terra", "kind": "kvm", "label": "HDMI + USB console"},
    ]
    panels = []
    if T.get("media_pipeline"):
        panels.append(dict(T["media_pipeline"], type="media_pipeline"))
    return {
        "schema": 2,
        "meta": inv["meta"], "redact": inv["redact"], "networks": nets,
        "internet": {"label": "Internet", "sub": "semi-static public IPv4", "speed": inv["internet"]["speed"]},
        "remote": [dict(inv["remote"], icon="wireguard", net="vpn")],
        "cloud": inv["internet"].get("cloud_services", []),
        "devices": devices, "links": links,
        "port_forwards": inv.get("port_forwards", []),
        "panels": panels,
        "ip_extra": inv.get("ip_extra", []),
    }
