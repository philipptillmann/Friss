# Friss API · Version 1.0.0

Self-hosted Ernährungserfassung für Debian/Docker und iPhone-Kurzbefehle. Deutsche und englische BLS-Namen, unveränderliche Originale, SQLite, Open Food Facts und Health-Export-Reservierungen. Keine fertige iPhone-App oder Foto-KI.

## Start auf Debian

```bash
cp .env.example .env
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
# Ausgabe als FRISS_API_KEY in .env eintragen.
# FRISS_BIND_IP auf die LAN-/VPN-IP des Servers setzen.
mkdir -p data/originals
sudo chown -R 10001:10001 data
chmod 600 .env
docker compose up -d --build
```

Port 8000 über LAN/VPN erreichen, nicht im Router ins Internet freigeben. HTTP nur innerhalb der vertrauenswürdigen VPN-Verbindung verwenden; ansonsten TLS über einen Reverse Proxy. Die API benötigt `Authorization: Bearer <FRISS_API_KEY>`. Swagger unter `/docs` öffnen, **Authorize** wählen und den API-Schlüssel eintragen (ohne Bearer-Präfix).

BLS-Datei `data/bls/de.json` liegt im Download-Paket, wird aber nicht in Git versioniert: 7.140 Datensätze, jeweils mit beiden Namen. Weitere Sprachdateien und Buchstabenteile können hier liegen; BLS-Code ist der eindeutige Schlüssel, zuerst importierter Datensatz gewinnt. Vollimport beim Start. Keine externe BLS-Anfrage. OFF wird bei Barcode-Erfassung online angefragt.

## Schnittstelle

- `GET /foods?q=Apfel&lang=de`: Suche; `lang=en` liefert englische Anzeigenamen.
- `POST /entries`: Eintrag mit vom iPhone erzeugter UUID und Zeitzonen-Zeitstempel.
- `GET /entries?status=needs_review`: Nachbearbeitung; Liste derzeit maximal 1.000 Einträge pro Abruf, keine Pagination.
- `GET /entries/{id}`: Details.
- `POST /entries/{id}/resolve`: `{"bls_code":"F110100","quantity":{"value":180,"unit":"g"}}`.
- `PUT /entries/{id}/photo`: unveränderte JPEG-Bytes, maximal 15 MiB. Nach bestätigter JSON-Anlage hochladen. HEIC vorher bewusst konvertieren; JPEG ist das gespeicherte Original dieses Imports.
- `GET /health-export/pending`: exportierbare Einträge.
- `POST /health-export/{id}/claim`: einmalige Reservierung, liefert `export_token`.
- `POST /health-export/{id}/ack`: `{"export_token":"…","success":true}` nach vollständig erfolgreichem Health-Schreiben; sonst `false`.

Textbeispiel:

```json
{"id":"08b29332-e879-4b8a-a40c-d3f6da703f6c","type":"text","timestamp":"2026-10-04T15:31:40+02:00","description":"Banane","quantity":{"value":100,"unit":"g"}}
```

Barcode: `type=barcode`, `barcode` als String. Auswahl: `type=item`, `bls_code`. Foto: `type=picture`, anschließend Upload. Unbekannte Menge: `quantity=null`. Getränke: `type=drink`, `drink=water|coffee|alcohol`, Menge in ml, optional **gesamte konsumierte** Koffeinmenge `caffeine_mg` oder `alcohol_abv` in Volumenprozent. Alkoholmenge wird mit 0,789 g/ml berechnet, keine automatische Berechnung sämtlicher Getränkekalorien. Koffein ohne Mengenangabe wird nicht geraten.

## iPhone-Kurzbefehle

1. UUID erzeugen und zusammen mit Originaleingabe lokal behalten, bis der Server bestätigt. Beim Wiederholen dieselbe UUID und denselben JSON-Inhalt verwenden.
2. „Inhalt von URL abrufen“: POST an `http://SERVER:8000/entries`, Bearer-Header, JSON-Daten. Foto anschließend mit PUT hochladen.
3. Für Health: pending abholen, jeden Eintrag claimen, zurückgegebene `nutrients` mit angegebenen Einheiten und dem ursprünglichen Zeitstempel in Health schreiben.
4. Nach allen erfolgreichen Health-Aktionen bestätigen. Falls ein Teil scheitert, `success=false`; nie blind erneut schreiben.

Reservierungen laufen nicht automatisch ab: Bei Abbruch zwischen Health-Schreiben und Bestätigung muss der tatsächliche Health-Bestand manuell geprüft werden. Die API allein kann kein Exactly-once-Schreiben in Health garantieren. Korrekturen bereits reservierter/exportierter Einträge sind blockiert. Die tatsächlich verfügbaren Health-Aktionen und Einheiten müssen auf deinem iOS getestet werden. Noch kein mitgelieferter `.shortcut`.

## BLS-Einheiten und Apple Health

