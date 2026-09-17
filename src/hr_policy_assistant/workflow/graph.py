"""Der Ablauf als Graph. Suchen, entwerfen, kritisieren, bei Bedarf ein zweites Mal entwerfen."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from hr_policy_assistant.auskunft import (
    SYSTEM,
    baue_prompt,
    erzwinge_leere_belegstellen,
    suche,
)
from hr_policy_assistant.gateway.llm import frage_modell
from hr_policy_assistant.modelle import Auskunft, Kritik
from hr_policy_assistant.pruefung import pruefe

MAX_RUNDEN = 2                       # zwei Entwuerfe, also ein Ruecksprung. 16.09. von 3 zurueckgesetzt, der Vergleich war
                                     # nicht auswertbar: das Modell antwortet auch bei temperature 0 nicht in jedem Lauf gleich.

KRITIK_SYSTEM = """Du vergleichst eine fertige Auskunft mit den Belegstellen, auf denen sie beruhen soll.

Deine Frage lautet nicht «ist alles vollstaendig abgedeckt», sondern: Welche einzelne Aussage der
Auskunft geht ueber das hinaus, was in den Belegstellen steht?

So gehst du vor:
1. Lies die Auskunft Aussage fuer Aussage.
2. Suche fuer jede Aussage die Stelle im Belegstellentext, aus der sie stammt.
3. Findest du keine, beanstandest du genau diese Aussage. Alle anderen bleiben unberuehrt.

Gedeckt ist:
- Eine Aufzaehlung, die die Belegstelle enthaelt, auch wenn die Auskunft sie verkuerzt wiedergibt.
- Eine Umformulierung mit anderen Worten, solange die Sache dieselbe bleibt.
- Die Feststellung, dass die Belegstellen zu etwas nichts sagen, wenn sie wirklich nichts dazu sagen.
  Eine solche Feststellung ist keine Behauptung und wird nie beanstandet.

Nicht gedeckt ist:
- Ein Begriff oder eine Personengruppe, die in keiner Belegstelle vorkommt, in der Auskunft aber
  einer Kategorie zugeordnet wird.
- Eine Zahl, eine Frist oder ein Betrag, der so in keiner Belegstelle steht.
- Eine Aussage ueber ein Haus, die sich auf eine Belegstelle des anderen Hauses stuetzt.

Beispiel A
Belegstelle [1] USB Ziff. 4.2 Weiterbildung: «Das Spital beteiligt sich an den Kosten
berufsbezogener Weiterbildungen.»
Auskunft: «Das Spital beteiligt sich an den Kosten berufsbezogener Weiterbildungen, bis zu
5'000 Franken pro Jahr.»
gedeckt: false
beanstandungen: ["bis zu 5'000 Franken pro Jahr"]
begruendung: "Der Betrag steht in keiner Belegstelle, der Rest des Satzes ist gedeckt."

Beispiel B
Dieselbe Belegstelle.
Auskunft: «Das Spital beteiligt sich an den Kosten. Zur Hoehe des Beitrags sagen die Belegstellen nichts.»
gedeckt: true
beanstandungen: []
begruendung: "Beide Aussagen sind gedeckt, die zweite ist eine Feststellung ueber eine Luecke."

Beachte an Beispiel A, dass nur der zusaetzliche Teil beanstandet wird und nicht der ganze Satz.

