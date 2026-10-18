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
    weg: Literal["einstufig", "workflow", "agent"] = "einstufig"  # NEU. Standard bleibt der schnelle Weg,
    # damit bestehende Aufrufe sich nicht aendern


class Ergebnis(BaseModel):
    """Was die Schnittstelle zurueckgibt."""

    auskunft: Auskunft | None = None   # None, wenn der Agent abbricht, bevor ein Entwurf steht
    belegstellen: list[Belegstelle]    # die Treffer, auf die sich die Nummern in auskunft beziehen
    maengel: list[str]                 # Ergebnis von pruefe(), leere Liste heisst sauber
    modell: str                        # welches Sprachmodell geantwortet hat
    weg: str                           # welcher der drei Wege gelaufen ist
    aufrufe: int                       # wie viele Modellaufrufe, 1 beim einstufigen Weg
    dauer_s: float                     # Summe ueber alle Aufrufe
    kosten_chf: float                  # Summe, bei lokalen Modellen null
    tokens_ein: int                    # Summe tokens_prompt, das ist die teure Seite
    tokens_aus: int                    # Summe tokens_antwort
    runden: int | None = None          # Graph 1 oder 2, Agent 1 bis 8, einstufig None
    verlauf: list[str] = []            # was in jeder Runde passiert ist, fuer die UI sichtbar
    status: str = "ok"                 # "ok" oder "abgebrochen", nur der Agent kann abbrechen
    abbruchgrund: str | None = None


class Kritik(BaseModel):
    """Das Urteil des Kritik-Knotens über einen Entwurf."""

    gedeckt: bool                    # True heisst, jede Aussage steht so in den Belegstellen
    beanstandungen: list[str]        # die nicht gedeckten Saetze im Wortlaut, leere Liste wenn gedeckt True ist
    begruendung: str                 # ein Satz zur Begruendung, nur fuer das Protokoll, der Ablauf liest ihn nicht