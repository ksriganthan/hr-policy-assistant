"""Auskunft. Der fachliche Endpunkt."""

from fastapi import APIRouter

from hr_policy_assistant.auskunft import antworte
from hr_policy_assistant.modelle import Belegstelle, Ergebnis, FrageAnfrage
from hr_policy_assistant.pruefung import pruefe

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
            ziffer=str(m["nummer"]),          # heisst in den Metadaten nummer, hier ziffer, um die Verwechslung
            titel=str(m["titel"]),            # mit der Belegstellen-Nummer zu vermeiden
            text=text,
            seite=m.get("seite"),
            stand=m.get("stand"),
            distanz=distanz,
        )
        for i, (text, m, distanz) in enumerate(treffer, start=1)
    ]


@router.post("/frage")                           # POST, weil die Frage im Rumpf mitkommt und nicht in der URL steht
def stelle_frage(anfrage: FrageAnfrage) -> Ergebnis:
    """Beantwortet eine Frage und gibt die Antwort zusammen mit den gefundenen Maengeln zurueck."""
    auskunft, a, treffer = antworte(anfrage.frage, anfrage.spital)   # a ist die Gateway-Huelle mit Modell, Dauer, Kosten
    return Ergebnis(
        auskunft=auskunft,
        belegstellen=zu_belegstellen(treffer),   # NEU: dieselben Treffer, die ins Prompt gingen
        maengel=pruefe(auskunft, treffer),
        modell=a.modell,
        dauer_s=a.dauer_s,
        kosten_chf=a.kosten_chf,
    )