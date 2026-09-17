"""Zeigt einen Graphenlauf Schritt fuer Schritt, statt nur das Ergebnis zu drucken.

GRAPH.invoke() laeuft den ganzen Graphen durch und gibt den Endzustand zurueck.
Dazwischen sieht man nichts. GRAPH.stream(stream_mode="updates") gibt nach jedem
Knoten aus, was dieser Knoten zurueckgegeben hat, also genau die Aenderungsmeldung,
die LangGraph anschliessend per zustand.update(...) in den Zustand schreibt.

Damit wird dreierlei sichtbar:
  - in welcher Reihenfolge die Knoten laufen und ob es einen Ruecksprung gab
  - welche Felder ein Knoten anfasst und welche er unberuehrt stehen laesst
  - was der Kritiker beanstandet hat, bevor der zweite Entwurf darauf antwortet

Das Ergebnis am Ende ist der letzte Entwurf, auch wenn der Kritiker ihn beanstandet
hat. Nach MAX_RUNDEN geht der Graph so oder so nach pruefen.

Start:  uv run python zeige_ablauf.py
        uv run python zeige_ablauf.py "Gilt der GAV für Chefärzte?"
        uv run python zeige_ablauf.py --bild
"""

import sys

from hr_policy_assistant.workflow.graph import GRAPH

STANDARDFRAGE = "Gilt der GAV für Chefärzte?"


def zeige(knoten: str, aenderung: dict) -> None:
    """Druckt einen Knoten und das, was er geaendert hat. Der Rest des Zustands bleibt."""
    felder = ", ".join(aenderung.keys())                  # genau die Schluessel der Rueckgabe
    print(f"\n--- {knoten:12} aendert: {felder}")

    if knoten == "suchen":
        for i, (_, m, d) in enumerate(aenderung["treffer"], start=1):
            print(f"      [{i}] {d:.3f}  {m['dokument']:5} Ziff. {m['nummer']:9} {m['titel'][:40]}")

    elif knoten == "entwerfen":
        print(f"      Entwurf Nr. {aenderung['runde']}")   # runde zaehlt die Entwuerfe, nicht die Schleifen
        for s in aenderung["auskunft"].spitaeler:
            print(f"      {s.spital:5} {s.text[:110]}")

    elif knoten == "kritisieren":
        kritik = aenderung["kritik"]
        print(f"      gedeckt = {kritik.gedeckt}")
        for b in kritik.beanstandungen:
            print(f"      beanstandet: {b}")
        if not kritik.beanstandungen:
            print("      nichts beanstandet, der Graph geht direkt nach pruefen")

    elif knoten == "pruefen":
        maengel = aenderung["maengel"]                    # deterministisch, ohne Modell
        print(f"      {len(maengel)} Maengel" if maengel else "      keine Maengel")
        for mangel in maengel:
            print(f"      ! {mangel}")


if __name__ == "__main__":
    if "--bild" in sys.argv:
        # Das Diagramm aus dem echten Graphen erzeugt, kann also nicht veralten.
        print(GRAPH.get_graph().draw_mermaid())
        raise SystemExit

    frage = sys.argv[1] if len(sys.argv) > 1 else STANDARDFRAGE
    print(f"Frage: {frage}")

    # Dieselben Startwerte wie in antworte_mit_kritik(). Hier bewusst noch einmal
    # ausgeschrieben, damit dieses Skript nichts am laufenden Code aendert.
    start = {
        "frage": frage,
        "spital": None,
        "treffer": [],
        "auskunft": None,
        "kritik": None,
        "beanstandungen": [],
        "runde": 0,
        "maengel": [],
        "verlauf": [],
        "aufrufe": [],
    }

    letzte_auskunft = None
    schritte = 0

    # stream() liefert je fertigem Knoten ein dict {knotenname: aenderungsmeldung}.
    for schritt in GRAPH.stream(start, stream_mode="updates"):
        for knoten, aenderung in schritt.items():
            schritte += 1
            zeige(knoten, aenderung)
            if knoten == "entwerfen":
                letzte_auskunft = aenderung["auskunft"]   # der jeweils juengste Entwurf

    print(f"\n=== {schritte} Knoten gelaufen. Ausgeliefert wird der letzte Entwurf:")
    for s in letzte_auskunft.spitaeler:
        nummern = ", ".join(str(n) for n in s.belegstellen) or "keine"
        zeichen = "+" if s.frage_beantwortet else "-"
        print(f" {zeichen} {s.spital}: {s.text}")
        print(f"     Belegstellen: {nummern}")
