# Plan: Homelab-Diagramm-Tool perfektionieren

Stand: 12.11.2026. Hier steht, was Max gesagt hat, was er will, was noch erklärt werden musste, und die ganze Ideenliste zum Auswählen.
Nichts davon ist schon umgesetzt, außer es steht ausdrücklich „erledigt“ dabei.

---

## 1. Erledigt

| Was | Ergebnis |
|---|---|
| Alle genutzten IPs im Diagramm | 4 Varianten: `--ips=table` (Liste unter dem Server), `inline` (volle IPs auf den Karten), `both`, `sheet` (eigenes Bild). `--variants` rendert alle. Doppelte IPs werden rot. |
| Schneller einrichten | `python3 setup.py` in ~4 s statt ~7 Min. Fonts liegen im Repo, Icons laden parallel. `python3 setup.py --check-fonts` prüft, ob es neuere Fonts gibt, `--update-fonts` holt sie. |

---

## 2. Was Max gesagt hat (seine Meinung, so soll es werden)

### 2.1 Neue Idee: öffentliche und private IPs sofort unterscheiden
- Man soll **ohne auf die Zahlen zu achten** sehen, ob eine IP öffentlich oder privat ist.
- Wird zur Idee **G7** (siehe unten).

### 2.2 IP-Bereiche
- Die Werte in den alten Notizen (10.10.x, 10.0.x usw.) sind **nicht wichtig**. Sie kamen von verschiedenen KIs, Max ist noch unentschlossen.
- **Fest ist nur:** Max will **alle privaten Adressbereiche nutzen, die es gibt, wirklich jeden**, und jeder Bereich hat einen **eigenen Sinn**:
  - **192.168.x.x**: Dinge, die Gäste und Alltag berühren dürfen, nicht komplett abgeriegelt.
  - **10.x.x.x**: Kerninfrastruktur, das, was niemand anfassen soll.
  - **Bereiche dazwischen** (172.16.x.x usw.): andere Dinge, Sinn noch festzulegen.
- Siehe Erklärung 3.1, welche Bereiche es überhaupt gibt.

### 2.3 Das Tool ist auf ein Lab festgenagelt: muss unbedingt geändert werden
- Nur 4 Geräte unter dem Switch ist „lächerlich“. Max plant **viel mehr und viele separate Geräte**.
- **Kabelwege dürfen nicht fest im Code stehen.** Sie sollen automatisch entstehen und trotzdem **so schön sein wie beim Original**: nicht überlappen, nicht eng nebeneinander, klar strukturiert, man erkennt alles.
- Ziel: ein schönes, ordentliches Diagramm, **obwohl** es sehr viele Geräte sind.

### 2.4 Geräte, die Max plant (seine Angaben, Stand heute)
> Wichtig: Die ~33 Geräte aus den alten Notizen („Neun Welten“) sind **nur Möglichkeiten**, nichts davon ist fest. Max hat einen eigenen Plan mit ein paar festen Dingen.

| Gerät | Zweck laut Max |
|---|---|
| **Workload-Server** | Hauptserver, auf dem alles läuft, für alles nutzbar. Hier werden Dienste getestet, bevor sie genutzt werden. |
| **KI-Server** | KI |
| **Lab-Server** | üben, testen, ausprobieren: nicht für einzelne Dienste, sondern für Szenarien, Sicherheit, besser werden in etwas |
| **Redundante Netzwerkgeräte** | wahrscheinlich je 2: Router, Switch |
| **Desktop-Switch** | am Schreibtisch |
| **KVM-Switch** | an den Servern, um zwischen **allen** Servern umzuschalten |
| **Raspberry Pi** | vorhanden |
| **Philips Luftreiniger** | bekommt eine IP |
| **3D-Drucker Bambu Lab** | vorhanden |
| **NAS 1 + NAS 2** | spiegeln sich gegenseitig (redundant). Grob **80 % Daten**: Fotos, Videos, Filme, Dokumente, Passwörter, Lesezeichen, gespeicherte Instagram- und Pinterest-Beiträge, 3D-Druck-Sammlung, Musiksammlung und vieles mehr. Grob **20 % Backup**: der **wichtigste Teil** der Backups, als letzte Rettung, falls alles schiefgeht. |
| **NAS 3** | reiner **Backup-Speicher**, wohin alle Backups laufen |
| **Lokale Backups auf jedem Gerät** | etwas Backup direkt auf dem Gerät selbst, damit man bei Problemen sofort zurückspielen und reparieren kann |

