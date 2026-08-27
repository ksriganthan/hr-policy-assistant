# Korpus – Quellenverzeichnis

Jedes Dokument in `data/raw/` hier eintragen. Diese Metadaten landen später an jedem Chunk und in jedem Zitat.
`data/raw/` ist gitignored – die PDFs werden **nicht** committet (GAV = privatrechtlicher Vertrag der Sozialpartner, kein amtliches Werk).

| Datei | Titel | Herausgeber | Stand / gültig ab | Geltungsbereich | Seiten | URL | Abrufdatum |
|---|---|---|---|---|---|---|---|
| `gav_universitaetsspital_basel.pdf` | Gesamtarbeitsvertrag (GAV) USB / FPS / UPK | Universitätsspital Basel, Universitäre Psychiatrische Kliniken Basel, Felix Platter-Spital + Sozialpartner | **gültig per 01.01.2016** (PDF erstellt 07/2015) | Voll- und teilzeitbeschäftigte Mitarbeitende von USB, UPK, FPS. **Nicht unterstellt:** Geschäfts-/Spitalleitung, Führungs- und Fachkader, Personal in Ausbildung und Praktikanten | 24 | _nachtragen_ | _nachtragen_ |
| `spitalbl_gav.pdf` | GAV Kantonsspital Baselland / Psychiatrie Baselland | Kantonsspital Baselland, Psychiatrie Baselland + Sozialpartner | **01.07.2015** | Gesamtes voll- und teilzeitlich beschäftigtes Personal von KSBL und PBL. **Nicht unterstellt:** integrative Arbeitsplätze, Berufslernende, Tertiär-Lernende Gesundheitsberufe, Praktikanten, Aushilfen bis 3 Monate, Study Nurses, fondsfinanzierte wiss. Mitarbeitende, leitende Ärzte/Chefärzte | 26 | _nachtragen_ | _nachtragen_ |

## Aktualitätsstatus
⚠️ **Beide Fassungen sind von 2015/2016.** Vor dem Eval-Set prüfen, ob neuere Versionen existieren, und den Status hier festhalten:

| Datei | neuere Fassung geprüft am | Ergebnis | Feld `status` |
|---|---|---|---|
| `gav_universitaetsspital_basel.pdf` |  |  | `unbekannt` |
| `spitalbl_gav.pdf` |  |  | `unbekannt` |

Mögliche Werte für `status`: `aktuell` · `veraltet` · `unbekannt`.
Das Feld muss an jedem Chunk hängen – dein System soll bei veralteten Quellen warnen, nicht einfach zitieren.
