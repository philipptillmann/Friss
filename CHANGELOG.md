# Changelog

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