Daraus folgt fürs Diagramm: **drei Backup-Stufen** sichtbar machen (lokal auf dem Gerät → Backup-NAS 3 → wichtigster Teil gespiegelt auf NAS 1 + 2). Das ist Idee **D7/E6**.

### 2.5 Textlängen
- Nicht schätzen. Der Text ist bekannt, also **erst exakt messen, daraus Größe der Box und Abstände bestimmen**.
- Es darf **nie** passieren, dass Text am Ende verkleinert oder verschoben wird und dann über einem anderen Teil liegt. „Mach's einfach richtig.“
- Umsetzung: Idee **A8** + Layout-Engine **B** (erst alles messen, dann platzieren).

### 2.6 Daten automatisch einlesen (sehr wichtig)
- Max will **nichts selbst ausfüllen müssen**.
- Wenn das Lab läuft, soll er auf dem Server sagen können „prüf die Struktur“, und das Tool holt sich **alle Werte selbst**: welche Geräte, IPs, VLANs, Dienste, Backups usw.
- Mögliche Quellen: Ansible-Inventar, Monitoring, NetBox, DNS, DHCP, Backup.
- Dafür soll ein **genauer Plan** her, damit das Skript am Ende wirklich alle Infos bekommt. Siehe Abschnitt 4.

### 2.7 Zu A1 und A2
- **A1** (build.py aufteilen): Max hat es richtig verstanden und findet es eigentlich gut, will aber noch überlegen.
- **A2** (Prüfung der Daten): gleicher Stand, noch überlegen.
- Erklärung zu beiden siehe 3.5.

### 2.8 Allgemein
- Alles, was unklar ist, soll **einfach und deutlich erklärt** werden.
- Max macht später weiter und wählt dann aus der Ideenliste aus.

---

## 3. Erklärungen (was unklar war)

### 3.1 Welche privaten Adressbereiche gibt es?
Es gibt genau **drei** echte private IPv4-Bereiche (RFC 1918). Dazu kommen ein paar Sonderbereiche, die man privat nutzen *kann*, aber mit Vorsicht:

| Bereich | Größe | Art | Vorschlag zu Max' Idee |
|---|---|---|---|
| `10.0.0.0/8` | 16,7 Mio. Adressen | privat (RFC 1918) | **Kerninfrastruktur**, niemand fasst es an |
| `172.16.0.0/12` (172.16.–172.31.) | 1 Mio. | privat (RFC 1918) | **dazwischen**: z. B. Lab, Container, virtuelle Netze |
| `192.168.0.0/16` | 65 536 | privat (RFC 1918) | **Endgeräte, Gäste, Alltag** |
| `100.64.0.0/10` | 4 Mio. | „Shared Address Space“ (für Provider-NAT gedacht) | oft für **VPN/Overlay** genutzt (Tailscale macht das so). **Achtung:** Wenn der Internetanschluss DS-Lite/CGNAT hat, kann es kollidieren. |
| `198.18.0.0/15` | 131 072 | Test/Benchmark | nur Lab, nie produktiv |
| `169.254.0.0/16` | | Link-Local | wird automatisch vergeben, **nicht** selbst planen |
| `127.0.0.0/8` | | Loopback | nur im eigenen Gerät |
| `fd00::/8` | riesig | privat für **IPv6** (ULA) | eigenes Präfix für IPv6 im Heimnetz |

