"""Baut den Chroma-Index aus den GAV-PDFs.

Ablauf: laden, bereinigen, an Gliederungsziffern chunken, mit Ollama einbetten,
in Chroma ablegen. Wird direkt gestartet und einmal pro Korpusaenderung gebraucht.
"""

from contextlib import suppress
from dataclasses import dataclass

import chromadb
import ollama

from hr_policy_assistant.ingestion.loader import (
    PROJEKT_WURZEL,
    bereinige_seiten,
    entferne_wiederholte_zeilen,
    finde_wiederholte_zeilen,
    lade_pdf,
    schneide_in_abschnitte,
    setze_pfade,
)

# --------------------------------------------------------------------------
# Einstellungen
# --------------------------------------------------------------------------

# Muss beim Indexbau und beim Abfragen identisch sein. Zwei Modelle zeichnen zwei
# verschiedene Bedeutungskarten, deren Punkte nicht vergleichbar sind.
# Modellwechsel bedeutet Neuaufbau des gesamten Index.
EMBEDDING_MODELL = "bge-m3"

SAMMLUNG = "hr_policy"
CHROMA_PFAD = PROJEKT_WURZEL / "chroma"

# Ollama bekommt die Texte portionsweise statt alle 211 in einem Aufruf.
STAPEL = 32


# --------------------------------------------------------------------------
# Der Korpus
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Dokument:
    """Ein Korpusdokument mit allem, was an jedem seiner Chunks haengen soll.

     frozen, weil ein Korpuseintrag eine Feststellung ueber das Dokument ist
     und sich zur Laufzeit nicht aendern darf.
     """

    kuerzel: str
    datei: str
    titel: str
    stand: str
    status: str
    ueberspringen: frozenset[int]


# Ein neues Dokument heisst ein neuer Eintrag hier und keine Codeaenderung sonst.
# ueberspringen enthaelt Deckblatt und Inhaltsverzeichnis. Diese Seitenzahlen sind
# eine Eigenschaft des Dokuments und gehoeren deshalb hierher, nicht in den Loader.
# status: aktuell | veraltet | unbekannt. Beide Fassungen sind von 2015/2016,
# ob neuere existieren, ist ungeprueft. Das Feld haengt an jedem Chunk, damit das
# System spaeter bei veralteten Quellen warnen kann statt einfach zu zitieren.
KORPUS = [
    Dokument(
        kuerzel="USB",
        datei="gav_universitaetsspital_basel.pdf",
        titel="GAV Universitätsspital Basel / UPK / FPS",
        stand="2016-01-01",
        status="unbekannt",
        ueberspringen=frozenset({1, 2, 3}),
    ),
    Dokument(
        kuerzel="KSBL",
        datei="spitalbl_gav.pdf",
        titel="GAV Kantonsspital Baselland / Psychiatrie Baselland",
        stand="2015-07-01",
        status="unbekannt",
        ueberspringen=frozenset({1, 2, 3, 4, 5}),
    ),
]

# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------

def lese_abschnitte(dok: Dokument):
    """Volle Ingestion fuer ein Dokument, ohne die leeren Elternabschnitte."""
    pfad = PROJEKT_WURZEL / "data" / "raw" / dok.datei

    # Laden ohne Deckblatt und Verzeichnis, dann jede Seite einzeln normalisieren.
    seiten = bereinige_seiten(lade_pdf(pfad, set(dok.ueberspringen)))

    # Kopf- und Fusszeilen ueber ihre Wiederholung finden und entfernen.
    seiten = entferne_wiederholte_zeilen(seiten, finde_wiederholte_zeilen(seiten))

    # Erst schneiden, dann Pfade setzen. Die Pfade brauchen die fertigen Abschnitte.
    abschnitte = setze_pfade(schneide_in_abschnitte(seiten))

    # Leere Elternabschnitte raus, aber erst NACH den Pfaden. Sonst waeren ihre
    # Titel weg, bevor die Unterabschnitte sie erben.
    return [a for a in abschnitte if a.text]


