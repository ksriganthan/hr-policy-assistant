# hr-policy-assistant

A retrieval system over public Swiss collective labour agreements that answers
questions with citations down to section number and page. The corpus is German,
so the rest of this README is German as well.

RAG-System über öffentliche Schweizer HR-Dokumente wie GAV und
Personalreglemente, das Fragen mit nachprüfbaren Quellenzitaten beantwortet.

> **In Arbeit** – AI-Engineering-Sprint 24.08.–04.10.2026. Was heute läuft und
> was fehlt, steht unter «Stand».

## Warum dieses Projekt

Wer wissen will, wie lang seine Kündigungsfrist in der Probezeit ist, sucht die
Antwort in einem PDF, das kaum jemand liest. Ein Sprachmodell allein beantwortet
solche Fragen flüssig und manchmal falsch, weil es plausibel klingende
Regelungen erfindet. Eine reine Ähnlichkeitssuche findet Stellen, die dem
Wortlaut der Frage ähneln, aber nicht zwingend die, die auf den Fall anwendbar
sind. Deshalb Retrieval mit Quellenangabe und Metadaten, damit jede Aussage auf
Ziffer, Seite und Dokument zurückführbar bleibt und eine veraltete Fassung als
solche erkennbar ist.

## Stand

**Läuft heute**

- Ingestion beider GAV vom PDF bis in den Vektorstore
- Textbereinigung, Schnitt an Gliederungsziffern, Hierarchiepfad pro Abschnitt
- Einbettung lokal über Ollama mit `bge-m3`
- Chroma-Sammlung `hr_policy` mit Kosinus-Abstand, laut Gegenprobe im Code 211 Chunks
- Metadaten an jedem Chunk, darunter Dokument, Ziffer, Seite, Titel, Pfad, Stand und Aktualitätsstatus
- Tests für Loader und Textbereinigung, Linting mit ruff

**Fehlt noch**

- Antwortgenerierung. Wer eine Frage stellt, bekommt Chunks zurück, keinen Text.
- API, Workflow und LLM-Gateway. Die Pakete `api/`, `workflow/`, `evals/` und `gateway/` enthalten nur ihren Docstring.
- Eval-Set und Metriken. Unter `evals/` steht bisher nur, was gemessen werden soll.
- Aktualitätsprüfung. Beide Fassungen sind von 2015 und 2016, das Feld `status` steht auf `unbekannt`.

**Arbeitsskripte im Wurzelverzeichnis**

Drei Skripte, die nicht Teil des Pakets sind, sondern zum Prüfen von Hand dienen.

- `frage.py` stellt fünf feste Testfragen an den Index und zeigt zu jedem Treffer Abstand, Dokument, Seite, Ziffer und Titel
- `messung.py` misst pro Dokument die Anzahl Abschnitte und die Längenverteilung, also Minimum, Median und Maximum
- `test_embed.py` prüft die Ollama-Verbindung und gibt Anzahl und Dimension der Vektoren aus

## Architektur

1. `lade_pdf` in `ingestion/loader.py` liest den Text je Seite und überspringt die im Korpus vermerkten Verzeichnisseiten
2. `bereinige_seiten` normalisiert die Zeichen und entfernt Symbolzeichen
3. `finde_wiederholte_zeilen` und `entferne_wiederholte_zeilen` werfen Kopf- und Fusszeilen weg
4. `schneide_in_abschnitte` schneidet an nummerierten Überschriften, `setze_pfade` trägt den Pfad der übergeordneten Titel ein
5. `lese_abschnitte` in `ingestion/index.py` führt das pro Korpusdokument zusammen
6. `einbetten` schickt die Texte in Stapeln von 32 an Ollama
7. `baue_index` legt die Chroma-Sammlung neu an und schreibt Vektoren, Zitattext und Metadaten

Ein Diagramm kommt später.

## Ingestion

Beide PDF sind für Menschen gesetzt und nicht für Maschinen, und jedes bricht
auf eigene Art.

**Zeichen normalisieren.** Im USB-PDF stehen die Umlaute zerlegt, also als
Grundbuchstabe plus kombinierendes Trema. Eine Suche nach «Kündigungsfrist»
findet im Rohtext null Treffer, obwohl das Wort achtmal im Dokument steht. Nach
der Normalisierung nach NFC sind es acht. Der Fehler ist unsichtbar, weil der
Text auf dem Bildschirm richtig aussieht.

**Symbolzeichen entfernen.** Dasselbe PDF enthält 43 Zeichen aus dem
Private-Use-Bereich, alle U+F0B7, ein Aufzählungspunkt aus Wingdings. Der Loader
verwirft alles der Unicode-Kategorie Co. Das KSBL-PDF hat beide Probleme nicht,
an einem einzelnen Dokument wären sie also gar nicht aufgefallen.