Alles andere ist **öffentlich**, also im Internet erreichbar bzw. gehört jemandem.

### 3.2 Der Nummernplan (Punkt 2 der Auffälligkeiten)
- In Proxmox bekommt jede virtuelle Maschine und jeder Container eine **Nummer (VMID)**, z. B. 149.
- In Max' Datei „Wichtige infos“ steht eine Regel: **VMID = Kategorie × 1000 + letzte Zahl der IP**.
  - Beispiel `1217`: die `1` heißt Kategorie „Netzdienst“, `217` heißt die IP endet auf `.217`.
- **Das Problem:** Das Tool macht es anders. Hat ein Container keine IP eingetragen, nimmt es einfach die VMID als Endung: Container 149 bekommt `.149`. Mit Max' Regel käme bei `1217` dann `.1217` heraus, und das ist keine gültige IP.
- **Lösung (Idee C4):** Das Tool lernt Max' Regel und liest aus der Nummer Kategorie, IP-Endung, Startreihenfolge und Backup-Zeit ab. Es meldet auch, wenn Nummer und IP nicht zusammenpassen.
- Ob Max diese Regel überhaupt behält, ist offen. Das Tool sollte die Regel deshalb **einstellbar** haben.

### 3.3 „Auf ein Lab festgenagelt“ (Punkt 3), was genau fest im Code steht
- **„other guests“** (nicht „Old Faulands“): die 4 virtuellen Maschinen außerhalb der DMZ (TrueNAS, Home Assistant, UniFi, BlissOS). Sie sind mit festen Positionen und Höhen untereinander gezeichnet. Kommt eine fünfte dazu, wird sie nicht gezeichnet.
- **`ALL_VLANS`**: eine Liste im Code, welche VLANs über das Kabel zwischen Firewall und Switch laufen. Steht von Hand drin, statt aus den Daten zu kommen.
- **Gerätezeile**: genau 4 Geräte (MADCAT, JetKVM, Access Point, Zigbee-Funk) mit festen Positionen und **von Hand gezeichneten Kabelwegen**.
- **Ein Server** (terra), **ein Switch**, **eine Firewall** und die **Media-Pipeline** sind ebenfalls fest.
- **Lösung:** Layout-Engine (Ideen B1–B8). Geräte, Server und Kabel kommen aus den Daten, die Positionen und Kabelwege rechnet das Tool selbst aus.

### 3.4 DMZ-Chips, CT und VM (Punkt 4)
- **DMZ:** ein abgetrenntes Netz für Dienste, die aus dem Internet erreichbar sind. Wird dort einer gehackt, kommt der Angreifer nicht ins Heimnetz.
- **DMZ-Chips:** die kleinen Karten im orangen Bereich unten rechts im Bild, eine pro Dienst (Grafana, Immich, Forgejo …).
- **CT** = Container (in Proxmox „LXC“): leicht und sparsam, teilt sich den Kern des Betriebssystems mit dem Server.
- **VM** = virtuelle Maschine: ein komplett eigener Computer mit eigenem Betriebssystem. Braucht mehr Ressourcen, ist aber stärker abgeschottet.
- **Das Problem:** Das Tool schreibt auf **jeden** DMZ-Chip „CT 149“. Steckt dort eine VM, steht trotzdem „CT“ dran, also falsch.
- **Lösung:** Die Art (CT/VM) kommt aus den Daten, wie es bei den anderen Gästen schon ist.

