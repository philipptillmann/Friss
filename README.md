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

Die Einheiten und die Bezugsgröße pro 100 g wurden anhand der BLS-4.0-Komponentenliste und der Originaltabelle BLS_4_0_Daten_2025_DE.xlsx bestätigt. Die bestehenden JSON-Zahlen wurden laut Nutzer unverändert übernommen. `app/bls_units.py` enthält die Zuordnung: Cholesterin und die meisten Mineralstoffe in mg; Vitamin B6, Kupfer und Mangan ausdrücklich in mcg. Selenium und Koffein sind im gelieferten BLS-Komponentenkatalog nicht enthalten und erhalten keine geratene Einheit. TR, null und Nachweisgrenzen bleiben unbekannt. BLS-Nahrungswasser bleibt in g sichtbar und wird nicht als getrunkenes Wasser oder Health-Wasservolumen exportiert.

Beim Start ergänzt eine idempotente Migration die Einheiten und zuvor ausgelassenen numerischen Nährstoffe aus den gespeicherten Food-Snapshots für noch nicht exportierte BLS-Einträge. Rezeptportionen erhalten fehlende Werte aus ihren eingefrorenen Zutaten; bereits gespeicherte Rezept-Gesamtwerte bleiben erhalten. Originaldateien, reservierte Tage und bereits exportierte Einträge werden nicht geändert. BLS-Einträge ohne prüfbaren Snapshot bleiben gesperrt.

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

Verzehr buchen als Portionen (1 von z.B. 4 Portionen = 1/4 des Rezepts), als Bruchteil (0,25 = 1/4) oder in Gramm (150 g eines 600-g-Rezepts = 1/4). Datum und Uhrzeit können gewählt werden. Fehlende Mengen oder Zuordnungen blockieren die Berechnung. Standardmäßig bleiben fehlende Nährstoffe unbekannt: nur Nährstoffe, die alle Zutaten liefern, erhalten einen Rezept-Gesamtwert. Mit der Einstellung „Fehlende Nährwerte als 0 behandeln“ werden fehlende Angaben als Null angenommen; bekannte Beiträge anderer Zutaten werden weiterhin mitgerechnet. Kochverluste werden nicht berechnet. Rezepte mit bestätigten BLS-Einheiten können nach Health exportiert werden; nicht prüfbare Alt-Einträge bleiben gesperrt.

### Gesamtgewicht und Portionsberechnung

Das Gesamtgewicht ist das Gewicht des **fertigen Rezepts**, beispielsweise nach dem Kochen. Es wird für Einträge in Gramm verwendet; die Summe der Zutatengewichte wird dafür nicht automatisch herangezogen.

- **In Gramm eintragen:** verzehrte Gramm ÷ fertiges Gesamtgewicht = Anteil der Rezeptnährwerte.
- **In Portionen eintragen:** verzehrte Portionen ÷ festgelegte Gesamt-Portionszahl = Anteil der Rezeptnährwerte. Diese Berechnung funktioniert auch ohne Gesamtgewicht.
- **Als Anteil eintragen:** z.B. 0,25 für ein Viertel des ganzen Rezepts. Auch dafür ist kein Gesamtgewicht erforderlich.

**Beispiel:** Ein fertiges Rezept wiegt 800 g und hat 4 Portionen. Sowohl 200 g als auch 1 Portion beziehungsweise ein Anteil von 0,25 ergeben jeweils 25 % der gesamten Rezeptnährwerte. Das rechnerische Durchschnittsgewicht einer Portion beträgt hier 200 g.

**Ohne Gesamtgewicht** sind Portionen und Anteile weiterhin möglich. Gramm-Verzehr ist erst möglich, wenn du das fertige Gesamtgewicht ergänzt hast. Friss schätzt dieses Gewicht nicht aus den Zutaten: Beim Kochen kann Wasser verdampfen oder aufgenommen werden.

Die gesamten Nährwerte stammen weiterhin aus den Zutaten und zusätzlichen Rezeptangaben. Das fertige Gewicht bestimmt bei Gramm-Verzehr lediglich den verzehrten Anteil; Nährstoffverluste durch das Kochen werden nicht automatisch berechnet. Spätere Änderungen am Gesamtgewicht oder an der Portionszahl verändern bereits gebuchte Einträge nicht.

Jeder gebuchte Verzehr enthält einen Rezept-Snapshot. Spätere Änderungen an Rezeptname, Portionen, Gewicht oder Zutaten verändern keine alten Tagebucheinträge. Wiederholte Übertragung mit derselben UUID erzeugt keinen doppelten Verzehr.

