# CLAUDE.md – Homelab-Diagramm-Tool

Diese Datei ist die Hauptanleitung für dieses Repo. Lies sie bei jeder Sitzung zuerst.

## Was dieses Repo ist

| Ordner | Inhalt | Rolle |
|---|---|---|
| `homelab-diagram-main/` | Das **Homelab-Diagramm-Tool** (Python: YAML → SVG → PNG) | **Hier wird gearbeitet.** Ziel: das Tool massiv verbessern, Features ergänzen, perfekt aussehen lassen. |
| `Vorherige plaene/` | Max' frühere Planungsprojekte (HTML-Tools + seine Angaben als Text) | **Nur Kontext, nicht ändern.** Zeigt, wie Max plant, was er will und wie sein Homelab werden soll. |

Herkunft des Tools: Es stammt ursprünglich von *u/goblinmine* (MIT-Lizenz, `LICENSE` behalten) und zeigt in `inventory.yaml` noch **dessen** Beispiel-Homelab (OPNsense, MikroTik, Proxmox-Server „terra“, TrueNAS, DMZ-LXCs, *arr-Pipeline). Max' eigenes Homelab ist **geplant, aber noch kaum gebaut** (siehe unten). `homelab-diagram-main/CLAUDE.md` ist die englische Original-Anleitung des Autors zum „Anpassen an ein fremdes Lab“ (Interview-Fragen, Designregeln). Sie gilt weiter als Referenz. Bei Widersprüchen gilt **diese** Datei.

---

## So arbeiten wir (verbindlich)

1. **Immer genau eine Aufgabe.** Max gibt eine Aufgabe, ich setze sie **komplett** um. Erst danach kommt die nächste. Nichts Ungefragtes „nebenbei“ umbauen. Ideen für später nur am Ende kurz vorschlagen.
2. **Fertig heißt:**
   - Code geändert und `python3 build.py` läuft ohne Fehler und ohne `assert`-Abbruch.
   - **Ich habe das PNG selbst angesehen**, gesamt und in Ausschnitten (siehe „Prüfen“). Es gibt keine Überlappungen, keinen Text, der aus Boxen läuft, keine Kabel quer durch Karten und keine leeren Löcher.
   - Nichts anderes ist kaputtgegangen: Vorher/Nachher-Vergleich des Renders, und die Teile außerhalb der Aufgabe sehen unverändert aus.
   - Die geschwärzte Version (Standard-Render) enthält keine privaten Daten.
   - Die Arbeit ist committet und auf den Arbeits-Branch gepusht.
3. **Zurückmelden:** kurz auf Deutsch sagen, was geändert wurde, wie geprüft wurde und was auffiel. Das Ergebnisbild mitschicken.
4. **Qualität vor Tempo:** Es soll richtig gut aussehen und richtig informativ sein, aber klar, nicht eng oder überladen. Man muss sehen, wo jede Verbindung hingeht.
5. **Sprache:** Mit Max immer **Deutsch**. Code, Kommentare und YAML-Schlüssel bleiben im bestehenden Stil (Englisch), solange Max nichts anderes sagt.

---

## Das Tool im Detail (`homelab-diagram-main/`)

### Dateien

- `inventory.yaml` enthält **alle Inhalte**: VLANs, ISP-Router, Firewall, Switch-Ports, Geräte, SSIDs, Portweiterleitungen, Server-Hardware, VMs/CTs, DMZ-Gruppen, Pools und Media-Pipeline.
- `build.py` (~920 Zeilen) enthält das **handplatzierte Layout**. Es zeichnet eine SVG mit absoluten Koordinaten (Canvas `W=2400`, `H=2326`), bettet Icons als Base64 ein und wandelt mit `rsvg-convert -z 1.6` in PNG um (PNG-Pixel = SVG-Einheit × 1,6 → 3840 × 3722 px).
- `setup.py` richtet alles ein (Fonts aus `fonts/`, rsvg-convert, Icons), `--check-fonts`/`--update-fonts` prüfen bzw. holen neue Font-Versionen.
- `fetch_icons.py` lädt die Dienst-Icons aus `homarr-labs/dashboard-icons` nach `icons/`. Nur die eigenen `icons/glyph-*.svg` (CPU, RAM, SSD, HDD, NIC, GPU, DHCP, Schild, Block, Antenne) sind im Git.
- `docs/example.png` ist das Referenzbild (so sieht der unveränderte Stand aus).
- `out/` ist die Ausgabe (gitignored): `homelab.svg/png` (geschwärzt) und `homelab-unredacted.*` (mit `--unredacted`).

