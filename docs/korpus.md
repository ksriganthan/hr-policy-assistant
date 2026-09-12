# Korpus – Quellenverzeichnis

Jedes Dokument in `data/raw/` hier eintragen. Diese Metadaten hängen an jedem Chunk
(`ingestion/index.py`, `KORPUS`) und in jedem Zitat. `data/raw/` ist gitignored, die PDF
werden **nicht** committet. Ein GAV ist ein privatrechtlicher Vertrag der Sozialpartner und kein
amtliches Werk, deshalb nur verlinken.

| Datei | Titel | Herausgeber | Stand / gültig ab | Geltungsbereich | Seiten | URL | Abrufdatum |
|---|---|---|---|---|---|---|---|
| `gav_universitaetsspital_basel.pdf` | Gesamtarbeitsvertrag (GAV) USB / FPS / UPK | Universitätsspital Basel, Universitäre Psychiatrische Kliniken Basel, Felix Platter-Spital + Sozialpartner | **gültig per 01.01.2016** (PDF erstellt 07/2015) | Voll- und teilzeitbeschäftigte Mitarbeitende von USB, UPK, FPS. **Nicht unterstellt:** Geschäfts-/Spitalleitung, Führungs- und Fachkader, Personal in Ausbildung und Praktikanten | 24 | [sbk-bsbl.ch](https://www.sbk-bsbl.ch/fileadmin/bsbl/sozialpartnerschaft/gav/basel-stadt/gesamtarbeitsvertrag_fps-usb-upk_bs.pdf), Zweitquelle [syna.ch](https://syna.ch/nordwestschweiz/images/Nordwestschweiz/Regionale-GAV/Spit%C3%A4ler_Basel-Stadt_GAV.pdf) | vor 24.08.2026, genaues Datum nicht festgehalten |
| `spitalbl_gav.pdf` | GAV Kantonsspital Baselland / Psychiatrie Baselland | Kantonsspital Baselland, Psychiatrie Baselland + Sozialpartner | **01.07.2015** | Gesamtes voll- und teilzeitlich beschäftigtes Personal von KSBL und PBL. **Nicht unterstellt:** integrative Arbeitsplätze, Berufslernende, Tertiär-Lernende Gesundheitsberufe, Praktikanten, Aushilfen bis 3 Monate, Study Nurses, fondsfinanzierte wiss. Mitarbeitende, leitende Ärzte/Chefärzte | 26 | [syna.ch](https://syna.ch/images/Nordwestschweiz/Regionale-GAV/SpitalBL_GAV.pdf) (Dateiname stimmt mit dem lokalen überein), Zweitquelle [ksbl.ch](https://www.ksbl.ch/media/M247214U/GAV.pdf) | vor 24.08.2026, genaues Datum nicht festgehalten |

## Aktualitätsstatus

Beide Fassungen sind von 2015 und 2016. Das Feld `status` hängt an jedem Chunk, damit das
System bei veralteten Quellen warnen kann statt einfach zu zitieren.

| Datei | neuere Fassung geprüft am | Ergebnis | Feld `status` |
|---|---|---|---|
| `gav_universitaetsspital_basel.pdf` | 13.09.2026 | Die Sozialpartner (SBK BS/BL, Syna, VSAO Basel) verlinken weiterhin die Fassung «gültig per 1.1.2016». Kein neuerer Volltext gefunden. Die Lohntabellen werden davon getrennt jährlich nachgeführt (Stand 2026 beim VSAO). Nicht geprüft, ob der Vertrag seit 2016 durch Nachträge geändert wurde | `unbekannt` |
| `spitalbl_gav.pdf` | 13.09.2026 | Syna und KSBL verlinken weiterhin die Fassung vom 01.07.2015. Kein neuerer Volltext gefunden. Nachträge nicht geprüft | `unbekannt` |

Mögliche Werte für `status`: `aktuell` · `veraltet` · `unbekannt`. `unbekannt` bleibt
stehen, weil «kein neuerer Volltext gefunden» nicht dasselbe ist wie «geprüft aktuell». Der
Wechsel auf `aktuell` oder `veraltet` setzt eine Auskunft der Sozialpartner voraus und
bedeutet einen Neuaufbau des Index, weil das Feld in den Chunk-Metadaten steht.

**Bekannte Grenze.** Der Vaterschaftsurlaub ist seit 2021 bundesrechtlich geregelt. Eine
Antwort aus dem USB-GAV von 2016 kann perfekt belegt und trotzdem fachlich überholt sein.
Genau das ist der Grund für das Feld.
