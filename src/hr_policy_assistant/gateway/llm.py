"""LLM-Gateway. Eine Stelle fuer alle Ollama-Aufrufe, Chat und Embedding.

Jeder Aufruf wird bei Verbindungsfehlern wiederholt, jeder Chat-Aufruf protokolliert.
"""

import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime

import httpx
import ollama

from hr_policy_assistant.config import (
    PROJEKT_WURZEL,  # dieselbe Wurzel wie Ingestion und API, nur noch in config.py definiert
)

MODELL = "gemma3:12b"
EMBEDDING_MODELL = "bge-m3"
VERSUCHE = 3
WARTEN_S = 1.0

PROTOKOLL = PROJEKT_WURZEL / "logs" / "llm.jsonl"     # unveraendert, nimmt jetzt die importierte Wurzel

VORUEBERGEHEND = (
    ConnectionError,                                     # NEU: das wirft die ollama-Bibliothek selbst
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)

PREISE_CHF_PRO_MIO = {                       # (Eingabe, Ausgabe) in CHF pro Million Tokens
    "gemma3:12b": (0.0, 0.0),                # lokal, kostet Strom, keine Franken
    "bge-m3": (0.0, 0.0),
}

@dataclass(frozen=True)
class Antwort:
    text: str
    modell: str
    tokens_prompt: int
    tokens_antwort: int
    dauer_s: float
    versuch: int
    kosten_chf: float  # NEU


def _mit_wiederholung(aufruf: Callable):
    """Fuehrt aufruf() aus, bei Verbindungsfehler bis zu VERSUCHE Mal.

    Gibt das Ergebnis und die Nummer des erfolgreichen Versuchs zurueck.
    Die Schleife von vorhin, nur dass der eigentliche Aufruf von aussen kommt.
    """
    pause = WARTEN_S
    for versuch in range(1, VERSUCHE + 1):
        try:
            return aufruf(), versuch                     # aufruf() ist chat oder embed, siehe unten
        except VORUEBERGEHEND as fehler:
            if versuch == VERSUCHE:
                raise
            print(f"Versuch {versuch} gescheitert ({type(fehler).__name__}), warte {pause:.0f} s")
            time.sleep(pause)
            pause *= 2
    raise RuntimeError("unerreichbar")


def protokolliere(a: Antwort, nutzer: str) -> None:
    PROTOKOLL.parent.mkdir(exist_ok=True)
    frage = nutzer.rsplit("Frage: ", maxsplit=1)[-1]
    eintrag = {
        "zeit": datetime.now().isoformat(timespec="seconds"),
        **asdict(a),
        "frage": frage[:200],
    }
    eintrag.pop("text")
    with PROTOKOLL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(eintrag, ensure_ascii=False) + "\n")


def embed(texte: list[str], modell: str = EMBEDDING_MODELL) -> list[list[float]]:
    """Vektoren fuer eine Liste von Texten. Gleiche Wiederholung wie beim Chat."""
    r, _ = _mit_wiederholung(
        lambda: ollama.embed(model=modell, input=texte)  # lambda: Funktion ohne Namen, wird erst in der Schleife gerufen
    )
    return r["embeddings"]

def berechne_kosten(modell: str, tokens_prompt: int, tokens_antwort: int) -> float:
    """Kosten eines Aufrufs in CHF. Unbekanntes Modell kostet null, aber das sieht man im Log."""
    ein, aus = PREISE_CHF_PRO_MIO.get(modell, (0.0, 0.0))   # .get mit Standardwert, kein KeyError
    return round((tokens_prompt * ein + tokens_antwort * aus) / 1_000_000, 6) # 6 Nachkommastellen

def frage_modell(
    system: str,
    nutzer: str,
    modell: str = MODELL,
    schema: dict | None = None,      # NEU: JSON-Schema aus einem Pydantic-Modell, oder None
) -> Antwort:
    """Schickt eine System- und eine Nutzernachricht ans Modell. temperature 0.

    Ist schema gesetzt, darf das Modell nur noch JSON in dieser Form erzeugen.
    """
    start = time.perf_counter()
    r, versuch = _mit_wiederholung(
        lambda: ollama.chat(
            model=modell,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": nutzer},
            ],
            options={"temperature": 0},
            format=schema,           # NEU: None bedeutet freier Text, ein Schema erzwingt die Form
        )
    )
    a = Antwort(
        text=r["message"]["content"],
        modell=modell,
        tokens_prompt=r.get("prompt_eval_count", 0),
        tokens_antwort=r.get("eval_count", 0),
        dauer_s=round(time.perf_counter() - start, 2),
        versuch=versuch,
        kosten_chf=berechne_kosten(
            modell, r.get("prompt_eval_count", 0), r.get("eval_count", 0)
        ),
    )
    protokolliere(a, nutzer)
    return a