### Aufbau von `build.py` (Reihenfolge im Code)

1. **Konstanten & Palette**: dunkles GitHub-artiges Theme (`BG #0b0f15`, `PANEL`, `CHIP`, `TEXT`, `MUTED`, `FAINT`), `SPEED_W` (Linienbreite je Geschwindigkeit), VLAN-Farben aus der YAML (`C[key]`).
2. **Helfer**:
   - `sub()`/`esc()` füllen `{domain}` und schwärzen.
   - `tw()` schätzt grob die Textbreite. `measure()` misst sie exakt mit Pillow und der echten Fira Sans.
   - Klasse `SVG` mit `rect`, `text`, `icon`, `line`, `trunk`, `arrow`, `pill`, `label` (Text mit Hintergrund-Aussparung). `rounded()` erzeugt orthogonale Linien mit runden Ecken.
3. **Bausteine**:
   - `card()`, `device_card()` (Ordner-Reiter-Karte für physische Geräte, `folder()` + `tab_width()`), `hw_bar()` (hellbraune Hardware-Leiste).
   - `jack()` (RJ45/SFP-Buchse), `ticks()` (VLAN-Striche an Ports), `vlan_tag()`, `addr()` (IP · Hostname).
4. **Sektionen** (im Code mit `# ====` markiert):
   - Header: Titel, Watermark, Datum.
   - `TOP: edge chain`: Internet-Wolke, Fernzugriff, Cloud-Dienste, FRITZ!Box mit Ports, OPNsense (Hardware + Dienste), LACP-Trunk.
   - `switch`: Ports aus der YAML, `port_x()` mit `PX0`/`PITCH`.
   - `device row` (`DY`): MADCAT, JetKVM, AP + SSIDs, SLZB. Die Kabelwege zu den Geräten sind von Hand geführt.
   - `open to the internet`: Portweiterleitungen.
   - `legend` und `VLAN table` (linke Spalte).
   - `terra`: große Server-Karte mit Hardware-Liste, Gästen außerhalb der DMZ (TrueNAS mit Pools/Disks, HAOS, UniFi, BlissOS) und der DMZ-Zone mit 4 Spalten (`column(i, [Gruppen])`) aus `chip()`/`chip_apps()`.
   - `media pipeline`: Erklär-Panel rechts.
5. **Ausgabe**: `assert` für Canvas-Höhe, SVG schreiben, `rsvg-convert` aufrufen.

**Generisch** (kommt aus der YAML): VLAN-Tabelle, Legende, Portweiterleitungen, Cloud-Dienste, Firewall-Hardware/-Dienste, Switch-Ports, Gerätekarten, SSIDs, Hardware-Kacheln, DMZ-Gruppen/-Chips, Pools.
**Hartkodiert** (Koordinaten in `build.py`): Positionen aller großen Blöcke, Anzahl/Art der Geräte in der Gerätezeile und deren Kabelwege, die 4 festen „other guests“, die Zuordnung der DMZ-Spalten und die komplette Media-Pipeline. Details stehen in der Tabelle in `homelab-diagram-main/CLAUDE.md`.

### Sicherheitsnetze

`assert`s brechen ab, wenn Hardware-Liste, DMZ-Spalte, Pipeline-Panel oder Canvas überlaufen. Dann `H`, `ZH` usw. vergrößern oder umverteilen, **nie** einfach das Assert löschen.

### Designregeln (beibehalten, außer Max will es anders)

