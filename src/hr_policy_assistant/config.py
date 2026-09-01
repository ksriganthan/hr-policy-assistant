"""Projektweite Konstanten.

Liegt hier, damit Ingestion, Gateway und API
dieselbe Projektwurzel benutzen, ohne voneinander abzuhaengen.
"""

from pathlib import Path

# resolve() zuerst, weil __file__ je nach Startart relativ sein kann und
# parents dann nicht genug Ebenen haette.
# parents[0]  hr_policy_assistant
# parents[1]  src
# parents[2]  die Projektwurzel
PROJEKT_WURZEL = Path(__file__).resolve().parents[2]
