# hr-policy-assistant

A retrieval system over public Swiss collective labour agreements that answers
questions with citations down to section number and page. The corpus is German,
so the rest of this README is German as well.

RAG-System über öffentliche Schweizer HR-Dokumente wie GAV und
Personalreglemente, das Fragen mit nachprüfbaren Quellenzitaten beantwortet.

> **In Arbeit** – AI-Engineering-Sprint 24.08.–18.10.2026. Was heute läuft und
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
- Tabellen werden zeilenweise in Satzform gelesen, jeder Wert trägt seine Spaltenbezeichnung
- Einbettung lokal über Ollama mit `bge-m3`
- Chroma-Sammlung `hr_policy` mit Kosinus-Abstand, 211 Chunks. Das Embedding-Modell steht in
  den Metadaten der Sammlung, die Abfrage prüft es beim Start
- Metadaten an jedem Chunk, darunter Dokument, Ziffer, Seite, Titel, Pfad, Stand und Aktualitätsstatus
- LLM-Gateway für alle Ollama-Aufrufe, Chat und Embedding. Jeder Aufruf wird als JSON-Zeile
  protokolliert, bei Verbindungsfehlern bis zu dreimal mit wachsender Pause wiederholt und mit
  Tokenzahlen, Dauer und Kosten zurückgegeben
- End-to-End-Antwort mit Belegnummern über ein lokales Sprachmodell (`gemma3:12b`)
- Strukturierte Ausgabe. Das Schema aus den Pydantic-Klassen geht als `format` an Ollama, die
  Rückgabe wird mit `model_validate_json` geprüft. Pro Spital ein Eintrag mit Aussage und
  Belegstellennummern
- Deterministische Prüfung jeder Antwort gegen die gelieferten Belegstellen, vier Regeln
- HTTP-Schnittstelle mit FastAPI. `POST /frage` gibt Auskunft, Mängel und Messwerte zurück,
  `GET /gesund` ist ein Lebenszeichen. Die Schnittstellenbeschreibung nach OpenAPI und die
  Oberfläche unter `/docs` entstehen aus denselben Pydantic-Klassen
- Eval-Set mit 20 Fällen, zu jedem eine vor dem Lauf festgelegte Sollantwort je Haus.
  Runner misst Retrieval, `frage_beantwortet`, Pflicht- und Verbotsbegriffe, Strukturmängel,
  p50 und p95, Tokens und Kosten und schreibt eine CSV je Lauf
- Tests für Loader und Textbereinigung, Linting mit ruff

**Fehlt noch**

- Workflow. Das Paket `workflow/` enthält nur seinen Docstring.
- Anhänge ohne Gliederungsziffer. Die Lohntabelle auf Seite 24 des USB-GAV liegt im Index unter
  einem Abschnitt über Verbandskosten, weil «Anhang 3: Lohntabelle» keine Ziffer trägt und deshalb
  keinen neuen Abschnitt auslöst. Der Chunk ist über die Vektorsuche nicht auffindbar.
- Groundedness. Die vier Prüfregeln prüfen die Struktur einer Antwort, nicht ihre Deckung durch
  den zitierten Text. Ein Lauf ohne Mangel enthielt eine Aussage, die in der genannten Belegstelle
  nicht steht, siehe «Strukturierte Ausgabe und Prüfung».
- Tests für die Prüfregeln und für die Schnittstelle.
- Aktualitätsprüfung. Beide Fassungen sind von 2015 und 2016, das Feld `status` steht auf `unbekannt`.

**Arbeitsskripte im Wurzelverzeichnis**

Skripte, die nicht Teil des Pakets sind, sondern zum Prüfen von Hand dienen. Alle gitignored.

- `frage.py` stellt fünf feste Testfragen an den Index und zeigt zu jedem Treffer Abstand, Dokument, Seite, Ziffer, Titel und Textanfang
- `antworte.py` stellt dieselben fünf Fragen End-to-End über `auskunft.antworte` und druckt Auskunft, Mängel und Messwerte
- `zeige_index.py` zeigt, was in der Chroma-Sammlung steht, inklusive Metadatenfilter
- `messung.py` misst pro Dokument die Anzahl Abschnitte und die Längenverteilung
- `test_embed.py` und `test_llm.py` prüfen die Ollama-Verbindung für Embedding und Sprachmodell
- `kosten.py` liest das Protokoll und zeigt pro Aufruf Tokens, Dauer und Kosten sowie die Summen