Antworte als JSON in der vorgegebenen Form. Bei gedeckt true ist beanstandungen eine leere Liste."""


class Zustand(TypedDict):
    """Was zwischen den Knoten weitergereicht wird. Ein Eintrag pro Sache, die ein Knoten braucht."""

    frage: str                       # kommt von aussen herein und aendert sich nie
    spital: str | None               # optionaler Filter, None heisst beide Haeuser
    treffer: list                    # setzt suchen, lesen tun entwerfen und kritisieren
    auskunft: Auskunft | None        # setzt entwerfen, None bevor der erste Entwurf existiert
    kritik: Kritik | None            # setzt kritisieren, None in der ersten Runde vor der Kritik
    beanstandungen: list[str]        # was der Kritiker bemaengelt hat, geht in den zweiten Entwurf
    runde: int                       # zaehlt die Entwuerfe, startet bei 0
    maengel: list[str]               # Ergebnis von pruefe(), setzt der letzte Knoten
    verlauf: list[str]               # was in jeder Runde passiert ist, nur zum Mitlesen
    aufrufe: list  # je Modellaufruf eine Antwort aus dem Gateway, fuer Tokens und Kosten


def suchen(z: Zustand) -> dict:
    """Holt die Belegstellen. Laeuft genau einmal, der Ruecksprung geht nicht hierher zurueck."""
    return {"treffer": suche(z["frage"], z["spital"])}        # nur das eine Feld, alles andere bleibt


def entwerfen(z: Zustand) -> dict:
    """Schreibt die Auskunft. In der zweiten Runde mit den Beanstandungen als Zusatzauftrag."""
    nutzer = baue_prompt(z["frage"], z["treffer"])            # derselbe Prompt wie im Weg ohne Graph

    if z["beanstandungen"]:
        nutzer += (
                "\n\nDein erster Entwurf enthielt Aussagen, die so nicht in den Belegstellen stehen:\n"
                + "\n".join(f"- {b}" for b in z["beanstandungen"])
                + "\n\nSchreibe die Auskunft neu. Entferne nur den nicht belegten Teil und behalte alles "
                  "Uebrige unveraendert, insbesondere Angaben, die woertlich aus den Belegstellen stammen. "
                  "Pruefe je Haus einzeln, ob die gefragte Gruppe in dessen Belegstellen vorkommt. "
                  "Kommt sie dort nicht vor, nenne was die Belegstelle regelt und sage dazu, dass die "
                  "Gruppe nicht genannt wird. Kommt sie dort vor, gehoert dieser Zusatz nicht hin. "
                  "Erfinde nichts dazu."
        )

    a = frage_modell(system=SYSTEM, nutzer=nutzer, schema=Auskunft.model_json_schema())
    auskunft = Auskunft.model_validate_json(a.text)
    erzwinge_leere_belegstellen(auskunft)                     # dieselbe Regel wie im Weg ohne Graph

    return {
        "auskunft": auskunft,
        "runde": z["runde"] + 1,
        "aufrufe": z["aufrufe"] + [a],  # ← hier, a ist der Entwurfs-Aufruf
        "verlauf": z["verlauf"] + [
            f"Runde {z['runde'] + 1} Entwurf USB: {auskunft.spitaeler[0].text}"
        ],
    }


def kritisieren(z: Zustand) -> dict:
    """Ein Kritik-Aufruf pro Haus. Kein Aufruf sieht den Text des anderen Hauses.

    Geaendert am 18.09.2026. Vorher ein einziger Aufruf mit dem zusammengefuegten Entwurf
    beider Haeuser. Die Ablation vom 17.09. hat gezeigt, dass der Kritiker dann eine
    USB-Aussage gegen die Belegstellen beider Haeuser prueft, eine widersprechende Zahl
    findet und den Widerspruch als fehlende Deckung liest. Ein Haus je Aufruf senkt die
    Fehlalarme in der Messung von 3 bis 4 von 4 auf 1 von 4.
    """
    kritiken, aufrufe, zeilen = [], [], []                    # sammeln statt einmal zuweisen

    for s in z["auskunft"].spitaeler:                         # NEU: Schleife, vorher ein Aufruf fuer beide
        entwurf = f"{s.spital}: {s.text} (genannte Belegstellen: {s.belegstellen})"
        nutzer = baue_prompt(z["frage"], z["treffer"]) + f"\n\nZu pruefende Auskunft:\n{entwurf}"

        a = frage_modell(system=KRITIK_SYSTEM, nutzer=nutzer, schema=Kritik.model_json_schema())
        k = Kritik.model_validate_json(a.text)

        kritiken.append(k)                                    # ein Urteil je Haus
        aufrufe.append(a)                                     # ein Aufruf je Haus, zaehlt bei Tokens und Kosten
        zeilen.append(
            f"Runde {z['runde']} Kritik {s.spital}: "         # Hausname NEU im Verlauf, sonst nicht zuordenbar
            f"gedeckt={k.gedeckt}, beanstandet={k.beanstandungen}"
        )

    gesamt = Kritik(                                          # NEU: die Urteile zu einem zusammenfassen
        gedeckt=all(k.gedeckt for k in kritiken),             # nur gedeckt, wenn JEDES Haus gedeckt ist
        beanstandungen=[b for k in kritiken for b in k.beanstandungen],   # alle in eine flache Liste
        begruendung=" | ".join(k.begruendung for k in kritiken),
    )

    return {
        "kritik": gesamt,                                     # wie_weiter liest weiterhin kritik.gedeckt
        "beanstandungen": gesamt.beanstandungen,              # entwerfen liest weiterhin diese Liste
        "aufrufe": z["aufrufe"] + aufrufe,                    # jetzt zwei statt einer pro Runde
        "verlauf": z["verlauf"] + zeilen,                     # jetzt zwei Zeilen statt einer
    }



def pruefen(z: Zustand) -> dict:
    """Die vier deterministischen Regeln, unveraendert. Sie laufen zuletzt und immer."""
    return {"maengel": pruefe(z["auskunft"], z["treffer"])}


def wie_weiter(z: Zustand) -> str:
    """Entscheidet nach der Kritik, ob ein zweiter Entwurf kommt oder geprueft wird."""
    if z["kritik"].gedeckt:          # der Kritiker hat nichts beanstandet, fertig
        return "pruefen"
    if z["runde"] >= MAX_RUNDEN:     # Beanstandungen offen, aber das Budget ist aufgebraucht
        return "pruefen"
    return "entwerfen"               # Beanstandungen offen und noch eine Runde frei


def baue_graph():
    """Steckt Knoten und Kanten zusammen. compile() macht daraus einen lauffaehigen Ablauf."""
    g = StateGraph(Zustand)                                   # der Zustand sagt LangGraph, was durchgereicht wird

    g.add_node("suchen", suchen)                              # Name im Graphen, dann die Funktion
    g.add_node("entwerfen", entwerfen)
    g.add_node("kritisieren", kritisieren)
    g.add_node("pruefen", pruefen)

    g.set_entry_point("suchen")                               # hier faengt jeder Lauf an
    g.add_edge("suchen", "entwerfen")                         # feste Kante, immer derselbe Weg
    g.add_edge("entwerfen", "kritisieren")
    g.add_conditional_edges(                                  # bedingte Kante, wie_weiter nennt das Ziel
        "kritisieren",
        wie_weiter,
        {"entwerfen": "entwerfen", "pruefen": "pruefen"},      # Rueckgabewert links, Knotenname rechts
                # g.add_conditional_edges("kritisieren", wie_weiter)
    )
    g.add_edge("pruefen", END)                                # END ist LangGraphs Schlusspunkt

    return g.compile()


GRAPH = baue_graph()                                          # einmal beim Import gebaut, danach wiederverwendet


def antworte_mit_kritik(frage: str, spital: str | None = None) -> dict:
    """Wie antworte(), aber ueber den Graphen mit Kritik-Rolle. Gibt den ganzen Endzustand zurueck."""
    start: Zustand = {                       # Annotation, damit die IDE das dict als Zustand liest
        "frage": frage,
        "spital": spital,
        "treffer": [],
        "auskunft": None,
        "kritik": None,
        "beanstandungen": [],
        "runde": 0,
        "maengel": [],
        "verlauf": [],
        "aufrufe": [],
    }
    return GRAPH.invoke(start)