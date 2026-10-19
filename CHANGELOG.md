## 1.33.0 — Originalfotos zu KI-Mahlzeiten hochladen

- #76: Authentifizierter Datei-Upload über `PUT /entries/{id}/photos` für bis zu 20 Originalbilder (JPEG/PNG/WebP) pro Eintrag; identische Wiederholungen erzeugen keine Duplikate.
- KI-Mahlzeitantwort enthält zusätzlich `entry_id` und `photo_upload_url`. Kein neues Modellformat, keine Base64-Konvertierung erforderlich.
- Originalfotos in der Eintragsdetailseite anzeigen; Dateien unverändert erhalten und bei Eintrags-/Rezeptkopien und ZIP-Sicherungen berücksichtigen.
- Dateigröße und tatsächliches Bildformat prüfen; Kurzbefehl-Anleitung für Datei-Upload und HEIC-zu-JPEG-Konvertierung ergänzt.

## 1.32.1 — Kategorien auf Home benennen

- #70: Home zeigt „Nährwerte“, „Koffein / Alkohol“ und die bestätigte Überschrift „Mikronährstoffe“; Englisch entsprechend „Nutrition“, „Caffeine / alcohol“, „Micronutrients“.

## 1.32.0 — ZIP-/JSON-Datensicherung und Wiederherstellung

- Einstellungen: ZIP herunterladen, Sicherung prüfen und nach Bestätigung vollständig wiederherstellen.
- Versionierter JSON-Export aller Fachdaten inklusive effektiver BLS-Daten, Bildern, Originaldateien und Health-Exportstatus; Zugangsdaten und Sitzungen ausgeschlossen.
- Vor Wiederherstellung automatisches Sicherungs-ZIP unter `data/recovery`; Datenbanktransaktion, Dateitausch mit Fehler-Rollback, Größen-/Pfad-/Prüfsummenprüfung und temporärer Wartungsmodus.
- Anleitung zu Wiederherstellung auf anderem Server und Health-Status nach älteren Sicherungen ergänzt.

## 1.31.0 — Schnellwahl, Mengenbearbeitung und Produktsuche

- #74: Schnellwahl in Einstellungen mit „Nach vorne“ / „Nach hinten“ sortieren; Reihenfolge wird sofort gespeichert und für Getränke übernommen.
- #3: Rezeptzutaten und Tagebucheinträge öffnen dieselbe Detailseite mit Nährwerten und Mengenbearbeitung. Änderungen skalieren gespeicherte Werte und erhalten Rezept-Snapshots, Originale und Zeitpunkte. Bereits exportierte Werte werden als geändert erkennbar; Health bleibt separat zu korrigieren.
- #1: Letzte bekannte Produktmenge aus Tagebuch und Rezeptzutaten als Vorschlag für BLS, Open Food Facts und eigene Zutaten übernehmen. Explizite Favoritenmengen und bereits ausgefüllte Eingaben bleiben erhalten.
- #2: Open Food Facts verwendet den funktionierenden Search-a-licious-Suchdienst; bisherige Suche bleibt Ausweichweg. Duplo-Suche live geprüft. Markenlisten korrekt anzeigen.

## 1.30.0 — KI-Mahlzeiten mit einem API-Aufruf speichern

- `POST /json-import` übernimmt KI-Text oder Objekt mit Nährstoffsummen für die verzehrte Portion; Zeitpunkt und Originalnachricht stammen aus dem Kurzbefehl.
- Server erzeugt IDs und verhindert doppelte Einträge bei identischen Wiederholungen. Originale, Schätzkennzeichnung und Portionsmenge bleiben erhalten.
- Kein UUID-, Vorschau- oder Commit-Schritt im Kurzbefehl nötig. Bestehender Browser-/Legacy-Importer bleibt verfügbar.
- Dokumentation, deutsche Modellvorlage und geprüftes Anfragebeispiel ergänzt.

## 1.29.1 — Rezept- und Getränkeauswahl trennen

- Getrennte Erfassungswege „Rezept essen“ und „Getränk trinken“ zeigen ausschließlich die passende Kategorie.
- Auswahl über die gemeinsame Suche übernimmt dieselbe Kategorietrennung; Getränke erhalten einen eigenen rosafarbenen Such-Tag statt des gelben Rezept-Tags.
- Veraltete separate OFF-Suchoption aus der iPhone-Auswahl entfernen. Open Food Facts bleibt Teil der gemeinsamen Suche.

## 1.29.0 — Home beginnt mit Tageswerten

