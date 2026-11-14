"""Prometheus targets → which devices/guests are monitored and whether they are up.

cfg: {type: prometheus, url: http://prometheus:9090}
Matches a target's instance (host or IP, port removed) against device/guest ids, hostnames and IPs.
The result is stored as extra field `monitor: up|down` on the device; render shows a small dot.
"""
from .base import get_json, slug


def collect(cfg):
    data = get_json(cfg, "/api/v1/targets", fixture_key="/api/v1/targets")
    targets = (data.get("data") or {}).get("activeTargets", [])
    seen = {}
    for t in targets:
        inst = (t.get("labels") or {}).get("instance") or t.get("scrapeUrl", "")
        host = inst.split("//")[-1].split("/")[0].rsplit(":", 1)[0]
        up = t.get("health") == "up"
        seen[host] = seen.get(host, True) and up      # down wins if one target of a host is down
    return {"_monitor": {h: ("up" if ok else "down") for h, ok in seen.items()}}


def apply(lab_d, mon):
    """Mark devices and guests whose id, hostname or IP is a monitored instance."""
    def match(o):
        keys = {str(o.get("id", "")), slug(o.get("name", "")), str(o.get("ip", "")).split(" ")[0],
                str(o.get("internal", "")), str(o.get("host", ""))}
        for k in keys:
            if k and k in mon:
                return mon[k]
        return None
    for d in lab_d.get("devices", []):
        m = match(d)
        if m:
            d["monitor"] = m
        for g in d.get("guests", []):
            m = match(g)
            if m:
                g["monitor"] = m
    return lab_d
