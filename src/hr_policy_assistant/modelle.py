"""Form der Antwort. Das Modell muss sie einhalten, Pydantic prueft sie."""

from typing import Literal

from pydantic import BaseModel


class SpitalAuskunft(BaseModel):     # BaseModel ist die Pydantic-Klasse, wie ein dataclass, aber mit Pruefung
    """Was genau ein Spital zur Frage regelt."""

    spital: Literal["USB", "KSBL"]   # Literal laesst nur diese zwei Werte zu, "Universitaetsspital" waere ein Fehler
    frage_beantwortet: bool                   # True heisst, die Belegstellen regeln die Frage fuer dieses Spital
    text: str                        # die Aussage in ganzen Saetzen, ohne Klammernummern im Text
    belegstellen: list[int]          # Nummern der verwendeten Belegstellen, leere Liste wenn geregelt False ist


class Auskunft(BaseModel):
    """Die ganze Antwort, ein Eintrag pro Spital."""

    spitaeler: list[SpitalAuskunft]  # zwei Eintraege, USB und KSBL
    hinweis: str | None = None       # verwandte Belegstelle, die die Frage nicht beantwortet, None wenn es keine gibt