- Schnellwahl-Kachelbereich von Home entfernen; Getränke behalten ihre Schnellwahl.
- Links neben den Such- / Barcode-Symbolen einen kompakten Fortschritt zum Kalorienziel anzeigen, alternativ zum ersten gesetzten Makroziel.
- Verbleibende / überschrittene Menge, fehlende Ziele und unvollständige Werte berücksichtigen.

## 1.28.2 — Navigation und Überschriften

- Menüfolge: Home, Mahlzeiten, Getränke, Rezepte, Favoriten, Manuell, Statistik, Export, Einstellungen.
- Menü und Seite Eigene Zutaten in Manuell umbenennen; Health-Export heißt im Menü Export.
- Getränkeüberschrift verkürzen und die Rezeptverwaltung als „Rezepte auswählen / anlegen“ beschriften.

## 1.28.1 — Einheitliche Schnellwahl und Home-Symbole

- Home-Such- und Barcode-Symbole mittig ausrichten, dauerhaft dunkelgrün mit weißen Piktogrammen darstellen.
- Home und Getränke verwenden dasselbe Vierer-Raster mit randlosen quadratischen Bildkacheln.
- Getränke-Link „Schnellwahl anpassen“ und Überschrift an Home angleichen; Einrichtungshinweis nur bei leerer Schnellwahl zeigen.

## 1.28.0 — Gemeinsame Suche und Home-Verknüpfungen

- BLS, Open Food Facts, eigene Zutaten sowie Lebensmittel- und Getränkerezepte in einer Suchliste mit farbigen Quellen und Favoritensternen.
- Auswahl pro Suchbegriff und Sprache lernen, einschließlich eigener Daten und OFF-Produkte; bisherige BLS-Präferenzen erhalten.
- Lokale Treffer sofort, externe Produkte nach Schreibpause; lokale Suche bleibt bei OFF-Ausfall nutzbar.
- Home: kleine Barcode- und Suchsymbole oben rechts für Kamera beziehungsweise Mahlzeitensuche.

## 1.27.0 — Open Food Facts Produktsuche

- Produktnamen unter Mahlzeiten, Rezepten und Getränkerezepten in Open Food Facts suchen; Treffer mit Marke und Packungsgröße auswählen.
- Produkte über ihren Barcode mit der konsumierten Menge buchen und wie bisher nachbearbeiten.
- Verzögerte Suchabfrage, kurze Zwischenspeicherung und Anfragelimit; keine API-Schlüssel für Open Food Facts nötig.

## 1.26.1 — API-Schlüssel in Einstellungen

- Vorhandenen API-Schlüssel nach Anmeldung auf ausdrücklichen Klick anzeigen und für iPhone-Kurzbefehle kopieren.
- Ausblenden / Seitenwechsel / Abmelden leeren den Schlüssel; keine Browser-Speicherung und keine ungeschützte Ausgabe.

## 1.26.0 — Trinkdauer im BAC-Verlauf

- Optionalen Zeitpunkt des letzten Schlucks bei manuellen Getränken, Rezeptverzehr und in Eintragsdetails erfassen.
- Alkohol gleichmäßig über die Trinkdauer zuführen; analytische Absorption / Elimination mit überlappenden Getränken und Mitternachtswechsel.
- Trinkdauer bei Kopien und rückwirkenden Rezeptkorrekturen erhalten; Einträge ohne Endzeit behalten die bisherige Berechnung.

## 1.25.0 — Getränke und rückwirkende Rezeptkorrekturen

- Alkoholseite in Getränke umbenennen: Schnellwahl, Getränkerezepte mit Zutaten / Gesamtvolumen / finalem ABV, danach manuelle Eingabe und BAC.
- Bestehende Rezepte zwischen Lebensmittel- und Getränkerezepten verschieben, ohne IDs, Zutaten oder Schnellwahl-Verknüpfungen zu ändern.
- Definitionen nur für künftige Einträge speichern oder nach Bestätigung bereits gebuchte Portionen neu berechnen; Mengen und Zeiten bleiben erhalten.
- Vorherige Eintragsstände archivieren und Health-Exportänderungen anzeigen; Apple Health wird nicht automatisch korrigiert.

## 1.24.0 — Nährwertetiketten lokal scannen

- Unter Eigene Zutaten ein Etikett fotografieren und erkannte Nährwerte pro 100 g vor dem Speichern prüfen.
- Tesseract mit Deutsch / Englisch im Docker-Image, ohne KI-API oder Gebühren.
- Erkannter Text bleibt in den Notizen, unklare Angaben werden nicht als Null übernommen; Salz wird in Natrium umgerechnet.

