## 1.13.1 — Bestätigte BLS-4.0-Einheiten

- Originaltabelle bestätigt Einheiten und alle Werte pro 100 g; Mikronährstoffe werden berechnet und sind für Health verfügbar.
- Noch nicht exportierte BLS-Einträge werden beim Start aus ihren gespeicherten Originalwerten ergänzt, einschließlich eingefrorener Rezeptzutaten. Exportierte Einträge und reservierte Tage bleiben unverändert.
- TR/null bleiben unbekannt; nicht belegte Einheiten bleiben gesperrt. Lebensmittelwasser bleibt in g und wird nicht als Health-Wasservolumen exportiert.
- 46 Python-Tests sowie BAC- und JavaScript-Prüfungen bestanden.

# Changelog

## 1.13.0

Eigene Zutaten mit Deutsch-/Englisch-Namen und expliziten Nährwerten pro 100 g anlegen, bearbeiten und löschen. Auswahl in Mahlzeiten und Rezeptzutaten; Integration in zuletzt benutzt und Favoriten. Unbekannte Werte bleiben leer, Einträge behalten unveränderliche Definitions-Momentaufnahmen.

## 1.12.1

Mengenbeschriftung ohne „optional“, spätere Ergänzung bleibt möglich. Nachbearbeitung stellt bekannte Lebensmittel, Menge, Zeitpunkt und Getränkeparameter wieder her. Bereits erkannte OFF-Produkte werden bei Mengenergänzung aus gespeicherten Daten berechnet.

## 1.12.0

Lernende BLS-Suchsortierung nach ausgewählten Treffern pro normalisiertem Suchbegriff und Sprache. Häufigkeit, letzte Auswahl und Textrelevanz bestimmen die Reihenfolge vor der Trefferbegrenzung. Auswahl aus Mahlzeiten, Rezeptzutaten, Favoriten und Schnellwahl lernt gemeinsam; Speicherung lokal in SQLite.

## 1.11.0

Zuletzt benutzte Lebensmittel aus Tagebuch und Rezeptzutaten mit Deduplizierung und Vorschlagsmengen. Separate Favoritenseite zum Anlegen, Bearbeiten, Löschen und Verwenden; persistente Vorlagen ohne Health-Status. Auswahl füllt die bestehende Erfassungsmaske, ohne automatisch zu buchen.

## 1.10.0

Rezeptverzehr als Erfassungsoption statt separatem Mahlzeitenpanel. Anklickbare Tagebucheinträge mit Detailseite für Metadaten, Herkunft, Health-Status und sämtliche Mengenbeiträge. Zeitpunkt bearbeitbar, Originaldateien und Nährwert-Momentaufnahmen bleiben erhalten; betroffene Health-Tagesexporte werden als geändert markiert.

## 1.9.1

Barcode fotografieren über den iPhone-Datei-/Kamera-Dialog, lokal auf dem Server dekodieren und Nummer übernehmen. EAN-8, EAN-13 und UPC-A; Auswahl bei mehreren Treffern. In Mahlzeiten, Rezeptzutaten und Barcode-Schnellwahl verfügbar; manuelle Eingabe bleibt möglich.

## 1.9.0

Zutaten ohne Health-Status, Rezept-Momentaufnahmen erklärt. Einstellbare Kalorien-/Makroziele mit Fortschrittsanzeigen auf Home. Health-Tagesexport mit unveränderlichen Reservierungen, Download/Teilen für iPhone-Kurzbefehle, ausdrücklicher Erfolgsbestätigung und Änderungskennzeichnung. BLS-Einheitensperre bleibt erhalten.

## 1.8.3

Einzelne Tagebucheinträge und Rezeptzutaten löschen; ausgewählten Tagebuchtag zurücksetzen, jeweils mit Bestätigung. Rezepte und Originaldateien bleiben erhalten. Hinweis auf separat nötige Apple-Health-Korrekturen.

## 1.8.2