## Architektur

1. `lade_pdf` in `ingestion/loader.py` liest den Text je Seite mit Seitenzahl und überspringt die im Korpus vermerkten Verzeichnisseiten. `seite_als_text` liest eine Seite mit Tabellen in Bändern, also Text oberhalb, Tabelle in Satzform, Text unterhalb
2. `bereinige_seiten` normalisiert die Zeichen und entfernt Symbolzeichen
3. `finde_wiederholte_zeilen` und `entferne_wiederholte_zeilen` werfen Kopf- und Fusszeilen weg
4. `schneide_in_abschnitte` schneidet an nummerierten Überschriften und merkt sich die Startseite, `setze_pfade` trägt den Pfad der übergeordneten Titel ein
5. `lese_abschnitte` in `ingestion/index.py` führt das pro Korpusdokument zusammen
6. `einbetten` schickt die Texte in Stapeln von 32 an `embed` im Gateway
7. `baue_index` legt die Chroma-Sammlung neu an und schreibt Vektoren, Zitattext und Metadaten
8. `embed` in `gateway/llm.py` bettet die Frage ein, `frage_modell` ruft das Sprachmodell. Beide laufen durch
   `_mit_wiederholung`, das bei Verbindungsfehlern bis zu dreimal nachfasst, mit Pausen von 1 und 2 Sekunden zwischen den Versuchen
9. Die Antwort entsteht aus Frage, den vier nächsten Chunks als nummerierte Belegstellen und einer Systemnachricht mit Regeln
10. `protokolliere` schreibt Zeit, Modell, Tokens, Dauer, Versuchsnummer, Kosten und Frage als eine Zeile nach `logs/llm.jsonl`
11. `antworte` in `auskunft.py` gibt das Schema aus `modelle.py` an das Gateway weiter und prüft die Rückgabe mit `model_validate_json`
12. `pruefe` in `pruefung.py` vergleicht die Auskunft mit den Metadaten der Treffer und gibt eine Liste von Mängeln zurück
13. `stelle_frage` in `api/main.py` setzt Auskunft, Mängel und Messwerte zu einem `Ergebnis` zusammen und gibt es als JSON zurück

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

**Tabellen.** `extract_text` gibt eine Tabelle als das aus, was optisch dasteht, also
«Dienstjahre In Monatslohn Oder in Tagen» und darunter «20 ½ 10». Welche Zahl zu welcher
Spalte gehört, ist danach nicht mehr entscheidbar, und beim Chunking kann die Kopfzeile
ganz wegfallen. Bei der Lohntabelle ist das der teuerste Fehlertyp des Systems, weil
Bandminimum und Bandmaximum ununterscheidbar werden. Tabellen laufen deshalb über
`extract_tables` und werden zeilenweise in Sätze umgeschrieben, «Dienstjahre 20, In
Monatslohn ½, Oder in Tagen 10». Ob die erste Zeile eine Kopfzeile ist, entscheidet die
Zellenlänge, weil ein PDF diese Auszeichnung nicht speichert. Gemessen haben echte
Kopfzeilen höchstens 13 Zeichen pro Zelle, die Urlaubstabelle auf Seite 10 hat 80, die
Schwelle liegt bei 30. Passen Kopfzeile und Datenzeile nicht in der Länge zusammen, wird
die reine Werteliste geschrieben, denn ein `zip` würde überzählige Werte still verwerfen.
Nichts verlieren geht vor sauber benennen. Gelesen wird die Seite in Bändern statt die
Tabellenzeilen anzuhängen, sonst stünde derselbe Inhalt zweimal im Text und beide Fassungen
konkurrierten im Retrieval um dieselbe Frage. Betroffen sind die drei Tabellen des
USB-GAV auf den Seiten 10, 11 und 24. Der KSBL-GAV hat keine.

Nicht behandelt sind Tabellen über einen Seitenumbruch. `extract_tables` sieht auf der
Folgeseite eine eigene Tabelle ohne Kopfzeile, dann greift der Rückfall auf die Werteliste.
Der Fall kommt im Korpus nicht vor und wäre ohne Testfall nicht prüfbar.