### 3.5 A1 und A2 einfach erklärt
- **A1 – build.py aufteilen:** Max hat es richtig verstanden. Heute ist alles in einer Datei mit ~1000 Zeilen. Danach gäbe es z. B. `theme.py` (Farben), `bausteine.py` (Karten, Kabel, Buchsen), eine Datei pro Bereich (Firewall, Switch, Server …) und `ausgabe.py`. Das Bild sieht dadurch nicht anders aus. Der Vorteil: Wenn wir die Layout-Engine bauen, kann man einen Teil ändern, ohne den Rest zu gefährden. **Vor B1/B2 sehr zu empfehlen.**
- **A2 – Daten prüfen:** Bevor gezeichnet wird, liest das Tool die YAML und prüft sie. Beispiele: Gibt es VLAN 45 überhaupt? Fehlt bei einem Gerät die IP? Ist eine IP doppelt? Passt die IP ins Netz des VLANs? Passt die Nummer zum Nummernplan? Bei einem Fehler kommt eine klare Meldung auf Deutsch („Gerät ‚Luftreiniger‘: VLAN 45 gibt es nicht“). Ohne die Prüfung gibt es einen kryptischen Absturz oder ein falsches Bild. **Wichtig für 2.6:** Automatisch eingelesene Daten müssen geprüft werden.

---

## 4. Plan: alle Daten automatisch einlesen (zu 2.6)

**Prinzip:** Nur lesen, nie etwas am Lab ändern. Ein Befehl sammelt alles, prüft es und zeigt, was sich geändert hat.

```
python3 collect.py           → sammelt aus allen Quellen → inventory.generated.yaml
python3 collect.py --diff    → zeigt nur, was sich seit dem letzten Mal geändert hat
python3 build.py             → zeichnet aus generated + overrides
```

- **Zwei Dateien:**
  - `inventory.generated.yaml` wird **automatisch** erzeugt und nie von Hand bearbeitet.
  - `inventory.overrides.yaml` bearbeitet Max **von Hand**, nur für das, was keine Maschine wissen kann: Mythos-Name, Notizen, Wichtigkeit, Farben, Layout-Wünsche.
- Das Tool **verbindet** beide Dateien, die Overrides gewinnen.

### Quellen und was sie liefern

| Quelle | Was sie weiß | Wie (nur lesen) |
|---|---|---|
| **NetBox** (IPAM, „Quelle der Wahrheit“) | Geräte, IPs, VLANs, Subnetze, Kabel, Standorte, Racks | REST-API mit Lese-Token |
| **Proxmox** | alle Nodes, VMs/Container, VMID, CPU/RAM/Disk, Netzwerk-Bridges, Cluster | API mit Lese-Token (Rolle `PVEAuditor`) |
| **Ansible-Inventar** (`hosts.yml`) | welche Hosts es gibt, Gruppen (z. B. `dns`, `monitoring`), Variablen | Datei direkt lesen |
| **Firewall** (OPNsense o. ä.) | VLAN-Schnittstellen, DHCP-Leases (wer hat welche IP), Portweiterleitungen, WireGuard-Peers | API mit Lese-Rechten |
| **Switch(es)** | Port → Gerät, Geschwindigkeit, VLANs je Port | SNMP / LLDP oder CLI (`show interfaces status`, `show vlan`) |
| **DNS** (Pi-hole, PowerDNS) | Hostnamen ↔ IPs | API |
| **Prometheus** (Monitoring) | was überwacht wird, was gerade läuft/ausfällt | API |
| **Backup** (Proxmox Backup Server o. ä.) | welche Gäste gesichert werden, wohin, wie oft, letzter Erfolg | API |
| **Docker** | Container pro Host (Apps in einem Container) | `docker ps` über SSH oder Portainer-API |
| **Traefik** | welche Dienste öffentlich unter welchem Namen erreichbar sind | API |

> Hinweis: **NetBird** ist ein VPN, keine IP-Verwaltung. Das Programm, das IPs verwaltet, heißt **NetBox**.

### Schritte
1. Erst die Daten-Prüfung (A2), denn ohne sie ist automatisches Einlesen gefährlich.
2. Datenmodell festlegen: was ist ein Gerät, Gast, Dienst, Netz, Kabel, Backup-Ziel.
3. Je Quelle ein kleiner „Sammler“, einzeln testbar, einzeln abschaltbar.
4. Zusammenführen und Widersprüche melden (z. B. NetBox sagt IP A, DHCP sagt IP B).
5. Änderungsbericht: „seit letztem Mal: +2 Container, IP von X geändert, Backup von Y fehlt“.
6. Später automatisch per Zeitplan (Ansible, n8n oder cron): täglich neues Bild.

