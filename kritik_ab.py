"""A/B-Test am Kritiker-Prompt. Legt vier Fehlalarm-Saetze einzeln vor, mit zwei Prompt-Fassungen.

Aendert nichts im System. Importiert nur und ruft das Modell auf.
Start aus der Projektwurzel:  uv run python kritik_ab.py
"""

from hr_policy_assistant.auskunft import baue_prompt, suche      # dieselbe Suche wie im Graphen
from hr_policy_assistant.gateway.llm import frage_modell         # derselbe Weg zum Modell
from hr_policy_assistant.modelle import Kritik
from hr_policy_assistant.workflow.graph import KRITIK_SYSTEM     # Fassung A, unveraendert

# ── Die vier Saetze, alle am 17.09.2026 als Fehlalarm belegt ──────────────

FAELLE = [
    (7,  "USB",  "Wie lange ist die Kuendigungsfrist nach der Probezeit?",
     "Nach Ablauf der Probezeit betragen die Fristen fuer die Kuendigung des "
     "Arbeitsverhaeltnisses fuer beide Vertragsparteien im ersten Anstellungsjahr 1 Monat "
     "und ab zweitem Anstellungsjahr 3 Monate."),
    (11, "KSBL", "Wie hoch ist die Abfindung bei einer Kuendigung?",
     "Die Abgangsentschaedigung betraegt maximal zwoelf Monatsloehne."),
    (18, "USB",  "Wie viele freie Tage bekomme ich bei meiner Heirat?",
     "Bei der Heirat oder Eintragung der Partnerschaft der Mitarbeiterin bzw. des "
     "Mitarbeiters werden 2 Arbeitstage bezahlten Urlaub gewaehrt."),
    (1,  "USB",  "Gilt der GAV fuer Chefaerzte?",
     "Chefaerzte werden in den genannten Ausnahmen nicht explizit genannt."),
]

# ── Fassung B entsteht aus A durch zwei gezielte Ersetzungen ──────────────
# Nur diese beiden Stellen unterscheiden sich, alles andere ist byteweise identisch.

ALT_REGEL = "- Eine Zahl, eine Frist oder ein Betrag, der so in keiner Belegstelle steht."
NEU_REGEL = (
    "- Eine Zahl, eine Frist oder ein Betrag, den du im Belegstellentext nicht wiederfindest.\n"
    "  Suche die Zahl zuerst im Belegstellentext. Findest du sie dort, ist sie gedeckt, auch\n"
    "  wenn sie als Wort statt als Ziffer geschrieben ist. Beanstande eine Zahl nie, weil sie\n"
    "  eine Zahl ist, sondern nur, wenn du sie im Text nicht findest."
)

ALT_BEISPIEL = """Beispiel A
Belegstelle [1] USB Ziff. 4.2 Weiterbildung: «Das Spital beteiligt sich an den Kosten
berufsbezogener Weiterbildungen.»
Auskunft: «Das Spital beteiligt sich an den Kosten berufsbezogener Weiterbildungen, bis zu
5'000 Franken pro Jahr.»
gedeckt: false
beanstandungen: ["bis zu 5'000 Franken pro Jahr"]
begruendung: "Der Betrag steht in keiner Belegstelle, der Rest des Satzes ist gedeckt." """

NEU_BEISPIEL = """Beispiel A
Belegstelle [1] USB Ziff. 1.3 Geltungsbereich: «Ausgenommen sind Fuehrungs- und Fachkader
gemaess spitalspezifischer Regelung des Verwaltungsrats.»
Auskunft: «Ausgenommen sind Fuehrungs- und Fachkader, wozu auch die Chefaerzte zaehlen.»
gedeckt: false
beanstandungen: ["wozu auch die Chefaerzte zaehlen"]
begruendung: "Chefaerzte kommen in keiner Belegstelle vor und werden hier einer Kategorie zugeordnet." """


def baue_fassung_b(a: str) -> str:
    """Ersetzt Regel und Beispiel. Bricht ab, wenn eine Stelle nicht passt."""
    if ALT_REGEL not in a:
        raise SystemExit("ALT_REGEL nicht im Prompt gefunden, Skript anpassen")
    if ALT_BEISPIEL.strip() not in a:
        raise SystemExit("ALT_BEISPIEL nicht im Prompt gefunden, Skript anpassen")
    b = a.replace(ALT_REGEL, NEU_REGEL, 1)
    return b.replace(ALT_BEISPIEL.strip(), NEU_BEISPIEL.strip(), 1)


FASSUNG_B = baue_fassung_b(KRITIK_SYSTEM)


def pruefe(system: str, frage: str, spital: str, satz: str) -> Kritik:
    """Ein Kritik-Aufruf, genau wie im Knoten kritisieren, nur mit einem Satz."""
    treffer = suche(frage, None)                                  # keine LLM-Kosten, nur Chroma
    entwurf = f"{spital}: {satz}"                                 # bewusst ohne Belegstellen-Liste
    nutzer = baue_prompt(frage, treffer) + f"\n\nZu pruefende Auskunft:\n{entwurf}"
    a = frage_modell(system=system, nutzer=nutzer, schema=Kritik.model_json_schema())
    return Kritik.model_validate_json(a.text)


def main() -> None:
    treffer_a = treffer_b = 0
    for nummer, spital, frage, satz in FAELLE:
        print("=" * 78)
        print(f"FALL {nummer}  {spital}")
        print(f"  Satz: {satz[:110]}")
        for name, system in (("A unveraendert", KRITIK_SYSTEM), ("B geaendert", FASSUNG_B)):
            k = pruefe(system, frage, spital, satz)
            marke = "BEANSTANDET" if not k.gedeckt else "gedeckt"
            print(f"  {name:16s} {marke:12s} {k.beanstandungen}")
            print(f"  {'':16s} Begruendung: {k.begruendung[:120]}")
            if not k.gedeckt:
                if name.startswith("A"):
                    treffer_a += 1
                else:
                    treffer_b += 1
    print("=" * 78)
    print(f"Beanstandungen  Fassung A: {treffer_a}/4   Fassung B: {treffer_b}/4")
    print("Erwartung, wenn der Prompt die Ursache ist: A hoch, B null oder fast null.")


if __name__ == "__main__":
    main()
