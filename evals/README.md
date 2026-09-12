# Eval-Set

Woche 3 (13.09.2026). 20 Fragen mit vorher festgelegter Sollantwort, zwei Läufe mit
`gemma3:12b`, Ergebnis als CSV. Nicht unter 15 Fragen, sonst ist p95 aus zu wenigen
Werten gerechnet.

Die fachliche Quelle ist der Fragenkatalog im Sprint-Vault
(`03 Ressourcen/Eval-Set Fragenkatalog.md`). Die Sollantworten entstehen dort durch Lesen
in den beiden GAV, nicht aus dem Gedächtnis. `faelle.yaml` ist die technische Fassung davon.

## Warum die Sollantwort vor dem Lauf kommt

«Elternurlaub erwähnt» ist mal richtig und mal falsch, je nachdem wie er erwähnt wird.
Ohne vorher festgelegte Sollantwort misst ein Eval-Set nichts. Ein Lauf mit null
Strukturmängeln enthielt eine Aussage, die in der zitierten Belegstelle nicht steht
(Chefärzte als Führungs- und Fachkader, USB Ziff. 1.3 nennt sie nicht). Deshalb wird zu jeder
Frage **vor dem Lauf** festgehalten, was vorkommen muss und was nicht vorkommen darf.

## Felder pro Fall in `faelle.yaml`

| Feld | Bedeutung |
|---|---|
| `frage` | Der Text, wie ein HR-Mensch ihn stellen würde |
| `usb.ziffer` / `ksbl.ziffer` | Die Ziffer, die unter den k=4 Treffern stehen muss. Leer, wenn das Haus dazu nichts regelt |
| `usb.beantwortet` / `ksbl.beantwortet` | Sollwert für `frage_beantwortet`, true oder false |
| `usb.muss` / `ksbl.muss` | Begriffe oder Zahlen, die im Text dieses Hauses vorkommen müssen |
| `usb.darf_nicht` / `ksbl.darf_nicht` | Begriffe, die dort nicht vorkommen dürfen. Hält bekannte Fehler fest |
| `kategorie` | `beide` · `nur_eines` · `keines` · `tabelle` · `nachbarthema` |

## Mischung

| Kategorie | Warum | Ziel |
|---|---|---|
| `beide` | Normalfall, beide GAV regeln dasselbe Thema unterschiedlich | 8 |
| `nur_eines` | Prüft, ob das Modell eine Abwesenheit melden kann | 4 |
| `keines` | Prüft, ob es bei fehlender Grundlage schweigt statt zu erfinden | 2 |
| `tabelle` | Prüft die Tabellenarbeit aus Woche 2 gegen einen Rückfall | 3 |
| `nachbarthema` | Ein ähnliches Thema liegt im Korpus daneben und kommt bei der Ähnlichkeitssuche immer mit | 3 |

## Was `lauf.py` misst

Retrieval-Treffer (erwartete Ziffer unter den k=4 Treffern), Pflicht- und Verbotsbegriffe,
Sollwert von `frage_beantwortet`, Strukturmängel aus `pruefung.pruefe()`, Dauer p50 und p95
über mindestens zwei Läufe, Tokens und Kosten aus `logs/llm.jsonl`.

**Was es nicht misst.** Ob jeder Satz der Antwort durch die zitierte Belegstelle gedeckt
ist. Ein Verbotsbegriff fängt genau die eine bekannte Halluzination, keine unbekannte. Ein
Eval-Set misst Regressionen gegen bekannte Fehler, es entdeckt keine neuen. Dafür kommt in
Woche 4 die Kritik-Rolle.

## Ablage

- `faelle.yaml` – die Fälle
- `lauf.py` – lädt die Fälle, ruft `auskunft.antworte()`, wendet `pruefung.pruefe()` an,
  prüft die Sollkriterien, schreibt eine Zeile pro Frage
- `ergebnisse/` – CSV pro Lauf, Zeitstempel und Modellname im Dateinamen

Die Prüflogik pro Frage gehört hierher und nicht nach `pruefung.py`. Dort steht, was immer
gilt, unabhängig von der Frage. Hier steht, was für diese eine Frage erwartet wird.
