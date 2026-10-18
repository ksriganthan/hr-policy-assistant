"""Auskunft. Der fachliche Endpunkt."""

from fastapi import APIRouter

from hr_policy_assistant.auskunft import antworte
from hr_policy_assistant.modelle import Belegstelle, Ergebnis, FrageAnfrage
from hr_policy_assistant.pruefung import pruefe
from hr_policy_assistant.workflow.agent import antworte_mit_agent  # NEU
from hr_policy_assistant.workflow.graph import antworte_mit_kritik  # NEU

router = APIRouter(tags=["Auskunft"])


def zu_belegstellen(treffer) -> list[Belegstelle]:
    """Wandelt die Treffer in die Form um, die nach aussen geht.

    start=1 muss mit der Zaehlung in baue_prompt uebereinstimmen. Nur dann zeigt
    belegstellen=[1] in der Auskunft auf dieselbe Stelle wie [1] im Prompt.
    """
    return [
        Belegstelle(
            nummer=i,
            dokument=str(m["dokument"]),
            ziffer=str(m["nummer"]),
            titel=str(m["titel"]),
            text=text,
            seite=m.get("seite"),
            stand=m.get("stand"),
            distanz=distanz,
        )
        for i, (text, m, distanz) in enumerate(treffer, start=1)
    ]


def summiere(aufrufe: list) -> dict:
    """Fasst mehrere Gateway-Antworten zu einer Zeile zusammen.

    Der einstufige Weg hat einen Aufruf, der Graph zwei bis vier, der Agent drei bis acht.
    Nach aussen geht die Summe, damit die drei Wege vergleichbar sind.
    """
    return {
        "modell": aufrufe[0].modell if aufrufe else "unbekannt",   # alle Aufrufe eines Laufs nutzen dasselbe Modell
        "aufrufe": len(aufrufe),
        "dauer_s": round(sum(a.dauer_s for a in aufrufe), 2),      # runden, weil Gleitkomma sonst 4.300000000001 liefert
        "kosten_chf": round(sum(a.kosten_chf for a in aufrufe), 6),# sechs Stellen wie in berechne_kosten
        "tokens_ein": sum(a.tokens_prompt for a in aufrufe),       # die teure Seite, beim Agenten rund 14000 je Fall
        "tokens_aus": sum(a.tokens_antwort for a in aufrufe),
    }


@router.post("/frage")
def stelle_frage(anfrage: FrageAnfrage) -> Ergebnis:
    """Beantwortet eine Frage auf dem gewaehlten Weg und gibt Antwort, Maengel und Messwerte zurueck."""
    if anfrage.weg == "einstufig":
        auskunft, a, treffer = antworte(anfrage.frage, anfrage.spital)   # gibt ein Tupel zurueck, kein dict
        return Ergebnis(
            auskunft=auskunft,
            belegstellen=zu_belegstellen(treffer),
            maengel=pruefe(auskunft, treffer),
            weg="einstufig",
            runden=None,                                  # ein Aufruf, es gibt keine Runden
            verlauf=[],
            **summiere([a]),                              # ** packt die sechs Schluessel aus summiere als Argumente aus
        )

    # Graph und Agent geben beide dasselbe dict zurueck, der Agent zusaetzlich status und abbruchgrund.
    # Deshalb ab hier ein gemeinsamer Zweig und .get() fuer die beiden Felder, die nur der Agent kennt.
    z = (antworte_mit_kritik if anfrage.weg == "workflow" else antworte_mit_agent)(
        anfrage.frage, anfrage.spital
    )

    return Ergebnis(
        auskunft=z["auskunft"],                           # kann beim Agenten None sein, darum ist das Feld optional
        belegstellen=zu_belegstellen(z["treffer"]),
        maengel=z["maengel"],                             # beide Wege rufen pruefe() selbst, nicht nochmals hier
        weg=anfrage.weg,
        runden=z["runde"],
        verlauf=z["verlauf"],
        status=z.get("status", "ok"),                     # der Graph hat kein status-Feld, er bricht nie ab
        abbruchgrund=z.get("abbruchgrund"),
        **summiere(z["aufrufe"]),
    )