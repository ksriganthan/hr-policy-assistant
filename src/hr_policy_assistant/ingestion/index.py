"""Baut den Chroma-Index aus den GAV-PDFs."""

from contextlib import suppress
from dataclasses import dataclass

import chromadb
import ollama

from hr_policy_assistant.ingestion.loader import (
    PROJEKT_WURZEL,
    bereinige_text,
    entferne_wiederholte_zeilen,
    finde_wiederholte_zeilen,
    lade_pdf,
    schneide_in_abschnitte,
    setze_pfade,
)

EMBEDDING_MODELL = "bge-m3"
SAMMLUNG = "hr_policy"
CHROMA_PFAD = PROJEKT_WURZEL / "chroma"
STAPEL = 32


@dataclass(frozen=True)
class Dokument:
    """Ein Korpusdokument mit allem, was an jedem Chunk haengen soll."""

    kuerzel: str
    datei: str
    titel: str
    stand: str
    status: str
    ueberspringen: frozenset[int]


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


def lese_abschnitte(dok: Dokument):
    """Volle Ingestion fuer ein Dokument, ohne die leeren Elternabschnitte."""
    pfad = PROJEKT_WURZEL / "data" / "raw" / dok.datei
    seiten = [bereinige_text(s) for s in lade_pdf(pfad, set(dok.ueberspringen))]
    seiten = entferne_wiederholte_zeilen(seiten, finde_wiederholte_zeilen(seiten))
    abschnitte = setze_pfade(schneide_in_abschnitte(seiten))
    return [a for a in abschnitte if a.text]


def einbetten(texte: list[str]) -> list[list[float]]:
    """Vektoren fuer eine Liste von Texten, in Stapeln an Ollama."""
    vektoren = []
    for start in range(0, len(texte), STAPEL):
        teil = texte[start : start + STAPEL]
        vektoren.extend(ollama.embed(model=EMBEDDING_MODELL, input=teil)["embeddings"])
        print(f"   {start + len(teil)} von {len(texte)} eingebettet")
    return vektoren


def baue_index() -> None:
    """Legt die Sammlung neu an und fuellt sie mit beiden Dokumenten."""
    klient = chromadb.PersistentClient(path=str(CHROMA_PFAD))

    with suppress(Exception):
        klient.delete_collection(SAMMLUNG)
    sammlung = klient.create_collection(name=SAMMLUNG, metadata={"hnsw:space": "cosine"})

    for dok in KORPUS:
        abschnitte = lese_abschnitte(dok)
        print(f"{dok.kuerzel}: {len(abschnitte)} Abschnitte")

        ids = [f"{dok.kuerzel}-{i:03d}-{a.nummer}" for i, a in enumerate(abschnitte)]
        einbett_texte = [f"{a.pfad}\n{a.text}" for a in abschnitte]
        dokumente = [a.text for a in abschnitte]
        metadaten = [
            {
                "dokument": dok.kuerzel,
                "titel_dokument": dok.titel,
                "nummer": a.nummer,
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

    print("Im Index", sammlung.count(), "Chunks")


if __name__ == "__main__":
    baue_index()