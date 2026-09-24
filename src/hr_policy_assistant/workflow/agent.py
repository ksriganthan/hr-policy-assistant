"""Der Ablauf als Agent-Loop. Gleiches Ziel wie der Graph, nur bestimmt das Modell die Reihenfolge.

Im Graphen steht die Reihenfolge fest: suchen, entwerfen, kritisieren, pruefen.
Hier bekommt das Modell dieselben vier Schritte als Werkzeuge und waehlt in jeder
Runde selbst, welchen es ausfuehren laesst. Alles andere ist absichtlich gleich,
damit der Vergleich nur die Steuerung misst und nicht zwei verschiedene Systeme.
"""

from dataclasses import dataclass, field

from hr_policy_assistant.auskunft import (
    SYSTEM,
    baue_prompt,
    erzwinge_leere_belegstellen,
    suche,
)
from hr_policy_assistant.gateway.llm import frage_modell, frage_modell_verlauf
from hr_policy_assistant.modelle import Auskunft, Kritik
from hr_policy_assistant.pruefung import pruefe
from hr_policy_assistant.workflow.graph import KRITIK_SYSTEM

MAX_RUNDEN = 8          # Notbremse. Der Graph braucht 3 bis 5 Aufrufe, acht laesst Luft und deckelt die Kosten.

AGENT_SYSTEM = """Du beantwortest Fragen zu den Gesamtarbeitsvertraegen zweier Schweizer Spitaeler.
USB steht fuer das Universitaetsspital Basel, KSBL fuer das Kantonsspital Baselland.

Du arbeitest nicht selbst am Text. Du waehlst in jeder Runde genau ein Werkzeug.

Ein sinnvoller Ablauf ist:
1. suche_dokumente, um Belegstellen zu holen.
2. entwurf_schreiben, um aus den Belegstellen eine Auskunft zu erzeugen.
3. pruefe_auskunft, um den Entwurf gegen die Belegstellen pruefen zu lassen.
4. Bei Beanstandungen noch einmal entwurf_schreiben, sonst antwort_abgeben.

Du darfst davon abweichen. Suche noch einmal mit anderen Worten, wenn die Belegstellen
die Frage nicht abdecken. Gib nicht ab, bevor ein Entwurf existiert.

Rufe genau ein Werkzeug pro Runde auf und schreibe keinen freien Text."""


# ── Die Werkzeugliste, die das Modell zu sehen bekommt ───────────────
# Das ist reines JSON-Schema. Ollama haengt es an den Prompt, das Modell
# antwortet daraufhin mit einem tool_call statt mit Text.