Die JSON-Datei enthält keine Einheiten und keine Bezugsgröße. Vorläufige Berechnung: pro 100 g, Makronährstoffe in g, Energie in kcal. Diese Annahmen stehen als Warnung am Eintrag. **BLS-Health-Export bleibt vollständig gesperrt**, bis die ursprüngliche Konvertierung/Spalteneinheiten geprüft sind. Mikronährstoffwerte sowie TR, null und <LOD/<LOQ bleiben im Food-Original erhalten; unbekannte Einheiten werden nicht exportiert. Nahrungswasser aus BLS wird nicht als getrunkenes Wasser gewertet.

Nährstoffnamen folgen dem Schema `dietaryEnergyConsumed`, `dietaryWater`, `dietaryCaffeine` usw. Grundlage: https://developer.apple.com/documentation/healthkit/nutrition-type-identifiers . Apple-Dokumentation war während der Erstellung aufgrund eines Netzwerkfehlers nicht abrufbar; vollständiges geprüftes HealthKit-Mapping steht noch aus. OFF liefert derzeit nur Energie, Makronährstoffe, Natrium und Koffein; weitere Mikronährstoffe folgen nach Prüfung.

## Bestehende Dateien importieren

Original-Dateinamen wiederherstellen, insbesondere beim Foto (Upload-Präfixe entfernen). Danach:

```bash
python3 -m pip install httpx
export FRISS_API_KEY='dein-api-schluessel'
python3 scripts/import_legacy.py /pfad/zu/entries --url http://SERVER:8000
```

Raw-JSONs und Fotos werden unter `data/legacy` unverändert archiviert. Altes `amount` wird vorläufig als Gramm interpretiert; 0 wird unbekannt. Ergebnis-JSONs ohne Typ werden archiviert, nicht als zweiter Verzehr importiert. Bereits bestehende Health-Einträge werden nicht automatisch erkannt; importierte Daten vor Freigabe des Health-Exports prüfen. BLS-Daten bleiben geschützt durch die Export-Sperre.

## Prüfung und Betrieb

```bash
python3 -m unittest discover -s tests -v
```

Integrationstests prüfen Authentifizierung, Wiederholungen, Einheiten-Sperre, Foto-Unveränderlichkeit und Export-Reservierung. Docker und reales Health-Schreiben müssen auf dem Zielsystem geprüft werden. Backup: Dienst stoppen und komplettes `data` inklusive SQLite, Originalen und Legacy-Archiv sichern; `.env` separat sicher verwahren. OFF-Daten: Open Food Facts, ODbL; BLS-Lizenz vor Weitergabe der enthaltenen Daten prüfen.

## Installation aus GitHub auf Debian

```bash
git clone --branch server --single-branch https://github.com/philipptillmann/Friss.git
cd Friss
mkdir -p data/bls data/originals
# Deine de.json nach data/bls/de.json kopieren. Lebensmitteldaten bleiben außerhalb von Git.
cp .env.example .env
openssl rand -hex 32
nano .env
# Secret und LAN/VPN-Bind-IP eintragen.
sudo chown -R 10001:10001 data
docker compose up -d --build
docker compose logs --tail=50
```

Für ein privates Repository ist ein für GitHub autorisierter SSH-Schlüssel oder GitHub CLI erforderlich. Ein ChatGPT-GitHub-Anschluss authentifiziert deinen Server nicht automatisch. Keine Tokens in Clone-URLs speichern. Auf dem iPhone über VPN `http://SERVER-IP:8000/docs` öffnen und Authorize verwenden. Dort zuerst GET /health und GET /foods mit q=Apfel testen. POST /entries mit einer neuen UUID testen; denselben Request wiederholen und prüfen, dass nur ein Eintrag entsteht.

Die Server-Entwicklung erfolgt im Branch `server`. `Friss.shortcut` aus dem bisherigen Projekt bleibt erhalten und ist noch nicht an diese API angepasst.

## Dashboard (Version 1.1.0)

Öffne `http://SERVER-IP:8001/`, gib den API-Schlüssel ein und wähle Deutsch oder Englisch. Der Schlüssel bleibt im sessionStorage dieses Browser-Tabs. Persönliche API-Daten bleiben geschützt. Tagesübersicht, BLS-Suche, Text, Barcode, JPEG-Upload, Wasser, Koffein und Alkohol sowie Zuordnung offener Einträge sind integriert. Kein Health-Schreiben aus dem Browser. Pro Tag maximal 1.000 Einträge; dann wird vor unvollständigen Summen gewarnt.

`FRISS_PORT=8001` konfiguriert nun den äußeren Port. Auf deinem Server vor dem Update die lokal bearbeitete Compose-Datei sichern, dann den Branch aktualisieren:

```bash
cd ~/Friss
cp compose.yaml /tmp/friss-compose-before-dashboard.yaml
git restore compose.yaml
git pull --ff-only origin server
# In .env bei Bedarf FRISS_PORT=8001 ergänzen.
docker compose up -d --build
docker compose logs --tail=50
```