API: `POST /recipes`, `GET /recipes`, `GET /recipes/{id}`, `PUT /recipes/{id}`. Zutaten sind reguläre `POST /entries` mit zusätzlichem `recipe_id`; Foto-Upload und Resolve verwenden die bestehenden Endpunkte. `POST /recipes/{id}/intake` erwartet `id`, Zeitzonen-`timestamp`, `unit` (`portion`, `fraction`, `g`) und `amount`. Rezepte und Zutaten liegen in SQLite und sind damit in der Update-Sicherung enthalten.

## Navigation und Schnellwahl (1.4.0)

Drei Seiten: Übersicht mit Tageswerten und Schnellwahl, Mahlzeiten mit normaler Erfassung und Rezept-Verzehr, Rezepte mit Bearbeitung und Zutaten-Erfassung. Die Navigation unterstützt Zurück/Vorwärts über URL-Fragmente. Schnellwahl erfasst 250 ml Wasser oder 200 ml Kaffee mit vorbelegten 80 mg Koffein zum aktuellen Zeitpunkt, unabhängig vom gewählten Tag. Die Koffeinmenge ist eine Schätzung, keine Messung. Bei Übertragungsfehlern verwendet erneutes Tippen dieselbe Eintrags-ID. Einstellungen und konfigurierbare Schnellwahl folgen später.

## Alkohol-Tagebuch (1.14.0)

Die Alkoholseite speichert echte Getränke im Tagebuch. Eingabe wahlweise als Gramm reinen Alkohols oder als Getränkemenge in ml und Volumenprozent (Ethanol = ml × ABV/100 × 0,789 g/ml). Ein optionaler Name und eine bearbeitbare Uhrzeit gehören zum Eintrag; die Uhrzeit steht beim Öffnen und nach erfolgreichem Speichern auf jetzt. Getränkekalorien werden ohne Produktdaten nicht geschätzt.

Die Schnellwahl zeigt in Einstellungen gespeicherte Alkohol-Kacheln und verknüpfte Rezepte mit Alkohol. Auch hierfür gilt die Uhrzeit aus der Eingabemaske. Reiner Alkohol in Gramm kann als Schnellwahl und Favorit gespeichert werden. Einträge erscheinen unter Mahlzeiten und lassen sich über die Detailseite zeitlich ändern oder mit Bestätigung löschen. Unklare Übertragungen werden mit derselben ID und denselben Daten wiederholt.

Der Tagesverlauf kommt aus `/alcohol-summary?start=…&end=…` und den Körperparametern in Einstellungen: Körpergewicht, Verteilungsfaktor r, Abbau β und Aufnahmerate kₐ. Der Tag ist wählbar; frühere Einträge fließen als Restalkohol ein, Rezeptzutaten zählen erst beim gebuchten Verzehr. Ohne Körperprofil oder bei offenen Alkoholeinträgen wird keine Kurve angezeigt. Der aktuelle BAC verwendet nur bis jetzt eingetragene Getränke. Zukünftige Abschnitte der Kurve sind gestrichelt und stellen eine Prognose aus den bereits eingetragenen Mengen dar.

Die exponentielle Aufnahme wird zwischen Getränkezeiten analytisch integriert, der Abbau endet bei null. Es entsteht kein Abbau-Abzug für spätere Getränke nach Nüchternphasen. Die Kurve wird minütlich abgetastet, Eintragungszeiten werden exakt berücksichtigt. Home und Alkoholseite verwenden dieselbe Berechnung. BAC ist ein Schätzwert, kein Messwert und keine Grundlage für Fahrentscheidungen. Die frühere separate Simulation entfällt vollständig.

Prüfungen: `python -m unittest discover -s tests -q`, `node tests/test_alcohol_ui.cjs`, `node tests/test_goals.cjs`. Ein echter iPhone-Test bleibt auf dem Zielgerät erforderlich.

## Home und Einstellungen (1.6.0)

Home zeigt zuerst deine Schnellwahl-Buttons, darunter heutige Standard-Nährwerte als Liste, eine Tabelle für Koffein (mg), Alkohol (g Ethanol) und aktuellen modellierten BAC (% / ‰), danach alle weiteren Nährstoffe aus den BLS-Einträgen. Home verwendet immer den aktuellen lokalen Tag des Browsers. Die Datumswahl gilt für Mahlzeiten. Getrunkenes Wasser bleibt getrennt von Wasser in Lebensmitteln. Tagesgesamtwerte mit fehlenden Zutaten-/Nährwertangaben werden als unvollständig markiert; TR und Nachweisgrenzen bleiben erhalten. Bestätigte BLS-Mikronährstoffe werden mit ihren Einheiten dargestellt; unbekannte Quellenwerte werden nicht nach Health exportiert.

