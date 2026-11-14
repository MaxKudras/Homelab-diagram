# Versionen des Diagramm-Tools

Jede größere Version ist hier als lauffähige Kopie eingefroren (Code + Daten + Beispielbild) und im Git als Tag `vN` markiert.
Alte Version rendern (aus `homelab-diagram-main/`, nach `python3 setup.py`):

```bash
python3 versions/v1/build.py            # → versions/v1/out/homelab.png
python3 versions/v1/build.py --variants # alle IP-Varianten dieser Version
```

| Version | Datum | Was |
|---|---|---|
| **v1** | 14.11.2026 | Original-Tool von u/goblinmine mit festem Layout (1 Firewall, 1 Switch, 4 Geräte, 1 Server) + IP-Liste (`--ips=table/inline/both/sheet`). |
