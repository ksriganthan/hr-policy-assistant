"""Baut den Chroma-Index aus den GAV-PDFs.

Ablauf: laden, bereinigen, an Gliederungsziffern chunken, mit Ollama einbetten,
in Chroma ablegen. Wird direkt gestartet und einmal pro Korpusaenderung gebraucht.
"""

from dataclasses import dataclass
from typing import Literal

import chromadb
import ollama

from hr_policy_assistant.config import PROJEKT_WURZEL
from hr_policy_assistant.ingestion.loader import (
    Abschnitt,
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
# Drei Gruende: der Fortschritt wird sichtbar, ein Fehler ist auf einen Stapel
# eingegrenzt, und Ollama haelt weniger gleichzeitig im Speicher.
# Die 32 ist bewusst nicht optimiert. Der Lauf findet einmal pro Korpusaenderung
# statt, da lohnt sich die Messung nicht. 211 Chunks ergeben damit 7 Aufrufe.
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
    stand: str  # ISO, damit sich Staende als Text vergleichen und sortieren lassen
    status: Literal["aktuell", "veraltet", "unbekannt"]
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


def lese_abschnitte(dok: Dokument) -> list[Abschnitt]:
    """Volle Ingestion fuer ein Dokument, ohne die leeren Elternabschnitte."""
    pfad = PROJEKT_WURZEL / "data" / "raw" / dok.datei

    # Laden ohne Deckblatt und Verzeichnis, dann jede Seite einzeln normalisieren.
    seiten = bereinige_seiten(lade_pdf(pfad, dok.ueberspringen))

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

        # Vor dem Aufruf ausgeben, nicht danach. Der erste Stapel laedt das
        # Modell in den Speicher und braucht deshalb ein Vielfaches der Zeit
        # der folgenden. Stand die Meldung dahinter, sah der Lauf genau
        # waehrend dieser Wartezeit aus, als haenge er.
        # flush, weil Python die Ausgabe sonst puffert und erst spaeter zeigt.
        print(f"   Stapel {start + 1}-{start + len(teil)} von {len(texte)} ...", flush=True)

        # extend statt append, sonst entstuenden verschachtelte Stapel-Listen
        # statt einer flachen Liste mit einem Vektor pro Text.
        vektoren.extend(ollama.embed(model=EMBEDDING_MODELL, input=teil)["embeddings"])
    return vektoren


# --------------------------------------------------------------------------
# Indexaufbau
# --------------------------------------------------------------------------


def baue_index() -> None:
    """Legt die Sammlung neu an und fuellt sie mit beiden Dokumenten."""
    # Persistent, sonst laege der Index nur im Arbeitsspeicher und waere nach
    # Programmende weg.
    klient = chromadb.PersistentClient(path=str(CHROMA_PFAD))

    # Die Sammlung wird bei jedem Lauf neu angelegt statt ergaenzt. Der Grund
    # ist nicht in erster Linie doppeltes Einfuegen, denn die IDs sind
    # deterministisch und Chroma legt bei bekannter ID keine zweite Zeile an.
    # Der Grund sind Leichen: aendert sich ein Dokument, verschieben sich die
    # Laufnummern in den IDs, und weggefallene Abschnitte blieben mit altem
    # Text im Index stehen und tauchten weiter in Suchergebnissen auf.
    #
    # Gefragt wird, statt einen Fehler zu fangen. Ein try/except haette beim
    # ersten Lauf dasselbe getan, aber auch echte Fehler verschluckt, etwa
    # fehlende Schreibrechte oder eine beschaedigte Datenbank.
    if SAMMLUNG in {c.name for c in klient.list_collections()}:
        klient.delete_collection(SAMMLUNG)

    # cosine vergleicht die Richtung der Vektoren und ignoriert ihre Laenge.
    # Damit spielt es keine Rolle, ob ein Chunk 200 oder 2000 Zeichen hat.
    # Laesst sich nach dem Anlegen nicht mehr aendern, ein Wechsel bedeutet
    # Neuaufbau des Index.
    #
    # Dasselbe gilt fuers Embedding-Modell, das deshalb hier mitgeschrieben
    # wird. frage.py kann vergleichen, ob es mit demselben Modell fragt, mit
    # dem indexiert wurde, und abbrechen statt still Unsinn zu liefern. Ohne
    # diesen Eintrag waere die Regel im Kommentar bei EMBEDDING_MODELL nur eine
    # Notiz und im Code nirgends durchgesetzt.
    sammlung = klient.create_collection(
        name=SAMMLUNG,
        metadata={"hnsw:space": "cosine", "embedding_modell": EMBEDDING_MODELL},
    )

    for dok in KORPUS:
        abschnitte = lese_abschnitte(dok)
        print(f"{dok.kuerzel}: {len(abschnitte)} Abschnitte")

        # Ein Eintrag pro Abschnitt, in einer einzigen Schleife gebaut.
        # Chroma will vier getrennte Listen und ordnet sie allein ueber die
        # Position einander zu. Wuerden die vier hier einzeln erzeugt, koennte
        # sich eine gegen die anderen verschieben, und die Metadaten haengen am
        # falschen Chunk, ohne dass irgendetwas abstuerzt. Ueber diesen
        # Zwischenschritt kann das konstruktiv nicht mehr passieren.
        eintraege = [
            {
                # Die Laufnummer muss rein, weil Gliederungsnummern im Dokument
                # nicht eindeutig sind. Gemessen 01.09.: im USB kommen alle
                # sechs einstelligen Nummern doppelt vor, ohne Laufnummer gaebe
                # es zwoelf ID-Kollisionen allein in diesem Dokument.
                # :03d fuellt mit Nullen auf, damit IDs als Text richtig
                # sortieren, USB-002 vor USB-010. Traegt bis 999 Chunks.
                "id": f"{dok.kuerzel}-{i:03d}-{a.nummer}",
                # Was eingebettet wird. Der Pfad kommt dazu, weil das Thema oft
                # nur in einer uebergeordneten Ueberschrift steht. Beleg:
                # Ziff. 2.3.3 haengt unter «2.3 Beendigung des
                # Arbeitsverhaeltnisses», das Wort «Beendigung» kommt im
                # Absatztext selbst nicht vor.
                "einbett_text": f"{a.pfad}\n{a.text}",
                # Was gespeichert und spaeter zitiert wird. Ohne Pfad, damit ein
                # Zitat nur enthaelt, was woertlich im GAV steht.
                "dokument": a.text,
                # Wird nicht eingebettet und ist deshalb nicht semantisch
                # durchsuchbar. Dient dem Zitat und dem exakten Filtern, etwa
                # where={"dokument": "USB"}.
                "metadaten": {
                    "dokument": dok.kuerzel,
                    "titel_dokument": dok.titel,
                    "nummer": a.nummer,
                    "seite": a.seite,
                    "titel": a.titel,
                    "pfad": a.pfad,
                    "stand": dok.stand,
                    "status": dok.status,
                },
            }
            for i, a in enumerate(abschnitte)
        ]

        vektoren = einbetten([e["einbett_text"] for e in eintraege])

        # Erst hier wird in die vier Listen zerlegt, die Chroma erwartet.
        sammlung.add(
            ids=[e["id"] for e in eintraege],
            embeddings=vektoren,
            documents=[e["dokument"] for e in eintraege],
            metadatas=[e["metadaten"] for e in eintraege],
        )

    # Gegenprobe. Erwartet sind 211 bei den zwei aktuellen Dokumenten.
    print("Im Index", sammlung.count(), "Chunks")


# Laeuft nur beim direkten Start, nicht beim Importieren durch ein anderes Modul.
if __name__ == "__main__":
    baue_index()
