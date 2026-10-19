"""Fingerabdruck der Dateien, die ein Eval-Ergebnis beeinflussen.

Beim Lauf wird er neben die CSV gelegt, beim Gate neu berechnet und
verglichen. Stimmt er nicht, stammt die Messung aus einem anderen Stand.
"""

import hashlib
from pathlib import Path

from hr_policy_assistant.config import PROJEKT_WURZEL

# Was die Antwort beeinflusst. gate.py steht bewusst nicht drin, sonst
# wuerde jede Aenderung am Gate die eigene Pruefung ungueltig machen.
RELEVANT = [
    "src/hr_policy_assistant/auskunft.py",
    "src/hr_policy_assistant/modelle.py",
    "src/hr_policy_assistant/pruefung.py",
    "src/hr_policy_assistant/gateway/llm.py",
    "src/hr_policy_assistant/workflow/graph.py",
    "src/hr_policy_assistant/workflow/agent.py",
    "src/hr_policy_assistant/evals/lauf.py",
    "evals/faelle.yaml",
]


def fingerabdruck() -> str:
    """Ein Hash ueber alle relevanten Dateien, in fester Reihenfolge."""
    h = hashlib.sha256()
    for rel in sorted(RELEVANT):                  # sortiert, damit die Reihenfolge nie zufaellig ist
        pfad = PROJEKT_WURZEL / rel
        h.update(rel.encode())                    # der Name zaehlt mit, sonst faellt Umbenennen nicht auf
        h.update(pfad.read_bytes())               # Bytes, nicht Text, damit Zeilenenden nicht mitreden
    return h.hexdigest()[:16]                     # 16 Zeichen reichen, der Rest ist nicht lesbarer


def begleitdatei(csv_pfad: Path) -> Path:
    """Zur CSV gehoert eine gleichnamige Datei mit der Endung .herkunft."""
    return csv_pfad.with_suffix(".herkunft")


def schreibe(csv_pfad: Path) -> None:
    """Nach einem Lauf aufrufen."""
    begleitdatei(csv_pfad).write_text(fingerabdruck(), encoding="utf-8")


def lies(csv_pfad: Path) -> str | None:
    """None, wenn keine Begleitdatei da ist, also bei alten Laeufen."""
    p = begleitdatei(csv_pfad)
    return p.read_text(encoding="utf-8").strip() if p.exists() else None