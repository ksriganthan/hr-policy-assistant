"""Ablation am Kritiker. Sucht die Ursache der Fehlalarme im uebergebenen Entwurf.

Erzeugt pro Fall einen echten Entwurf ueber die Knoten suchen() und entwerfen() und legt
ihn dem Kritiker in vier Formen vor. 2x2-Plan, zwei Faktoren.

    Variante   Haeuser            Belegstellen-Liste
    P          beide              ja      <- exakt die Produktionsform
    P1         beide              nein
    P2         nur betroffenes    ja
    P3         nur betroffenes    nein

Aendert nichts im System. Start aus der Projektwurzel:  uv run python kritik_ablation.py
"""

from hr_policy_assistant.auskunft import baue_prompt
from hr_policy_assistant.gateway.llm import frage_modell
from hr_policy_assistant.modelle import Kritik
from hr_policy_assistant.workflow.graph import KRITIK_SYSTEM, entwerfen, suchen

# Fall, betroffenes Haus, Frage, Kernwort des beanstandeten Satzes
FAELLE = [
    (7,  "USB",  "Wie lange ist die Kuendigungsfrist nach der Probezeit?", "Anstellungsjahr"),
    (11, "KSBL", "Wie hoch ist die Abfindung bei einer Kuendigung?",        "Monatsl"),
    (18, "USB",  "Wie viele freie Tage bekomme ich bei meiner Heirat?",     "Arbeitstage"),
    (1,  "USB",  "Gilt der GAV fuer Chefaerzte?",                           "Chefaerzte"),
]


def erzeuge_entwurf(frage: str):
    """Laeuft suchen() und entwerfen() genau wie der Graph. Ein Modellaufruf."""
    z = {"frage": frage, "spital": None, "treffer": [], "auskunft": None, "kritik": None,
         "beanstandungen": [], "runde": 0, "maengel": [], "verlauf": [], "aufrufe": []}
    z.update(suchen(z))                                  # nur Chroma, kein Modell
    z.update(entwerfen(z))                               # ein Modellaufruf
    return z["auskunft"], z["treffer"]


def baue_text(auskunft, haus: str | None, mit_liste: bool) -> str:
    """Baut den Entwurfstext. haus=None nimmt beide, wie kritisieren() es tut."""
    teile = []
    for s in auskunft.spitaeler:
        if haus is not None and s.spital != haus:
            continue
        if mit_liste:
            teile.append(f"{s.spital}: {s.text} (genannte Belegstellen: {s.belegstellen})")
        else:
            teile.append(f"{s.spital}: {s.text}")
    return "\n".join(teile)


def frag_kritiker(frage: str, treffer, entwurfstext: str) -> Kritik:
    nutzer = baue_prompt(frage, treffer) + f"\n\nZu pruefende Auskunft:\n{entwurfstext}"
    a = frage_modell(system=KRITIK_SYSTEM, nutzer=nutzer, schema=Kritik.model_json_schema())
    return Kritik.model_validate_json(a.text)


VARIANTEN = [
    ("P  beide + Liste  ", None, True),
    ("P1 beide ohne Liste", None, False),
    ("P2 eines + Liste   ", "HAUS", True),
    ("P3 eines ohne Liste", "HAUS", False),
]


def main() -> None:
    bilanz = {name: 0 for name, _, _ in VARIANTEN}
    for nummer, haus, frage, kernwort in FAELLE:
        print("=" * 78)
        print(f"FALL {nummer}   betroffenes Haus {haus}")
        auskunft, treffer = erzeuge_entwurf(frage)

        eintrag = next((s for s in auskunft.spitaeler if s.spital == haus), None)
        if eintrag is None:
            print("  ABBRUCH, das Modell hat dieses Haus weggelassen")
            continue
        print(f"  Entwurf {haus}: {eintrag.text[:150]}")
        print(f"  genannte Belegstellen: {eintrag.belegstellen}")
        if kernwort.lower() not in eintrag.text.lower():
            print(f"  WARNUNG, Kernwort «{kernwort}» fehlt im neuen Entwurf, "
                  f"Fall nur begrenzt vergleichbar")

        for name, modus, mit_liste in VARIANTEN:
            ziel = haus if modus == "HAUS" else None
            text = baue_text(auskunft, ziel, mit_liste)
            k = frag_kritiker(frage, treffer, text)
            marke = "BEANSTANDET" if not k.gedeckt else "gedeckt    "
            print(f"    {name} {marke} {k.beanstandungen}")
            if not k.gedeckt:
                bilanz[name] += 1

    print("=" * 78)
    for name, _, _ in VARIANTEN:
        print(f"  {name}  {bilanz[name]}/4 beanstandet")
    print()
    print("Lesen: P hoch und P1 tief -> die Belegstellen-Liste ist die Ursache.")
    print("       P hoch und P2 tief -> der Text des anderen Hauses ist die Ursache.")
    print("       P tief             -> der Fehlalarm ist so nicht nachstellbar, weitersuchen.")


if __name__ == "__main__":
    main()
