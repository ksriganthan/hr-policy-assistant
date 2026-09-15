"""Eval-Runner. Stellt die Fragen aus faelle.yaml und misst das Ergebnis.

Ruft bewusst dieselbe antworte() auf wie die API. Ein eigener Weg zum Modell
wuerde den Runner messen und nicht das System.
"""

import csv
import math
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import yaml

from hr_policy_assistant.auskunft import antworte
from hr_policy_assistant.config import PROJEKT_WURZEL
from hr_policy_assistant.pruefung import pruefe
from hr_policy_assistant.workflow.graph import antworte_mit_kritik    # statt: from ...auskunft import antworte

FAELLE = PROJEKT_WURZEL / "evals" / "faelle.yaml"
ERGEBNISSE = PROJEKT_WURZEL / "evals" / "ergebnisse"
HAEUSER = ("USB", "KSBL")


# ── Hilfsfunktionen ──────────────────────────────────────────

def lade_faelle() -> list[dict]:
    """Liest die Faelle. safe_load fuehrt keinen Code aus, load koennte es."""
    with FAELLE.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def vereinheitliche(text: str) -> str:
    """Macht Apostrophe vergleichbar. 44’000 und 44'000 sollen gleich sein."""
    text = unicodedata.normalize("NFC", text)
    for zeichen in "’‘`´":
        text = text.replace(zeichen, "'")
    return text


def enthaelt(text: str, begriff: str) -> bool:
    """Sucht einen Begriff im Text. Ein Pipe trennt gleichwertige Schreibweisen,
    "zwei|2" gilt als gefunden, sobald eine der beiden Formen vorkommt.
    """
    inhalt = vereinheitliche(text).lower()                    # einmal umwandeln, nicht je Variante
    varianten = vereinheitliche(begriff).lower().split("|")   # "zwei|2" wird zu ["zwei", "2"]
    return any(v in inhalt for v in varianten)                # eine einzige reicht


def finde_haus(auskunft, haus: str):
    """Holt den Eintrag eines Hauses. None, wenn das Modell es weggelassen hat."""
    for s in auskunft.spitaeler:
        if s.spital == haus:
            return s
    return None


def perzentil(werte: list[float], p: float) -> float:
    """p-tes Perzentil nach nearest rank. Bei 20 Werten ist p95 der 19. Wert."""
    if not werte:
        return 0.0
    sortiert = sorted(werte)
    k = max(0, math.ceil(p / 100 * len(sortiert)) - 1)
    return sortiert[k]


# ── Messen ───────────────────────────────────────────────────

def frage_stellen(fall: dict) -> dict | None:
    """Stellt eine Frage ueber den Graphen und gibt die Rohdaten zurueck. None bei Absturz."""
    start = time.perf_counter()
    try:
        e = antworte_mit_kritik(fall["frage"])        # Endzustand des Graphen, ein dict
    except Exception as fehler:
        print(f"  Fall {fall['id']} abgestuerzt: {type(fehler).__name__}: {fehler}")
        return None
    dauer_gesamt = time.perf_counter() - start

    aufrufe = e["aufrufe"]                            # zwei bis vier Stueck, je nach Ruecksprung

    return {
        "fall": fall,
        "auskunft": e["auskunft"],
        "treffer": e["treffer"],
        "maengel": e["maengel"],                      # pruefe() lief schon im Graphen
        "modell": aufrufe[0].modell,
        "dauer_modell_s": round(sum(a.dauer_s for a in aufrufe), 2),
        "dauer_gesamt_s": round(dauer_gesamt, 2),
        "tokens_prompt": sum(a.tokens_prompt for a in aufrufe),
        "tokens_antwort": sum(a.tokens_antwort for a in aufrufe),
        "kosten_chf": sum(a.kosten_chf for a in aufrufe),
        "runde": e["runde"],                          # NEU: 1 heisst kein Ruecksprung, 2 heisst einer
        "gedeckt": e["kritik"].gedeckt,               # NEU: Urteil des Kritikers am Ende
        "beanstandungen": e["beanstandungen"],        # NEU: was am Ende offen blieb
    }


def bewerte_haus(ergebnis: dict, haus: str) -> dict:
    """Vergleicht die Antwort eines Hauses mit der Sollantwort aus der YAML."""
    soll = ergebnis["fall"][haus.lower()]
    ist = finde_haus(ergebnis["auskunft"], haus)

    if ist is None:                                # Modell hat dieses Haus weggelassen
        return {
            "eintrag_fehlt": True,
            "text": "",
            "ziffer_getroffen": None,
            "beantwortet_ok": False,
            "muss_fehlend": soll["muss"],
            "verboten_gefunden": [],
        }

    ziffern = [m["nummer"] for _, m, _ in ergebnis["treffer"] if m["dokument"] == haus]

    return {
        "eintrag_fehlt": False,
        "text": ist.text,
        "ziffer_getroffen": soll["ziffer"] in ziffern if soll["ziffer"] else None,
        "beantwortet_ok": ist.frage_beantwortet == soll["beantwortet"],
        "muss_fehlend": [b for b in soll["muss"] if not enthaelt(ist.text, b)],
        "verboten_gefunden": [b for b in soll["darf_nicht"] if enthaelt(ist.text, b)],
    }


# ── Schreiben ────────────────────────────────────────────────

