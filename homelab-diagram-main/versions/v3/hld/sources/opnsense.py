"""OPNsense API → DHCP leases (addresses without their own card) and WireGuard peers.

cfg: {type: opnsense, url: https://fw.lan, key_env: OPN_KEY, secret_env: OPN_SECRET, verify_tls: false}
Read only: /api/dhcpv4/leases/searchLease, /api/wireguard/client/searchClient.
Leases of hosts that already have a card are skipped later by the IP list (same IP = same entry).
"""
import base64

from .base import get_json, secret


def collect(cfg):
    key, sec = secret(cfg, "key_env"), secret(cfg, "secret_env")
    h = {"Authorization": "Basic " + base64.b64encode(f"{key}:{sec}".encode()).decode()} if key else {}
    out = []
    leases = get_json(cfg, "/api/dhcpv4/leases/searchLease", h, fixture_key="/api/dhcpv4/leases/searchLease")
    for l in leases.get("rows", []):
        if l.get("address"):
            out.append({"ip": l["address"], "name": l.get("hostname") or l.get("mac", "?"),
                        "kind": "DHCP" if l.get("type") != "static" else "static", "source": "opnsense"})
    peers = get_json(cfg, "/api/wireguard/client/searchClient", h, fixture_key="/api/wireguard/client/searchClient")
    for p in peers.get("rows", []):
        for addr in str(p.get("tunneladdress", "")).split(","):
            if addr.strip():
                out.append({"ip": addr.strip().split("/")[0], "name": p.get("name", "peer"), "kind": "wg peer",
                            "source": "opnsense"})
    return {"_ips": out}