## 1.23.0 — Statistik für alle Nährstoffe

- Alle unterstützten Nährstoffe im Statistikdiagramm, in Summen / Durchschnitten und der Tageswerttabelle auswählbar.
- Vorhandene Tagesziele als beschriftete Linie mit passender Diagrammskala anzeigen.
- Kompatible Masseinheiten umrechnen, unbekannte / ungeprüfte Werte weiterhin kennzeichnen.

## 1.22.1 — Rezeptzutaten bearbeiten

- Zutatenzeilen im Rezept anklickbar machen: gespeicherte Lebensmittel, Mengen und Zeitpunkte direkt in der Eingabemaske bearbeiten.
- Neuberechnung für das Rezept; bereits gebuchte Rezeptportionen behalten ihren gespeicherten Stand.

## 1.22.0 — Rezepte duplizieren

- Ausgewähltes Rezept einschließlich Zutaten, Mengen, Notizen, Gesamtgewicht und zusätzlichem Wasser / Koffein / Alkohol als unabhängige Kopie anlegen.
- Gespeicherte Nährwerte und offene Zutaten erhalten; Kopie direkt zum Umbenennen und Bearbeiten öffnen.
- Doppelfreie Wiederholung bei Übertragungsfehlern; keine Buchung ins Tagebuch.

## 1.21.0 — Einträge kopieren

- Tagebucheinträge auf der Detailseite auf einen anderen Tag oder Zeitpunkt kopieren.
- Mengen und gespeicherte Nährwerte einschließlich Rezeptständen erhalten; Health-Status für die Kopie neu beginnen.
- Kopierherkunft, eigene Originaldateien und doppelfreie Wiederholung bei Übertragungsfehlern.

## 1.20.0 — FDDB-Linkimport

- Deutsche FDDB-Lebensmittelseiten unter Eigene Zutaten importieren, prüfen und speichern; keine API oder Anmeldung erforderlich.
- Veröffentlichte Werte pro 100 g, Einheiten und Quellenangaben übernehmen; Wasser-Prozent in g umrechnen, fehlende Angaben unbekannt lassen.
- FDDB-Kohlenhydrate unverändert übernehmen; die USDA-Ballaststoffkorrektur bleibt auf FoodData beschränkt.

## 1.19.0 — ChatGPT-Nährwerte importieren

- Optionale Nährwerte pro 100 g / 100 ml direkt übernehmen, in der Vorschau korrigieren oder durch Datenbankwerte ersetzen.
- Schätzungen kennzeichnen, Originaldaten erhalten und fehlende Mengen ohne neue Lebensmittelsuche ergänzen.
- DE/EN-Vorlage mit HealthKit-Feldern, europäischen Kohlenhydraten und klaren Einheiten.

## 1.18.1 — Nährwertanzeige

- Angezeigte Zahlen mit maximal zwei Nachkommastellen, Mikrogramm als µg. Berechnung und gespeicherte Werte behalten ihre Genauigkeit.
- Wasser in Lebensmitteln ohne separat gezähltes Trinkwasser; Rezeptzutaten und Beitragslisten werden dabei berücksichtigt.

## 1.18.0 — JSON-Import für externe Foto-/Texterkennung

- Kopierbare ChatGPT-Vorlage, JSON-Dateiupload und Einfügen von Text auf Mahlzeiten- und Rezeptseiten, ohne KI-Anbindung oder API-Gebühren.
- Standardformat friss-meal-v1 für Lebensmittel, Mengen und Hinweise; Vorschau mit BLS- / eigenen Zutaten-Treffern und Korrekturmöglichkeit.
- Gemeinsame, atomare Buchung, unveränderte Originaleingabe, doppelfreie Wiederholung mit derselben Import-ID. Unbekannte Mengen / Lebensmittel bleiben zur Nachbearbeitung erhalten.
- Import-Herkunft und Hinweise in den Eintragsdetails; Anleitung und Beispieldatei beigefügt.

## 1.17.0 — Beiträge zu Tageswerten öffnen

