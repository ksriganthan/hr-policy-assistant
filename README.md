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

- ETL-Strecke beider GAV vom PDF bis in den Vektorstore
- Textbereinigung, Schnitt an Gliederungsziffern, Hierarchiepfad und Seitenzahl pro Abschnitt
- Einbettung lokal über Ollama mit `bge-m3`
- Chroma-Sammlung `hr_policy` mit Kosinus-Abstand, 211 Chunks. Das Embedding-Modell steht in
  den Metadaten der Sammlung, die Abfrage prüft es beim Start
- Metadaten an jedem Chunk, darunter Dokument, Ziffer, Seite, Titel, Pfad, Stand und Aktualitätsstatus
- LLM-Gateway für alle Ollama-Aufrufe, Chat und Embedding. Jeder Aufruf wird als JSON-Zeile
  protokolliert, bei Verbindungsfehlern bis zu dreimal mit wachsender Pause wiederholt und mit
  Tokenzahlen, Dauer und Kosten zurückgegeben
- End-to-End-Antwort mit Belegnummern über ein lokales Sprachmodell (`gemma3:12b`), in erster Fassung
- Tests für Loader und Textbereinigung, Linting mit ruff

**Fehlt noch**

- Strukturierte Ausgabe. Das Modell antwortet als Fliesstext, das Zitatformat wird erbeten statt erzwungen.
- API und Workflow. Die Pakete `api/`, `workflow/` und `evals/` enthalten nur ihren Docstring.
- Eval-Set und Metriken. Fünf Testfragen von Hand geprüft, kein automatisches Eval.
- Aktualitätsprüfung. Beide Fassungen sind von 2015 und 2016, das Feld `status` steht auf `unbekannt`.

**Arbeitsskripte im Wurzelverzeichnis**

Skripte, die nicht Teil des Pakets sind, sondern zum Prüfen von Hand dienen. Alle gitignored.

- `frage.py` stellt fünf feste Testfragen an den Index und zeigt zu jedem Treffer Abstand, Dokument, Seite, Ziffer, Titel und Textanfang
- `antworte.py` stellt dieselben fünf Fragen End-to-End, also mit Antwort des Sprachmodells und Belegliste
- `zeige_index.py` zeigt, was in der Chroma-Sammlung steht, inklusive Metadatenfilter
- `messung.py` misst pro Dokument die Anzahl Abschnitte und die Längenverteilung
- `test_embed.py` und `test_llm.py` prüfen die Ollama-Verbindung für Embedding und Sprachmodell
- `kosten.py` liest das Protokoll und zeigt pro Aufruf Tokens, Dauer und Kosten sowie die Summen

## Architektur

1. `lade_pdf` in `ingestion/loader.py` liest den Text je Seite mit Seitenzahl und überspringt die im Korpus vermerkten Verzeichnisseiten
2. `bereinige_seiten` normalisiert die Zeichen und entfernt Symbolzeichen
3. `finde_wiederholte_zeilen` und `entferne_wiederholte_zeilen` werfen Kopf- und Fusszeilen weg
4. `schneide_in_abschnitte` schneidet an nummerierten Überschriften und merkt sich die Startseite, `setze_pfade` trägt den Pfad der übergeordneten Titel ein
5. `lese_abschnitte` in `ingestion/index.py` führt das pro Korpusdokument zusammen
6. `einbetten` schickt die Texte in Stapeln von 32 an `embed` im Gateway
7. `baue_index` legt die Chroma-Sammlung neu an und schreibt Vektoren, Zitattext und Metadaten
8. `embed` in `gateway/llm.py` bettet die Frage ein, `frage_modell` ruft das Sprachmodell. Beide laufen durch
   `_mit_wiederholung`, das bei Verbindungsfehlern bis zu dreimal mit Pausen von 1, 2 und 4 Sekunden nachfasst
9. Die Antwort entsteht aus Frage, den vier nächsten Chunks als nummerierte Belegstellen und einer Systemnachricht mit Regeln
10. `protokolliere` schreibt Zeit, Modell, Tokens, Dauer, Versuchsnummer, Kosten und Frage als eine Zeile nach `logs/llm.jsonl`

Ein Diagramm kommt später.

## Ingestion