Unter Einstellungen Schnellwahl-Buttons anlegen, bearbeiten oder löschen: Wasser, Koffein, Alkohol, BLS-Lebensmittel, Barcode oder Text mit festgelegter Menge. Bei BLS kann über die Suche ein Code gewählt werden. Label und optionales Bild werden auf Home angezeigt. JPEG/PNG/WebP bis 5 MiB und 16 Megapixel; Bilder werden dekodiert, auf maximal 512×512 verkleinert und ohne Metadaten als PNG gespeichert. Bilder und Einstellungen liegen in SQLite und werden durch die Datenbank-Sicherung des Update-Skripts erfasst. Keine Fotos oder Schlüssel werden in Git gespeichert.

Für aktuellen BAC in Einstellungen Körpergewicht, r, β (% BAC/h) und Aufnahmefaktor kₐ (1/h) speichern. Berechnung aus tatsächlich protokollierten Getränke- und Rezept-Alkoholmengen bis jetzt; offene Alkoholeinträge blockieren die Schätzung. Der Home-Wert aktualisiert sich einmal pro Minute. Abbau endet bei null und wird nach Nüchternphasen nicht auf spätere Getränke angerechnet. Kein Messwert oder Fahreignungsnachweis.

API: GET/PUT `/settings` (Versionsnummer verhindert konkurrierendes Überschreiben), POST `/quick-buttons/{id}/intake`, PUT/GET/DELETE `/quick-buttons/{id}/image`, GET `/home-summary?start=…&end=…` mit Zeitzonen. Alle Endpunkte inklusive Bilder erfordern Authentifizierung.

## Statistik (1.7.0)

Neue Seite „Statistik“: 7, 30 oder 90 Tage bzw. frei wählbarer Zeitraum bis 366 Tage. Summen und Tagesdurchschnitte für Kalorien, getrunkenes Wasser, Koffein und Alkohol; Verlauf zusätzlich für Protein, Kohlenhydrate und Fett. Interaktive Balkengrafik mit Tagesauswahl per Slider oder Tippen, darunter vollständige Tageswerttabelle. Tage ohne Einträge oder ohne berechnete Nährwerte bleiben Lücken. Durchschnitte pro Kennzahl teilen durch Tage mit berechnetem Wert, nicht durch alle Kalendertage. Die jeweiligen Tagzahlen sind sichtbar. Null bei Wasser/Koffein/Alkohol bedeutet keine entsprechende Menge protokolliert an einem Tag mit berechneten Einträgen, nicht bestätigte Nichtaufnahme.

Offene Einträge und unvollständige Nährstoffsummen sind gekennzeichnet. Die BLS-Einheiten und die Bezugsgröße pro 100 g sind bestätigt. Rezeptzutaten sind ausgeschlossen; gegessene Rezeptportionen sind enthalten. Kalendergrenzen einschließlich Sommer-/Winterzeit verwenden die IANA-Zeitzone des Browsers.

API: `GET /statistics?start=2026-10-01&end=2026-10-10&tz=Europe/Berlin` (Start und Ende inklusive). Vollständige Auswertung ohne 1.000-Einträge-Limit, geschützt durch dieselbe Anmeldung. Keine neue Datenhaltung; bestehende Einträge werden ausgewertet.

## Rezept-Zusätze und Rezept-Schnellwahl (1.8.0)

Auf der Rezeptseite zusätzliche Mengen für das **ganze Rezept** erfassen: Wasser in ml, Koffein in mg und reiner Alkohol in g. Diese werden zu bereits erfassten Zutatenmengen addiert, nicht als deren Ersatz verstanden. Beispiel Cappuccino: Espresso und Milch als Zutaten, fehlende Koffeinmenge im Zusatzfeld. Bereits erfasstes Koffein nicht nochmals ergänzen. Jede Portion, jeder Bruchteil und jede Grammmenge skaliert Zusätze und Nährwerte mit demselben Faktor. Fertiges Gesamtgewicht bei Wasserzugabe gegebenenfalls selbst anpassen. Zusätzliche Alkoholangaben ergänzen keine automatisch geschätzten Getränkekalorien.

Unter Einstellungen → Schnellwahl → Erfassung „Rezept“ wählen, Rezept und Menge auswählen (Portionen, Anteil 0–1 oder Gramm). Für Gramm ist das fertige Rezeptgewicht erforderlich. Ein Antippen auf Home bucht den Rezept-Verzehr mit allen berechneten Nährwerten, Koffein, Wasser und Alkohol. Derselbe Übertragungsversuch erzeugt keinen zweiten Eintrag; gespeicherte Rezept-Snapshots schützen frühere Mahlzeiten vor späteren Änderungen. Ungeklärte Zutaten blockieren die Buchung weiterhin.

