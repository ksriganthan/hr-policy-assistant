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


class Belegstelle(BaseModel):
    """Ein Treffer aus dem Vektorstore, so wie das Modell ihn im Prompt gesehen hat.

    Neu am 19.09.2026. Ohne diese Klasse gibt die Schnittstelle nur die Nummern heraus,
    und keine Oberflaeche kann die Quelle zeigen, auf der eine Aussage beruht.
    """

    nummer: int                      # dieselbe Zahl wie [1] im Prompt, Zaehlung beginnt bei 1
    dokument: str                    # USB oder KSBL
    ziffer: str                      # Gliederungsziffer im GAV, etwa 11.15
    titel: str                       # Titel des Abschnitts
    text: str                        # der Chunk-Text, also was das Modell wirklich gelesen hat
    seite: int | None = None         # optional, weil eine Metadate leer sein kann
    stand: str | None = None
    distanz: float | None = None     # Cosinus-Distanz, kleiner ist naeher. Nur zur Diagnose, kein Fachwert


class FrageAnfrage(BaseModel):
    """Was von aussen an die Schnittstelle hereinkommt."""

    frage: str = Field(min_length=5, max_length=500)   # Field erlaubt Grenzen, ohne Standardwert ist das Feld Pflicht
    spital: Literal["USB", "KSBL"] | None = None       # optional, None heisst beide Spitaeler durchsuchen


class Ergebnis(BaseModel):
    """Was die Schnittstelle zurueckgibt."""

    auskunft: Auskunft                 # die Antwort selbst, so wie das Modell sie geliefert hat
    belegstellen: list[Belegstelle]    # NEU: die Treffer, auf die sich die Nummern in auskunft beziehen
    maengel: list[str]                 # Ergebnis von pruefe(), leere Liste heisst sauber
    modell: str                        # welches Sprachmodell geantwortet hat
    dauer_s: float                     # Dauer des Modellaufrufs
    kosten_chf: float                  # aus dem Gateway, bei lokalen Modellen null


class Kritik(BaseModel):
    """Das Urteil des Kritik-Knotens über einen Entwurf."""

    gedeckt: bool                    # True heisst, jede Aussage steht so in den Belegstellen
    beanstandungen: list[str]        # die nicht gedeckten Saetze im Wortlaut, leere Liste wenn gedeckt True ist
    begruendung: str                 # ein Satz zur Begruendung, nur fuer das Protokoll, der Ablauf liest ihn nicht