Eingebettet wird Pfad plus Abschnittstext, zitiert wird nur der Abschnittstext.
Der Pfad muss in die Einbettung, weil das Thema oft nur in der Überschrift
steht. Ziffer 2.3.3 des USB hängt unter «2.3 Beendigung des Arbeitsverhältnisses»,
und das Wort «Beendigung» kommt im Absatztext selbst nicht vor.

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
Chunk als `20 ½ 10` ohne Spaltenzuordnung stand. Das Retrieval hat funktioniert,
die Generierung nicht. Belegt ist nicht richtig. **Behoben in der Ingestion**, siehe
«Tabellen». Seither lautet die Antwort «halber Monatslohn oder 10 Tage» mit Beleg auf
USB Ziff. 2.5.9.

Bei der Frage nach dem Vaterschaftsurlaub hat das Modell den Elternurlaub des
anderen Dokuments so dargestellt, als beantworte er die Frage. **Teilweise behoben.** Die
falsche Gleichsetzung ist weg, und die Dokumentzuordnung prüft seit der strukturierten
Ausgabe der Code. Ob das KSBL die Frage überhaupt beantwortet, bleibt eine inhaltliche Frage
und gehört ins Eval-Set.

**Fünf Prompt-Fassungen gegen diesen einen Fehler.** Ohne Regel gab das Modell den
Elternurlaub als Antwort aus. Mit der Regel «ein benachbartes Thema ist keine Antwort»
nannte es ihn korrekt als Elternurlaub, ohne das Fehlen zu melden. Mit der Anweisung,
das Fehlen zuerst zu melden, liess es beides weg. Mit einem Rollen- und Aufbaublock
(«nenne immer beide Spitäler») wurden vier von fünf Fragen deutlich besser und die
Antwortzeit sank von 35 auf 20 Sekunden, aber der Elternurlaub füllte den KSBL-Platz
wieder ohne Vermerk. Ein längerer Aufbaublock mit nummerierten Entscheidungsschritten
machte es schlimmer und lieferte bei der Tabellenfrage «ein Monatslohn» statt «ein
halber». Behalten wurde die vierte Fassung.

Der Befund daraus. Eine Anweisung, die verlangt, eine Abwesenheit zu bemerken, ist die
schwerste Aufgabe für ein Sprachmodell, weil im Prompt nichts steht, was sie auslöst.
Und «nenne immer beide Häuser» steht im Widerspruch zu «nenne nur Passendes»; das Modell
bricht dann die weichere Regel. Die Information ist aber ausrechenbar. Nach der Suche ist
bekannt, aus welchen Dokumenten Treffer kamen, nach der Antwort, welche Belegstellen
verwendet wurden. Der Abgleich gehört deshalb in den Code und braucht die strukturierte
Ausgabe als Voraussetzung. Prompt-Regeln sind Bitten, Code ist eine Garantie.

## Gateway

Alle Aufrufe an Ollama gehen durch `gateway/llm.py`, beim Indexbau wie bei der
Abfrage. Das Embedding-Modell ist dort als einzige Konstante definiert, `index.py`
importiert sie. Drei Dinge passieren im Gateway für jeden Aufruf, ohne dass die
aufrufenden Module davon wissen.

**Protokoll.** Eine JSON-Zeile pro Modellaufruf in `logs/llm.jsonl`, angehängt, nie
überschrieben. Zeit, Modell, Tokens ein und aus, Dauer, Versuchsnummer, Kosten und die
Frage. Der Antworttext bleibt draussen, das Protokoll soll messen, nicht speichern.
`kosten.py` wertet es aus. Das ist die Datenbasis für die Eval-Tabelle.

**Wiederholung.** Bei Verbindungsfehlern bis zu drei Versuche, mit Pausen von 1 und
2 Sekunden zwischen den Versuchen. Gefangen werden nur Fehler, die von selbst wieder verschwinden können,
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

## Strukturierte Ausgabe und Prüfung

Das Modell antwortet nicht mehr in Fliesstext, sondern in einer vorgegebenen Form.
`Auskunft.model_json_schema()` erzeugt aus den Pydantic-Klassen ein JSON-Schema, das als
`format` an `ollama.chat` geht. Ollama schränkt damit beim Erzeugen ein, welche Zeichen
zulässig sind, statt das Format im Prompt zu erbitten. Die Rückgabe wird anschliessend mit
`model_validate_json` ein zweites Mal geprüft, weil ein anderes Modell oder eine Cloud-API
sich anders verhalten kann.