Wasser aus Rezeptzusätzen und expliziten Wasser-Zutaten zählt zu getrunkenem Wasser auf Home und in der Statistik. Wassergehalt aus BLS-Lebensmitteln bleibt davon getrennt. Alkohol aus Rezepten wird auch für den BAC-Modellwert berücksichtigt. Nur nicht prüfbare BLS-Alt-Einträge bleiben für Health gesperrt.

API-Rezeptfelder: `added_water_ml`, `added_caffeine_mg`, `added_ethanol_g` (nichtnegative Mengen, Standard 0). Schnellwahl-Preset: `{"type":"recipe","recipe_id":"UUID","quantity":{"value":1,"unit":"portion"}}`.

## Tagesziele und Tagesexport (1.9.0)

Einstellungen: optionale, unabhängige Ziele für kcal, Protein, Kohlenhydrate und Fett. Home zeigt bekannte Mengen, Prozent, Rest/Überschreitung und unvollständige Summen. Keine automatisch berechneten Empfehlungen.

Health-Export listet die Tage in der iPhone-Zeitzone. „Tag exportieren“ reserviert eine unveränderliche Tagesdatei. Download/Teilen allein bedeutet **nicht**, dass Health geschrieben wurde. Erst nach erfolgreichem Schreiben durch einen iPhone-Kurzbefehl bestätigen. Bei Teilfehlern/Abbruch „fehlgeschlagen / unklar“ wählen und Health manuell prüfen. Keine automatische Wiederholung. Nachträgliche Tagebuchänderungen werden gekennzeichnet; vorhandene Health-Samples werden nicht automatisch korrigiert.

Tage und Rezepte mit bestätigten BLS-Einheiten sind exportierbar. Nicht prüfbare Alt-Einträge bleiben gesperrt. Offene Einträge und vorherige Einzel-Exporte sperren ebenfalls die Tagesreservierung. Exportiert werden bekannte Ernährungswerte mit bestätigten Einheiten; fehlende Nährstoffe werden nicht als Null ergänzt. Alkoholgramm und BAC sind keine HealthKit-Ernährungstypen und werden nicht exportiert. Tageswerte haben als Zeitpunkt 12 Uhr in der gewählten Zeitzone. Rezeptzutaten werden ausgeschlossen.

### iPhone-Kurzbefehl für die Tagesdatei

Ein Kurzbefehl muss erst auf dem iPhone erstellt und getestet werden; diese Version liefert keine installierbare .shortcut-Datei und kann keine Health-Berechtigung aus dem Browser erteilen.

1. Einen Kurzbefehl erstellen und im Teilen-Menü für Dateien aktivieren.
2. „Wörterbuch aus Eingabe abrufen“ auf die geteilte JSON-Datei anwenden.
3. Den Wert `samples` abrufen und alle Elemente wiederholen.
4. `identifier`, `value`, `unit` und `timestamp` aus dem Wiederholungselement lesen. Je identifier eine passende „Gesundheitsdaten protokollieren“-Aktion verwenden, mit expliziter Einheit und Datum. Die Aktion muss auf dem iPhone für die betreffende Kategorie verfügbar sein.
5. Beispiele: dietaryEnergyConsumed → Nahrungsenergie (kcal), dietaryProtein → Protein (g), dietaryCarbohydrates → Kohlenhydrate (g), dietaryFatTotal → Gesamtfett (g), dietaryWater → Wasser (ml), dietaryCaffeine → Koffein (g). Andere exportierte Typen benötigen eigene Zuordnungen. Unbekannte Typen müssen den Ablauf abbrechen, nicht still übersprungen werden.
6. Erst nach **allen** erfolgreichen Aktionen in Friss „Health-Schreiben bestätigen“. Das ist eine Nutzerbestätigung, keine automatische Prüfung der Health-Daten. Bei Fehlern Health-Bestand prüfen und Export als unklar markieren.

API für eine spätere automatische Anbindung: GET /health-days?tz=Europe/Berlin, POST /health-days/prepare mit day und timezone, GET /health-days/{id}, POST /health-days/{id}/ack mit export_token und success. Authentifizierung wie bisher über Bearer-API-Key bzw. Dashboard-Sitzung. API-Key nicht in geteilten Dateien speichern.

Rezeptbuchungen speichern Nährwerte und Rezeptdetails zum Buchungszeitpunkt. Rezeptänderungen betreffen nur künftige Buchungen. Alte Verzehre bei Bedarf löschen und neu buchen; Health-Korrekturen separat vornehmen.

