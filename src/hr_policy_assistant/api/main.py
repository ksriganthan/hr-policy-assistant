"""HTTP-Schnittstelle. Eine Frage rein, eine geprüfte Auskunft raus.

Diese Datei erzeugt nur noch die Anwendung und haengt die Router ein.
Die Endpunkte selbst liegen unter api/routen/, nach Zweck getrennt.
"""

from fastapi import FastAPI

from hr_policy_assistant.api.routen import frage, gesund

app = FastAPI(              # das Anwendungsobjekt, uvicorn sucht genau diese Variable - Server als Objekt
    title="hr-policy-assistant",                 # Titel und Beschreibung landen in /docs und in openapi.json
    description="Fragen zu zwei Schweizer Spital-GAV, beantwortet mit Belegstellen und geprueft.",
    version="0.1.0",
)

app.include_router(frage.router)                 # ab hier kennt die App POST /frage
app.include_router(gesund.router)                # und GET /gesund