Die Form hat zwei Ebenen. `SpitalAuskunft` hält Spital, ob die Belegstellen die Frage
beantworten, die Aussage in ganzen Sätzen und die Nummern, auf denen sie beruht. `Auskunft`
hält die Liste dieser Einträge und einen optionalen Hinweis. Die Belegstellen hängen
bewusst am einzelnen Spital und nicht an der ganzen Antwort, sonst liesse sich nicht
prüfen, ob eine Aussage über das eine Haus auf einer Belegstelle des anderen beruht.

Mit den Formatregeln aus dem Systemprompt verschwanden auch die eckigen Klammern im
Antworttext. Eine übersehene Zeile, die noch ein umbenanntes Feld nannte, hat gezeigt, wie
teuer eine tote Referenz im Prompt ist. Sie war die Ursache von drei Fehlern in der Ausgabe
und verschwand mit einer einzigen Korrektur.

`pruefe` in `pruefung.py` vergleicht danach die Antwort mit dem, was geliefert wurde. Vier
Regeln, alle deterministisch und ohne Modellaufruf.

1. Genau ein Eintrag je Spital
2. Jede genannte Belegstellennummer existiert und stammt aus dem Dokument dieses Spitals
3. Wer die Frage beantwortet, nennt eine Belegstelle, wer sie nicht beantwortet, nennt keine
4. Im Antworttext stehen keine Belegstellennummern in eckigen Klammern

Die Zuordnung von Nummer zu Dokument kommt aus den Metadaten der Treffer, also aus derselben
Nummerierung, die der Prompt vergibt.

**Was die Prüfung nicht kann.** Sie prüft die Struktur einer Antwort, nicht ihre Wahrheit.
Ein Lauf mit null Mängeln enthielt die Aussage, Chefärzte gehörten zu den Führungs- und
Fachkadern und seien deshalb vom GAV ausgenommen. Die zitierte Ziffer nennt Chefärzte gar
nicht, sie nennt drei ausgenommene Gruppen und hält fest, dass die betroffenen Funktionen
anderswo benannt werden. Richtiges Dokument, richtige Nummer, alle vier Regeln grün, Aussage
nicht gedeckt. Deckung zu messen braucht ein Eval-Set mit Sollantworten, und sie im Betrieb
zu erkennen braucht eine zweite Instanz, die jede Aussage gegen ihre Belegstelle hält.

## API

`api/main.py` stellt zwei Endpunkte bereit.

| Methode | Pfad | Zweck |
|---|---|---|
| `GET` | `/gesund` | Lebenszeichen ohne Modellaufruf |
| `POST` | `/frage` | Frage beantworten, prüfen und mit Messwerten zurückgeben |

Die Anfrage kommt als `FrageAnfrage` mit der Frage und optional einem Spital. Die Frage ist
auf 5 bis 500 Zeichen begrenzt, und zwar auf der Serverseite. Eine Grenze, die nur ein
Client kennt, ist keine Grenze.

Zurück geht ein `Ergebnis` mit der Auskunft, der Mängelliste aus `pruefe`, dem verwendeten
Modell, der Dauer und den Kosten. Mängel führen bewusst nicht zu einem Fehlercode. Die
Antwort existiert, sie hat nur einen Makel, und der Aufrufer soll entscheiden, was er damit
macht.

Die Signatur `def stelle_frage(anfrage: FrageAnfrage) -> Ergebnis` ist zugleich die
Spezifikation. Aus ihr entstehen die Prüfung der eingehenden Daten, die Form der Antwort und
die Beschreibung nach OpenAPI unter `/openapi.json`. Die Oberfläche unter `/docs` zeigt
diese Beschreibung als bedienbares Formular. Geschrieben ist davon keine Zeile, deshalb kann
sie auch nicht veralten.

```bash
uv run uvicorn hr_policy_assistant.api.main:app --reload
```

## Technische Entscheide