Größeres App-Icon mit gemeinsam ausgerichteter Grundlinie von f und Punkt. Neue Icon-Dateinamen für iOS und PWA.

## 1.8.1

Überschriftenblock unter der Navigation entfernt. Alle Menütasten bleiben ohne horizontales Scrollen sichtbar. Schnellwahlbilder füllen ihre Kacheln randlos aus; weiterhin vier Kacheln pro Reihe.

## 1.8.0

Zusätzliche Wasser-, Koffein- und Alkoholmengen pro Rezept mit gemeinsamer Portion-/Gramm-Skalierung. Rezept-Schnellwahltasten inklusive aller berechneten Nährwerte. Wasserzusätze fließen in Home und Statistik ein; Rezeptalkohol in den BAC-Modellwert.

## 1.7.1

Kleine Schnellwahl-Kacheln mit ausschließlich Piktogrammen, vier je Reihe auch auf dem iPhone. Eigene Bilder oder Standardsymbole; Beschriftung und Menge bleiben für Screenreader/Tooltip erhalten. Keine feste Button-Anzahlbegrenzung.

## 1.7.0

Statistikseite mit Zeitraumauswahl, Summen und Tagesdurchschnitten, interaktiven Verläufen und Tageswerttabelle. Fehlende Tage bleiben Lücken, unvollständige Werte sind markiert. Lokale Kalendergrenzen mit Sommerzeit-Unterstützung.

## 1.6.0

Home mit anpassbarer Schnellwahl und hochladbaren Button-Bildern. Einstellungen für Presets und explizite BAC-Modellparameter. Heutige Nährwerte als Liste, Koffein/Alkohol/BAC-Tabelle und vollständige weitere BLS-Nährstoffe mit ungeprüften Quelleinheiten klar gekennzeichnet.

## 1.5.0

Alkohol-Seite mit illustrativem BAC-Modell für mehrere Getränke, globalen und individuellen Parametern, interaktiver Zeitreihe und Prozent/Promille-Anzeige. Einheitenkorrektur und Modellgrenzen explizit erklärt; keine automatische Verzehrbuchung.

## 1.4.0

Drei navigierbare Seiten für Übersicht, Mahlzeiten und Rezepte. Schnellwahl für Wasser und Kaffee mit sichtbaren Mengen; getrennte Tages- und Zutatenlisten.

## 1.3.0

Gespeicherte Rezepte mit separaten Zutaten über alle bestehenden Erfassungsmethoden. Tagebuch-Verzehr per Portion, Bruchteil oder Gramm mit fertigem Gesamtgewicht. Unaufgelöste Zutaten blockieren Verzehr, Snapshots schützen bestehende Einträge vor späteren Rezeptänderungen.

## 1.2.2

Docker setzt Eigentümer und Leserechte der App explizit. Update-Skript verwendet restriktive Rechte nur für Backups, nicht für den Git-Checkout, und zeigt Logs bei Startfehlern.

## 1.2.1

Passwort-Label direkt im HTML korrigiert; versionierte Dashboard-Assets und no-store gegen veraltete Login-Anzeige.

## 1.2.0

Passwort-Anmeldung mit scrypt-Hash, widerrufbaren 30-Tage-Sitzungen und Login-Limit. Cookie-Anfragen prüfen den Origin. Update-Skript mit SQLite-Sicherung und Startprüfung. PWA-Manifest und Home-Screen-Icons.

## 1.1.0

Deutsch/englisches Dashboard auf `/`, Tagesfilter, Erfassung und Nachbearbeitung. Persönliche API-Daten weiterhin mit Bearer-Key geschützt. Konfigurierbarer äußerer Port (Standard 8001).

## 1.0.0

Erste Server-API mit SQLite, zweisprachiger BLS-Suche, Open Food Facts, JPEG-Upload, unveränderten Originalen und reserviertem Health-Export. Docker-Deployment und Legacy-Importer. BLS-Export bis zur Einheitenprüfung gesperrt. Kein fertiger iPhone-Kurzbefehl und keine Foto-KI.