---

## 5. Ideenliste (zum Auswählen)

★ = Empfehlung für den Anfang. Aufwand: S klein, M mittel, L groß.

### A · Fundament im Code
- **A1 ★** build.py in mehrere Dateien aufteilen (siehe 3.5). M · *Max: gut, noch überlegen*
- **A2 ★** Daten-Prüfung vor dem Zeichnen (siehe 3.5). M · *Max: noch überlegen*
- **A3** Profile: mehrere Inventare nebeneinander (`--profile max`), das Beispiel-Lab bleibt. S
- **A4** Jeden Bereich per YAML ein- und ausschalten. S
- **A5** Themes: dunkel, hell, Druck, „Nordisch“. M
- **A6** Bild-Regressionstest: ein Befehl prüft, ob sich etwas ungewollt verändert hat. S
- **A7** Automatischer Überlappungs-Check: Das Tool findet selbst Text auf Text oder Kabel durch Karten. M
- **A8 ★** Alle Texte exakt messen und Boxen danach bauen (siehe 2.5). S
- **A9** Watch-Modus: YAML speichern rendert sofort neu. S

### B · Layout-Engine (Positionen und Kabel automatisch, siehe 2.3)
- **B1 ★** Gerätezeile automatisch, beliebig viele Geräte, Kabel kreuzungsfrei. L
- **B2 ★** Mehrere Server (Workload, KI, Lab …), jeder als eigene Karte. L
- **B3 ★** Mehrere/redundante Router und Switches, Desktop-Switch per Trunk. L
- **B4** DMZ-Spalten automatisch verteilen. M
- **B5** Bildhöhe automatisch. M
- **B6 ★** Kabel-Router: eigene Spuren, Mindestabstand, nie durch Karten, wenig Kreuzungen. L
- **B7** Gäste außerhalb der DMZ beliebig viele. M
- **B8** Jede Zone (VLAN) als farbiger Bereich. M

### C · Daten & Schema
- **C1 ★** Max' eigenes Lab als eigenes Inventar (wenn der Plan feststeht). M
- **C2 ★** Benennung: Funktion groß, Mythos-Name klein daneben. S
- **C3** Status je Gerät/Dienst: vorhanden / geplant / später / bewusst nicht. M
- **C4** Nummernplan einstellbar (siehe 3.2). M
- **C5** Namensschema-Prüfung `<wirt>-<aufgabe>-<art>`. S
- **C6** Standorte: Zuhause, Offsite, VPS, Cloud. M
- **C7** Strom und Kosten je Gerät. S
- **C8** Ressourcen je Server: vergeben vs. vorhanden. M
- **C9** Import aus „Neun Welten“. M
- **C10** Art (CT/VM) überall aus den Daten (siehe 3.4). S

### D · Mehr Inhalt im Hauptbild
- **D1 ★** Geplante Geräte gestrichelt mit „geplant“-Pill. S
- **D2** Mythos-Name im Reiter. S
- **D3** Proxmox-Cluster-Band + Quorum. M
- **D4** VPS als eigene Karte mit Tunnel. M
- **D5** Zwei DNS-Geräte, Redundanz sichtbar. S
- **D6** Strom/USV je Gerät. M
- **D7 ★** Backup-Pfeile: lokal → Backup-NAS → wichtigster Teil gespiegelt auf NAS 1 + 2 (siehe 2.4). M
- **D8** Firewall-Regeln als kleine Matrix. M
- **D9** Monitoring-Symbol an überwachten Dingen. S
- **D10** Wichtigkeit (Tier 0–3) als Farbpunkt. S
- **D11** Reifegrad-Badge R0–R5. S
- **D12** NAS-Karten allgemein (nicht nur TrueNAS), mit Datenanteil/Backup-Anteil. M
- **D13** Mehrere Access Points mit SSIDs. S
- **D14** IPv6-Präfix in der Netzwerk-Tabelle. S
- **D15** DHCP-Bereiche je VLAN. S
- **D16** Zweite Internetleitung (Mobilfunk-Backup). S
- **D17** Fußzeile mit Kennzahlen (Geräte, Dienste, Watt, Kosten). S
- **D18** Redundanz-Paare sichtbar verbunden (Router A ↔ B, Switch A ↔ B, NAS 1 ↔ 2). S
- **D19** KVM-Switch mit gestrichelten Konsolen-Linien zu allen Servern. S

