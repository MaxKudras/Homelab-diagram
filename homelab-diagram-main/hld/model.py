"""Data model (schema 2).

A lab is a dict (YAML) with these top-level keys; everything except meta/networks/devices is
optional:

  meta:        {title, title_redacted, date, watermark, domain}
  redact:      {domain: true, domain_placeholder, ssid_names: true}
  networks:    [{key, tag, name, subnet, color, note}]            VLANs, VPN, WAN …
  internet:    {label, sub, speed: {down, up}}
  remote:      [{name, note, icon, net}]                          clients that come in over the internet
  cloud:       [{icon, name, note}]                               cloud services (dotted from the internet)
  devices:     [{id, role, name, type, model, os, ip, net, icons, ports: [...], hw, services, ssids,
                 guests: [...], status, mythos, redundant_with, ...}]
  links:       [{a: "dev.port", b: "dev.port", speed, net | vlans, kind, label, lag}]
  port_forwards, panels (media_pipeline / flow), ip_extra

Roles: isp_router, firewall, router, switch, ap, server, nas, workstation, kvm, pi, iot, printer,
ups, other. Link kinds: cable (default), kvm (console), wifi, vpn.
Every object keeps unknown keys in .extra, and `source` tells where a value came from (for the GUI).
"""
from dataclasses import dataclass, field, fields
import ipaddress

INFRA_ROLES = ("isp_router", "firewall", "router", "switch")
PORT_ROW_ROLES = ("isp_router", "switch")      # cards that draw their own row of jacks


def _from(cls, d):
    names = {f.name for f in fields(cls)}
    obj = cls(**{k: v for k, v in d.items() if k in names})
    obj.extra = {k: v for k, v in d.items() if k not in names}
    return obj


@dataclass
class Network:
    key: str
    name: str = ""
    tag: str = ""
    subnet: str = ""
    color: str = "#8d9aab"
    note: str = ""
    source: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.key = str(self.key)
        self.tag = self.tag or (f"VLAN {self.key}" if self.key.isdigit() else self.name)

    @property
    def net(self):
        return ipaddress.ip_network(self.subnet, strict=False) if self.subnet else None


@dataclass
class Port:
    id: str
    label: str = ""
    kind: str = "rj45"          # rj45 | sfp | coax
    untagged: str = None
    tagged: list = field(default_factory=list)
    to: str = None              # caption under the port (default: the linked device's name)
    note: str = None            # small text under an ISP-router port ("exposed host")
    ip: str = None              # address shown next to a jack (".20")
    uplink: bool = False        # the port the internet comes in on
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)
        self.untagged = str(self.untagged) if self.untagged is not None else None
        self.tagged = [str(t) for t in self.tagged or []]


@dataclass
class Guest:
    id: int = 0                 # VMID
    name: str = ""
    kind: str = "CT"            # CT | VM
    net: str = None
    ip: str = None
    host: str = None            # public name → host.domain (blue)
    internal: str = None        # name.internal
    exposure: str = None        # public | local
    icons: list = field(default_factory=list)
    note: str = ""
    apps: list = field(default_factory=list)
    docker: bool = False
    group: str = None           # chip group heading inside a zone
    featured: bool = False      # big guest card instead of a chip
    badge: str = None
    pools: list = field(default_factory=list)
    addons: list = field(default_factory=list)
    addons_text: str = ""
    footer: str = ""
    source: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.net = str(self.net) if self.net is not None else None


@dataclass
class Device:
    id: str
    role: str = "other"
    name: str = ""
    type: str = ""
    model: str = ""
    os: str = ""
    ip: str = ""
    internal: str = None
    host: str = None
    net: str = None
    icons: list = field(default_factory=list)
    ports: list = field(default_factory=list)
    hw: list = field(default_factory=list)
    services: list = field(default_factory=list)
    ssids: list = field(default_factory=list)
    config: str = ""
    guests: list = field(default_factory=list)
    zones: dict = field(default_factory=dict)     # net key → {note, columns}
    ip_labels: list = field(default_factory=list)
    status: str = "active"      # active | planned | later
    mythos: str = ""
    redundant_with: str = None
    border: str = None          # "trunk" → neutral border
    source: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.id = str(self.id)
        self.net = str(self.net) if self.net is not None else None
        self.name = self.name or self.id
        self.ports = [p if isinstance(p, Port) else _from(Port, p) for p in self.ports]
        self.guests = [g if isinstance(g, Guest) else _from(Guest, g) for g in self.guests]

    def port(self, pid):
        return next((p for p in self.ports if p.id == str(pid)), None)

    @property
    def port_row(self):
        return self.role in PORT_ROW_ROLES and bool(self.ports)

    @property
    def is_server(self):
        return bool(self.guests) or self.role == "server" and bool(self.hw)


@dataclass
class Link:
    a: str
    b: str
    speed: str = "1G"
    net: str = None             # access VLAN (untagged)
    vlans: list = field(default_factory=list)   # tagged VLANs → trunk
    kind: str = "cable"         # cable | kvm | wifi | vpn
    label: str = None           # text along the line (kvm: "HDMI + USB console")
    lag: str = None             # links with the same lag id are drawn as a bundle (LACP)
    lag_label: str = None
    source: str = ""
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.a, self.b = str(self.a), str(self.b)
        self.net = str(self.net) if self.net is not None else None
        self.vlans = [str(v) for v in self.vlans or []]
        self.speed = str(self.speed)

    @staticmethod
    def split(end):
        dev, _, port = end.partition(".")
        return dev, (port or None)

    @property
    def a_dev(self):
        return self.split(self.a)[0]

    @property
    def b_dev(self):
        return self.split(self.b)[0]

    @property
    def trunk(self):
        return bool(self.vlans)

    def port_of(self, dev):
        for end in (self.a, self.b):
            d, p = self.split(end)
            if d == dev:
                return p
        return None

    def other(self, dev):
        return self.b_dev if self.a_dev == dev else self.a_dev


class Lab:
    def __init__(self, d):
        self.raw = d
        self.meta = d.get("meta", {})
        self.redact = d.get("redact", {})
        self.networks = [n if isinstance(n, Network) else _from(Network, n) for n in d.get("networks", [])]
        self.net = {n.key: n for n in self.networks}
        self.internet = d.get("internet", {})
        self.remote = d.get("remote", [])
        self.cloud = d.get("cloud", [])
        self.devices = [x if isinstance(x, Device) else _from(Device, x) for x in d.get("devices", [])]
        self.dev = {x.id: x for x in self.devices}
        self.links = [x if isinstance(x, Link) else _from(Link, x) for x in d.get("links", [])]
        self.port_forwards = d.get("port_forwards", [])
        self.panels = d.get("panels", [])
        self.ip_extra = d.get("ip_extra", [])

    def color(self, key):
        n = self.net.get(str(key)) if key is not None else None
        return n.color if n else "#8d9aab"

    def links_of(self, dev):
        return [l for l in self.links if dev in (l.a_dev, l.b_dev)]

    def full_ip(self, key, ip, base=None):
        """'.49' → '10.0.20.49' (host part in the network's subnet, or in base's /24)."""
        ip = str(ip).strip()
        if ip.startswith("."):
            if base:
                pre = base
            elif key in self.net and self.net[key].net:
                pre = str(self.net[key].net.network_address)
            else:
                return ip
            return pre.rsplit(".", 1)[0] + ip
        return ip

    def net_of_ip(self, ip):
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            return None
        return next((n.key for n in self.networks if n.net and a in n.net), None)
