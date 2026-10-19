"""Eval-Gate. Liest die juengste Graph-CSV und prueft drei Schwellen.

Das Gate misst nichts. Es liest ab, was der Eval-Lauf gemessen hat, und
entscheidet ueber Exit-Code 0 oder 1. Darum laeuft es auch dort, wo kein
Modell vorhanden ist, etwa auf einem CI-Runner.
"""

import csv
import sys
from pathlib import Path

from hr_policy_assistant.config import PROJEKT_WURZEL

ERGEBNISSE = PROJEKT_WURZEL / "evals" / "ergebnisse"
HAEUSER = ("usb", "ksbl")

# Vorab festgelegt am 19.10.2026, gemessen 31/40 und 38/40 bei 7 Verbotstreffern.
# Die Schwellen liegen knapp darunter, damit Rauschen sie nicht reisst.
# Eine Schwelle wird nie nachtraeglich gesenkt, um einen roten Lauf gruen zu machen.
MIN_PFLICHTBEGRIFFE = 0.70
MIN_BEANTWORTET = 0.90
MAX_VERBOTSTREFFER = 8


def juengste_csv() -> Path:
    """Die neueste Graph-CSV. Agent-Laeufe tragen _agent im Namen und zaehlen nicht."""
    kandidaten = [p for p in ERGEBNISSE.glob("*.csv") if "_agent" not in p.name]
    if not kandidaten:
        print("Keine Eval-CSV gefunden.")
        raise SystemExit(1)
    return max(kandidaten, key=lambda p: p.name)        # der Zeitstempel steht vorne, Name sortiert = Zeit sortiert


def lies_seiten(pfad: Path) -> list[dict]:
    """Eine Zeile pro Fall wird zu zwei Seiten, je Haus eine."""
    with pfad.open(encoding="utf-8-sig", newline="") as f:   # utf-8-sig, die CSV hat ein BOM fuer Excel
        zeilen = list(csv.DictReader(f, delimiter=";"))
    return [
        {
            "muss_fehlend": z[f"{h}_muss_fehlend"],          # leer heisst: nichts fehlt
            "verboten": z[f"{h}_verboten"],                  # leer heisst: kein Verbotsbegriff drin
            "beantwortet_ok": z[f"{h}_beantwortet_ok"] == "True",   # CSV kennt nur Text, nicht True/False
        }
        for z in zeilen
        for h in HAEUSER
    ]


def main() -> None:
    pfad = juengste_csv()
    seiten = lies_seiten(pfad)
    n = len(seiten)

    pflicht = sum(1 for s in seiten if not s["muss_fehlend"]) / n
    beantwortet = sum(1 for s in seiten if s["beantwortet_ok"]) / n
    verbotstreffer = sum(1 for s in seiten if s["verboten"])

    print(f"Eval-Gate, Grundlage {pfad.name}, {n} Seiten")
    print(f"  Pflichtbegriffe   {pflicht:.2f}   Schwelle >= {MIN_PFLICHTBEGRIFFE}")
    print(f"  Beantwortet       {beantwortet:.2f}   Schwelle >= {MIN_BEANTWORTET}")
    print(f"  Verbotstreffer    {verbotstreffer}      Schwelle <= {MAX_VERBOTSTREFFER}")

    gruende = []                                        # alle Verstoesse sammeln, nicht beim ersten abbrechen
    if pflicht < MIN_PFLICHTBEGRIFFE:
        gruende.append(f"Pflichtbegriffe {pflicht:.2f} unter {MIN_PFLICHTBEGRIFFE}")
    if beantwortet < MIN_BEANTWORTET:
        gruende.append(f"Beantwortet {beantwortet:.2f} unter {MIN_BEANTWORTET}")
    if verbotstreffer > MAX_VERBOTSTREFFER:
        gruende.append(f"Verbotstreffer {verbotstreffer} ueber {MAX_VERBOTSTREFFER}")

    if gruende:
        print("\nGate zu:")
        for g in gruende:
            print(f"  - {g}")
        sys.exit(1)                                     # 1 macht den CI-Schritt rot

    print("\nGate offen.")
    sys.exit(0)                                         # 0 heisst in Ordnung


if __name__ == "__main__":
    main()