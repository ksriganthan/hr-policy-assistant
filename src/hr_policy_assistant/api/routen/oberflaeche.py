"""Oberflaeche. Liefert die Bedienseite aus, die dann selbst /frage aufruft."""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["Oberflaeche"])

# __file__ ist der Pfad dieser Datei, also .../api/routen/oberflaeche.py
# .parent ist routen, .parent.parent ist api, darunter liegt statisch/
# Der Pfad wird einmal beim Import berechnet und nicht bei jedem Aufruf.
SEITE = Path(__file__).resolve().parent.parent / "statisch" / "index.html"


@router.get(
    "/",                                     # die Wurzel, also http://127.0.0.1:8000/
    response_class=FileResponse,             # ohne das serialisiert FastAPI den Rueckgabewert zu JSON
    include_in_schema=False,                 # die Seite ist kein API-Endpunkt und stoert in /docs
)
def oberflaeche() -> FileResponse:
    """Gibt die Bedienseite zurueck."""
    return FileResponse(SEITE)               # FileResponse setzt text/html anhand der Endung .html selbst