- **Linienbreite = ausgehandelte Link-Geschwindigkeit** (`SPEED_W`), dazu ein kleines Speed-Label am Geräteeingang.
- **Trunk** (getaggte VLANs) = helles Kabel mit dunklem Kern. Access-Links haben die VLAN-Farbe.
- Durchgezogen = physisches Kabel. Gepunktet = logisch über das Internet (VPN, Cloud). Grau gestrichelt = KVM-Konsole.
- **Kartenrand = VLAN-Farbe** des Geräts. Geräte am Trunk bekommen `TRUNK_BORDER`.
- Physische Geräte nutzen die **Ordner-Reiter-Karte**: Reiter = `Name · Typ`, darunter Icon, Modell, `IP · Hostname` (VLAN-Farbe), OS + Version.
- Hardware-Kacheln haben die hellbraune Leiste links: Label = Typ, Wert = Bauteil, Unterzeile = Info oder `passthrough → Gast`.
- DMZ-Chips: `CT <id>` oben rechts, `.<Oktett>` darunter. Hostname in Blau = öffentlich über den Reverse Proxy, `name.internal` = nur lokal, `LAN`-Pill = öffentlicher Name, aber nur LAN/VPN.
- Multi-App-Container werden **eine** hohe Karte mit einer Zeile pro App. Das Docker-Badge gibt es nur bei Multi-App-Docker-CTs.
- Keine internen Ports, nur Portweiterleitungen aus dem Internet.
- ZFS in TiB/GiB, Platten in TB (wie verkauft). Texte kurz und sachlich.
- Kabel, die von oben in eine Gerätekarte gehen, treffen **rechts vom Reiter** ein (`tab_width()`).

---

## Umgebung & Befehle

```bash
cd homelab-diagram-main
python3 setup.py                # Fonts + rsvg-convert + Icons (einmal pro Sitzung, ~5 s)
python3 build.py                # → out/homelab.svg + out/homelab.png (geschwärzt)
python3 build.py --unredacted   # → out/homelab-unredacted.*
python3 build.py --ips=table    # IP-Varianten: table | inline | both | sheet → out/homelab-ips-<variante>.*
python3 build.py --variants     # alle Varianten auf einmal (Standard + 4 IP-Varianten)
```

**IP-Liste:** `collect_ips()` sammelt jede genutzte Adresse aus der YAML (Karten, Gäste, DMZ, OPNsense `.1` je Trunk-VLAN) plus `ip_extra` (Adressen ohne eigene Karte, z. B. VPN-Peers). Doppelt vergebene IPs werden rot markiert. `table` = Liste unter terra (Canvas wird höher), `inline` = volle IPs auf den DMZ-Chips, `both` = beides, `sheet` = Liste als eigenes Bild mit Hostnamen. Ohne `--ips` bleibt das Bild unverändert.

Abhängigkeiten: Python 3 + PyYAML + Pillow, `rsvg-convert` (librsvg) und die Fonts **Fira Sans** und **Fira Code**. Ohne Fira Sans stimmen alle Textbreiten nicht.

**Einrichtung (Cloud-Sitzung oder neuer PC), ein Befehl, ~5 Sekunden:**

```bash
cd homelab-diagram-main && python3 setup.py
```

Das installiert die Fonts **aus dem Repo** (`fonts/`: Fira Sans + Fira Code, OFL-Lizenz) nach `~/.local/share/fonts/homelab-diagram`, installiert `rsvg-convert` per apt falls es fehlt (als root) und lädt fehlende Icons **parallel**. `cdn.jsdelivr.net` ist in der Cloud gesperrt. `fetch_icons.py` merkt das beim ersten Fehlversuch und nimmt danach direkt `raw.githubusercontent.com` (vorher ~7 Min., jetzt ~2 s). `python3 fetch_icons.py --force` lädt alle Icons neu.

**Fonts aktuell halten:** `python3 setup.py --check-fonts` vergleicht `fonts/` mit dem neuesten Stand (Fira Sans: SHA-256 gegen `mozilla/Fira` master; Fira Code: Versionsnummer aus dem README von `tonsky/FiraCode`). `python3 setup.py --update-fonts` lädt neuere Dateien nach `fonts/` und trägt sie in `fonts/fonts.json` ein. Danach neu rendern, vergleichen und committen.