Einträge bleiben im unverändert eingebundenen `data`-Ordner. Diese Update-Anleitung setzt voraus, dass nur der Port in compose.yaml lokal geändert wurde. Weitere eigene Änderungen vor dem Restore sichern.

## Version 1.2.0: Passwort, PWA und Server-Updates

Einmalig nach dem Pull:

```bash
python3 scripts/set-password.py
bash scripts/update.sh
```

Das Passwort wird interaktiv eingegeben und nur als gesalzener scrypt-Hash in `.env` gespeichert. Bestehenden API-Key behalten: Kurzbefehle können ihn weiterhin verwenden. Das Dashboard verwendet jetzt Passwort und eine serverseitige Sitzung mit HttpOnly/SameSite-Cookie (30 Tage). Abmelden widerruft die Sitzung; Passwortwechsel mit anschließendem Container-Neustart widerruft alle alten Sitzungen. Apple Passwords kann das Passwort automatisch ausfüllen; die konkrete Anzeige hängt von iOS und der URL ab.

`FRISS_COOKIE_SECURE=false` ist für die bestehende HTTP-Adresse im vertrauenswürdigen VPN/LAN. Bei HTTPS auf `true` setzen. Ohne VPN/TLS wird ein Passwort über HTTP unverschlüsselt übertragen. Keine Internet-Portfreigabe. Keine Authentifizierungsdaten werden im Service-Worker oder Offline-Cache gespeichert; Offline-Erfassung ist noch nicht implementiert.

Spätere Updates: `bash scripts/update.sh`. Es prüft Branch und lokale Änderungen, erstellt eine konsistente SQLite-Sicherung unter `data/backups/` und sichert `.env` sowie die bisherige Commit-ID unter `~/.local/share/friss-backups/`. Danach Fast-forward-Pull, Docker-Build und Startprüfung. Ein Build-Fehler lässt den bisherigen Container laufen. Backups der Fotos/Originale separat einrichten; das Skript sichert nicht den gesamten Datenordner. Bei einem Fork muss dessen `server`-Branch vor dem Update mit dem Original synchronisiert werden.

Das Icon ist als `app/static/icon-192.png` und `icon-512.png` enthalten, verbunden über Manifest und apple-touch-icon. Eigene quadratische PNG-Dateien mit diesen Größen können sie ersetzen. Nach einem Icon-Wechsel auf dem iPhone gegebenenfalls die Home-Screen-Verknüpfung entfernen (keine Serverdaten werden gelöscht) und in Safari über Teilen → Zum Home-Bildschirm hinzufügen neu anlegen. Safari und installierte Web-App können getrennte Login-Sitzungen haben. HTTPS ermöglicht die vollständigen PWA-Funktionen.

## Rezepte (1.3.0)

Im Dashboard ein Rezept mit Name und Gesamt-Portionszahl speichern. Für Gramm-Verzehr zusätzlich das **fertige** Gesamtgewicht angeben, z.B. nach dem Kochen 1.200 g. In der normalen Erfassung unter „Speichern in“ das Rezept wählen: Lebensmittel-Suche, Text, Barcode, Foto und Getränke stehen wie im Tagebuch zur Verfügung. Zutaten erscheinen mit dem ausgewählten Rezept in der Eintragsliste; ungeklärte Zutaten können dort zugeordnet werden. Zutaten werden nicht separat als Tagesverzehr oder nach Health exportiert. Fotos benötigen wie bisher eine manuelle Zuordnung.

Verzehr buchen als Portionen (1 von z.B. 4 Portionen = 1/4 des Rezepts), als Bruchteil (0,25 = 1/4) oder in Gramm (150 g eines 600-g-Rezepts = 1/4). Datum und Uhrzeit können gewählt werden. Fehlende Mengen oder Zuordnungen blockieren die Berechnung. Fehlende Nährstoffe werden nicht als Null geraten: nur Nährstoffe, die alle Zutaten liefern, erhalten einen Rezept-Gesamtwert. Kochverluste werden nicht berechnet. Enthält das Rezept BLS-Zutaten, bleibt sein Health-Export wegen der ausstehenden Einheitenprüfung gesperrt.

Jeder gebuchte Verzehr enthält einen Rezept-Snapshot. Spätere Änderungen an Rezeptname, Portionen, Gewicht oder Zutaten verändern keine alten Tagebucheinträge. Wiederholte Übertragung mit derselben UUID erzeugt keinen doppelten Verzehr.

API: `POST /recipes`, `GET /recipes`, `GET /recipes/{id}`, `PUT /recipes/{id}`. Zutaten sind reguläre `POST /entries` mit zusätzlichem `recipe_id`; Foto-Upload und Resolve verwenden die bestehenden Endpunkte. `POST /recipes/{id}/intake` erwartet `id`, Zeitzonen-`timestamp`, `unit` (`portion`, `fraction`, `g`) und `amount`. Rezepte und Zutaten liegen in SQLite und sind damit in der Update-Sicherung enthalten.