## Barcode per Foto (1.9.1)

Bei Erfassung „Barcode“ auf „Barcode fotografieren“ tippen. Der iPhone-Kameradialog verwendet ein Datei-Eingabefeld mit capture=environment; Live-Kamera/HTTPS sind dafür nicht erforderlich. Der Browser verkleinert das Bild bei Bedarf auf 2.400 Pixel und sendet JPEG an den authentifizierten Endpunkt POST /barcode-scan. Der Server dekodiert EAN-8, EAN-13 und UPC-A mit ZXing-C++; das Scanbild wird nicht dauerhaft gespeichert oder an Open Food Facts geschickt. Bei mehreren Treffern Nummer auswählen, Menge in Gramm angeben und speichern. Erst beim Speichern erfolgt die Open-Food-Facts-Abfrage. Bei unscharfen Bildern erneut fotografieren oder Nummer manuell eingeben. Der genaue Kameradialog hängt vom Browser ab.

Auch bei Rezeptzutaten und Barcode-Presets unter Einstellungen verfügbar. Keine automatische Buchung durch einen Scan. Maximale Uploadgröße 10 MiB / 16 Megapixel; unterstützte Serverbildformate JPEG, PNG und WebP. HEIC wird nach Möglichkeit durch den Browser nach JPEG konvertiert; kann der Browser das Bild nicht öffnen, bitte JPEG verwenden. Scan-Prüfungen verwenden echte generierte Barcodes, rotierte Bilder, mehrere Codes, fehlerhafte Uploads und eine simulierte OFF-Antwort.

## Mahlzeitendetails (1.10.0)

„Rezept essen“ ist eine Erfassungsmethode unter Mahlzeiten. Rezept auswählen, Portionen/Bruchteil/Gramm und Zeitpunkt angeben, über den gemeinsamen Speichern-Button buchen. Auf der Rezeptbearbeitungsseite ist die Option ausgeblendet, um keine Rezepte als ihre eigenen Zutaten zu buchen.

Ein Tagebucheintrag öffnet seine Detailseite. Sie zeigt Name, Zeitpunkt, Menge, Erfassungsmethode, Datenquelle, Barcode (falls vorhanden), Eintrags-ID, Verarbeitung und Health-Status sowie alle Nährstoffbeiträge der eingetragenen Menge. Ungeprüfte BLS-Quelleinheiten und TR bleiben gekennzeichnet. Bei Rezeptverzehr werden die gespeicherten Momentaufnahmen verwendet.

Zeitpunktänderungen ändern ausschließlich Zeitpunkt/Revision im Tagebuch, keine Nährwerte oder Originaldateien. Ein Wechsel des Datums verschiebt den Beitrag zum neuen Tag. Bereits exportierte Health-Daten werden nicht geändert; betroffene Tagesexporte erscheinen als geändert. GET /entries/{id}/details liefert die Detaildaten, PATCH /entries/{id}/time akzeptiert einen zeitzonenbehafteten timestamp.

## Zuletzt benutzt und Favoriten (1.11.0)

Im Eingabebereich „Zuletzt benutzt“ oder „Favoriten“ öffnen. Ein Treffer füllt die Erfassungsmaske mit Lebensmittel und Vorschlagsmenge. Zeitpunkt und Menge prüfen und anschließend speichern. Jeder Verzehr ist ein neuer Eintrag mit eigener ID und eigenem Health-Status. Dieselben Auswahlhilfen stehen bei Rezeptzutaten bereit.

„Zuletzt benutzt“ zeigt die letzten 100 unterschiedlichen wiederverwendbaren Lebensmittel aus Tagebuch und Rezeptzutaten, in Reihenfolge der Anlage, unabhängig vom ausgewählten Tagebuchtag. Gleiche BLS-Codes und Barcodes werden zusammengefasst. Getränke und Texte sind ebenfalls wiederverwendbar. Aufgelöste Fotoeinträge werden als zugeordnetes Lebensmittel übernommen. Fotos ohne Lebensmittelzuordnung und ganze Rezeptverzehre werden ausgeschlossen; ganze Rezepte weiterhin über „Rezept essen“ buchen.

Die Favoritenseite bietet Anlegen über Lebensmittelsuche, Barcode, Text oder Getränke sowie Übernahme aus zuletzt benutzten Lebensmitteln. Name, Zuordnung und Vorschlagsmenge sind editierbar. Favoriten liegen in SQLite, bleiben nach Neustart erhalten und werden vom vorhandenen Backup erfasst. Änderungen/Löschen wirken nur auf Vorlagen, nicht auf bestehende Mahlzeiten, Rezepte oder Health-Daten. Löschen fragt nach Bestätigung. Gleichzeitige Änderungen werden über eine Versionsnummer abgefangen.

