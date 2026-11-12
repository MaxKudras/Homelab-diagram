#!/usr/bin/env python3
"""Download the third-party service icons into icons/.

They are not part of this repo (they belong to their projects). Source: the
homarr-labs/dashboard-icons collection via jsDelivr. The own glyph-*.svg icons
are already in icons/.

Usage: python3 fetch_icons.py           only the icons that are missing
       python3 fetch_icons.py --force   download all again (e.g. to get updated icons)
"""
import concurrent.futures
import pathlib
import shutil
import sys
import threading
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
ICONS = ROOT / "icons"
# tried in order; raw GitHub is the fallback when jsDelivr refuses a file
SOURCES = [
    "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/{}.svg",
    "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/{}.svg",
]

# local file name (as used in inventory.yaml / build.py) -> dashboard-icons name
ICON_MAP = {
    "actual": "actual-budget", "adguard": "adguard-home", "alloy": "alloy", "android": "android",
    "authentik": "authentik", "backblaze": "backblaze", "bazarr": "bazarr", "cinny": "cinny",
    "cloudflare": "cloudflare", "crowdsec": "crowdsec", "discord": "discord", "docker": "docker",
    "esphome": "esphome", "forgejo": "forgejo", "fritzbox": "fritzbox", "grafana": "grafana",
    "homeassistant": "home-assistant", "immich": "immich", "jellyfin": "jellyfin",
    "jellystat": "jellystat", "jetkvm": "jetkvm", "loki": "loki", "matrix-l": "matrix-light",
    "matter-l": "matter-light", "metube": "metube", "mikrotik-l": "mikrotik-light",
    "mosquitto": "mosquitto", "openspeedtest": "openspeedtest", "openwebui-l": "open-webui-light",
    "opnsense": "opnsense", "paperless": "paperless-ngx", "pelican": "pelican-panel",
    "penpot-l": "penpot-light", "prometheus": "prometheus", "prowlarr": "prowlarr",
    "proxmox": "proxmox", "qbittorrent": "qbittorrent", "radarr": "radarr", "seerr": "seerr",
    "signal": "signal", "sonarr": "sonarr", "stirling": "stirling-pdf", "tandoor": "tandoor-recipes",
    "traefik": "traefik", "truenas": "truenas-scale", "unifi": "unifi", "whatsapp": "whatsapp",
    "windows": "microsoft-windows", "wireguard": "wireguard", "zigbee2mqtt": "zigbee2mqtt",
}

# dark icons without a light variant: recolor them for the dark background
RECOLOR = {
    "ollama-l": ("ollama", 'fill="black"', 'fill="#e6edf3"'),
    "thread-l": ("thread", 'fill="#464646"', 'fill="#e6edf3"'),
}


DEAD = set()            # sources that refused the connection itself (blocked host): skip them from then on
_LOCK = threading.Lock()


def download(name, tries=3):
    """Fetch one icon from the first source that delivers it; retry with a short pause.
    A source that can't be reached at all (proxy/firewall refuses the host) is skipped for every
    later icon, instead of waiting out the retries each time."""
    last = None
    for url in SOURCES:
        if url in DEAD:
            continue
        req = urllib.request.Request(url.format(name), headers={"User-Agent": "homelab-diagram/1.0"})
        for attempt in range(tries):
            try:
                with urllib.request.urlopen(req, timeout=20) as r:
                    return r.read().decode("utf-8")
            except Exception as e:
                last = e
                code = getattr(e, "code", None)
                if code in (403, 404):                       # this source won't have it, try the next
                    break
                if code is None and ("tunnel" in str(e).lower() or "refused" in str(e).lower()):
                    with _LOCK:
                        DEAD.add(url)                        # host blocked: never try it again
                    break
                time.sleep(1 + attempt)
    raise last or RuntimeError("no source reachable")


def main():
    ICONS.mkdir(exist_ok=True)
    force = "--force" in sys.argv
    jobs = {local: (remote, None) for local, remote in ICON_MAP.items()}
    jobs.update({local: (remote, (old, new)) for local, (remote, old, new) in RECOLOR.items()})
    todo = {k: v for k, v in jobs.items() if force or not (ICONS / f"{k}.svg").exists()}
    failed = []

    def one(item):
        local, (remote, recolor) = item
        svg = download(remote)
        if recolor:
            svg = svg.replace(*recolor)
        (ICONS / f"{local}.svg").write_text(svg)

    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:   # parallel, still gentle
        futs = {ex.submit(one, it): it[0] for it in todo.items()}
        for f in concurrent.futures.as_completed(futs):
            if f.exception():
                local = futs[f]
                failed.append(f"{local} ({jobs[local][0]}): {f.exception()}")
    print(f"downloaded {len(todo) - len(failed)} of {len(todo)} missing icons in {time.time() - t0:.1f}s"
          + (f" (skipped unreachable: {', '.join(u.split('/')[2] for u in DEAD)})" if DEAD else ""))

    # CachyOS has no icon in dashboard-icons: use the one a CachyOS install ships, else the Arch logo
    system_logo = pathlib.Path("/usr/share/icons/cachyos.svg")
    try:
        if (ICONS / "cachyos.svg").exists() and not force:
            pass
        elif system_logo.exists():
            shutil.copy(system_logo, ICONS / "cachyos.svg")
        else:
            (ICONS / "cachyos.svg").write_text(download("arch-linux"))
    except Exception as e:
        failed.append(f"cachyos: {e}")

    print(f"icons in {ICONS}: {len(list(ICONS.glob('*.svg')))}")
    if failed:
        print("failed:\n  " + "\n  ".join(failed))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