Die Ingestion ist eine ETL-Strecke. **Extract** liest den Text je Seite aus dem PDF.
**Transform** normalisiert die Zeichen, entfernt Symbolzeichen sowie Kopf- und Fusszeilen,
schneidet an Gliederungsziffern und trägt Pfad und Seitenzahl ein. **Load** schreibt Vektoren,
Zitattext und Metadaten in die Chroma-Sammlung. Transformiert wird vor dem Laden und nicht danach,
weil der Vektorstore keine Transformationssprache hat und der Chunk beim Schreiben bereits die
Einheit sein muss, die später zitiert wird. Der grösste Teil der Arbeit steckt im Transform-Schritt,
und zwar nicht im Umformen, sondern im Finden der Fälle, die still danebengehen.

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

## Antwortgenerierung

Das Modell bekommt zwei Texte. Eine Systemnachricht mit Regeln, die aus den
Befunden der ersten Woche abgeleitet sind, etwa dass bei zwei zutreffenden
Dokumenten beide Regelungen mit Geltungsbereich zu nennen sind und dass eine
fehlende Regelung als solche zu benennen ist. Und eine Nutzernachricht mit den
vier nächsten Chunks als nummerierte Belegstellen, jede mit Dokument, Ziffer,
Titel, Seite und Stand in der Kopfzeile, gefolgt von der Frage.

Die Temperatur steht auf 0, damit dieselbe Frage dieselbe Antwort liefert und
sich Änderungen am Code von Zufall unterscheiden lassen.

**Erste Messung an den fünf Testfragen.** Vier von fünf inhaltlich richtig,
alle fünf mit Belegnummern, rund 1000 Prompt-Tokens und 14 bis 16 Sekunden pro
Antwort auf einer RTX 5070 Ti. Zwei Befunde daraus.

Bei der Frage nach 20 Dienstjahren lag der richtige Chunk auf Platz 2, und die
Antwort war trotzdem falsch. Aus «10 Tage» wurde «CHF 10», weil die Tabelle im
Chunk als `20 ½ 10` ohne Spaltenzuordnung steht. Das Retrieval hat funktioniert,
die Generierung nicht. Belegt ist nicht richtig.

Bei der Frage nach dem Vaterschaftsurlaub hat das Modell den Elternurlaub des
anderen Dokuments so dargestellt, als beantworte er die Frage. Die Regel im
Prompt hat das nicht verhindert.

Ein Versuch mit drei zusätzlichen Prompt-Regeln hat die Einheit bei der
Tabellenfrage gerettet, das Zitatformat aber verschlechtert. Prompt-Regeln sind
billig und unzuverlässig. Die Tabelle wird deshalb in der Ingestion repariert,
das Zitatformat über eine strukturierte Ausgabe erzwungen.

## Gateway

Alle Aufrufe an Ollama gehen durch `gateway/llm.py`, beim Indexbau wie bei der
Abfrage. Das Embedding-Modell ist dort als einzige Konstante definiert, `index.py`
importiert sie. Drei Dinge passieren im Gateway für jeden Aufruf, ohne dass die
aufrufenden Module davon wissen.

**Protokoll.** Eine JSON-Zeile pro Modellaufruf in `logs/llm.jsonl`, angehängt, nie
überschrieben. Zeit, Modell, Tokens ein und aus, Dauer, Versuchsnummer, Kosten und die
Frage. Der Antworttext bleibt draussen, das Protokoll soll messen, nicht speichern.
`kosten.py` wertet es aus. Das ist die Datenbasis für die Eval-Tabelle.

**Wiederholung.** Bei Verbindungsfehlern bis zu drei Versuche mit Pausen von 1, 2 und
4 Sekunden. Gefangen werden nur Fehler, die von selbst wieder verschwinden können,
Ollama nicht erreichbar, Zeitüberschreitung, abgebrochene Verbindung. Ein falscher
Modellname wird nicht wiederholt, der geht beim dritten Mal genauso schief.

**Kosten.** Aus Tokenzahlen und einer Preistabelle je Modell, Eingabe und Ausgabe
getrennt, in CHF pro Million Tokens. Lokale Modelle stehen mit null drin. Beim
Cloud-Vergleich in Woche 5 wächst nur die Tabelle, der Code bleibt gleich.

