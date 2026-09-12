"""Form der Antwort. Das Modell muss sie einhalten, Pydantic prueft sie."""

from typing import Literal

from pydantic import BaseModel, Field


class SpitalAuskunft(BaseModel):     # BaseModel ist die Pydantic-Klasse, wie ein dataclass, aber mit Pruefung
    """Was genau ein Spital zur Frage regelt."""

    spital: Literal["USB", "KSBL"]   # Literal laesst nur diese zwei Werte zu, "Universitaetsspital" waere ein Fehler
    frage_beantwortet: bool                   # True heisst, die Belegstellen regeln die Frage fuer dieses Spital
    text: str                        # die Aussage in ganzen Saetzen, ohne Klammernummern im Text
    belegstellen: list[int]          # Nummern der verwendeten Belegstellen, leere Liste wenn frage_beantwortet False ist


class Auskunft(BaseModel):
    """Die ganze Antwort, ein Eintrag pro Spital."""

    spitaeler: list[SpitalAuskunft]  # zwei Eintraege, USB und KSBL
    hinweis: str | None = None       # verwandte Belegstelle, die die Frage nicht beantwortet, None wenn es keine gibt

class FrageAnfrage(BaseModel):
    """Was von aussen an die Schnittstelle hereinkommt."""

    frage: str = Field(min_length=5, max_length=500)   # Field erlaubt Grenzen, ohne Standardwert ist das Feld Pflicht
    spital: Literal["USB", "KSBL"] | None = None       # optional, None heisst beide Spitaeler durchsuchen

class Ergebnis(BaseModel):
    """Was die Schnittstelle zurueckgibt."""

    auskunft: Auskunft        # die Antwort selbst, so wie das Modell sie geliefert hat
    maengel: list[str]        # Ergebnis von pruefe(), leere Liste heisst sauber
    modell: str               # welches Sprachmodell geantwortet hat
    dauer_s: float            # Dauer des Modellaufrufs
    kosten_chf: float         # aus dem Gateway, bei lokalen Modellen null