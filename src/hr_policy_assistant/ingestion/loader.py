import re
import unicodedata
from pathlib import Path
from collections import Counter
from dataclasses import dataclass

import pdfplumber

PROJEKT_WURZEL = Path(__file__).resolve().parents[3]

# parents[0]  ingestion
# parents[1]  hr_policy_assistant
# parents[2]  src
# parents[3]  D:\hr-policy-assistant     ← die Wurzel


def lade_pdf(pfad: Path, ueberspringen: set[int] | None = None) -> list[Seite]:
    """Extrahiert den Text jeder Seite einer PDF, eine Seite pro Listeneintrag.
       ueberspringen: Seitenzahlen (1-basiert), die nicht gelesen werden.
    """
    ueberspringen = ueberspringen or set() #None oder eingegebener Wert
    seiten = []

    with pdfplumber.open(pfad) as pdf:
        for nummer, page in enumerate(pdf.pages, start=1):
            if nummer in ueberspringen:
                continue
            text = page.extract_text()
            if text:
                seiten.append(Seite(nummer,text))
    return seiten

def bereinige_text(text: str) -> str:
    """Normalisiert und säubert den rohen PDF-Text."""
    text = unicodedata.normalize("NFC", text)

    # Wingdings-Aufzählungspunkte, Unicode-Kategorie Co, tragen keine Information
    text = "".join(z for z in text if unicodedata.category(z) != "Co")
    return text

def bereinige_seiten(seiten: list[Seite]) -> list[Seite]:
    """Wendet bereinige_text auf jede Seite an und behaelt die Seitenzahl."""
    return [Seite(s.nummer, bereinige_text(s.text)) for s in seiten]


def signatur(zeile: str) -> str:
    """ Form einer Zeile, jede Ziffernfolge wird durch '#' ersetzt.
        Damit gelten 'GAV 1 / 26' und 'GAV 2 / 26' als dieselbe Zeile.
        GAV 2 / 26'   →   'GAV # / #
    """
    return re.sub(r"\d+", "#", zeile).strip()


def finde_wiederholte_zeilen(seiten: list[str], schwelle: float = 0.8) -> set[str]:
    """Signaturen von Zeilen, die auf mindestens `schwelle` aller Seiten stehen.

    Kopf- und Fusszeilen wiederholen sich auf fast jeder Seite, Regelungstext
    nicht. Gemessen an den zwei GAV liegen Kopf- und Fusszeilen bei 95 bis 100
    Prozent, die naechsthaeufige Zeile bei 10 Prozent.

    Setzt ein Dokument mit genuegend Seiten voraus. Bei drei Seiten kann ein
    normaler Satz, der auf zweien steht, die Schwelle reissen.
    """
    zaehler = Counter()
    for s in seiten:
        for sig in {signatur(z) for z in s.text.split("\n") if z.strip()}:
            zaehler[sig] += 1

    # 21 Seiten mal 0.8 ergibt 16.8. Alles ab 17 Seiten gilt als Kopf- oder Fusszeile
    mindestens = schwelle * len(seiten)
    return {sig for sig, anzahl in zaehler.items() if anzahl >= mindestens}


def entferne_wiederholte_zeilen(seiten: list[str], signaturen: set[str]) -> list[str]:
    """Entfernt aus jeder Seite die Zeilen, deren Signatur in `signaturen` steht."""
    bereinigt = []
    for s in seiten:
        behalten = [z for z in s.text.split("\n") if signatur(z) not in signaturen]
        bereinigt.append(Seite(s.nummer, "\n".join(behalten)))
    return bereinigt

# Ueberschrift: mehrstufige Nummer mit optionalem Schlusspunkt (2.5.9 / 9.1.)
# ODER einstufige mit Punkt (1.), danach Leerzeichen und ein Nicht-Ziffer-Zeichen.
UEBERSCHRIFT = re.compile(r"^(\d+(\.\d+)+\.?|\d+\.)\s+\D")