WERKZEUGE = [
    {
        "type": "function",
        "function": {
            "name": "suche_dokumente",
            "description": (
                "Sucht Belegstellen in den beiden GAV und legt sie bereit. "
                "Ersetzt bei jedem Aufruf die bisherigen Belegstellen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "suchbegriff": {
                        "type": "string",
                        "description": "Wonach gesucht wird, in eigenen Worten.",
                    }
                },
                "required": ["suchbegriff"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "entwurf_schreiben",
            "description": (
                "Schreibt aus den bereitliegenden Belegstellen eine Auskunft fuer beide "
                "Spitaeler. Liegen Beanstandungen vor, werden sie beruecksichtigt."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pruefe_auskunft",
            "description": (
                "Laesst den aktuellen Entwurf gegen die Belegstellen pruefen und meldet, "
                "welche Aussagen nicht gedeckt sind."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "antwort_abgeben",
            "description": "Beendet die Arbeit. Der aktuelle Entwurf gilt als Antwort.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ── Der Zustand, den das Modell NIE sieht ────────────────────────────


@dataclass
class Lauf:
    """Buchhaltung ausserhalb des Gespraechs.

    Das Gespraech selbst ist die Erinnerung des Modells. Was hier steht, ist fuer
    mich: die Objekte, mit denen weitergearbeitet wird, und die Zaehler fuer die
    Notbremse und die Messung. Schriebe ich dem Modell "du bist in Runde 6 von 8",
    wuerde es sein Verhalten aendern, deshalb bleibt das draussen.
    """

    frage: str
    spital: str | None
    treffer: list = field(default_factory=list)
    auskunft: Auskunft | None = None
    kritik: Kritik | None = None
    beanstandungen: list[str] = field(default_factory=list)
    runde: int = 0
    verlauf: list[str] = field(default_factory=list)
    aufrufe: list = field(default_factory=list)


# ── Was die Werkzeuge tun ────────────────────────────────────────────
# Jede Funktion gibt einen kurzen Text zurueck. Genau dieser Text geht als
# Werkzeugergebnis zurueck ins Gespraech, mehr sieht das Modell nicht.


def _suche_dokumente(lauf: Lauf, suchbegriff: str) -> str:
    lauf.treffer = suche(suchbegriff, lauf.spital)        # spital ist vorgegeben, das Modell waehlt es nicht
    lauf.verlauf.append(f"Runde {lauf.runde} suche: {suchbegriff}")

    zeilen = [
        f"[{i}] {m['dokument']} Ziff. {m['nummer']} {m['titel']}"
        for i, (_, m, _) in enumerate(lauf.treffer, start=1)
    ]
    return f"{len(lauf.treffer)} Belegstellen bereit:\n" + "\n".join(zeilen)


def _entwurf_schreiben(lauf: Lauf) -> str:
    """Wortgleich mit dem Knoten entwerfen im Graphen. Nur der Aufrufzeitpunkt ist frei."""
    if not lauf.treffer:                                  # das Modell hat die Reihenfolge verdreht
        return "Fehler: es liegen keine Belegstellen bereit. Rufe zuerst suche_dokumente auf."

    nutzer = baue_prompt(lauf.frage, lauf.treffer)

    if lauf.beanstandungen:                               # zweiter Entwurf, derselbe Zusatztext wie im Graphen
        nutzer += (
            "\n\nDein erster Entwurf enthielt Aussagen, die so nicht in den Belegstellen stehen:\n"
            + "\n".join(f"- {b}" for b in lauf.beanstandungen)
            + "\n\nSchreibe die Auskunft neu. Entferne nur den nicht belegten Teil und behalte alles "
              "Uebrige unveraendert, insbesondere Angaben, die woertlich aus den Belegstellen stammen. "
              "Erfinde nichts dazu."
        )

    a = frage_modell(system=SYSTEM, nutzer=nutzer, schema=Auskunft.model_json_schema())
    lauf.auskunft = Auskunft.model_validate_json(a.text)
    erzwinge_leere_belegstellen(lauf.auskunft)
    lauf.aufrufe.append(a)                                # zaehlt bei Tokens und Kosten mit
    lauf.beanstandungen = []                              # der Entwurf ist neu, alte Beanstandungen gelten nicht mehr
    lauf.verlauf.append(f"Runde {lauf.runde} Entwurf USB: {lauf.auskunft.spitaeler[0].text}")

    teile = [f"{s.spital}: {s.text}" for s in lauf.auskunft.spitaeler]
    return "Entwurf steht:\n" + "\n".join(teile)


def _pruefe_auskunft(lauf: Lauf) -> str:
    """Wortgleich mit dem Knoten kritisieren im Graphen, ein Aufruf pro Haus."""
    if lauf.auskunft is None:
        return "Fehler: es gibt keinen Entwurf. Rufe zuerst entwurf_schreiben auf."

    kritiken = []
    for s in lauf.auskunft.spitaeler:
        entwurf = f"{s.spital}: {s.text} (genannte Belegstellen: {s.belegstellen})"
        nutzer = baue_prompt(lauf.frage, lauf.treffer) + f"\n\nZu pruefende Auskunft:\n{entwurf}"

        a = frage_modell(system=KRITIK_SYSTEM, nutzer=nutzer, schema=Kritik.model_json_schema())
        kritiken.append(Kritik.model_validate_json(a.text))
        lauf.aufrufe.append(a)
        lauf.verlauf.append(
            f"Runde {lauf.runde} Kritik {s.spital}: gedeckt={kritiken[-1].gedeckt}"
        )

    lauf.kritik = Kritik(
        gedeckt=all(k.gedeckt for k in kritiken),
        beanstandungen=[b for k in kritiken for b in k.beanstandungen],
        begruendung=" | ".join(k.begruendung for k in kritiken),
    )
    lauf.beanstandungen = lauf.kritik.beanstandungen

    if lauf.kritik.gedeckt:
        return "Pruefung bestanden, alle Aussagen sind gedeckt."
    return "Nicht gedeckt:\n" + "\n".join(f"- {b}" for b in lauf.beanstandungen)


# ── Die Schleife ─────────────────────────────────────────────────────

AUSFUEHRUNG = {                        # Name aus dem tool_call auf die Funktion hier oben
    "suche_dokumente": lambda lauf, arg: _suche_dokumente(lauf, arg.get("suchbegriff", "")),
    "entwurf_schreiben": lambda lauf, arg: _entwurf_schreiben(lauf),
    "pruefe_auskunft": lambda lauf, arg: _pruefe_auskunft(lauf),
}


def antworte_mit_agent(frage: str, spital: str | None = None) -> dict:
    """Wie antworte_mit_kritik(), aber das Modell bestimmt die Reihenfolge der Schritte.

    Gibt dieselben Felder zurueck wie der Graph, damit der Eval-Runner beide Wege
    gleich auswerten kann. Zusaetzlich status und abbruchgrund.
    """
    lauf = Lauf(frage=frage, spital=spital)

    gespraech = [                                          # DAS ist der Zustand, den das Modell sieht
        {"role": "system", "content": AGENT_SYSTEM},
        {"role": "user", "content": f"Frage: {frage}"},
    ]

    status, grund = "ok", ""

    while True:
        if lauf.runde >= MAX_RUNDEN:                       # Notbremse zuerst, vor dem naechsten teuren Aufruf
            status, grund = "abgebrochen", f"MAX_RUNDEN {MAX_RUNDEN} erreicht"
            break

        a = frage_modell_verlauf(gespraech, WERKZEUGE, frage=frage)
        lauf.runde += 1
        lauf.aufrufe.append(a)                             # auch der Steuerungsaufruf kostet Tokens

        if not a.werkzeugrufe:                             # Modell hat freien Text geschrieben statt zu waehlen
            gespraech.append({"role": "assistant", "content": a.text})
            gespraech.append({"role": "user",
                              "content": "Rufe ein Werkzeug auf, schreibe keinen freien Text."})
            lauf.verlauf.append(f"Runde {lauf.runde}: kein Werkzeug gewaehlt")
            continue

        ruf = a.werkzeugrufe[0]                            # ein Werkzeug pro Runde, weitere werden ignoriert
        gespraech.append({"role": "assistant", "content": "",
                          "tool_calls": [{"function": {"name": ruf["name"],
                                                       "arguments": ruf["argumente"]}}]})

        if ruf["name"] == "antwort_abgeben":               # das Signal zum Aufhoeren
            if lauf.auskunft is None:                      # abgeben ohne Entwurf, das waere leer
                gespraech.append({"role": "tool", "content":
                                  "Fehler: es gibt keinen Entwurf. Rufe zuerst entwurf_schreiben auf."})
                lauf.verlauf.append(f"Runde {lauf.runde}: abgeben ohne Entwurf abgelehnt")
                continue
            lauf.verlauf.append(f"Runde {lauf.runde}: antwort_abgeben")
            break

        fkt = AUSFUEHRUNG.get(ruf["name"])
        ergebnis = (fkt(lauf, ruf["argumente"]) if fkt
                    else f"Fehler: Werkzeug {ruf['name']} gibt es nicht.")
        gespraech.append({"role": "tool", "content": ergebnis})   # Ergebnis zurueck ins Gespraech

    return {
        "frage": frage,
        "spital": spital,
        "treffer": lauf.treffer,
        "auskunft": lauf.auskunft,
        "kritik": lauf.kritik,
        "beanstandungen": lauf.beanstandungen,
        "runde": lauf.runde,
        "maengel": pruefe(lauf.auskunft, lauf.treffer) if lauf.auskunft else [],
        "verlauf": lauf.verlauf,
        "aufrufe": lauf.aufrufe,
        "status": status,                                  # "ok" oder "abgebrochen"
        "abbruchgrund": grund,
    }
