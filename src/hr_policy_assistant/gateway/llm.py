"""LLM-Gateway. Eine Stelle fuer alle Modellaufrufe.

Nur der Aufruf selbst mit Tokenzahl und Dauer. Protokoll, Wiederholungen
bei Fehlern und Kostenzaehlung kommen dazu, ohne dass die Aufrufer sich aendern.
"""

import time
from dataclasses import dataclass

import ollama

MODELL = "gemma3:12b"


@dataclass(frozen=True)
class Antwort:
    """Was ein Modellaufruf zurueckgibt, mit dem was er gekostet hat."""

    text: str
    modell: str
    tokens_prompt: int
    tokens_antwort: int
    dauer_s: float


def frage_modell(system: str, nutzer: str, modell: str = MODELL) -> Antwort:
    """Schickt eine System- und eine Nutzernachricht ans Modell.

    temperature 0, damit dieselbe Frage dieselbe Antwort gibt. Fuer ein System,
    das Vertragstext wiedergeben soll, ist Zufall kein Vorteil.
    """
    start = time.perf_counter()
    r = ollama.chat(
        model=modell,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": nutzer},
        ],
        options={"temperature": 0}, # Wahrscheinlichkeit vom nächsten Wort steuern
    )
    return Antwort(
        text=r["message"]["content"], # r = Dictionary
        modell=modell,
        tokens_prompt=r.get("prompt_eval_count", 0),
        tokens_antwort=r.get("eval_count", 0),
        dauer_s=round(time.perf_counter() - start, 2),
    )