ImageMagick heißt hier `convert`, nicht `magick`.

**Geprüft am 12.11.2026:** Mit diesem Setup rendert der unveränderte Stand fehlerfrei. Gegenüber `docs/example.png` liegt die mittlere Pixelabweichung bei ~0,9/255. Das ist nur Kantenglättung bzw. Font-Version, Layout und Inhalt sind identisch. Diese Abweichung ist also normal und kein Fehler.

---

## Prüfen (vor jeder Rückmeldung)

1. **Vorher-Bild sichern:** `cp out/homelab.png <scratchpad>/before.png` (vor der Änderung).
2. `python3 build.py`. Es muss ohne Fehler und ohne Assert durchlaufen.
3. **Gesamtbild ansehen** (verkleinert): `convert out/homelab.png -resize 30% <scratchpad>/full.png` und mit Read öffnen.
4. **Ausschnitte ansehen** an der geänderten Stelle und an dichten Bereichen. Koordinaten mal 1,6 rechnen: `convert out/homelab.png -crop 1400x900+X+Y +repage <scratchpad>/crop.png`.
5. **Diff gegen vorher:** mit Pillow `ImageChops.difference(...).getbbox()`. Die Änderung darf nur dort sein, wo sie hingehört.
6. **Privatsphäre:** `grep` in `out/homelab.svg` nach echter Domain, SSIDs usw. Sie dürfen nur in `--unredacted` erscheinen.
7. Ergebnis-PNG an Max schicken.

## Git

- Arbeits-Branch: siehe Sitzungsvorgabe (aktuell `claude/ecstatic-planck-8tlt5r`). Basis ist `main`.
- `out/`, `__pycache__/` und heruntergeladene Icons werden nicht committet (`.gitignore`).
- Nach jeder abgeschlossenen Aufgabe committen und pushen, Commit-Nachricht auf Deutsch, knapp und sachlich.

---

## Kontext: Wer Max ist und wie er plant

Quellen: `Vorherige plaene/Homelab aufteilung/Meine Angaben fuer homelab aufteilung`, `…/homelab-02-reife-atlas.html`, `Vorherige plaene/Homelab planner/Meine Angaben fuer homelab planner`, `…/neun-welten(1).html`.

### Arbeitsweise und Geschmack

- Er will **bewusst overengineered** arbeiten: alles durchgeplant, viele Schichten, viele Schritte, „immer weiter, ausführlicher, durchdachter“. **Aber jede Komplexität braucht einen Zweck.**
- Lieber viel und vielfältig als wenig.
- Optik: **cool, schön, informativ, aber nicht eng oder überladen**. Klare Linien, man sieht, wohin jede Verbindung geht.
- Bedienung: nicht durch viele Bereiche klicken müssen. Das Wichtige soll auf einen Blick da sein.
- Lieferform seiner Pläne: eigenständige **HTML-Dateien** für Browser und Handy, kein Artifact. Entscheidungen sollen gespeichert bleiben.
- Bestehende Diagramme lieber **nicht ersetzen, sondern neue Ansichten dazubauen**, damit er vergleichen und später aussortieren kann.
- **Benennung:** Funktion als Hauptname, der Mythologie-Name nur klein daneben. Hardware/Netzwerk tragen nordische Namen.
- Hintergrund: Fachinformatiker-Ausbildung, CCNA-Vorbereitung, Lernwert zählt mit.

### Sein geplantes Homelab (Stand Planung, kaum gebaut)

