# JSON aus ChatGPT importieren

Friss kann Ergebnisse aus der ChatGPT-App oder einem anderen Programm einlesen. Es gibt keine KI-Verbindung von Friss und keinen API-Schlüssel für diesen Import. Lebensmittel, Mengen und optional Nährwerte stammen aus deinem JSON. In der Vorschau kannst du die ChatGPT-Nährwerte übernehmen oder stattdessen einen Datenbanktreffer wählen.

Für den direkten iPhone-Kurzbefehl gibt es ab v1.30.0 außerdem den [Ein-Schritt-Import mit Portionssummen](AI_SHORTCUT.md). Dieser verwendet ein eigenes, kleineres Format; die folgenden Angaben beschreiben weiterhin den Browser-Import.

## So funktioniert es

1. Unter **Mahlzeiten → Eintrag hinzufügen → JSON aus ChatGPT importieren** die **ChatGPT-Vorlage kopieren**. Auf der Rezeptseite ist derselbe Import für Zutaten verfügbar.
2. Die Vorlage zusammen mit deinem Foto oder deiner Beschreibung in die ChatGPT-App einfügen.
3. Das JSON-Ergebnis kopieren und in Friss einfügen, oder als `.json`-Datei hochladen.
4. **Import prüfen** wählen. Es wurde noch nichts gebucht. Pro Lebensmittel importierte Nährwerte, einen BLS-Treffer oder eine eigene Zutat auswählen; Suchbegriff und Mengen bei Bedarf ändern.
5. Zeitpunkt und Ziel prüfen, dann **Alle Einträge speichern**. Auf der Rezeptseite ist das aktuell ausgewählte Rezept das Ziel.

Fotos erlauben häufig keine sichere Gewichtsbestimmung. Prüfe geschätzte Mengen und Hinweise. Nicht zugeordnete Lebensmittel oder unbekannte Mengen lassen sich trotzdem speichern; sie bleiben zur Nachbearbeitung erhalten. Friss wählt für nicht zugeordnete Importpositionen nicht eigenständig einen Datenbanktreffer.

Wenn die Übertragung unklar war, erneut auf **Alle Einträge speichern** drücken: Friss sendet dieselbe Import-ID, ohne doppelte Einträge zu erzeugen. Währenddessen bleiben die Eingaben gesperrt. Bei einer ausdrücklich abgelehnten Eingabe lassen sich die Daten korrigieren. Bei Abbruch einer unklaren Übertragung oder einem Neuladen der Seite zunächst im Tagebuch prüfen, ob der Import bereits gespeichert wurde.

## Standardformat `friss-meal-v1`

```json
{
  "schema": "friss-meal-v1",
  "title": "Cappuccino",
  "items": [
    {
      "name": "Espresso",
      "quantity": { "value": 45, "unit": "g" },
      "notes": "Menge angegeben"
    },
    {
      "name": "Vollmilch 3,5 % Fett",
      "quantity": { "value": 90, "unit": "g" },
      "notes": "Menge angegeben"
    }
  ]
}
```

| Feld | Bedeutung |
| --- | --- |
| `schema` | Muss genau `friss-meal-v1` sein. |
| `title` | Optionaler Name der Mahlzeit; maximal 300 Zeichen. |
| `timestamp` | Optionaler Zeitpunkt mit Zeitzone, z.B. `2026-10-12T08:30:00+02:00`. Ohne Angabe zeigt die Vorschau jetzt an. Vor dem Speichern bearbeitbar. Gilt für alle Positionen. |
| `items` | 1–100 einzelne Lebensmittel oder Zutaten. Ein ganzes Gericht **oder** seine Zutaten aufführen, nicht beides doppelt. |
| `name` | Lebensmittelname für die Suche; maximal 200 Zeichen. |
| `quantity` | Positive Zahl als `value`, Einheit `g` oder `ml`. Bei unbekannter Menge `null` oder weglassen. |
| `notes` | Optionaler Hinweis zu Schätzung, Zubereitung oder Unsicherheit; maximal 2.000 Zeichen. |
| `bls_code` / `manual_id` / `barcode` | Optionale bekannte Referenz; höchstens eine pro Position. Diese Werte nicht von der KI erfinden lassen. Normalerweise in der Friss-Vorschau auswählen. |

Für BLS und eigene Zutaten werden Gramm benötigt. ml werden ohne bekannte Dichte nicht stillschweigend als g interpretiert: solche Positionen bleiben gegebenenfalls zur Nachbearbeitung offen. Barcodes verwenden den vorhandenen Open-Food-Facts-Abruf und dürfen 8–14 Ziffern enthalten. Gewählte Datenbanktreffer liefern ihre tatsächlichen Nährwerte, nicht die Schätzung des Sprachmodells.