# Notbremse gegen Satzzeilen. Die laengste echte Ueberschrift hat 81 Zeichen.
MAX_UEBERSCHRIFT = 100

@dataclass
class Seite:
    """Eine Seite mit ihrer echten Seitenzahl."""

    nummer: int
    text: str

@dataclass
class Abschnitt:
    """Ein Abschnitt des Dokuments, erkannt an seiner Gliederungsnummer."""
    nummer: str
    titel: str
    text: str
    seite: int = 0
    pfad: str = ""


def nummer_von(zeile: str) -> str:
    """Die Gliederungsnummer am Zeilenanfang, ohne Schlusspunkt."""
    return zeile.split()[0].rstrip(".")


def titel_von(zeile: str) -> str:
    """Die Zeile ohne die fuehrende Gliederungsnummer."""
    teile = zeile.split(maxsplit=1)
    return teile[1] if len(teile) > 1 else ""


def ist_ueberschrift(zeile: str) -> bool:
    """Nummerierte Ueberschrift, kein Satz und keine Ordnungszahl im Fliesstext.

    Ein Satz enthaelt einen Punkt mit Leerzeichen dahinter ('berechnet. Fuer'),
    eine Ordnungszahl endet mit einem Punkt ('13. Monatslohn.').
    Beides geprueft am Titel, also ohne die eigene Nummer.

    An zwei GAV gemessen: KSBL findet 123 von 123 Verzeichnisnummern,
    USB alle 97 plus die tieferen Ebenen, die das Verzeichnis nicht auflistet.
    """
    if not UEBERSCHRIFT.match(zeile) or len(zeile) > MAX_UEBERSCHRIFT:
        return False
    t = titel_von(zeile)
    return ". " not in t and not t.endswith(".")


def schneide_in_abschnitte(seiten: list[str]) -> list[Abschnitt]:
    """Schneidet den Text an jeder nummerierten Ueberschrift.

    Zeilen vor der ersten Ueberschrift entfallen.
    """
    abschnitte: list[Abschnitt] = []
    nummer, titel, zeilen = None, None, []

    for s in seiten:
        for zeile in s.text.split("\n"):
            if ist_ueberschrift(zeile):
                if nummer is not None:
                    text = "\n".join(zeilen).strip()
                    abschnitte.append(Abschnitt(nummer, titel, text, seite))
                nummer, titel, seite, zeilen = nummer_von(zeile), titel_von(zeile), s.nummer, []
            elif nummer is not None:
                zeilen.append(zeile)

    if nummer is not None:
        abschnitte.append(Abschnitt(nummer, titel, "\n".join(zeilen).strip(), seite))

    return abschnitte

def setze_pfade(abschnitte: list[Abschnitt]) -> list[Abschnitt]:
    """Traegt in jeden Abschnitt den Pfad seiner uebergeordneten Titel ein.

    Die Tiefe kommt aus der Anzahl Punkte in der Nummer. '2.3.3' ist Tiefe 3,
    also haengt der Abschnitt unter '2.3' und '2'. Gearbeitet wird in Lesereihenfolge
    mit einem Stapel, damit doppelt vergebene Nummern nicht durcheinanderbringen.
    """
    stapel: list[str] = []

    for a in abschnitte:
        tiefe = a.nummer.count(".") + 1
        stapel = stapel[: tiefe - 1]
        stapel.append(f"{a.nummer} {a.titel}")
        a.pfad = " > ".join(stapel)

    return abschnitte

if __name__ == "__main__":
    pfad = PROJEKT_WURZEL / "data" / "raw" / "gav_universitaetsspital_basel.pdf"
    seiten = [bereinige_text(s) for s in lade_pdf(pfad, ueberspringen={2, 3})]
    seiten = entferne_wiederholte_zeilen(seiten, finde_wiederholte_zeilen(seiten))

    text = "\n".join(seiten)
    print("Kündigungsfrist" in text)
    print(text[:1500])