- Privat, zu Hause, **alte/gebrauchte, unspezialisierte Hardware**, möglichst alles selbst gehostet und kostenlos. Er will trotzdem Rechenzentrums-Features (HA, Monitoring, Backup …).
- **Proxmox auf jedem Server**, Debian auf allen Linux-Geräten. Der erste Node ist **PVE1** (alter PC, wird Workload-Node „Midgard“).
- Geräte-Rollen aus „Neun Welten“ (`NW.D`):
  - Provider-Modem *Ásbrú* (Bridge)
  - Firewall & Router *Heimdall* (Mini-PC mit mehreren Intel-NICs, OPNsense), Ersatz-Firewall *Víðarr* (später)
  - Core-Switch *Hvergelmir* (VLAN-fähig, z. B. Cisco 2960/3750), Schreibtisch-Switch *Þund*, APs *Walküren*
  - Management-Node *Asgard* (Mini-PC, Kern: Identität, Passwörter, Git, Automatisierung), Workload-Node *Midgard*, GPU-Node *Muspelheim* (später), Game-Node *Vanaheim*, Lab-Node *Jötunheim*
  - NAS *Valhalla* (alter Laptop + USB-Platte, OMV), Backup-Server *Niflheim* (ohne Internet, Pull-Backups), Offsite-Pi *Utgard* (bei Familie)
  - Quorum-Pi *Nornen*, 2× DNS-Pi *Muninn* (Pi-hole, getrennt vom Management-Node), KVM *Hliðskjálf*, NOC-Display *Valaskjálf*
  - Smart-Home-Box (eigene HAOS-Box), Funk-Koordinator *Landvættir*, USV *Megingjörð*, Steckdosen *Mjölnir*, Rack *Bilskirnir*
  - Wächter-Node (Monitoring getrennt), DMZ-Node, VPS **Yggdrasil** (WireGuard-Tunnel; dort u. a. Traefik, n8n, PostgreSQL), Cloudflare
- **VLAN-Plan** (`NW.V`/`NW.NETDEF`):

  | VLAN | Name | Netz |
  |---|---|---|
  | 10 | MGMT | 10.10.10.0/24 |
  | 20 | SERVER | 10.10.20.0/24 |
  | 30 | DMZ | 10.10.30.0/24 |
  | 40 | TRUSTED | 192.168.40.0/24 |
  | 50 | IOT | 192.168.50.0/24 |
  | 60 | GUEST | 192.168.60.0/24 |
  | 70 | STORAGE | 10.10.70.0/24 |
  | 80 | LAB | 172.16.80.0/24 |
  | 90 | AI | 10.10.90.0/24 |
  | 100 | CLUSTER | 10.10.100.0/24 |
  | 110 | GAME | 10.10.110.0/24 |
  | 120 | CAM | 192.168.120.0/24 |

  Logik der Bereiche: 10.x = Infrastruktur, 192.168.x = Endgeräte, 172.x = Lab/Container, 100.64.x = Tunnel/Overlay (WireGuard 100.64.10.0/24). `.1` ist das Gateway, `.2–.3` die Firewall-Knoten, `.4–.9` Netzgeräte, `.10–.39` feste Hosts.
- **Stack:**
  - eingeplant: Proxmox-Cluster, Docker, Ansible, Gitea/Forgejo, Vaultwarden, NetBox, Backup (PBS), n8n („Hermes“), Ollama, Nextcloud, Pi-hole ×2, PowerDNS (Auth + Recursor), Traefik, Cloudflare Tunnel, Keycloak, Prometheus/Grafana/Loki, Paperless, Immich, Jellyfin, Home Assistant, Game-Server, Containerlab
  - überlegt: OpenTofu, Kubernetes
- **Planungsmodelle:**
  - 100 Schichten in 10 Bändern (wichtigste zuerst)
  - Reifegrade R0–R5
  - Geräte-Reife G0–G14 mit 16 Strängen (z. B. Strom: Steckdose → Messsteckdose → USV)
  - Dienste-Turm E0–E6 (E1 = „Substrat“ = Proxmox)
  - „Reifegrad-Dienste“ = Querschnittsdienste wie Monitoring, Backup, SSO, Passwortmanager
  - Gesamtreife = schwächstes Glied

**Wichtig für die Arbeit am Tool:** Das alles ist Hintergrundwissen für Ideen und für später, etwa wenn das Diagramm einmal Max' eigenes Lab zeigen oder Features wie Reifegrad-Anzeige, mehrere Nodes, Offsite-Standorte oder deutsche Beschriftung bekommen soll. **Nicht von selbst umsetzen.** Erst wenn Max es als Aufgabe gibt.
