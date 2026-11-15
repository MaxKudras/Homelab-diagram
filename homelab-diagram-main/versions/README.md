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
| **v2** | 14.11.2026 | Neue Engine `hld/`: beliebig viele Geräte, Switches, Firewalls und Server; Positionen und Kabelwege werden berechnet (Ebenen, Kabel-Router mit Spuren, Umbruch, Redundanz-Paare); Datenprüfung und Überlappungs-QA; Datenquellen Ansible, NetBox, Proxmox, Prometheus, OPNsense (`--collect`); Beispiel-Labs in `examples/` (`--examples`). |
| **v3** | 15.11.2026 | Zwei neue Ansichten neben den Reihen (v2): `--layout=cluster` (Baum-Block je Switch, Kamm ohne Kreuzungen) und `--layout=flow` (links → rechts). Flächen-Router (A*), QA für aufeinanderliegende Kabel, Bewertung je Bild, Vergleichsseite `vergleich.py`. `example.png` = Zukunftsplan in der Cluster-Ansicht. |