def einbetten(texte: list[str]) -> list[list[float]]:
    """Vektoren fuer eine Liste von Texten, in Stapeln an Ollama."""
    vektoren = []
    for start in range(0, len(texte), STAPEL):
        teil = texte[start : start + STAPEL]

        # extend statt append, sonst entstuenden verschachtelte Stapel-Listen
        # statt einer flachen Liste mit einem Vektor pro Text.
        vektoren.extend(ollama.embed(model=EMBEDDING_MODELL, input=teil)["embeddings"])
        print(f"   {start + len(teil)} von {len(texte)} eingebettet")
    return vektoren

# --------------------------------------------------------------------------
# Indexaufbau
# --------------------------------------------------------------------------

def baue_index() -> None:
    """Legt die Sammlung neu an und fuellt sie mit beiden Dokumenten."""
    # Persistent, sonst laege der Index nur im Arbeitsspeicher und waere nach
    # Programmende weg.
    klient = chromadb.PersistentClient(path=str(CHROMA_PFAD))

    # add fuegt immer hinzu. Ohne Loeschen staende nach dem zweiten Lauf jeder
    # Chunk doppelt im Index. Beim allerersten Lauf gibt es nichts zu loeschen,
    # deshalb suppress.
    with suppress(Exception):
        klient.delete_collection(SAMMLUNG)

    # cosine vergleicht die Richtung der Vektoren und ignoriert ihre Laenge.
    # Damit spielt es keine Rolle, ob ein Chunk 200 oder 2000 Zeichen hat.
    sammlung = klient.create_collection(name=SAMMLUNG, metadata={"hnsw:space": "cosine"})


    for dok in KORPUS:
        abschnitte = lese_abschnitte(dok)
        print(f"{dok.kuerzel}: {len(abschnitte)} Abschnitte")

        # Die folgenden vier Listen muessen gleich lang sein und dieselbe
        # Reihenfolge haben. Chroma ordnet allein ueber die Position zu.
        # Verschiebt sich eine, haengen die Metadaten am falschen Chunk, ohne
        # dass irgendetwas abstuerzt.

        # Laufnummer muss rein, weil Gliederungsnummern im Dokument nicht
        # eindeutig sind. Das USB hat zweimal die Nummer 2.

        ids = [f"{dok.kuerzel}-{i:03d}-{a.nummer}" for i, a in enumerate(abschnitte)]

        # Was eingebettet wird. Der Pfad kommt dazu, weil das Thema oft nur in
        # der Ueberschrift steht. Ziff. 2.3.3 enthaelt das Wort
        # «Kuendigungsfrist» im Absatztext nicht.
        einbett_texte = [f"{a.pfad}\n{a.text}" for a in abschnitte]

        # Was gespeichert und spaeter zitiert wird. Ohne Pfad, damit ein Zitat
        # nur enthaelt, was woertlich im GAV steht.
        dokumente = [a.text for a in abschnitte]

        # Wird nicht eingebettet und ist deshalb nicht semantisch durchsuchbar.
        # Dient dem Zitat und dem exakten Filtern, etwa where={"dokument": "USB"}.
        metadaten = [
            {
                "dokument": dok.kuerzel,
                "titel_dokument": dok.titel,
                "nummer": a.nummer,
                "seite": a.seite,
                "titel": a.titel,
                "pfad": a.pfad,
                "stand": dok.stand,
                "status": dok.status,
            }
            for a in abschnitte
        ]

        vektoren = einbetten(einbett_texte)
        sammlung.add(
            ids=ids,
            embeddings=vektoren,
            documents=dokumente,
            metadatas=metadaten,
        )

    # Gegenprobe. Erwartet sind 211 bei den zwei aktuellen Dokumenten.
    print("Im Index", sammlung.count(), "Chunks")

# Laeuft nur beim direkten Start, nicht beim Importieren durch ein anderes Modul.
if __name__ == "__main__":
    baue_index()