### E · Neue Ansichten (eigene Bilder, das Hauptbild bleibt)
- **E1 ★** Dienste-Diagramm: Fundament → Netzwerk → Reifegrad-Dienste → Anwendungen. L
- **E2 ★** IP-Plan-Bild mit allen Adressbereichen und ihrem Sinn (siehe 3.1). M
- **E3** Kabel- & Port-Plan. M
- **E4** Rack-Ansicht. L
- **E5** Standort-Karte. M
- **E6 ★** Backup-Fluss je Datentyp (Fotos, Dokumente, Passwörter, Musik, 3D-Druck …). M
- **E7** Ausfall-Ansicht: was fällt aus, wenn Gerät X ausfällt. M
- **E8** Zugriffspfad Handy → Dienst. M
- **E9** Firewall-Matrix groß. S
- **E10** DNS-Ansicht. M
- **E11** Port-Matrix. M
- **E12** Startreihenfolge als Zeitstrahl. S
- **E13** Backup-Zeitplan als Tagesuhr. S
- **E14** OSI-Ansicht (CCNA). M
- **E15** Grundriss/Wohnung. L
- **E16** Proxmox-Bauplan je Server. M
- **E17** Stack-Ansichten. M
- **E18** Stromlaufplan. S
- **E19** Poster: alle Ansichten auf einem Bild/PDF. M
- **E20** Ist-Stand vs. Ziel-Stand nebeneinander. M

### F · Reifegrad & Planung
- **F1 ★** Reifegrad R0–R5 je Dienst. S
- **F2** Geräte-Reife als Mini-Balken. M
- **F3** Gesamtreife (schwächstes Glied) in der Kopfzeile. S
- **F4** Die 10 Bänder als Fortschritt. M
- **F5** Reifegrad-Dienste-Matrix. M
- **F6** „Was fehlt“-Liste automatisch (ohne Backup, ohne Monitoring …). M
- **F7** Heatmap Geräte × Stränge. M
- **F8** Diagramm je Ausbauphase. M