**Kopf- und Fusszeilen entfernen.** Statt fester Muster zählt der Loader, auf
wie vielen Seiten eine Zeile vorkommt, und ersetzt dafür jede Ziffernfolge durch
ein Rautezeichen. Damit gelten «GAV 1 / 26» und «GAV 2 / 26» als dieselbe Zeile.
Was auf mindestens 80 Prozent der Seiten steht, fliegt raus. Gemessen liegen
Kopf- und Fusszeilen bei 95 bis 100 Prozent, die nächsthäufige Zeile bei 10.

**Inhaltsverzeichnis.** Die Verzeichnisseiten werden nicht erkannt, sondern im
Korpuseintrag deklariert. Ein früherer Filter versuchte, sie an ihrer Form zu
erkennen, und warf dabei Tabellenzeilen wie «20 ½ 10» und Fussnoten aus dem
Regelungstext weg. Zwei Regressionstests halten diesen Fall fest. Welche Seiten
Verzeichnis sind, ist eine Eigenschaft des Dokuments und steht deshalb im
Korpus, nicht im Loader.

**Überschriften erkennen.** Ein Chunk ist keine feste Zeichenlänge, sondern ein
Abschnitt des Vertrags. Die Nummer am Zeilenanfang genügt zur Erkennung nicht.
«13. Monatslohn.» ist ein Begriff, «8.4 beziehungsweise 9.2 Stunden berechnet.
Für Teilzeit» ist ein Satz. `ist_ueberschrift` prüft deshalb zwei Signale
zugleich, das Nummernmuster und die Abwesenheit von Satzmerkmalen im Titel. So
findet der Loader beim KSBL 123 von 123 Verzeichnisnummern und beim USB alle 97
plus die tieferen Ebenen, die das Verzeichnis nicht auflistet.

Eingebettet wird Pfad plus Abschnittstext, zitiert wird nur der Abschnittstext.
Der Pfad muss in die Einbettung, weil das Thema oft nur in der Überschrift
steht. Ziffer 2.3.3 des USB enthält das Wort «Kündigungsfrist» im Absatztext
nicht.

## Technische Entscheide

| Entscheid | Gewählt | Alternativen | Begründung |
|---|---|---|---|
| Vektor-DB | Chroma | pgvector, Qdrant | lokal, kein Betriebsaufwand, Repository-Interface hält pgvector austauschbar |
| Paketmanager | uv | poetry, pip-tools | schnelle Auflösung und ein Lockfile, das den Neuaufbau reproduzierbar macht |
| Chunking | Schnitt an Gliederungsziffern | feste Fenster mit Überlappung | der Abschnitt ist die Einheit, die zitiert wird, und der Vertrag ist bereits so gegliedert |
| Embedding-Modell | `bge-m3` über Ollama | multilingual-e5, jina-embeddings-v3 | läuft lokal, muss bei Indexbau und Abfrage identisch sein, ein Wechsel erzwingt den Neuaufbau |
| Workflow vs. Agent |  |  |  |

## Resultate

Die Zahlen kommen ab Woche 3. Bis dahin bleibt die Tabelle leer. Die Einbettung
läuft bereits lokal über Ollama, offen ist die Generierung. Die letzte Zeile
vergleicht also nur, was ein On-Premise-Modell beim Antworten kostet.

| Setup | Retrieval-Precision | Groundedness | Halluzinationsrate | CHF/Anfrage | p95-Latenz |
|---|---|---|---|---|---|
| Baseline (naives RAG) |  |  |  |  |  |
| LangGraph + Kritik-Rolle |  |  |  |  |  |
| Agent-Loop |  |  |  |  |  |
| On-Premise (Ollama) |  |  |  |  |  |

## Setup

Vorausgesetzt sind Python 3.12 oder neuer, uv und ein laufendes Ollama.

```bash
uv sync
cp .env.example .env
ollama pull bge-m3
```

Der Korpus liegt nicht im Repository, weil ein GAV ein privatrechtlicher Vertrag
der Sozialpartner ist und kein amtliches Werk. Beide PDF müssen von Hand nach
`data/raw/` gelegt werden, unter genau diesen Dateinamen.

| Datei | Dokument |
|---|---|
| `gav_universitaetsspital_basel.pdf` | GAV Universitätsspital Basel, UPK und Felix Platter-Spital, gültig ab 01.01.2016, 24 Seiten |
| `spitalbl_gav.pdf` | GAV Kantonsspital Baselland und Psychiatrie Baselland, gültig ab 01.07.2015, 26 Seiten |

Herausgeber und Geltungsbereich stehen in `docs/korpus.md`. Danach folgt der
Indexbau.

```bash
uv run python -m hr_policy_assistant.ingestion.index
uv run pytest
uv run ruff check .
```

Der Indexbau schreibt nach `chroma/` und meldet am Ende die Anzahl Chunks. Die
Tests, die das PDF brauchen, überspringen sich selbst, wenn der Korpus fehlt.