API: GET /recent-ingredients?limit=100 (maximal 200), GET/POST /favorites, PUT /favorites/{id}, DELETE /favorites/{id}?version=N. Alle Endpunkte benötigen Authentifizierung. Vorlagen enthalten weder Verbrauchszeitpunkt noch recipe_id oder Health-Status.

## Lernende BLS-Suche (1.12.0)

Jeder bewusst angeklickte BLS-Suchtreffer speichert eine Zuordnung von Suchbegriff, UI-Sprache und BLS-Code. Groß-/Kleinschreibung, äußere/mehrfache Leerzeichen und Akzente werden normalisiert. Wenn du bei „Zucker“ Haushaltszucker auswählst, wird derselbe Treffer bei zukünftigen Suchen nach „Zucker“ höher angezeigt. Häufigere Auswahlen stehen zuerst; bei gleicher Häufigkeit zählt die zuletzt getroffene Auswahl. Danach folgen exakte Namen, Namensanfänge und kürzere Bezeichnungen. Die Sortierung findet vor der Begrenzung auf die angefragte Trefferzahl statt.

Mahlzeiten- und Rezeptzutatensuche, Favoritensuche und Schnellwahl-Suche verwenden dieselben persönlichen Zuordnungen. Deutsch und Englisch sowie verschiedene Suchbegriffe werden getrennt gelernt. Bloßes Tippen, Anzeige eines Treffers, automatisches Textauflösen oder Wiederverwenden eines Favoriten zählen nicht als Suchauswahl. Die Zuordnungen liegen lokal in SQLite, bleiben nach Neustart erhalten und sind Bestandteil der bestehenden Datenbanksicherung. Aktuell gilt die Personalisierung für den gemeinsamen Friss-Zugang.

POST /food-search/selections erhält id (UUID pro Auswahl), query, lang (de/en) und bls_code. Wiederholte Übertragung derselben ID zählt nur einmal. Die API prüft, dass der gewählte BLS-Treffer zur Suche gehört. Schlägt das Lernen fehl, bleibt der gewählte Lebensmittel-Treffer verwendbar und das Dashboard zeigt einen Hinweis.

## Nachbearbeiten (1.12.1)

Die Mengenbeschriftung heißt „Menge (g)“. Bei der ersten Erfassung darf sie weiterhin leer sein; beim Nachbearbeiten wird eine Menge benötigt. „Nachbearbeiten“ lädt das bereits bekannte Lebensmittel, Menge, ursprünglichen Zeitpunkt und vorhandene Getränkeparameter in die Erfassungsmaske. Nur noch Fehlendes ergänzen. Ohne bisherige Lebensmittelzuordnung bleibt die Suche nötig. Erkannte OFF-Produkte werden beim Ergänzen der Menge aus ihren gespeicherten Produktdaten berechnet; die ursprüngliche Erfassungsmethode, Rezeptzuordnung und Originaldatei bleiben erhalten.

## Eigene Zutaten (1.13.0)

Auf der Seite „Eigene Zutaten“ Namen, Notizen und bekannte Nährwerte **pro 100 g** erfassen. Ein leerer englischer Name übernimmt den deutschen Namen. Die Oberfläche bietet Kalorien, Makros und alle unterstützten weiteren Ernährungswerte mit expliziter Einheit. Wasser verwendet ml, Energie kcal, Massenwerte g/mg/mcg; reiner Alkohol hat ein eigenes g-pro-100-g-Feld. Keine automatische Schätzung von Kalorien aus Makronährstoffen. Leer bedeutet unbekannt; eingegebene 0 bedeutet bekanntes Null. Mindestens ein Wert ist erforderlich.

Unter Mahlzeiten und Rezeptzutaten „Eigene Zutaten“ als Erfassungsoption wählen, Definition auswählen und konsumierte/verwendete Gramm eingeben. Eine zunächst fehlende Menge kann wie gewohnt nachbearbeitet werden. Erfassung speichert eine Definitions-Momentaufnahme. Änderungen und Löschen an einer Definition verändern keine vorhandenen Mahlzeiten oder Rezeptzutaten. Um eine aktualisierte Definition in einem bestehenden Rezept zu verwenden, dessen entsprechende Zutat neu hinzufügen. Bereits gebuchter Rezeptverzehr behält ebenfalls seine Werte.