- Mengen auf Home und in den Zielkarten öffnen eine Liste der zugehörigen Tagebucheinträge mit Uhrzeit, verzehrter Menge und individuellem Nährwertbeitrag.
- Unterstützt Standard- und Mikronährstoffe, Koffein, Alkoholmenge und getrunkenes Wasser; Rezeptverzehr wird einmal als gebuchte Portion gezählt.
- Nullwerte und unbekannte Angaben separat aufklappbar; Links öffnen die jeweilige Detailseite. Gleiche Berechnung und Null-Einstellung wie die Tagesgesamtwerte.

## 1.16.1 — Nullannahmen auch für Spuren und Nachweisgrenzen

- Die aktivierte Null-Einstellung erfasst nun auch TR, <LOD, <LOQ und kombinierte Angaben wie „<LOD or <LOQ“.
- Summen und Rezeptanteile behalten bekannte Nährwerte; für die ersetzten Angaben entfallen „unvollständig“ und die Grenzmarker.
- Ausschalten stellt die Originalangaben wieder her. Numerische Werte mit ungeprüften Einheiten werden weiterhin nicht verändert.

## 1.16.0 — Option für fehlende Nährwerte

- Neue, standardmäßig ausgeschaltete Einstellung: fehlende Nährwerte bei der Auswertung als 0 annehmen.
- Einheitliche Anwendung auf bestehende / neue Einträge, Tageswerte, Rezepte, Statistik und zukünftige Health-Exporte; bekannte Rezeptanteile bleiben erhalten.
- Reversibel ohne Überschreiben von Rohdaten und gebuchten Snapshots. Fehlende Mengen, Lebensmittelzuordnungen, Spuren und ungeprüfte Einheiten bleiben sichtbar.
- Exportbatches und reservierte Einzelwerte bleiben eingefroren; Einstellung und Nullannahmen werden nachvollziehbar gekennzeichnet.

## 1.15.1 — Amerikanische Kohlenhydrate ohne Ballaststoffe

- FoodData-Import zieht bekannte Ballaststoffe von USDA-Gesamtkohlenhydraten ab. Zimt: 80,59 − 53,1 = 27,49 g pro 100 g.
- Ballaststoffe und Quellenergie bleiben unverändert; Originalwerte und Umrechnung werden gespeichert.
- Fehlende oder widersprüchliche Ballaststoffangaben ergeben keinen geratenen Kohlenhydratwert. Bestehende Zutaten lassen sich erneut importieren; gebuchte Snapshots bleiben unverändert.

## 1.15.0 — FoodData-Importer für eigene Zutaten

- Import per FoodData Explorer-Link: Nährwerte pro 100 g automatisch in die manuelle Eingabemaske übernehmen, vor dem Speichern prüfen und bearbeiten.
- Explizite Einheitenumrechnung, bekannte Nullwerte erhalten, fehlende / nicht unterstützte Werte nicht schätzen; Varianten nicht addieren.
- Quelle, Zeitpunkt und veröffentlichte Rohwerte dauerhaft in der Zutat und gebuchten Snapshots erhalten.
- Lebensmittelwasser als g unterstützen; USDA-Kohlenhydratdefinition kennzeichnen.
- API- und UI-Tests für den verlinkten Zimt-Datensatz, Speicherung, Umrechnung, Abruffehler und verspätete Antworten.

## 1.14.0 — Alkohol direkt ins Tagebuch

- Separate Simulation ersetzt durch Getränkeerfassung: reiner Alkohol in g oder ml und Volumenprozent, Name und bearbeitbare Uhrzeit.
- Alkohol-Schnellwahl nutzt bestehende Kacheln / alkoholhaltige Rezepte und die gewählte Eintragungszeit. Gramm-Eingaben auch in Schnellwahl, Favoriten und Nachbearbeitung.
- Tageskurve aus gespeicherten Einträgen und Körperprofil; Restalkohol vor Tagesbeginn, minütliche Punkte, Prognose gestrichelt. Home nutzt dieselbe Berechnung.
- Abbau endet bei null; spätere Getränke nach Nüchternphasen werden nicht mehr durch fortgesetzten Abzug unterschätzt.
- API- und UI-Tests für Speicherung, Zeitpunktänderungen, Löschen, Mengenformate, Tagesgrenzen und identische Wiederholung unklarer Übertragungen.

## 1.13.2 — Tagesziele auf Home

- Ein verspäteter Home-Abruf kann frisch gespeicherte Kalorien- und Makroziele nicht mehr durch alte Einstellungen ersetzen.
- Veraltete Abrufe nach Abmeldung werden verworfen.
- Regressionstest für Ziel speichern → verspäteter Abruf → Fortschrittsanzeige und API-Prüfung der Speicherung über Neustarts.

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

