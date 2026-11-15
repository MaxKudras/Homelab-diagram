#!/usr/bin/env python3
"""Generates examples/stress-60.yaml: 60 devices, 2 core + 3 access switches, 4 servers (test data)."""
import pathlib
import random

import yaml

random.seed(7)
nets = [("10", "MGMT", "10.10.10.0/24", "#e3b341"), ("20", "SERVER", "10.10.20.0/24", "#58a6ff"),
        ("40", "TRUSTED", "192.168.40.0/24", "#39c5cf"), ("50", "IOT", "192.168.50.0/24", "#3fb950"),
        ("80", "LAB", "172.16.80.0/24", "#ff7eb6")]
NV = [k for k, *_ in nets]
d = {"schema": 2, "meta": {"title": "Stresstest · 60 Geräte", "title_redacted": "Stresstest · 60 Geräte",
                            "date": "Testdaten", "watermark": "hld v2", "domain": "example.com"},
     "redact": {"domain": True, "domain_placeholder": "redacted.com", "ssid_names": True},
     "networks": [{"key": k, "name": n, "subnet": s, "color": c, "note": "Testnetz"} for k, n, s, c in nets]
     + [{"key": "wan", "tag": "Modem", "name": "WAN", "subnet": "192.168.0.0/24", "color": "#f85149", "note": "Uplink"}],
     "internet": {"label": "Internet", "sub": "Testanschluss", "speed": {"down": "1 Gbit/s", "up": "1 Gbit/s"}},
     "devices": [], "links": []}
D, L = d["devices"], d["links"]
D.append({"id": "modem", "role": "isp_router", "name": "Modem", "type": "ISP", "model": "Kabelmodem", "ip": "192.168.0.1",
          "net": "wan", "icons": ["fritzbox"], "ports": [{"id": "c", "label": "Cable", "kind": "coax", "uplink": True},
                                                          {"id": "l1", "label": "1G"}]})
D.append({"id": "fw", "role": "firewall", "name": "Firewall", "type": "router", "model": "Mini-PC", "ip": "10.10.10.1",
          "net": "10", "border": "trunk", "icons": ["opnsense"], "os": "OPNsense",
          "services": [{"icon": "wireguard", "name": "WireGuard", "note": "VPN"}], "ports": [{"id": "wan"}, {"id": "a"}, {"id": "b"}]})
L.append({"a": "modem.l1", "b": "fw.wan", "speed": "1G", "net": "wan"})
ip = 20


def sw(i, nports):
    return {"id": f"sw{i}", "role": "switch", "name": f"Switch {i}", "type": "switch", "model": "24-Port Managed",
            "ip": f"10.10.10.{i + 1}", "net": "10", "border": "trunk", "icons": ["cisco"],
            "ports": [{"id": f"p{j}", "label": str(j), "tagged": NV if j <= 2 else []} for j in range(1, nports + 1)]
            + [{"id": "x1", "label": "SFP+1", "kind": "sfp", "tagged": NV}, {"id": "x2", "label": "SFP+2", "kind": "sfp", "tagged": NV}]}


D += [sw(1, 16), sw(2, 16)]
L += [{"a": "fw.a", "b": "sw1.p1", "speed": "10G", "vlans": NV}, {"a": "fw.b", "b": "sw2.p1", "speed": "10G", "vlans": NV},
      {"a": "sw1.x1", "b": "sw2.x1", "speed": "10G", "vlans": NV}]
for i in (3, 4, 5):
    D.append(sw(i, 8))
    L.append({"a": f"sw{1 if i < 5 else 2}.p{i}", "b": f"sw{i}.p1", "speed": "1G", "vlans": NV})
icons = ["raspberrypi", "debian", "windows", "glyph-air", "bambulab", "unifi", "homeassistant", "glyph-antenna"]
n = 0
free = {1: list(range(6, 17)), 2: list(range(6, 17)), 3: list(range(2, 9)), 4: list(range(2, 9)), 5: list(range(2, 9))}
while n < 40 and any(free.values()):
    s = random.choice([1, 2, 3, 3, 4, 4, 5, 5])
    if not free[s]:
        continue
    p = free[s].pop(0)
    v = random.choice(NV)
    n += 1
    ip += 1
    net = dict(nets_ := {k: s_ for k, _, s_, _ in nets})[v]
    D.append({"id": f"d{n}", "role": "iot", "name": f"Gerät {n}", "type": random.choice(["Pi", "IoT", "PC", "Drucker"]),
              "model": random.choice(["Raspberry Pi 4", "Mini-PC", "Smart Plug", "Drucker", "NAS"]),
              "ip": net.rsplit(".", 1)[0][:-2] + f".{ip}" if False else net.split("/")[0].rsplit(".", 1)[0] + f".{ip}",
              "internal": f"geraet-{n}", "net": v, "icons": [random.choice(icons)],
              "status": random.choice(["active", "active", "planned"])})
    L.append({"a": f"sw{s}.p{p}", "b": f"d{n}", "speed": random.choice(["1G", "1G", "100M", "2.5G"]), "net": v})
for k in range(1, 5):
    D.append({"id": f"pve{k}", "role": "server", "name": f"pve{k}", "type": "server", "model": "Proxmox Node",
              "os": "Proxmox VE 9", "ip": f"10.10.20.{k}", "net": "20", "border": "trunk", "icons": ["proxmox"],
              "hw": [{"icon": "glyph-cpu", "label": "CPU", "value": "8 Kerne", "sub": "Test"}],
              "guests": [{"id": 100 * k + j, "ip": f".{100 + 20 * k + j}", "net": "20",
                          "group": "Dienste", "name": f"Dienst {k}.{j}", "icons": ["docker"], "note": "Test",
                          "internal": f"svc{k}{j}"} for j in range(1, 6)]})
    L.append({"a": f"sw{1 if k % 2 else 2}.p{2 + k // 2}" if False else f"sw{1 if k % 2 else 2}.x2" if k <= 2 else f"sw{k - 2}.p2",
              "b": f"pve{k}", "speed": "10G", "vlans": NV})
pathlib.Path(__file__).with_name("stress-60.yaml").write_text(
    "# TESTDATEN – automatisch erzeugt von make_stress.py\n" + yaml.safe_dump(d, sort_keys=False, allow_unicode=True))
