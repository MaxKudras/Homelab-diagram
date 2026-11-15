"""Shared helpers for the data sources: HTTP (read only), fixtures, ids.

Every source module has  collect(cfg) -> dict  returning a partial schema-2 lab
({devices: [...], links: [...], networks: [...], ip_extra: [...]}). Nothing is ever written to a
system: only GET requests. Secrets never live in files: cfg names an environment variable
(token_env) that holds the token.
"""
import json
import os
import pathlib
import re
import ssl
import urllib.request


class SourceError(Exception):
    pass


def slug(name):
    """Stable device id from a hostname: 'PVE1.home.lan' → 'pve1'."""
    s = str(name).split(".")[0].lower()
    return re.sub(r"[^a-z0-9_-]+", "-", s).strip("-")


def secret(cfg, key="token_env"):
    env = cfg.get(key)
    if not env or cfg.get("fixture"):        # offline test data needs no secret
        return None
    v = os.environ.get(env)
    if v is None:
        raise SourceError(f"Umgebungsvariable {env} ist nicht gesetzt (für {cfg.get('type')})")
    return v


def fixture(cfg, name):
    """Offline data: cfg['fixture'] is a JSON file {endpoint: response} used instead of HTTP."""
    f = cfg.get("fixture")
    if not f:
        return None
    data = json.loads(pathlib.Path(f).read_text())
    if name not in data:
        raise SourceError(f"Fixture {f} hat keinen Eintrag „{name}“")
    return data[name]


def get_json(cfg, path, headers=None, fixture_key=None):
    """GET url+path (JSON). With a fixture file the answer comes from there."""
    fx = fixture(cfg, fixture_key or path)
    if fx is not None or cfg.get("fixture"):
        return fx
    url = cfg["url"].rstrip("/") + path
    req = urllib.request.Request(url, headers={"Accept": "application/json", **(headers or {})})
    ctx = None
    if cfg.get("verify_tls", True) is False:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, timeout=cfg.get("timeout", 20), context=ctx) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise SourceError(f"{cfg.get('type')}: {url} nicht lesbar: {e}") from e


def short_ip(ip):
    """'10.0.20.5/24' → '10.0.20.5'."""
    return str(ip).split("/")[0] if ip else None