| Entscheid | Gewählt | Alternativen | Begründung |
|---|---|---|---|
| Vektor-DB | Chroma | pgvector, Qdrant | lokal, kein Betriebsaufwand. Der Zugriff ist heute direkt, ein Repository-Interface für einen späteren Wechsel ist Absicht, nicht Stand |
| Paketmanager | uv | poetry, pip-tools | schnelle Auflösung und ein Lockfile, das den Neuaufbau reproduzierbar macht |
| Chunking | Schnitt an Gliederungsziffern | feste Fenster mit Überlappung | der Abschnitt ist die Einheit, die zitiert wird, und der Vertrag ist bereits so gegliedert |
| Chunk-Splitter | keiner | Obergrenze mit Nachteilung | gemessen liegt je ein Abschnitt pro Dokument über 2000 Zeichen, der Median bei 388 und 434 |
| Tabellen | über `extract_tables` in Satzform, Seite in Bändern gelesen | Kopfzeile jedem Chunk voranstellen, Tabellenzeilen anhängen | die Zuordnung steht dann im Text selbst und übersteht Chunking und Retrieval, und kein Inhalt steht doppelt |
| Kopfzeile erkennen | Heuristik über die Zellenlänge, Schwelle 30 | Schriftauszeichnung über `page.chars`, Liste von Hand | ein PDF speichert die Auszeichnung nicht. Die Alternativen sind deutlich mehr Code für drei Tabellen oder beim nächsten Dokument kaputt. Ein Fehlgriff kostet Zuordnung, nicht Inhalt |
| Embedding-Modell | `bge-m3` über Ollama | multilingual-e5, jina-embeddings-v3 | läuft lokal, muss bei Indexbau und Abfrage identisch sein, ein Wechsel erzwingt den Neuaufbau |
| Sprachmodell | `gemma3:12b` über Ollama | qwen3:14b, Cloud-API | passt in 12 GB Grafikspeicher, Deutsch, kein Denkmodus. Vergleich mit Cloud folgt |
| Temperatur | 0 | Standard | reproduzierbare Antworten sind Voraussetzung für Evals |
| Gateway | eine Datei für Chat und Embedding, ein Rückgabeobjekt | direkter Aufruf an jeder Stelle | Protokoll, Wiederholungen und Kosten stehen an einer Stelle. Der Retry-Test hat gezeigt, dass ein Aufruf am Gateway vorbei alles davon verliert |
| Protokollformat | JSON Lines, eine Zeile pro Aufruf | eine JSON-Datei, SQLite | anhängen ohne Lesen, Zeile für Zeile auswertbar, im Editor lesbar |
| Wiederholung | 3 Versuche, Pausen 1 und 2 s, nur Verbindungsfehler | alles wiederholen, nie wiederholen | vorübergehende Fehler überbrücken, dauerhafte sofort sichtbar machen |
| Strukturierte Ausgabe | JSON-Schema als `format` an Ollama, danach Validierung | Zitatformat im Prompt erbitten, Antwort mit regulären Ausdrücken zerlegen | fünf Prompt-Fassungen haben das Format nicht erzwungen, ein Schema tut es. Die Validierung bleibt, weil ein anderes Modell sich anders verhalten kann |
| Belegstellen | je Spital statt je Antwort | flaches Feld über die ganze Antwort | nur so ist prüfbar, ob eine Aussage über ein Haus auf einer Belegstelle des anderen beruht |
| Prüfung | eigenes Modul, deterministisch, vier Regeln | Prüfung im Prompt, Prüfung durch ein zweites Modell | gleiche Eingabe, gleiches Ergebnis, begründbar und ohne Kosten. Ein Modell für diese Aufgabe wäre teurer und unzuverlässiger |
| Mängel in der Antwort | mit Status 200 zurückgeben | Fehlercode werfen, Mängel verschweigen | ein Mangel ist keine gescheiterte Anfrage. Verschweigen wäre schlimmer als benennen |
| Schema im Gateway | als `dict` übergeben | Gateway kennt Pydantic | das Gateway bleibt die eine Stelle zu Ollama und muss über den Rest des Programms nichts wissen |
| Workflow vs. Agent |  |  |  |

## Evals

Zwanzig Fragen aus beiden GAV, zu jeder eine vor dem Lauf festgelegte Sollantwort **je Haus**.
Pro Fall stehen dort die Ziffer, die unter den vier Treffern sein muss, der Sollwert für
`frage_beantwortet`, Pflichtbegriffe und Verbotsbegriffe. Die Fälle liegen als `evals/faelle.yaml`
und damit als Daten neben dem Code, der sie ausführt. Der Massstab ist eine fachliche Setzung,
das Messgerät ist Code, und die Trennung hält nachvollziehbar, dass die Erwartung nicht
nachträglich an das Ergebnis angepasst wurde.

Die Mischung ist Absicht. Acht Fragen regeln beide Häuser, vier nur eines, zwei keines, drei
prüfen Tabellen und drei ein Nachbarthema, das die Ähnlichkeitssuche zuverlässig mitbringt.
Gemessen wird pro Haus, also 40 Antworten je Lauf, weil bei einer Frage die eine Seite stimmen
und die andere falsch sein kann.

