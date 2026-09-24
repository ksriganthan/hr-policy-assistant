# -*- coding: utf-8 -*-
"""Ein einziger Durchlauf durch den Agent-Loop, bevor das ganze Eval-Set laeuft.

Schreibt alles nach rauchtest_agent.log in UTF-8, damit die Bruecke die Datei lesen kann.
"""
import os
import traceback
from pathlib import Path

os.environ["HRPA_MODELL"] = "qwen2.5:14b"   # muss VOR dem Import stehen, llm.py liest es beim Import

LOG = Path(r"D:\hr-policy-assistant\rauchtest_agent.log")
zeilen = []


def sag(*teile):
    text = " ".join(str(t) for t in teile)
    zeilen.append(text)
    LOG.write_text("\n".join(zeilen), encoding="utf-8")


try:
    from hr_policy_assistant.workflow.agent import antworte_mit_agent

    sag("Import ok, Lauf startet")
    e = antworte_mit_agent("Wie viele Ferientage habe ich mit 50 Jahren?")

    sag("=" * 60)
    sag("status", e["status"], e["abbruchgrund"])
    sag("Runden", e["runde"])
    sag("Modellaufrufe", len(e["aufrufe"]))
    sag("Belegstellen", len(e["treffer"]))
    sag("Maengel", e["maengel"])
    sag("-" * 60)
    for zeile in e["verlauf"]:
        sag("  ", zeile[:200])
    sag("-" * 60)
    if e["auskunft"]:
        for s in e["auskunft"].spitaeler:
            sag(f"{s.spital}: beantwortet={s.frage_beantwortet} belege={s.belegstellen}")
            sag("  ", s.text[:300])
    else:
        sag("keine Auskunft entstanden")
    sag("FERTIG")
except Exception:
    sag("ABSTURZ")
    sag(traceback.format_exc())
