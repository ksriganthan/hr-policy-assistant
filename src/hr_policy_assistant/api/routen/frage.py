"""Auskunft. Der fachliche Endpunkt."""

from fastapi import APIRouter

from hr_policy_assistant.auskunft import antworte
from hr_policy_assistant.modelle import Ergebnis, FrageAnfrage
from hr_policy_assistant.pruefung import pruefe

router = APIRouter(tags=["Auskunft"])


@router.post("/frage")                           # POST, weil die Frage im Rumpf mitkommt und nicht in der URL steht
def stelle_frage(anfrage: FrageAnfrage) -> Ergebnis:
    """Beantwortet eine Frage und gibt die Antwort zusammen mit den gefundenen Maengeln zurueck."""
    auskunft, a, treffer = antworte(anfrage.frage, anfrage.spital)   # a ist die Gateway-Huelle mit Modell, Dauer, Kosten
    return Ergebnis(
        auskunft=auskunft,
        maengel=pruefe(auskunft, treffer),
        modell=a.modell,
        dauer_s=a.dauer_s,
        kosten_chf=a.kosten_chf,
    )