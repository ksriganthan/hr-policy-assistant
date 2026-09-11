"""Frage rein, geprüfte Auskunft raus. Suche, Prompt, Modellaufruf, Validierung."""

import chromadb

from hr_policy_assistant.gateway.llm import embed, frage_modell
from hr_policy_assistant.ingestion.index import CHROMA_PFAD, SAMMLUNG
from hr_policy_assistant.modelle import Auskunft

SYSTEM = """Du bist die Auskunft eines Vergleichswerkzeugs fuer zwei Gesamtarbeitsvertraege
von Schweizer Spitaelern. USB steht fuer das Universitaetsspital Basel, KSBL fuer das
Kantonsspital Baselland. Beide GAV regeln dieselben Themen unterschiedlich. Wer fragt,
arbeitet im HR und muss wissen, was in seinem Haus gilt. Eine Auskunft, die offen laesst,
ob ein Haus etwas regelt, ist unbrauchbar.

Du antwortest als JSON in der vorgegebenen Form. Zu den Feldern:
- spitaeler: genau zwei Eintraege, einer fuer USB und einer fuer KSBL.
- frage_beantwortet: true, wenn die Belegstellen dieses Spitals die Frage beantworten, auch
  wenn die Antwort ein Ausschluss ist. Beispiel, die Frage lautet «Gilt der GAV fuer X» und
  eine Belegstelle nimmt X ausdruecklich aus, dann ist frage_beantwortet true und text nennt
  den Ausschluss. false nur, wenn die Belegstellen dieses Spitals zur Frage nichts sagen.
- text: die Antwort dieses Spitals in ganzen Saetzen. Bei frage_beantwortet false ein Satz,
  dass die Belegstellen fuer dieses Spital nichts zur Frage sagen. Keine Nummern in eckigen
  Klammern im Text, die Nummern gehoeren in belegstellen.
- belegstellen: die Nummern, auf denen der Text beruht. Bei frage_beantwortet false eine
  leere Liste.
- hinweis: eine verwandte Belegstelle mit Ziffer und Titel, die die Frage nicht beantwortet,
  sonst null.

Regeln:
- Verwende ausschliesslich die mitgelieferten Belegstellen. Kein eigenes Wissen.
- Pruefe zuerst am Titel jeder Belegstelle, ob sie die gefragte Sache selbst regelt.
  Ein benachbartes Thema ist keine Antwort.
- Eine Belegstelle gehoert zu dem Spital, das in ihrer Kopfzeile steht. Nimm fuer USB keine
  KSBL-Belegstelle und umgekehrt.
- Erfinde nichts.
- Schreibe auf Deutsch."""

TREFFER = 4

_sammlung = None                                 # Unterstrich heisst, das geht nur dieses Modul etwas an


def hole_sammlung():
    """Oeffnet die Chroma-Sammlung beim ersten Aufruf und merkt sie sich danach."""
    global _sammlung                             # ohne global entstuende hier eine neue lokale Variable
    if _sammlung is None:                        # beim zweiten Aufruf steht sie schon bereit
        _sammlung = chromadb.PersistentClient(path=str(CHROMA_PFAD)).get_collection(SAMMLUNG)
    return _sammlung


def suche(frage: str, spital: str | None = None):
    """Die naechsten Chunks zur Frage, auf Wunsch nur aus einem Dokument."""
    vektor = embed([frage])
    where = {"dokument": spital} if spital else None
    t = hole_sammlung().query(query_embeddings=vektor, n_results=TREFFER, where=where)
    return list(zip(t["documents"][0], t["metadatas"][0], t["distances"][0]))


def baue_prompt(frage: str, treffer) -> str:
    """Belegstellen nummeriert und mit Herkunft, danach die Frage."""
    teile = []
    for i, (text, m, _) in enumerate(treffer, start=1):
        kopf = (
            f"[{i}] {m['dokument']} Ziff. {m['nummer']} {m['titel']} "
            f"(S. {m['seite']}, Stand {m['stand']})"
        )
        teile.append(f"{kopf}\n{text}")
    return f"Belegstellen:\n\n{chr(10).join(teile)}\n\nFrage: {frage}"


def antworte(frage: str, spital: str | None = None):
    """Gibt die geprüfte Auskunft, die Modell-Metadaten und die verwendeten Treffer zurueck."""
    treffer = suche(frage, spital)
    a = frage_modell(
        system=SYSTEM,
        nutzer=baue_prompt(frage, treffer),
        schema=Auskunft.model_json_schema(),
    )
    auskunft = Auskunft.model_validate_json(a.text)
    return auskunft, a, treffer