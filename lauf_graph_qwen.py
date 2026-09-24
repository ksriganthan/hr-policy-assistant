# -*- coding: utf-8 -*-
"""Neue Baseline. Derselbe Graph, dasselbe Eval-Set, nur auf qwen2.5:14b statt gemma3:12b.

Noetig, weil der Agent-Loop Tool-Calling braucht und gemma3 das nicht kann. Ohne diesen
Lauf wuerde der Vergleich zwei Modelle messen statt zwei Steuerungen.
"""
import os
import sys
import traceback
from pathlib import Path

os.environ["HRPA_MODELL"] = "qwen2.5:14b"
os.environ["HRPA_WEG"] = "graph"

LOG = Path(r"D:\hr-policy-assistant\lauf_graph_qwen.log")
LOG.write_text("Start\n", encoding="utf-8")


class Mitschrift:
    """Schreibt alles, was gedruckt wird, zusaetzlich in die Logdatei."""

    def __init__(self, original):
        self.original = original

    def write(self, text):
        self.original.write(text)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(text)

    def flush(self):
        self.original.flush()


sys.stdout = Mitschrift(sys.stdout)

try:
    from hr_policy_assistant.evals.lauf import main
    main()
    print("\nFERTIG")
except Exception:
    print("\nABSTURZ\n" + traceback.format_exc())