**Ein Befund aus dem Test.** Ollama beendet, Skript gestartet, Ollama neu gestartet. Der
erste Lauf scheiterte, bevor die Wiederholung greifen konnte, weil das Embedding der
Frage noch direkt an Ollama ging und nicht durch das Gateway. Ein Tor nützt nur, wenn
niemand daran vorbeigeht. Seither laufen Abfrage und Indexbau durch dieselbe Schleife. Ausserdem
wirft die Ollama-Bibliothek bei fehlender Verbindung Pythons eingebauten
`ConnectionError`, nicht den `httpx.ConnectError`, den sie intern fängt. Ohne den Test
wäre beides erst im Betrieb aufgefallen.

## Technische Entscheide

| Entscheid | Gewählt | Alternativen | Begründung |
|---|---|---|---|
| Vektor-DB | Chroma | pgvector, Qdrant | lokal, kein Betriebsaufwand. Der Zugriff ist heute direkt, ein Repository-Interface für einen späteren Wechsel ist Absicht, nicht Stand |
| Paketmanager | uv | poetry, pip-tools | schnelle Auflösung und ein Lockfile, das den Neuaufbau reproduzierbar macht |
| Chunking | Schnitt an Gliederungsziffern | feste Fenster mit Überlappung | der Abschnitt ist die Einheit, die zitiert wird, und der Vertrag ist bereits so gegliedert |
| Chunk-Splitter | keiner | Obergrenze mit Nachteilung | gemessen liegt je ein Abschnitt pro Dokument über 2000 Zeichen, der Median bei 388 und 434 |
| Embedding-Modell | `bge-m3` über Ollama | multilingual-e5, jina-embeddings-v3 | läuft lokal, muss bei Indexbau und Abfrage identisch sein, ein Wechsel erzwingt den Neuaufbau |
| Sprachmodell | `gemma3:12b` über Ollama | qwen3:14b, Cloud-API | passt in 12 GB Grafikspeicher, Deutsch, kein Denkmodus. Vergleich mit Cloud folgt |
| Temperatur | 0 | Standard | reproduzierbare Antworten sind Voraussetzung für Evals |
| Gateway | eine Datei für Chat und Embedding, ein Rückgabeobjekt | direkter Aufruf an jeder Stelle | Protokoll, Wiederholungen und Kosten stehen an einer Stelle. Der Retry-Test hat gezeigt, dass ein Aufruf am Gateway vorbei alles davon verliert |
| Protokollformat | JSON Lines, eine Zeile pro Aufruf | eine JSON-Datei, SQLite | anhängen ohne Lesen, Zeile für Zeile auswertbar, im Editor lesbar |
| Wiederholung | 3 Versuche, Pausen 1, 2, 4 s, nur Verbindungsfehler | alles wiederholen, nie wiederholen | vorübergehende Fehler überbrücken, dauerhafte sofort sichtbar machen |
| Workflow vs. Agent |  |  |  |

## Resultate

Belastbar ist bisher nur das Retrieval, die Generierung ist von Hand an fünf
Fragen geprüft. Die vollständigen Zahlen kommen ab Woche 3 mit dem Eval-Set.

| Setup | Retrieval-Precision | Groundedness | Halluzinationsrate | CHF/Anfrage | p95-Latenz |
|---|---|---|---|---|---|
| Baseline (naives RAG) | k=2 → 1.0 · k=4 → 0.6–0.7 | offen | 1 von 5 von Hand | 0.00 (lokal) | ~16 s |
| LangGraph + Kritik-Rolle |  |  |  |  |  |
| Agent-Loop |  |  |  |  |  |
| On-Premise (Ollama) |  |  |  |  |  |

Die Retrieval-Precision wurde an fünf Testfragen von Hand beurteilt. Bei allen
fünf sind die ersten zwei Treffer relevant, ab Platz drei steht Rauschen. Fünf
Fragen sind eine kleine Stichprobe, die Zahl ist ein Ausgangspunkt und kein
Beleg.

## Setup

Vorausgesetzt sind Python 3.12 oder neuer, uv und ein laufendes Ollama.

```bash
uv sync
cp .env.example .env
ollama pull bge-m3
ollama pull gemma3:12b
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
