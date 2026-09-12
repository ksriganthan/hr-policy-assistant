"""Deterministische Pruefung der Modellausgabe gegen die gelieferten Belegstellen."""

import re

from hr_policy_assistant.modelle import Auskunft

SPITAELER = ("USB", "KSBL")
KLAMMERNUMMER = re.compile(r"\[\d+\]")           # NEU: findet [1], [12] usw. im Fliesstext


def pruefe(auskunft: Auskunft, treffer) -> list[str]:
    """Vergleicht die Auskunft mit den Belegstellen. Leere Liste heisst sauber."""
    maengel = []

    herkunft = {}
    for i, (_, m, _) in enumerate(treffer, start=1):
        herkunft[i] = m["dokument"]

    genannt = [s.spital for s in auskunft.spitaeler]
    for spital in SPITAELER:
        anzahl = genannt.count(spital)
        if anzahl != 1:
            maengel.append(f"{spital} kommt {anzahl} mal vor statt genau einmal")

    for s in auskunft.spitaeler:
        for nr in s.belegstellen:
            if nr not in herkunft:
                maengel.append(f"{s.spital} nennt Belegstelle {nr}, die es nicht gibt")
            elif herkunft[nr] != s.spital:
                maengel.append(f"{s.spital} nennt Belegstelle {nr} aus {herkunft[nr]}")

        if s.frage_beantwortet and not s.belegstellen:
            maengel.append(f"{s.spital} beantwortet die Frage, nennt aber keine Belegstelle")
        if not s.frage_beantwortet and s.belegstellen:
            maengel.append(f"{s.spital} beantwortet die Frage nicht, nennt aber {s.belegstellen}")

        klammern = KLAMMERNUMMER.findall(s.text)          # NEU: alle Fundstellen, nicht nur die erste
        if klammern:
            maengel.append(f"{s.spital} hat Klammernummern im Text: {', '.join(klammern)}")

    return maengel