```bash
uv run python -m hr_policy_assistant.evals.lauf
```

### Baseline, 13.09.2026

gemma3:12b, temperature 0, fünf Läufe. Massgeblich ist der fünfte.

| Kennzahl | Wert | von |
|---|---|---|
| Erwartete Ziffer unter den Treffern | 28 | 31 Seiten mit erwarteter Ziffer |
| `frage_beantwortet` stimmt | 38 | 40 |
| Pflichtbegriffe vollständig | 35 | 40 |
| Verbotsbegriffe, keiner gefunden | 38 | 40 |
| Strukturmängel aus `pruefe()` | 12 | ganzer Lauf |
| Dauer p50 / p95 | 32.2 s / 46.2 s | 20 Werte |
| Tokens ein / aus | 30338 / 4226 | 20 Fragen |
| Kosten | CHF 0.000000 | lokal |

Neun der vierzig Seiten haben keine erwartete Ziffer, weil das jeweilige Haus das Thema nicht
regelt. Sie zählen bei der Retrieval-Quote nicht mit, sonst würde gegen eine Grundgesamtheit
gerechnet, in der es nichts zu treffen gibt. Verfehlt wurden drei Ziffern.

### Was die Zahlen gezeigt haben

**Reproduzierbarkeit.** Vier Läufe lieferten aufs Token identische Werte, 30338 hinein und
4226 hinaus, und alle fünf dieselben zwölf Strukturmängel bei identischen Quoten. Temperature 0 arbeitet über den ganzen Katalog
reproduzierbar, nicht nur über fünf Fragen.

**Die Halluzination ist noch da.** Der Chefärzte-Fall antwortet, Chefärzte seien den Führungs-
und Fachkadern zugeordnet. USB Ziff. 1.3 nennt sie nicht und hält fest, dass die Funktionen
betrieblich benannt werden. Der Verbotsbegriff hat den Fall zuerst durchgelassen, weil er als
ganzer Satz eingetragen war und das Modell anders formuliert. Gefunden wurde er über den
fehlenden Pflichtbegriff, also über die ausgelassene Einschränkung. Ein Verbotsbegriff sucht
eine bekannte Formulierung, ein Pflichtbegriff eine Einschränkung aus der Quelle.

**p95 ist aus zwanzig Werten nicht belastbar.** Über fünf Läufe schwankt er zwischen 42.8 und
48.5 Sekunden bei identischen Tokenzahlen, der Median dagegen nur zwischen 31.1 und 32.2. Bei
zwanzig Werten ist p95 praktisch der zweitlangsamste, ein einzelner Ausreisser bestimmt ihn.
Wer die Zahl nennt, nennt die Anzahl Messungen dazu.

**Der Katalog war an drei Stellen falsch**, obwohl er von Hand aus dem Gesetzestext geschrieben
wurde. Wer «gut genug» definiert, definiert es nicht einmal, sondern korrigiert den Massstab,
sobald die erste Messung zeigt, wo er danebenlag.

### Was das Set nicht misst

Ob eine Aussage durch ihre Belegstelle gedeckt ist. Geprüft wird, ob die Belegstelle existiert,
zum richtigen Haus gehört und ob bestimmte Wörter vorkommen. Verglichen wird die Antwort gegen
eine Begriffsliste, nicht gegen den Text der Belegstelle selbst. Ein Verbotsbegriff fängt genau
den einen bekannten Fehler und keinen unbekannten. Ein Eval-Set misst Regressionen, es entdeckt
nichts Neues. Das ist die Aufgabe der Kritik-Rolle, und der Chefärzte-Fall ist ihr Abnahmetest.

## Resultate

| Setup | Ziffer getroffen | Pflichtbegriffe | Verbotsbegriffe | Strukturmängel | CHF/Anfrage | p95 |
|---|---|---|---|---|---|---|
| Baseline (naives RAG) | 28/31 | 35/40 | 38/40 | 12 | 0.000000 | 46.2 s |
| LangGraph + Kritik-Rolle |  |  |  |  |  |  |
| Agent-Loop |  |  |  |  |  |  |
| On-Premise gegen Cloud |  |  |  |  |  |  |

Aus Woche 1 zusätzlich die Retrieval-Precision, an fünf Testfragen von Hand beurteilt, k=2
gleich 1.0 und k=4 zwischen 0.6 und 0.7. Fünf Fragen sind eine kleine Stichprobe, die Zahl ist
ein Ausgangspunkt und kein Beleg.

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