Die maximale Eingabegröße beträgt **256 KiB**. JSON-Zahlen verwenden einen Punkt als Dezimaltrennzeichen. Markdown-Codeblöcke wie ` ```json … ``` ` werden ebenfalls akzeptiert, aber zusätzlicher Erklärungstext und zusätzliche Felder nicht. Die kopierbare Vorlage enthält diese Vorgaben auf Deutsch beziehungsweise Englisch.

## Speicherung

Der gesamte Import wird gemeinsam in einer Datenbanktransaktion gespeichert. Eine unterbrochene Verarbeitung bucht nicht nur die ersten Positionen. Wiederholungen eines bereits abgeschlossenen Imports erzeugen keine neuen Einträge, auch wenn du ursprüngliche Einträge später gelöscht hast.

Die Originaleingabe bleibt unverändert als `originals/import-<Import-ID>.txt` erhalten; daneben liegt eine normalisierte JSON-Datei. Jeder Tagebucheintrag behält seine eigene Originaldatei und die Import-ID. Die Detailseite zeigt **JSON-Import**, den Mahlzeitentitel und Erkennungshinweise. Rezeptzutaten werden erst durch gebuchten Rezeptverzehr zum Tagesverlauf gezählt. Die bisherigen Health-Export- und Nullwert-Einstellungen gelten weiterhin.

## API

- Authentifiziertes `POST /json-import/preview` mit `{ "raw": "JSON als Text", "lang": "de" }` liefert geprüfte Positionen und Datenbankvorschläge, ohne Buchung.
- Authentifiziertes `POST /json-import/commit` mit neuer UUID als `id`, derselben `raw`-Eingabe, `timestamp`, optional `recipe_id` und der geprüften `items`-Liste speichert die Positionen gemeinsam. Bei Wiederholung dieselbe UUID und dieselben Daten verwenden.

Der normale iPhone-Test erfolgt nach `./update.sh`. Friss analysiert selbst keine Fotos: Das Foto wird in deiner gewählten ChatGPT-App verarbeitet, und nur deren JSON-Ergebnis wird nach Friss übernommen.

## Nährwerte direkt übernehmen

Jede Position kann optional `nutrition` enthalten. In der Vorschau werden Basis, Schätzungskennzeichnung und Nährwerte als bearbeitbares JSON angezeigt. Die Auswahl **ChatGPT-Nährwerte übernehmen** verwendet diese Werte; die Auswahl eines Datenbanktreffers verwendet ausschließlich dessen Werte. Beides wird niemals addiert. Ein JSON-Datensatz darf deshalb nicht gleichzeitig `nutrition` und eine Datenbankreferenz enthalten.

```json
{
  "schema": "friss-meal-v1",
  "items": [{
    "name": "Milch",
    "quantity": {"value": 150, "unit": "ml"},
    "notes": "Nährwerte von der Verpackung übernommen",
    "nutrition": {
      "basis": "100ml",
      "estimated": false,
      "nutrients": {
        "dietaryEnergyConsumed": {"value": 64, "unit": "kcal"},
        "dietaryProtein": {"value": 3.3, "unit": "g"},
        "dietaryCarbohydrates": {"value": 4.8, "unit": "g"},
        "dietaryFatTotal": {"value": 3.5, "unit": "g"}
      }
    }
  }]
}
```

`basis` muss `100g` oder `100ml` sein. Die konsumierte Menge braucht dieselbe Einheit: im Beispiel ergeben sich 96 kcal. Bei fehlender Menge bleibt der Eintrag zur Nachbearbeitung erhalten, ohne erneute Lebensmittelsuche. Es findet keine automatische Umrechnung zwischen Gramm und Millilitern statt.

`nutrients` verwendet die HealthKit-Bezeichner aus der kopierbaren Vorlage. Energie in `kcal`, Wasser in `g` oder `ml`, andere Nährstoffe in `g`, `mg` oder `mcg`. `ug`, `µg` und `μg` werden beim Import ebenfalls als Mikrogramm akzeptiert. Zahlen müssen endlich und nicht negativ sein. Unbekannte Werte weglassen oder `null` setzen; die Nullwert-Einstellung gilt wie bisher.

Kohlenhydrate müssen den europäischen verfügbaren Kohlenhydraten entsprechen, also ohne Ballaststoffe. Die Vorlage fordert das ausdrücklich an. Friss zieht von diesen importierten Werten nicht nochmals Ballaststoffe ab.

`estimated` ist standardmäßig `true`: die Detailseite kennzeichnet solche Werte als externe KI-Schätzung. `false` ist für abgelesene Angaben vorgesehen. Friss prüft Struktur und Einheiten, nicht die tatsächliche Zusammensetzung eines Fotos. Die gespeicherten Nährwerte behalten ihre Importquelle und werden bei Rezeptverzehr als Snapshot übernommen; der bestehende Health-Export kann sie übertragen.