def schreibe_csv(rohdaten: list[dict], bewertungen: list[dict], modell: str) -> Path:
    """Eine Zeile pro Fall, Spalten fuer beide Haeuser."""
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y-%m-%d_%H%M")
    pfad = ERGEBNISSE / f"{stempel}_{modell.replace(':', '-')}.csv"   # Doppelpunkt geht in Windows-Dateinamen nicht

    spalten = [
        "id", "kategorie", "frage",
        "runde", "gedeckt", "beanstandungen",  # NEU, direkt nach der Frage
        "dauer_gesamt_s", "dauer_modell_s", "tokens_prompt", "tokens_antwort", "kosten_chf",
        "maengel_anzahl", "maengel",
    ]
    for h in HAEUSER:
        k = h.lower()
        spalten += [f"{k}_ziffer", f"{k}_beantwortet_ok", f"{k}_muss_fehlend",
                    f"{k}_verboten", f"{k}_text"]

    with pfad.open("w", encoding="utf-8-sig", newline="") as f:   # utf-8-sig, damit Excel die Umlaute richtig liest
        schreiber = csv.DictWriter(f, fieldnames=spalten, delimiter=";")
        schreiber.writeheader()
        for roh, bew in zip(rohdaten, bewertungen, strict=True):
            zeile = {
                "id": roh["fall"]["id"],
                "kategorie": roh["fall"]["kategorie"],
                "frage": roh["fall"]["frage"],
                "runde": roh["runde"],
                "gedeckt": roh["gedeckt"],
                "beanstandungen": " | ".join(roh["beanstandungen"]),
                "dauer_gesamt_s": roh["dauer_gesamt_s"],
                "dauer_modell_s": roh["dauer_modell_s"],
                "tokens_prompt": roh["tokens_prompt"],
                "tokens_antwort": roh["tokens_antwort"],
                "kosten_chf": roh["kosten_chf"],
                "maengel_anzahl": len(roh["maengel"]),
                "maengel": " | ".join(roh["maengel"]),
            }
            for h in HAEUSER:
                k, b = h.lower(), bew[h]
                zeile[f"{k}_ziffer"] = b["ziffer_getroffen"]
                zeile[f"{k}_beantwortet_ok"] = b["beantwortet_ok"]
                zeile[f"{k}_muss_fehlend"] = " | ".join(b["muss_fehlend"])
                zeile[f"{k}_verboten"] = " | ".join(b["verboten_gefunden"])
                zeile[f"{k}_text"] = b["text"]
            schreiber.writerow(zeile)

    return pfad


def zusammenfassung(rohdaten: list[dict], bewertungen: list[dict]) -> None:
    """Die Zahlen, die ins Logbuch gehen."""
    seiten = [bew[h] for bew in bewertungen for h in HAEUSER]      # 20 Faelle mal 2 Haeuser

    mit_ziffer = [s for s in seiten if s["ziffer_getroffen"] is not None]
    treffer = sum(1 for s in mit_ziffer if s["ziffer_getroffen"])
    beantwortet = sum(1 for s in seiten if s["beantwortet_ok"])
    ohne_fehlende = sum(1 for s in seiten if not s["muss_fehlend"])
    ohne_verbotene = sum(1 for s in seiten if not s["verboten_gefunden"])
    fehlende_eintraege = sum(1 for s in seiten if s["eintrag_fehlt"])

    dauern = [r["dauer_gesamt_s"] for r in rohdaten]
    maengel = sum(len(r["maengel"]) for r in rohdaten)

    print("\n" + "=" * 55)
    print(f"Retrieval-Treffer      {treffer}/{len(mit_ziffer)}"
          f"   ({len(seiten) - len(mit_ziffer)} Seiten ohne erwartete Ziffer)")
    print(f"frage_beantwortet      {beantwortet}/{len(seiten)}")
    print(f"Pflichtbegriffe        {ohne_fehlende}/{len(seiten)} vollstaendig")
    print(f"Verbotsbegriffe        {ohne_verbotene}/{len(seiten)} sauber")
    print(f"Fehlende Eintraege     {fehlende_eintraege}")
    print(f"Strukturmaengel        {maengel} im ganzen Lauf")
    zweite_runde = sum(1 for r in rohdaten if r["runde"] >= 2)
    offen_geblieben = sum(1 for r in rohdaten if not r["gedeckt"])
    print(f"Kritiker hat gegriffen  {zweite_runde}/{len(rohdaten)} Faelle mit zweitem Entwurf")
    print(f"Am Ende nicht gedeckt   {offen_geblieben}/{len(rohdaten)}")
    print(f"Dauer p50 / p95        {perzentil(dauern, 50)} s / {perzentil(dauern, 95)} s")
    print(f"Tokens ein / aus       {sum(r['tokens_prompt'] for r in rohdaten)}"
          f" / {sum(r['tokens_antwort'] for r in rohdaten)}")
    print(f"Kosten                 CHF {sum(r['kosten_chf'] for r in rohdaten):.6f}")
    print("=" * 55)


def main() -> None:
    faelle = lade_faelle()
    print(f"{len(faelle)} Faelle geladen")

    rohdaten = []
    for i, fall in enumerate(faelle, start=1):
        print(f"[{i}/{len(faelle)}] Fall {fall['id']}: {fall['frage']}")
        ergebnis = frage_stellen(fall)
        if ergebnis:
            rohdaten.append(ergebnis)
            print(f"  {ergebnis['dauer_gesamt_s']} s, {len(ergebnis['maengel'])} Maengel")

    print(f"\n{len(rohdaten)} von {len(faelle)} Faellen durchgelaufen")
    if not rohdaten:
        return

    bewertungen = [{h: bewerte_haus(r, h) for h in HAEUSER} for r in rohdaten]
    pfad = schreibe_csv(rohdaten, bewertungen, rohdaten[0]["modell"])
    zusammenfassung(rohdaten, bewertungen)
    print(f"\nCSV: {pfad}")


if __name__ == "__main__":
    main()