Zuletzt benutzt und Favoriten können eigene Zutaten wiederverwenden. Gelöschte Definitionen müssen für neuen Verzehr neu angelegt bzw. durch eine gültige Definition ersetzt werden; vorhandene Einträge mit fehlender Menge lassen sich anhand ihrer gespeicherten Momentaufnahme weiterhin vervollständigen. Werte mit expliziten Einheiten gehen in Home, Statistik, Rezepte und Health-Ernährungsexport ein. Alkoholgramm fließen in das lokale Alkoholtracking ein; BAC wird wie bisher nur geschätzt. Nahrungswasser ist weiterhin kein separat getrunkenes Wasser.

Die Definitionen liegen in SQLite und sind Bestandteil des bestehenden Backups. Alle API-Endpunkte benötigen Authentifizierung: GET/POST /manual-ingredients, GET /manual-ingredients/schema, PUT /manual-ingredients/{id}, DELETE /manual-ingredients/{id}?version=N. Versionsprüfung verhindert Überschreiben paralleler Änderungen.


## Eigene Zutaten aus FoodData Explorer importieren (1.15.0)

Unter Eigene Zutaten einen Link wie `https://fooddata.the50.store/ingredients/2010-spices-cinnamon-ground` einfügen und Nährwerte importieren. Der Server liest die strukturierte Nährwertbeschreibung und ergänzt veröffentlichte Tabellenwerte. Nur ausdrücklich pro 100 g deklarierte Daten werden übernommen. Die Vorschau erstellt eine neue Zutat; vorhandene Eingaben werden nach Rückfrage ersetzt. Namen, Werte und Notizen können vor dem Speichern angepasst werden. Importierte Zutaten sind anschließend wie andere eigene Zutaten in Mahlzeiten, Rezepten, Favoriten und zuletzt benutzt verfügbar.

g / mg / UG / µg / mcg werden in die passenden Einheiten der Eingabemaske umgerechnet; Kilojoule in kcal, Vitamin-D-IU in mcg, sofern nötig. Vitamin-A-IU werden mangels eindeutiger Zusammensetzung nicht geraten. Folat-Gesamtwert wird nicht mit Food-Folat oder DFE addiert, Vitamin-A-RAE nicht mit Carotinen. Fehlende Werte und unbekannte Einheiten bleiben leer; ausdrücklich veröffentlichte Nullwerte bleiben 0. Nicht unterstützte Komponenten werden angezeigt. Englische Quellnamen werden übernommen und können auf Deutsch angepasst werden.

USDA-Kohlenhydrate „by difference“ enthalten Ballaststoffe. Ab 1.15.1 zieht der Importer die bekannte Ballaststoffmenge ab und übernimmt Kohlenhydrate ohne Ballaststoffe. Ballaststoffe und Energie bleiben unverändert; Originalwerte und Rechnung bleiben in den Quellenangaben erhalten. Fehlen Ballaststoffe oder übersteigen sie den Gesamtwert, bleibt Kohlenhydrate unbekannt. Bereits gespeicherte Zutaten bitte erneut importieren; bestehende Mahlzeiten und Rezept-Snapshots werden nicht rückwirkend geändert. Lebensmittelwasser wird als g gespeichert; kein Umrechnen in Trinkvolumen und kein Export als Health-Wasser in ml. Eigene Zutaten unterstützen dafür neben ml nun g als Wasser-Einheit.

Quelllink, Abrufzeit, Bezugsgröße und veröffentlichte Rohwerte werden mit der Zutat gespeichert und bleiben im Snapshot eines gebuchten Eintrags erhalten. Der Import benötigt vom Debian-Server aus Internetzugriff auf `fooddata.the50.store`. Andere Domains und Pfade werden abgelehnt, Weiterleitungen nicht verfolgt; Zeitüberschreitung, 404 und zu große Seiten führen zu einer Fehlermeldung ohne Speicherung. Ein HTML-Import führt keine fremden Skripte aus.

API: authentifiziertes `POST /manual-ingredients/import` mit `{"url":"https://fooddata.the50.store/ingredients/…"}` liefert eine Vorschau, keine automatische Speicherung. Noch offen ist ein echter Test in der iPhone-PWA auf dem Zielserver. Prüfungen umfassen den Zimt-Datensatz, Einheiten, Null-/Fehlwerte, Varianten, Quellen-Snapshots, Abrufgrenzen und die Eingabemaske (`node tests/test_manual_import_ui.cjs`).


## Fehlende Nährwerte als Null behandeln (1.16.0)

Unter Einstellungen → Fehlende Nährwerte lässt sich „Fehlende Nährwerte als 0 behandeln“ aktivieren. Standardmäßig ist die Option ausgeschaltet. Sie ergänzt leere / null / nicht vorhandene Nährwertfelder in der Auswertung mit gekennzeichneten, angenommenen Nullwerten. Bereits gespeicherte und neue Einträge, Tagesziele, Tageswerte, Rezeptberechnungen und Statistiken verwenden dieselbe Einstellung. Bei Rezepten werden bekannte Werte einzelner Zutaten weiterhin mitgerechnet, auch wenn andere Zutaten den jeweiligen Wert nicht liefern.

