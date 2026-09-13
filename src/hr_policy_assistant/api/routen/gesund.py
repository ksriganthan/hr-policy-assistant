"""Betrieb. Endpunkte, die ohne Sprachmodell auskommen."""

from fastapi import APIRouter

router = APIRouter(tags=["Betrieb"])             # tags gruppiert die Endpunkte in /docs


@router.get("/gesund")                           # GET, weil nichts mitgeschickt wird
def gesund() -> dict[str, str]:
    """Lebenszeichen. Prueft den Server, ohne das Sprachmodell zu bemuehen."""
    return {"status": "ok"}