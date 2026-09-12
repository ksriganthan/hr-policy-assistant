"""HTTP-Schnittstelle. Eine Frage rein, eine geprüfte Auskunft raus."""

from fastapi import FastAPI

from hr_policy_assistant.auskunft import antworte
from hr_policy_assistant.modelle import Ergebnis, FrageAnfrage
from hr_policy_assistant.pruefung import pruefe

app = FastAPI(              # das Anwendungsobjekt, uvicorn sucht genau diese Variable - Server als Objekt
    title="hr-policy-assistant",                 # Titel und Beschreibung landen in /docs und in openapi.json
    description="Fragen zu zwei Schweizer Spital-GAV, beantwortet mit Belegstellen und geprueft.",
    version="0.1.0",
)


@app.get("/gesund")                              # GET, weil nichts mitgeschickt wird
def gesund() -> dict[str, str]:
    """Lebenszeichen. Prueft den Server, ohne das Sprachmodell zu bemuehen."""
    return {"status": "ok"}


@app.post("/frage")                              # POST, weil die Frage im Rumpf mitkommt und nicht in der URL steht
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