Die Rohdaten, eigenen Zutaten und gebuchten Rezept-Snapshots werden nicht überschrieben. Ausschalten stellt die ursprünglichen unbekannten Angaben wieder her. Fehlende Mengen oder Lebensmittelidentitäten bleiben zur Nachbearbeitung offen; Bei aktivierter Option werden auch TR, <LOD und <LOQ sowie Kombinationen davon als angenommene Nullwerte ausgewertet. Beim Ausschalten erscheinen die Originalangaben wieder. Nicht leere Zahlen mit unbekannter Einheit bleiben als solche erhalten. „Unvollständig“ entfällt für durch Nullannahmen ergänzte Nährwertsummen, nicht für tatsächlich offene Einträge. Tage ohne Einträge bleiben Statistik-Lücken.

Die Einstellung gilt auch für künftig vorbereitete Health-Exporte; Nullannahmen sind keine gemessenen Nullwerte. Vorbereitete Tagesbatches und bereits reservierte Einzel-Exporte behalten ihre damaligen Werte. Ein Wechsel der Einstellung markiert einen vorhandenen Tagesbatch als seit Vorbereitung verändert und gibt ihn nicht erneut zum Export frei. Lebensmittelwasser in g bleibt vom Health-Wasservolumen in ml getrennt.

API-Einstellung: `missing_nutrients_as_zero` im bestehenden versionierten `/settings`-Objekt. Angenommene Werte tragen in Eintragsansichten `assumed: true`; Originaldaten bleiben in SQLite / ursprünglichen Dateien unverändert. Tests prüfen Umschalten, Neustart, Rezeptanteile, Statistik-Lücken, offene Mengen und unveränderliche Health-Batches.


## Beiträge zu Tageswerten (1.17.0)

Auf Home auf einen Kalorien-, Makro-, Mikro-, Wasser-, Koffein- oder Alkoholmengenwert tippen, auch in den Zielkarten. Eine Übersicht zeigt die heutigen Einträge mit Uhrzeit, verzehrter Menge und Beitrag zu genau diesem Wert. Ein Eintrag öffnet seine Detailseite. Nullwerte, angenommene Nullen und unbekannte Angaben stehen in einem separaten aufklappbaren Abschnitt. Rezeptportionen werden als gebuchte Einträge angezeigt, Zutaten nicht zusätzlich gezählt. BLS-Wassergehalt und getrunkenes Wasser behalten ihre getrennten Berechnungen. Der BAC ist eine Modellschätzung und keine additive Nährstoffsumme.

Die Daten kommen zusammen mit der Tagesübersicht aus `/home-summary`; Contributors verwenden dieselben Einheiten, Tagesgrenzen und Null-Einstellung wie die Summe. Bei Abmeldung schließt die Übersicht und verwirft ihre Inhalte. Tests prüfen die Übereinstimmung von Einzelbeiträgen und Summen, Rezeptzutaten-Ausschluss sowie Öffnen und Schließen der Übersicht.


## JSON-Handoff aus ChatGPT (1.19.0)

Unter Mahlzeiten oder bei Rezeptzutaten **JSON aus ChatGPT importieren** öffnen. Dort die kopierbare ChatGPT-Vorlage mit Foto oder Beschreibung in der ChatGPT-App verwenden, deren JSON als Text einfügen oder Datei hochladen, die Lebensmittel / Mengen prüfen und gemeinsam speichern. Friss führt keinen KI-Aufruf aus. Die Nährwerte können direkt aus der ChatGPT-Ausgabe übernommen und in der Vorschau korrigiert werden, oder aus gewählten BLS-Datensätzen / eigenen Zutaten kommen; fehlende Zuordnungen bleiben nachbearbeitbar. Die Eingabe wird im Original erhalten, Wiederholungen sind durch die Import-ID gegen doppelte Buchung abgesichert.

Das vollständige Format `friss-meal-v1`, Beispiele, API und Nutzung sind in [JSON_IMPORT.md](docs/JSON_IMPORT.md) beschrieben. Eine [Beispieldatei](app/static/friss-meal-example.json) liegt ebenfalls bei. Mengen in Fotos als Schätzungen behandeln; ml nicht ohne bekannte Dichte zu g umdeuten. Der Import gilt für eine Mahlzeit beziehungsweise eine Zutatenliste mit einem gemeinsamen, bearbeitbaren Zeitpunkt.