### G · IP & Netz
- **G1 ★** IP-Prüfung: IP passt zum VLAN und zur Rolle. S
- **G2** Belegungsbalken je Netz. S
- **G3** VMID ↔ IP-Abgleich. S
- **G4** Nächste freie IP vorschlagen. S
- **G5** IP-Liste als CSV/Markdown. S
- **G6** Warnung bei Konflikt mit typischen Heim-/Hotelnetzen (192.168.0/1.x). S
- **G7 ★ (Max' Idee)** Öffentlich vs. privat auf einen Blick: Jede IP bekommt automatisch eine Kennzeichnung, ohne dass man die Zahlen lesen muss, z. B.:
  - **öffentlich**: Weltkugel-Symbol + eigene Signalfarbe/Umrandung
  - **privat 10.x**: Schloss-Symbol (Kern)
  - **privat 172.16–31**: eigenes Symbol (Lab/virtuell)
  - **privat 192.168**: Haus-Symbol (Alltag/Gäste)
  - **Sonderbereiche** (100.64 VPN, IPv6-ULA …): eigenes Symbol
  - Erkennung automatisch aus der Adresse, dazu ein Eintrag in der Legende. Funktioniert in allen IP-Varianten (Karten, Tabelle, eigenes Bild). S–M

### H · Optik
- **H1 ★** Feinschliff: einheitliche Abstände, Schriftgrößen, Raster. M
- **H2** Kabel mit leichtem Glow. S
- **H3** Nummerierte Bereichs-Überschriften. S
- **H4** Icons für alle geplanten Dienste. S
- **H5** Eigene Symbole für Pi, USV, Rack, Luftreiniger, 3D-Drucker, KVM-Switch. S
- **H6** Helles Theme. M
- **H7** Dezente nordische Akzente. S
- **H8** Rand-Stil = Status. S
- **H9** Mini-Übersichtskarte. M

### I · Interaktive HTML-Ausgabe
- **I1 ★** HTML-Datei mit Zoom am Handy, offline. M
- **I2** Antippen zeigt Details. M
- **I3** Ebenen ein-/ausblenden (IPs, Strom, Backup …). M
- **I4** Kabelpfad hervorheben. M
- **I5** Suche. S
- **I6** Ausfall-Simulator. M
- **I7** Varianten-Vergleich mit Schieberegler. S

### J · Automatik & Qualität
- **J1 ★** GitHub Action: Jeder Push rendert alle Bilder, ansehbar am Handy. M
- **J2** Automatischer Privatsphäre-Check. S
- **J3** Änderungsbericht. S
- **J4** Diff-Bild (Änderungen rot). S

### K · Sprache
- **K1 ★** Deutsch/Englisch umschaltbar. M
- **K2** Glossar-Kästchen für Fachbegriffe. S

### L · Lernwert / CCNA
- **L1** CCNA-Modus mit Schichten/Protokollen. S
- **L2** Packet-Tracer-Vorlage. L
- **L3** Paketreise nummeriert. M

### M · Daten automatisch einlesen (siehe Abschnitt 4)
- **M1** Proxmox. M
- **M2** NetBox. L
- **M3** Switch. M
- **M4** Docker. S
- **M5** Live-Status über Prometheus. L
- **M6 ★** `collect.py` mit generated- + overrides-Datei und Änderungsbericht. L
- **M7** Ansible-Inventar. S
- **M8** Firewall (DHCP, Portweiterleitungen, VPN-Peers). M
- **M9** Backup-Server (was ist gesichert, wann zuletzt). M
- **M10** DNS und Traefik (Hostnamen, öffentliche Namen). S

### N · Ausgabe
- **N1** PDF. S
- **N2** Handy-Hochformat. M
- **N3** Geschwärzte Version zum Teilen mit eigenem Watermark. S

---

## 6. Vorgeschlagene Reihenfolge

1. **Fundament:** A1, A2, A8, A7, J1 (Bilder am Handy ansehen).
2. **Weg vom einen Lab:** B1, B2, B3, B6, B5, B7, C10.
3. **Netz:** IP-Bereiche festlegen (2.2 + 3.1), dann G7, G1, E2.
4. **Max' Geräte und Backup-Konzept:** C1, C2, C3, D1, D7, D12, D18, D19.
5. **Automatisch einlesen:** M6 + Quellen (Abschnitt 4), sobald das Lab läuft.
6. **Danach nach Lust:** Ansichten (E), Reifegrad (F), HTML (I).

## 7. Offen / Max entscheidet noch
- [ ] A1 machen?
- [ ] A2 machen?
- [ ] Welcher Adressbereich bekommt welchen Sinn (10 = Kern, 192.168 = Alltag/Gäste fest; 172.16 und Sonderbereiche offen)?
- [ ] Nummernplan (VMID-Regel) behalten?
- [ ] Welche Geräte sind fest (Abschnitt 2.4 ist der heutige Stand)?
- [ ] Welche IP-Variante wird Standard (table / inline / both / sheet)?
